from dataclasses import asdict
import httpx
import pytest
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.models import Media,State
from test_server.network_faults import ERRORS,transport
from .helpers import wait


@pytest.mark.parametrize('fault',list(ERRORS))
def test_transport_fault_retries_are_bounded_and_no_output(tmp_path,monkeypatch,fault):
    calls=[]
    monkeypatch.setattr('mediaharvester.download.client',lambda:httpx.Client(transport=transport(fault,calls)))
    monkeypatch.setattr('mediaharvester.download.executable',lambda name:None)
    repo=Repository(tmp_path/'db');manager=DownloadManager(repo,dict(Settings.defaults,directory=str(tmp_path),retries=1,retry_delay=1))
    try:
        task=manager.add(asdict(Media('https://example.com/file','','failed','audio','bin')))
        wait(lambda:task.state==State.FAILED and task.id not in manager.running)
        assert len(calls)==2 and task.attempts==2
        assert not task.final and not list(tmp_path.glob('*.bin'))
        assert repo.all()[0].state==State.FAILED
    finally:manager.close();repo.close()
