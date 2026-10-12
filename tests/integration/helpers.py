import hashlib
import json
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path
from mediaharvester.config import Settings, executable
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.models import State


def probe(path):
    p = subprocess.run([executable('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                       check=True, capture_output=True, text=True, timeout=20)
    return json.loads(p.stdout)


def wait(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, 'Task did not settle within deadline'
        time.sleep(.02)


def download(tmp_path, media, selector='', audio='', **options):
    settings = dict(Settings.defaults, directory=str(tmp_path), retries=0, auto_browser_cookies=False, **options)
    repo = Repository(tmp_path / 'tasks.db')
    manager = DownloadManager(repo, settings)
    try:
        task = manager.add(asdict(media), selector, audio)
        wait(lambda: task.state in (State.COMPLETED, State.FAILED) and task.id not in manager.running)
        assert task.state == State.COMPLETED, task.error
        path = Path(task.final)
        assert path.is_file() and path.stat().st_size > 0
        assert task.total == task.downloaded == path.stat().st_size
        assert hashlib.sha256(path.read_bytes()).hexdigest() == task.digest
        stored = repo.all()[0]
        assert stored.state == State.COMPLETED and stored.digest == task.digest
        return path
    finally:
        manager.close()
        repo.close()
