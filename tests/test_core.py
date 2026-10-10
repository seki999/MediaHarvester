import json
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import httpx
import pytest
from mediaharvester.security import validate_url,SecurityError,public_addresses,client
from mediaharvester.extractors import HtmlImageExtractor,format_options,YtDlpExtractor
from mediaharvester.models import Media,Task,State
from mediaharvester.database import Repository
from mediaharvester.download import HttpBackend,DownloadManager
from mediaharvester.files import safe_name,publish,sha256
from mediaharvester.config import Settings

@pytest.mark.parametrize('url',['file:///C:/secret','ftp://example.com','http://localhost','http://127.0.0.1','http://[::1]',
    'http://10.0.0.1','http://169.254.169.254','http://192.168.1.1','https://u:p@example.com','not a url','http://example.com:bad','https://example.com/\n  dir=C:/bad'])
def test_invalid_url(url):
    with pytest.raises(ValueError): validate_url(url)

@pytest.mark.parametrize('url',['https://example.com','https://example.com/a.jpg','http://example.com/video.mp4'])
def test_valid_url(url): assert validate_url(url)==url

def test_dns_private(monkeypatch):
    import socket
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',80))])
    with pytest.raises(SecurityError): public_addresses('rebind.test',80)

def test_redirect_private(monkeypatch):
    import mediaharvester.security as security
    class Redirect(httpx.MockTransport):
        pass
    transport=httpx.MockTransport(lambda r:httpx.Response(302,headers={'location':'http://127.0.0.1/private'}))
    def guard(request): validate_url(str(request.url))
    with httpx.Client(transport=transport,follow_redirects=True,event_hooks={'request':[guard]}) as c:
        with pytest.raises(SecurityError): c.get('https://example.com')

def test_real_transport_blocks_local():
    with client() as c:
        with pytest.raises(SecurityError): c.get('http://127.0.0.1:12345')

def test_images():
    html='''<img src="/a.jpg"><img src="/a.jpg"><img data-original="/lazy.png" src="/small.png">
    <picture><source srcset="/s.webp 320w, /l.webp 1280w"></picture>
    <div style="background-image:url('/bg.jpg')"></div><meta property="og:image" content="/og.jpg">'''
    result=HtmlImageExtractor().extract_html(html,'https://example.com/page')
    assert [r.url for r in result]==['https://example.com/a.jpg','https://example.com/lazy.png','https://example.com/l.webp','https://example.com/bg.jpg','https://example.com/og.jpg']

def test_image_cap():
    assert len(HtmlImageExtractor().extract_html(''.join(f'<img src="/{i}.jpg">' for i in range(20)), 'https://example.com',3))==3

FORMATS=[dict(format_id='v',vcodec='avc1',acodec='none',ext='mp4',height=1080),
         dict(format_id='a',vcodec='none',acodec='aac',ext='m4a',abr=128),
         dict(format_id='b',vcodec='avc1',acodec='aac',ext='mp4',height=360)]
def test_formats():
    choices=format_options(FORMATS)
    assert [c[1] for c in choices]==['v+a','a','b']
    assert format_options(FORMATS[:1])==[]
    assert format_options([])==[]
    assert format_options([dict(FORMATS[0],has_drm=True)])==[]

def test_video_extract(monkeypatch):
    monkeypatch.setattr('mediaharvester.extractors.run_job',lambda *a,**k:{'id':'xyz','title':'Real','formats':FORMATS})
    media=YtDlpExtractor().extract('https://example.com',threading.Event())
    assert media[0].identity=='xyz' and len(media[0].formats)==3

def test_video_failure(monkeypatch):
    def fail(*args,**kwargs): raise RuntimeError('403')
    monkeypatch.setattr('mediaharvester.extractors.run_job',fail)
    with pytest.raises(RuntimeError): YtDlpExtractor().extract('https://example.com',threading.Event())

def test_database_reopen(tmp_path):
    path=tmp_path/'tasks.db'; repo=Repository(path)
    t=Task(asdict(Media('https://example.com/a','https://example.com','A','image')),str(tmp_path))
    t.downloaded=123; t.etag='"one"'; repo.save(t); repo.close()
    repo=Repository(path); restored=repo.all()[0]
    assert restored.id==t.id and restored.downloaded==123 and restored.etag=='"one"'
    assert repo.db.execute('PRAGMA synchronous').fetchone()[0]==2
    repo.close()

PAYLOAD=bytes(range(256))*4096
@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_HEAD(self):
            self.send_response(200); self.send_header('Content-Length',str(len(PAYLOAD))); self.send_header('ETag','"one"'); self.end_headers()
        def do_GET(self):
            etag='"two"' if self.path=='/changed' else '"one"'
            start=0
            if self.path=='/416':
                self.send_response(416); self.send_header('Content-Range',f'bytes */{len(PAYLOAD)}'); self.send_header('ETag',etag); self.end_headers(); return
            if self.path not in ('/ignore','/changed') and self.headers.get('Range'):
                start=int(self.headers['Range'].split('=')[1].split('-')[0])
                self.send_response(206); self.send_header('Content-Range',f'bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}')
            else: self.send_response(200)
            self.send_header('Content-Length',str(len(PAYLOAD)-start)); self.send_header('ETag',etag); self.end_headers()
            try:
                for i in range(start,len(PAYLOAD),8192):
                    self.wfile.write(PAYLOAD[i:i+8192]); self.wfile.flush()
                    if self.path=='/slow': time.sleep(.003)
                    if self.path=='/drop' and i>65536: self.connection.shutdown(2); return
            except OSError: pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown(); server.server_close(); thread.join()

@pytest.fixture
def local_client(monkeypatch):
    # Explicit test-only injection; production has no allow-private switch.
    monkeypatch.setattr('mediaharvester.download.client',lambda:httpx.Client(trust_env=False,timeout=5))

def make_task(tmp_path,url):
    return Task(asdict(Media(url,url,'file.bin','audio','bin')),str(tmp_path))

@pytest.mark.parametrize('path',['/normal','/ignore','/changed'])
def test_resume_http(tmp_path,server,local_client,path):
    task=make_task(tmp_path,server+path); task.etag='"one"'
    (tmp_path/'payload.part').write_bytes(PAYLOAD[:12345])
    result=HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{'rate':0})
    assert result.read_bytes()==PAYLOAD and task.downloaded==len(PAYLOAD)

def test_no_validator_restarts(tmp_path,server,local_client):
    task=make_task(tmp_path,server+'/normal'); (tmp_path/'payload.part').write_bytes(b'WRONG DATA')
    assert HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{}).read_bytes()==PAYLOAD

def test_416_valid(tmp_path,server,local_client):
    task=make_task(tmp_path,server+'/416'); task.etag='"one"'; (tmp_path/'payload.part').write_bytes(PAYLOAD)
    assert HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{}).read_bytes()==PAYLOAD

def test_416_invalid(tmp_path,server,local_client):
    task=make_task(tmp_path,server+'/416'); task.etag='"one"'; (tmp_path/'payload.part').write_bytes(b'partial')
    with pytest.raises(OSError): HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert not (tmp_path/'payload.part').exists()

def test_pause_continue(tmp_path,server,local_client):
    task=make_task(tmp_path,server+'/slow'); cancel=threading.Event()
    def update():
        if task.downloaded>65536: cancel.set()
    with pytest.raises(InterruptedError): HttpBackend().download(task,tmp_path,cancel,update,{'rate':262144})
    assert 0<(tmp_path/'payload.part').stat().st_size<len(PAYLOAD)
    cancel.clear()
    assert HttpBackend().download(task,tmp_path,cancel,lambda:None,{}).read_bytes()==PAYLOAD

def test_disconnect_preserves_bytes(tmp_path,server,local_client):
    task=make_task(tmp_path,server+'/drop')
    with pytest.raises(httpx.HTTPError): HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert (tmp_path/'payload.part').stat().st_size>0

def wait_for(predicate,timeout=8):
    start=time.monotonic()
    while not predicate():
        assert time.monotonic()-start<timeout
        time.sleep(.02)

def test_manager_download(tmp_path,server,local_client,monkeypatch):
    monkeypatch.setattr('mediaharvester.download.executable',lambda name:None)
    repo=Repository(tmp_path/'db'); settings=Settings.defaults.copy(); settings['directory']=str(tmp_path)
    manager=DownloadManager(repo,settings)
    task=manager.add(asdict(Media(server+'/normal',server,'test.bin','audio','bin')))
    wait_for(lambda:task.state in (State.COMPLETED,State.FAILED))
    assert task.state==State.COMPLETED and Path(task.final).read_bytes()==PAYLOAD
    assert repo.all()[0].digest==sha256(task.final)
    manager.close(); repo.close()

@pytest.mark.parametrize('with_part',[True,False])
def test_crash_recovery(tmp_path,with_part):
    repo=Repository(tmp_path/'db'); task=make_task(tmp_path,'https://example.com/file')
    task.state=State.DOWNLOADING; repo.save(task)
    temp=tmp_path/'.mediaharvester'/task.id; temp.mkdir(parents=True)
    if with_part: (temp/'payload.part').write_bytes(b'partial')
    manager=DownloadManager(repo,Settings.defaults.copy())
    assert manager.tasks[task.id].state==State.PAUSED
    assert (temp/'payload.part').exists()==with_part
    manager.close(); repo.close()

def test_atomic_commit_recovery(tmp_path):
    repo=Repository(tmp_path/'db'); task=make_task(tmp_path,'https://example.com/file'); task.state=State.VERIFYING
    temp=tmp_path/'.mediaharvester'/task.id; temp.mkdir(parents=True)
    final=tmp_path/'already.bin'; final.write_bytes(PAYLOAD)
    (temp/'commit.json').write_text(json.dumps({'path':str(final),'digest':sha256(final)}),'utf-8')
    repo.save(task); settings=Settings.defaults.copy(); settings['auto_resume']=True
    manager=DownloadManager(repo,settings)
    wait_for(lambda:manager.tasks[task.id].state==State.COMPLETED)
    assert manager.tasks[task.id].final==str(final)
    manager.close(); repo.close()

def test_names(tmp_path):
    assert safe_name('CON')=='_CON' and '/' not in safe_name('../a:b')
    first=tmp_path/'one'; first.write_bytes(b'a'); target=publish(first,tmp_path,'file.bin')
    second=tmp_path/'two'; second.write_bytes(b'b'); other=publish(second,tmp_path,'file.bin')
    assert target!=other and target.read_bytes()==b'a' and other.read_bytes()==b'b'

def test_settings_atomic(tmp_path):
    settings=Settings(tmp_path/'settings.json'); settings.values['concurrency']=7; settings.save()
    assert Settings(settings.path).values['concurrency']==7
