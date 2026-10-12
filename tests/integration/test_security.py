import socket
import threading
from dataclasses import asdict
import httpx
import pytest
from mediaharvester.security import client, public_addresses, validate_url, SecurityError
from mediaharvester.download import HttpBackend
from mediaharvester.models import Media,Task
from mediaharvester.files import safe_name


@pytest.mark.parametrize('host',['127.1','2130706433','0x7f000001','127.0.0.1.nip.io','10.0.0.1','[::ffff:127.0.0.1]'])
def test_private_encoded_or_dns_target_blocked(host,monkeypatch):
    # Controlled DNS answers keep offline tests completely independent of public DNS.
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',12345))])
    with client() as c:
        with pytest.raises((SecurityError,httpx.HTTPError,socket.gaierror)):
            c.get('http://'+host+':12345')


def test_dns_mixed_public_private_denied(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',80)),(2,1,6,'',('10.0.0.1',80))])
    with pytest.raises(SecurityError): public_addresses('mixed.test',80)


@pytest.mark.parametrize('name',['../../evil.mp4','C:\\Windows\\secret','CON.mp4','日本_中文.mp4','bad\x00name','..\\..\\a.jpg'])
def test_windows_filename_cannot_escape(name):
    result=safe_name(name)
    assert '/' not in result and '\\' not in result and ':' not in result and '\x00' not in result
    assert result not in ('.','..')


def test_credentials_not_forwarded_direct_http(tmp_path,monkeypatch):
    seen=[]
    def respond(request):
        seen.append(dict(request.headers))
        return httpx.Response(200,content=b'complete')
    monkeypatch.setattr('mediaharvester.download.client',lambda:httpx.Client(transport=httpx.MockTransport(respond)))
    task=Task(asdict(Media('https://example.com/file','','file','audio','bin',headers={
        'Cookie':'private','Authorization':'Bearer private','Referer':'https://example.com/'})),str(tmp_path))
    HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert 'cookie' not in seen[0] and 'authorization' not in seen[0]


def test_production_guard_unchanged_after_test_injection(fixture_server,local_network):
    with client() as c:
        with pytest.raises(SecurityError): c.get(fixture_server.url+'/video/direct.mp4')
