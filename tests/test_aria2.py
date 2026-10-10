import threading
import socket
from pathlib import Path
import pytest
import httpx
from mediaharvester.aria2 import Aria2Backend
from mediaharvester.config import Settings
from test_core import server,make_task,PAYLOAD

@pytest.fixture
def aria_environment(monkeypatch):
    binary=Path(__file__).resolve().parents[1]/'.dev-tools/aria2-1.37.0-win-64bit-build1/aria2c.exe'
    if not binary.exists(): pytest.skip('Optional aria2 binary not installed')
    monkeypatch.setattr('mediaharvester.aria2.executable',lambda name:str(binary))
    monkeypatch.setattr('mediaharvester.aria2.client',lambda:httpx.Client(trust_env=False,timeout=5))
    monkeypatch.setattr('mediaharvester.proxy.validate_url',lambda url:url)
    monkeypatch.setattr('mediaharvester.proxy.public_addresses',lambda host,port:socket.getaddrinfo(host,port,type=socket.SOCK_STREAM))
    monkeypatch.setattr('mediaharvester.proxy.client',lambda:httpx.Client(trust_env=False,timeout=5))

def test_aria2_download(tmp_path,server,aria_environment):
    task=make_task(tmp_path,server+'/normal')
    result=Aria2Backend().download(task,tmp_path,threading.Event(),lambda:None,Settings.defaults.copy())
    assert result.read_bytes()==PAYLOAD and task.downloaded==len(PAYLOAD)

def test_aria2_pause_resume(tmp_path,server,aria_environment):
    task=make_task(tmp_path,server+'/slow'); cancel=threading.Event(); settings=Settings.defaults.copy(); settings['rate']=65536
    timer=threading.Timer(1.5,cancel.set); timer.start()
    with pytest.raises(InterruptedError): Aria2Backend().download(task,tmp_path,cancel,lambda:None,settings)
    timer.join()
    assert (tmp_path/'aria-payload').exists() and (tmp_path/'aria-payload.aria2').exists()
    cancel.clear(); settings['rate']=0
    result=Aria2Backend().download(task,tmp_path,cancel,lambda:None,settings)
    assert result.read_bytes()==PAYLOAD
