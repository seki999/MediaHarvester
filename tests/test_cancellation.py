import threading
import os
import signal
import subprocess
import sys
from pathlib import Path
import pytest
from dataclasses import asdict
from mediaharvester.models import Media,State
from mediaharvester.database import Repository
from mediaharvester.config import Settings
from mediaharvester.download import DownloadManager
from test_core import FORMATS,wait_for


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux process-group regression; Windows uses job objects')
def test_worker_kill_terminates_browser_children():
    from mediaharvester.worker import kill_tree
    code='import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); print(p.pid,flush=True); time.sleep(60)'
    process=subprocess.Popen([sys.executable,'-c',code],start_new_session=True,stdout=subprocess.PIPE,text=True)
    try:
        child=int(process.stdout.readline())
        kill_tree(process)
        assert process.returncode==-signal.SIGKILL
        def child_stopped():
            path=Path(f'/proc/{child}/stat')
            return not path.exists() or path.read_text().split()[2]=='Z'
        wait_for(child_stopped)
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL); process.wait()
        process.stdout.close()

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
