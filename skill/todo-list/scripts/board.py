#!/usr/bin/env python3
"""Todo List command line entry point (macOS/Linux, Python 3.11+)."""
from core import *
from webserver import handler

def project_identity(project):
    project = Path(project).resolve()
    try:
        result = subprocess.run(['git','-C',str(project),'rev-parse','--path-format=absolute','--git-common-dir'],capture_output=True,text=True,timeout=5)
        if result.returncode == 0:
            return 'git:' + str(Path(result.stdout.strip()).resolve())
    except (OSError,subprocess.TimeoutExpired):
        pass
    return 'path:' + str(project)


def resolve_state_dir(project, explicit=None, base=None):
    """One registered board per repository, including linked worktrees."""
    base = Path(base or Path.home()/'.local/share/todo-list')
    base.mkdir(parents=True,exist_ok=True)
    identity = project_identity(project)
    key = hashlib.sha256(identity.encode()).hexdigest()[:16]
    registry = base/'projects'
    registry.mkdir(exist_ok=True)
    with (registry/'registry.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        pointer = registry/(key+'.json')
        registered = Path(json.loads(pointer.read_text())['state_dir']) if pointer.exists() else None
        if explicit:
            directory = Path(explicit).resolve()
            if registered and registered.resolve()!=directory and (registered/'board.json').exists():
                existing=json.loads((registered/'board.json').read_text())
                if existing.get('tasks'):
                    raise ValueError('A board already exists for this project: '+str(registered)+'. Reopen it without --state-dir; no data was moved.')
        elif registered:
            if not (registered/'board.json').exists():
                raise ValueError('Registered board is unavailable: '+str(registered)+'. Restore its location; no empty replacement was created.')
            return registered
        else:
            legacy=base/hashlib.sha256(str(Path(project).resolve()).encode()).hexdigest()[:16]
            directory=legacy if (legacy/'board.json').exists() else base/key
        directory.mkdir(parents=True,exist_ok=True)
        atomic(pointer,{'identity':identity,'state_dir':str(directory.resolve())})
        return directory.resolve()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['serve', 'add', 'status', 'list', 'doctor'])
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--state-dir', type=Path, help='Override local state location (also used for migration)')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--language',choices=['ko','en'],default='en')
    parser.add_argument('--title')
    parser.add_argument('--id')
    parser.add_argument('--work')
    parser.add_argument('--criterion', action='append', default=[])
    parser.add_argument('--path', action='append', default=[])
    args = parser.parse_args()
    if args.command == 'doctor':
        executable = shutil.which('codex')
        print(json.dumps({'python': __import__('sys').version.split()[0], 'codex': executable, 'platform': __import__('sys').platform}))
        if not executable:
            raise SystemExit(1)
        raise SystemExit(subprocess.call([executable, 'login', 'status']))
    project = args.project.resolve()
    if not project.is_dir():
        parser.error('프로젝트 폴더가 없습니다.')
    directory = resolve_state_dir(project,args.state_dir)
    directory.mkdir(parents=True, exist_ok=True)
    runtime = directory / 'runtime.json'
    if args.command != 'serve':
        config = json.loads(runtime.read_text())
        url = config['url']
        if not url.startswith('http://127.0.0.1:'):
            raise ValueError('로컬 보드 주소가 아닙니다.')
        route = {'add': 'add', 'status': 'status', 'list': 'state'}[args.command]
        payload = {'language':args.language,'title': args.title, 'paths': args.path, 'criteria': args.criterion} if args.command == 'add' else {'id': args.id, 'work': args.work}
        request = Request(url + '/api/' + route, data=None if args.command == 'list' else json.dumps(payload).encode(), headers={'X-Board-Token': config['token'], 'Content-Type': 'application/json'})
        print(urlopen(request, timeout=20).read().decode())
        return
    lockfile = (directory / 'server.lock').open('w')
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        config = json.loads(runtime.read_text())
        print(config['url'], flush=True)
        return
    board = Board(project, directory)
    token = secrets.token_hex(32)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(board, token))
    url = f'http://127.0.0.1:{server.server_port}'
    atomic(runtime, {'url': url, 'token': token, 'pid': os.getpid()})
    print(url, flush=True)

    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        board.shutdown()
        server.server_close()

if __name__ == '__main__':
    main()
