import json
import sqlite3
import threading
import time
from .models import Task, State

class Repository:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        version=self.db.execute('PRAGMA user_version').fetchone()[0]
        if version>1:
            self.db.close()
            raise ValueError('任务数据库版本较新，请升级 MediaHarvester')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL, data TEXT NOT NULL)')
        if version==0: self.db.execute('PRAGMA user_version=1')
        self.db.commit()
    def save(self, task: Task):
        task.updated = time.time()
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?,?)',
                            (task.id, task.state, task.updated, json.dumps(task.dict())))
    def all(self):
        with self.lock:
            return [Task(**json.loads(r[0])) for r in self.db.execute('SELECT data FROM tasks ORDER BY updated DESC')]
    def delete(self, id):
        with self.lock, self.db:
            self.db.execute('DELETE FROM tasks WHERE id=?', (id,))
    def close(self):
        with self.lock:
            self.db.close()
