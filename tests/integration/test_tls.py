import shutil
import socket
import ssl
import subprocess
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import httpx
import pytest
from mediaharvester.download import HttpBackend
from mediaharvester.models import Media,Task


def test_real_self_signed_tls_rejected(tmp_path,monkeypatch):
    openssl=shutil.which('openssl')
    if not openssl:
        candidate=Path('C:/Program Files/Git/usr/bin/openssl.exe')
        if candidate.exists():openssl=str(candidate)
    if not openssl:pytest.skip('OpenSSL certificate generator unavailable')
    cert,key=tmp_path/'cert.pem',tmp_path/'key.pem'
    subprocess.run([openssl,'req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),
                    '-days','1','-subj','/CN=localhost'],check=True,capture_output=True,timeout=10)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Length','4');self.end_headers();self.wfile.write(b'test')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    # A test-only local client retains default certificate verification.
    monkeypatch.setattr('mediaharvester.download.client',lambda:httpx.Client(trust_env=False,timeout=2))
    task=Task(asdict(Media(f'https://127.0.0.1:{server.server_port}/','','tls','audio','bin')),str(tmp_path))
    try:
        with pytest.raises(httpx.ConnectError,match='CERTIFICATE_VERIFY_FAILED'):
            HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
        assert not (tmp_path/'payload.part').exists()
    finally:
        server.shutdown();server.server_close();thread.join()
