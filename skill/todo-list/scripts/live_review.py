"""Live UI review contract and evidence validation for configured computer-use MCPs."""
import json
import os
from pathlib import Path
import re
import struct
import shutil
import subprocess

PLATFORMS = ('web', 'android', 'ios')
UI_SERVERS = {'cua_repl', 'computer-use', 'XcodeBuildMCP', 'xcodebuildmcp', 'mobile-mcp'}

def ui_config_args(executable):
    result = subprocess.run([executable, 'mcp', 'list', '--json'], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise ValueError('Cannot inspect Codex UI tool configuration. Run codex mcp list.')
    entries = json.loads(result.stdout)
    enabled = [item['name'] for item in entries if item.get('enabled') and item.get('name') in UI_SERVERS]
    if not enabled:
        raise ValueError('Live review needs a configured computer-use MCP server (for example cua_repl or XcodeBuildMCP). No enabled UI server was found.')
    args = []
    environment=os.environ.copy()
    for item in entries:
        name=item.get('name','')
        if name not in enabled: continue
        if not re.fullmatch(r'[A-Za-z0-9_-]+',name): raise ValueError('Unsupported MCP server name.')
        transport=item.get('transport',{})
        if transport.get('type')!='stdio' or not transport.get('command'):
            raise ValueError('Live review currently requires a local stdio UI MCP server.')
        for field in ('command','args','cwd'):
            value=transport.get(field)
            if value is not None:
                args += ['-c',f'mcp_servers.{name}.{field}='+json.dumps(value)]
        injected=transport.get('env') or {}
        environment.update(injected)
        names=list(set(transport.get('env_vars') or [])|set(injected))
        if names:args+=['-c',f'mcp_servers.{name}.env_vars='+json.dumps(names)]
    return args,environment

def extend_schema(spec, platforms):
    platform = {'type':'object', 'properties':{
        'platform': {'type':'string', 'enum':platforms},
        'status': {'type':'string', 'enum':['pass','fail','blocked']},
        'steps': {'type':'array', 'items':{'type':'string'}},
        'screenshots': {'type':'array', 'items':{'type':'string'}}},
        'required':['platform','status','steps','screenshots'], 'additionalProperties':False}
    spec['properties']['platforms'] = {'type':'array','items':platform}
    spec['required'].append('platforms')
    return spec

def live_prompt(task, project, run_dir, language):
    return f'''Perform a REAL UI review on exactly these platforms: {', '.join(task.get('platforms',['android','ios']))}. Respond in {language}.
Task notes: {task.get('note','')}
Task: {json.dumps({k:task[k] for k in ('title','criteria','paths')},ensure_ascii=False)}
Source project: {project}
Evidence directory: {run_dir}
User environment details: {task.get('reviewContext','')}
Read-only host device inventory (availability only, NOT evidence of UI tool access): {json.dumps(task.get('deviceInventory',{}))}
Web test URL (if supplied): {task.get('webUrl','')} 
Use only the configured computer-use MCP tools and their documented APIs for ALL screen observation and interaction. Read their documentation before using them. Do not replace UI tools with shell UI automation or invented screenshots.
Inspect the project's instructions and source as needed to identify the app and navigation, but static code or test definitions are not proof of screen behavior.
For EACH platform: use the supplied local/test web URL in a browser for web, or discover a connected test physical device or running test simulator/emulator for mobile; inspect its actual screen, identify the target app, carry out the requested navigation/actions, inspect the resulting screen, and save original screenshot bytes to the evidence directory using documented capture/export APIs. Record concise actual actions and observations in steps, and project-independent paths to those screenshot files. Screenshots must show the observed app, never an HTML recreation, generated image or source listing.
Do not change source code, install software, reset devices, modify production data, publish, or log into accounts without the user's required authorization. Do not delete a real account, accept provider permissions, enter credentials or complete payments. If a destructive operation or login needs user input, mark only the affected platform/criteria blocked with a precise next action. Do not weaken computer-use approval policies.
Do not invent an app ID, device, URL, test account, observation, or tool success. An app list is NOT a device inventory. Use the supplied host inventory and documented device discovery APIs; distinguish device missing, device unauthorized, tool unavailable, and screenshot access unavailable. A connected device does not prove the UI tool can control it. If a platform/device/tool is unavailable, report blocked for that platform and explain exactly what is missing. Continue independent checks on the other platform.
Every original criterion must appear exactly once in checks, with an aggregate status across all selected platforms. A criterion passes only after directly observing its requested behavior on every selected platform. Return exactly one platforms entry per selected platform and none for unselected platforms. A passing platform requires actual steps and original screenshot evidence. If saving screenshots is unsupported, report blocked instead of passing. Do not rerun the workflow indefinitely; return the observations and blockers after one bounded attempt per platform.
'''

def validate_evidence(result, run_dir, platforms):
    entries = result.get('platforms')
    if not isinstance(entries,list) or len(entries)!=len(platforms) or any(not isinstance(x,dict) for x in entries):
        raise ValueError('Live review must report every selected platform.')
    if sorted(item.get('platform','') for item in entries)!=sorted(platforms):
        raise ValueError('Missing or duplicate platform result.')
    evidence = []
    for item in entries:
        if item.get('status') not in ('pass','fail','blocked'):
            raise ValueError('Invalid platform status.')
        steps, screenshots = item.get('steps'), item.get('screenshots')
        if not isinstance(steps,list) or not isinstance(screenshots,list) or len(screenshots)>10:
            raise ValueError('Invalid live observation record.')
        if any(not isinstance(step,str) or not step.strip() for step in steps):
            raise ValueError('Empty observation step.')
        if item['status']=='pass' and (not steps or not screenshots):
            raise ValueError('A passing platform needs observed steps and screenshot evidence.')
        for name in screenshots:
            if not isinstance(name,str): raise ValueError('Invalid screenshot path.')
            path = (run_dir/name).resolve()
            if not path.is_relative_to(run_dir.resolve()) or not path.is_file() or path.suffix.lower()!='.png':
                raise ValueError('Screenshot must be an original PNG in this review evidence directory.')
            if path.stat().st_size>20*1024*1024: raise ValueError('Screenshot exceeds 20 MB.')
            header=path.read_bytes()[:24]
            if len(header)<24 or header[:8]!=b'\x89PNG\r\n\x1a\n' or header[12:16]!=b'IHDR':
                raise ValueError('Invalid PNG evidence.')
            width,height=struct.unpack('>II',header[16:24])
            if min(width,height)<100: raise ValueError('Screenshot is too small to verify a screen.')
            evidence.append({'platform':item['platform'],'path':str(path.relative_to(run_dir))})
    statuses=[item['status'] for item in entries]
    outcome='changes' if 'fail' in statuses else 'blocked' if 'blocked' in statuses else 'complete'
    return outcome,evidence


def device_inventory():
    """Read device availability; never boot, authorize, install or interact."""
    result = {}
    adb = shutil.which('adb') or str(Path.home()/'Library/Android/sdk/platform-tools/adb')
    for platform, command in [('android',[adb,'devices','-l']), ('ios',['xcrun','simctl','list','devices','booted','-j'])]:
        try:
            probe=subprocess.run(command,capture_output=True,text=True,timeout=8)
            if probe.returncode:
                result[platform]={'status':'unavailable','devices':[]}
            elif platform=='android':
                devices=[]
                for line in probe.stdout.splitlines()[1:]:
                    fields=line.split()
                    if len(fields)>=2:
                        devices.append({'name':next((x[6:] for x in fields if x.startswith('model:')),fields[0]),'status':fields[1]})
                result[platform]={'status':'found' if devices else 'missing','devices':devices}
            else:
                devices=[{'name':d['name'],'status':'Booted'} for group in json.loads(probe.stdout)['devices'].values() for d in group if d.get('state')=='Booted']
                result[platform]={'status':'found' if devices else 'missing','devices':devices}
        except (OSError,subprocess.TimeoutExpired,ValueError,KeyError):
            result[platform]={'status':'unavailable','devices':[]}
    return result
