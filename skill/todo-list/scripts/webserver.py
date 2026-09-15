"""Loopback-only HTTP transport; explicit routes and same-origin protection."""
from core import *

def handler(board, token):

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def send(self, status, body, kind='application/json'):
            body = translate_payload(body, self.headers.get('X-Board-Language','ko')) if kind=='application/json' else body
            payload = body if isinstance(body,bytes) else body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def safe_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.safe_host():
                return self.send(403, {'error': 'Invalid host'})
            if self.path == '/':
                return self.send(200, (ASSETS / 'board.html').read_text().replace('__TOKEN__', token), 'text/html')
            if self.path in ('/board.css', '/board.js', '/locales.json'):
                filename = self.path[1:]
                return self.send(200, (ASSETS / filename).read_text(), 'text/css' if filename.endswith('.css') else 'application/json' if filename.endswith('.json') else 'application/javascript')
            if self.path.startswith('/api/evidence/') and secrets.compare_digest(self.headers.get('X-Board-Token',''),token):
                try:
                    parts=self.path.split('/')
                    if len(parts)!=5: raise ValueError('Invalid evidence URL')
                    task=board.find(parts[3]);item=task.get('evidence',[])[int(parts[4])]
                    root=(board.dir/'runs'/task['evidenceRun']).resolve();path=(root/item['path']).resolve()
                    if not path.is_relative_to(root) or not path.is_file(): raise ValueError('Missing evidence')
                    return self.send(200,path.read_bytes(),'image/png')
                except (ValueError,IndexError,KeyError,StopIteration,OSError): return self.send(404,{'error':'Evidence not found'})
            if self.path == '/api/state' and secrets.compare_digest(self.headers.get('X-Board-Token', ''), token):
                return self.send(200, board.state())
            self.send(404, {'error': 'Not found'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.safe_host() or (origin and origin != f'http://127.0.0.1:{self.server.server_port}') or (not secrets.compare_digest(self.headers.get('X-Board-Token', ''), token)):
                return self.send(403, {'error': 'Forbidden'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size < 1 or size > 65536:
                    raise ValueError('요청 크기가 잘못되었습니다.')
                d = json.loads(self.rfile.read(size))
                if not isinstance(d, dict):
                    raise ValueError('요청 형식이 잘못되었습니다.')
                if self.path == '/api/archive':
                    result=board.archive(d['id'],d['deleted'])
                elif self.path == '/api/environment':
                    from live_review import device_inventory
                    result=device_inventory()
                elif self.path == '/api/configure':
                    result = board.configure(d['project'])
                elif self.path == '/api/rename':
                    result = board.rename(d['name'])
                elif self.path == '/api/add':
                    result = board.add(d)
                elif self.path == '/api/edit':
                    result = board.add(d, d['id'])
                elif self.path == '/api/status':
                    result = board.status(d['id'], d['work'])
                elif self.path == '/api/review':
                    result = board.review(d['id'],d.get('language','ko'),d.get('mode','live'),d.get('context',''))
                else:
                    return self.send(404, {'error': 'Not found'})
                self.send(200, {'ok': True, 'result': result})
            except (ValueError, KeyError, TypeError, StopIteration) as e:
                self.send(400, {'error': str(e) or '항목을 찾을 수 없습니다.'})
    return Handler
