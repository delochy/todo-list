#!/usr/bin/env python3
"""Todo List command line entry point (macOS/Linux, Python 3.11+)."""
from core import *
from webserver import handler

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
    directory = args.state_dir or Path.home() / '.local' / 'share' / 'todo-list' / hashlib.sha256(str(project).encode()).hexdigest()[:16]
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
