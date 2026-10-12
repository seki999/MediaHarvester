import threading
import time
from dataclasses import asdict
import httpx
import pytest
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager, HttpBackend
from mediaharvester.models import Media, Task, State
from .helpers import wait


@pytest.mark.parametrize('code', [400,401,403,404,408,410,429,500,502,503,504])
def test_http_errors_never_publish(tmp_path, fixture_server, local_network, code):
    task=Task(asdict(Media(fixture_server.url+f'/status/{code}','','error','audio','bin')),str(tmp_path))
    with pytest.raises(httpx.HTTPStatusError) as error:
        HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert error.value.response.status_code==code
    assert not (tmp_path/'payload.part').exists()


def test_dropped_tcp_never_reports_complete(tmp_path,fixture_server,local_network):
    task=Task(asdict(Media(fixture_server.url+'/binary/drop','','drop','audio','bin')),str(tmp_path))
    with pytest.raises(httpx.HTTPError):
        HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert 0<(tmp_path/'payload.part').stat().st_size<10*1024*1024


def test_redirect_loop_bounded(tmp_path,fixture_server,local_network):
    task=Task(asdict(Media(fixture_server.url+'/loop','','loop','audio','bin')),str(tmp_path))
    count=fixture_server.counts['/loop']
    with pytest.raises(httpx.TooManyRedirects):
        HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert fixture_server.counts['/loop']-count==6


@pytest.mark.parametrize('code',[401,403,404,410,429])
def test_permanent_or_limited_status_stops_automatic_retry(tmp_path,fixture_server,local_network,code):
    path=f'/status/{code}'
    start=fixture_server.counts[path]
    repo=Repository(tmp_path/'db')
    manager=DownloadManager(repo,dict(Settings.defaults,directory=str(tmp_path),retries=2,retry_delay=1))
    try:
        task=manager.add(asdict(Media(fixture_server.url+path,'','error','audio','bin')))
        wait(lambda:task.state==State.FAILED and task.id not in manager.running)
        assert fixture_server.counts[path]-start==1
    finally:
        manager.close();repo.close()


def test_retry_after_honored_and_retry_count_bounded(tmp_path,fixture_server,local_network):
    path='/status/503'
    start=fixture_server.counts[path]
    repo=Repository(tmp_path/'db')
    manager=DownloadManager(repo,dict(Settings.defaults,directory=str(tmp_path),retries=1,retry_delay=1))
    begin=time.monotonic()
    try:
        task=manager.add(asdict(Media(fixture_server.url+path,'','503','audio','bin')))
        wait(lambda:task.state==State.FAILED and task.id not in manager.running)
        assert task.attempts==2 and fixture_server.counts[path]-start==2
        assert time.monotonic()-begin>=1
    finally:
        manager.close();repo.close()
