import threading
from pathlib import Path
from dataclasses import asdict
import pytest
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager,HttpBackend
from mediaharvester.config import Settings
from mediaharvester.models import Media,Task,State
from test_core import server,local_client,make_task,PAYLOAD,wait_for

def test_future_schema_is_not_overwritten(tmp_path):
    import sqlite3
    path=tmp_path/'db'
    with sqlite3.connect(path) as db: db.execute('PRAGMA user_version=9')
    with pytest.raises(ValueError): Repository(path)
    with sqlite3.connect(path) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==9

def test_completed_file_missing(tmp_path):
    repo=Repository(tmp_path/'db'); task=make_task(tmp_path,'https://example.com/a')
    task.state=State.COMPLETED; task.final=str(tmp_path/'gone.bin'); repo.save(task)
    manager=DownloadManager(repo,Settings.defaults.copy())
    assert manager.tasks[task.id].state==State.FAILED
    manager.close(); repo.close()

def test_shutdown_resume_keeps_progress(tmp_path,server,local_client,monkeypatch):
    monkeypatch.setattr('mediaharvester.download.executable',lambda name:None)
    repo=Repository(tmp_path/'db'); settings=Settings.defaults.copy(); settings.update(directory=str(tmp_path),rate=65536)
    manager=DownloadManager(repo,settings)
    task=manager.add(asdict(Media(server+'/slow',server,'file.bin','audio','bin')))
    wait_for(lambda:task.downloaded>65536)
    manager.close(); repo.close()
    part=tmp_path/'.mediaharvester'/task.id/'payload.part'
    assert 0<part.stat().st_size<len(PAYLOAD)
    settings['rate']=0
    repo=Repository(tmp_path/'db'); manager=DownloadManager(repo,settings)
    assert manager.tasks[task.id].state==State.PAUSED
    manager.resume(task.id)
    wait_for(lambda:manager.tasks[task.id].state==State.COMPLETED)
    assert Path(manager.tasks[task.id].final).read_bytes()==PAYLOAD
    manager.close(); repo.close()

def test_ytdlp_reextract_identity_error_keeps_part(tmp_path,monkeypatch):
    def mismatch(*args,**kwargs): raise RuntimeError('媒体内容标识改变，已停止续传')
    monkeypatch.setattr('mediaharvester.download.run_job',mismatch)
    from test_core import FORMATS
    repo=Repository(tmp_path/'db'); settings=Settings.defaults.copy(); settings['directory']=str(tmp_path)
    media=asdict(Media('https://example.com/video','https://example.com/page','v','video','mp4',formats=FORMATS,identity='old'))
    task=Task(media,str(tmp_path),selector='b')
    temp=tmp_path/'.mediaharvester'/task.id; temp.mkdir(parents=True); (temp/'media.mp4.part').write_bytes(b'old data')
    repo.save(task); settings['auto_resume']=True
    manager=DownloadManager(repo,settings)
    wait_for(lambda:manager.tasks[task.id].state==State.FAILED)
    assert (temp/'media.mp4.part').read_bytes()==b'old data'
    manager.close(); repo.close()
