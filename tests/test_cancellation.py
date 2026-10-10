import threading
from dataclasses import asdict
from mediaharvester.models import Media,State
from mediaharvester.database import Repository
from mediaharvester.config import Settings
from mediaharvester.download import DownloadManager
from test_core import FORMATS,wait_for

def test_cancel_survives_late_backend_progress(tmp_path,monkeypatch):
    entered=threading.Event()
    def engine(job,cancel,progress,**kwargs):
        entered.set(); assert cancel.wait(5)
        progress({'state':'DOWNLOADING','downloaded':999,'total':1000})
        raise InterruptedError('cancelled')
    monkeypatch.setattr('mediaharvester.download.run_job',engine)
    repo=Repository(tmp_path/'db'); settings=Settings.defaults.copy(); settings['directory']=str(tmp_path)
    manager=DownloadManager(repo,settings)
    task=manager.add(asdict(Media('https://example.com/v','https://example.com','v','video','mp4',formats=FORMATS,identity='v')),selector='b')
    try:
        assert entered.wait(5)
        manager.cancel(task.id)
        wait_for(lambda:task.id not in manager.running)
        assert task.state==State.CANCELLED and repo.all()[0].cancel_requested
    finally: manager.close(); repo.close()
