"""Loopback proxy used only by child engines; authenticated, public IPs pinned."""
import base64
import secrets
import select
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .security import public_addresses, validate_url, client

class EngineProxy:
    def __enter__(self):
        token=secrets.token_hex(24)
        expected='Basic '+base64.b64encode(('mh:'+token).encode()).decode()
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args): pass
            def handle(self):
                try: super().handle()
                except OSError: self.close_connection=True
            def authorized(self):
                if self.headers.get('Proxy-Authorization')!=expected:
                    self.send_response(407)
                    self.send_header('Proxy-Authenticate','Basic realm="MediaHarvester"')
                    self.send_header('Content-Length','0'); self.end_headers(); return False
                return True
            def do_CONNECT(self):
                if not self.authorized(): return
                try:
                    parsed=urlsplit('https://'+self.path)
                    validate_url('https://'+self.path)
                    port=parsed.port or 443
                    addresses=public_addresses(parsed.hostname,port)
                    remote=socket.create_connection((addresses[0][4][0],port),timeout=10)
                    with remote:
                        self.send_response(200); self.end_headers()
                        while True:
                            ready,_,_=select.select([self.connection,remote],[],[],20)
                            if not ready: break
                            for source in ready:
                                chunk=source.recv(64*1024)
                                if not chunk: return
                                (remote if source is self.connection else self.connection).sendall(chunk)
                except Exception:
                    self.close_connection=True
            def do_GET(self):
                if not self.authorized(): return
                try:
                    validate_url(self.path)
                    headers={k:v for k,v in self.headers.items() if k.lower() not in ('proxy-authorization','host','connection')}
                    length=int(self.headers.get('content-length') or 0)
                    if length>5*1024*1024: self.send_error(413); return
                    body=self.rfile.read(length) if length else None
                    with client() as c, c.stream(self.command,self.path,headers=headers,content=body) as r:
                        self.send_response(r.status_code)
                        for k,v in r.headers.items():
                            if k.lower() not in ('transfer-encoding','connection','content-encoding'):
                                self.send_header(k,v)
                        self.send_header('Connection','close'); self.end_headers()
                        for chunk in r.iter_bytes(): self.wfile.write(chunk)
                    self.close_connection=True
                except Exception:
                    self.close_connection=True
            do_HEAD=do_GET
            do_POST=do_GET
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://mh:{token}@127.0.0.1:{self.server.server_port}'
        self.browser={'server':f'http://127.0.0.1:{self.server.server_port}','username':'mh','password':token}
        return self
    def __exit__(self,*args):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
