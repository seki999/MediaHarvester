import threading
from dataclasses import asdict
import httpx
import pytest
from mediaharvester.config import Settings
from mediaharvester.cookies import scoped_cookies
from mediaharvester.extractors import YtDlpExtractor, format_options
from .helpers import download, probe


def cookie_file(tmp_path, value='valid', path='/', secure=False):
    target=tmp_path/'synthetic-cookies.txt'
    target.write_text(f'# Netscape HTTP Cookie File\n127.0.0.1\tFALSE\t{path}\t{str(secure).upper()}\t0\tsession\t{value}\n',encoding='utf-8')
    return target


@pytest.mark.parametrize('endpoint',['cookie-required','redirect-after-login'])
def test_synthetic_auth_actual_engine_download(tmp_path,fixture_server,local_engine,endpoint):
    cookie=cookie_file(tmp_path)
    before=cookie.read_bytes()
    url=fixture_server.url+'/auth/'+endpoint
    media=YtDlpExtractor().extract(url,threading.Event(),str(cookie))[0]
    result=download(tmp_path,media,format_options(media.formats)[0][1],cookie_file=str(cookie))
    assert probe(result)['streams'] and cookie.read_bytes()==before
    # Persisted metadata and commit journals must not contain synthetic credentials.
    assert all('session=valid' not in p.read_text('utf-8',errors='ignore') for p in tmp_path.rglob('*.json'))


@pytest.mark.parametrize('endpoint',['cookie-required','session-expired','token-expired','invalid-cookie'])
def test_no_or_expired_auth_is_rejected(fixture_server,local_network,endpoint):
    with local_network() as client:
        assert client.get(fixture_server.url+'/auth/'+endpoint).status_code==401


@pytest.mark.parametrize('path,secure,expected',[('/',False,200),('/other',False,401),('/',True,401)])
def test_cookie_path_and_secure_enforced(tmp_path,fixture_server,path,secure,expected):
    cookie=cookie_file(tmp_path,path=path,secure=secure)
    jar=scoped_cookies(cookie,fixture_server.url+'/auth/cookie-required')
    with httpx.Client(trust_env=False,cookies=jar,timeout=2) as client:
        assert client.get(fixture_server.url+'/auth/cookie-required').status_code==expected


def test_cross_host_cookie_not_leaked(tmp_path,fixture_server):
    cookie=cookie_file(tmp_path)
    jar=scoped_cookies(cookie,fixture_server.url+'/auth/cross-domain')
    with httpx.Client(trust_env=False,cookies=jar,follow_redirects=True,timeout=2) as client:
        response=client.get(fixture_server.url+'/auth/cross-domain')
        assert response.status_code==401
        assert 'Cookie' not in response.request.headers
