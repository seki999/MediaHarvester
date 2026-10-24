import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import httpx
import pytest

from mediaharvester.extractors import ExtractorRegistry
from mediaharvester.config import Settings
from mediaharvester.models import Media


def test_dynamic_registry_combines_sources(monkeypatch):
    registry=ExtractorRegistry(Settings.defaults.copy())
    jobs=[]
    def run(job,cancel,timeout):
        jobs.append((job,timeout))
        return dict(url='https://example.com/page',base='https://example.com/assets/',
                    html='<img src="photo.jpg">',media=[
                        dict(url='https://example.com/assets/photo.jpg',kind='image'),
                        dict(url='https://example.com/background.png',kind='image'),
                        dict(url='https://example.com/video.mp4',kind='video'),
                        dict(url='https://example.com/audio.mp3',kind='audio'),
                        dict(url='blob:https://example.com/123',kind='video'),
                        dict(url='http://127.0.0.1/private',kind='image')])
    monkeypatch.setattr('mediaharvester.extractors.run_job',run)
    monkeypatch.setattr(registry.plugins[1],'extract',lambda *args:[])
    result=registry.analyze('https://example.com',deep=True)
    assert jobs[0][0]['action']=='dynamic' and jobs[0][1]==45
    assert [m.kind for m in result]==['video','audio','image','image']
    assert result[2].url=='https://example.com/assets/photo.jpg'
    assert all(m.headers=={'Referer':'https://example.com/page'} for m in result)


def test_dynamic_stream_and_image_limit(monkeypatch):
    registry=ExtractorRegistry(dict(Settings.defaults,max_images=1))
    monkeypatch.setattr('mediaharvester.extractors.run_job',lambda *args,**kwargs:dict(
        url='https://example.com',html='<img src="/one.jpg">',media=[
            dict(url='https://example.com/two.jpg',kind='image'),
            dict(url='https://example.com/main.m3u8',kind='stream')]))
    def extract(url,*args):
        if url.endswith('.m3u8'):
            assert args[-1]=='https://example.com'
            return [Media(url,url,'Stream','video',formats=[{'format_id':'1'}])]
        raise ValueError('Unsupported page')
    monkeypatch.setattr(registry.plugins[1],'extract',extract)
    result=registry.analyze('https://example.com',deep=True)
    assert len(result)==2 and result[0].formats
    assert result[0].headers=={'Referer':'https://example.com'}
    assert result[1].url.endswith('/one.jpg')


def test_dynamic_empty_and_cancelled(monkeypatch):
    registry=ExtractorRegistry(Settings.defaults.copy())
    monkeypatch.setattr('mediaharvester.extractors.run_job',lambda *args,**kwargs:dict(url='https://example.com',html=''))
    monkeypatch.setattr(registry.plugins[1],'extract',lambda *args:[])
    with pytest.raises(ValueError,match='未发现'): registry.analyze('https://example.com',deep=True)
    cancel=threading.Event(); cancel.set()
    with pytest.raises(InterruptedError): registry.analyze('https://example.com',cancel,deep=True)


def test_browser_launch_error_is_actionable(monkeypatch):
    api=pytest.importorskip('playwright.sync_api')
    from types import SimpleNamespace
    from mediaharvester.dynamic import render_page
    def launch(**kwargs): raise RuntimeError('Executable does not exist')
    @contextmanager
    def driver():
        yield SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    monkeypatch.setattr(api,'sync_playwright',driver)
    with pytest.raises(RuntimeError,match='python -m playwright install chromium'):
        render_page(dict(url='https://example.com'),SimpleNamespace(browser={}))


def test_real_browser_dynamic_page(monkeypatch,tmp_path):
    pytest.importorskip('playwright.sync_api')
    from mediaharvester.dynamic import render_page
    from mediaharvester.proxy import EngineProxy
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            requests.append((self.path,self.headers.get('Cookie','')))
            if self.path=='/':
                content=b'''<html><head><base href="/assets/"><style>.photo{background-image:url(bg.png)}</style></head>
                <body><div class="photo">Background</div><script>
                setTimeout(()=>{
                    const img=document.createElement('img');img.src='dynamic.png';document.body.append(img);
                    const video=document.createElement('video');video.src='clip.mp4';video.preload='auto';document.body.append(video);
                    const blocked=document.createElement('img');blocked.src='file:///private.png';document.body.append(blocked);
                },100);
                </script></body></html>'''
                mime='text/html'
            else:
                content=b'fixture'; mime='video/mp4' if self.path.endswith('.mp4') else 'image/png'
            self.send_response(200); self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(content))); self.end_headers(); self.wfile.write(content)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    url=f'http://127.0.0.1:{server.server_port}/'
    # Explicitly allow only this test's loopback fixture, never production requests.
    from mediaharvester.security import validate_url
    def validate_fixture(candidate):
        if candidate.startswith(url): return candidate
        return validate_url(candidate)
    monkeypatch.setattr('mediaharvester.dynamic.validate_url',validate_fixture)
    monkeypatch.setattr('mediaharvester.proxy.validate_url',validate_fixture)
    monkeypatch.setattr('mediaharvester.proxy.client',lambda:httpx.Client(trust_env=False))
    cookie=tmp_path/'cookies.txt'
    cookie.write_text('# Netscape HTTP Cookie File\n127.0.0.1\tFALSE\t/\tFALSE\t0\tsession\tfixture\n')
    try:
        with EngineProxy() as proxy:
            rendered=render_page(dict(url=url,cookie_file=str(cookie)),proxy)
        assert 'dynamic.png' in rendered['html']
        sources={item['url']:item['kind'] for item in rendered['media']}
        assert sources[url+'assets/dynamic.png']=='image'
        assert sources[url+'assets/bg.png']=='image'
        assert sources[url+'assets/clip.mp4']=='video'
        assert not any(candidate.startswith('file:') for candidate in sources)
        assert requests[0]==('/','session=fixture')
    finally:
        server.shutdown(); server.server_close(); thread.join()
