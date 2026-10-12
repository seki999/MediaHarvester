import hashlib
from dataclasses import asdict
from pathlib import Path
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.models import Media,State
from .helpers import wait


def test_concurrent_tasks_and_duplicate_resume(tmp_path,fixture_server,local_network):
    repo=Repository(tmp_path/'db')
    manager=DownloadManager(repo,dict(Settings.defaults,directory=str(tmp_path),concurrency=3,retries=0))
    try:
        tasks=[manager.add(asdict(Media(fixture_server.url+'/binary/normal?size=1048576','','same.bin','audio','bin'))) for _ in range(6)]
        for task in tasks:
            manager.resume(task.id);manager.resume(task.id)
        wait(lambda:all(t.state==State.COMPLETED for t in tasks) and not manager.running)
        assert len({t.final for t in tasks})==6
        assert len({t.digest for t in tasks})==1
        assert all(repo_task.state==State.COMPLETED for repo_task in repo.all())
        assert all(hashlib.sha256(Path(t.final).read_bytes()).hexdigest()==t.digest for t in tasks)
    finally:
        manager.close();repo.close()
