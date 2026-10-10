from dataclasses import dataclass, field, asdict
from enum import StrEnum
import uuid

class State(StrEnum):
    PENDING='PENDING'
    ANALYZING='ANALYZING'
    READY='READY'
    DOWNLOADING='DOWNLOADING'
    PAUSING='PAUSING'
    PAUSED='PAUSED'
    WAITING_RETRY='WAITING_RETRY'
    MERGING='MERGING'
    VERIFYING='VERIFYING'
    COMPLETED='COMPLETED'
    FAILED='FAILED'
    CANCELLED='CANCELLED'

@dataclass
class Media:
    url: str
    page: str
    title: str
    kind: str
    ext: str = ''
    size: int = 0
    width: int = 0
    height: int = 0
    thumbnail: str = ''
    source: str = ''
    duration: float = 0
    formats: list = field(default_factory=list)
    identity: str = ''
    headers: dict = field(default_factory=dict)
    auth: dict = field(default_factory=dict)

@dataclass
class Task:
    media: dict
    directory: str
    selector: str = ''
    audio: str = ''
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = State.PENDING
    downloaded: int = 0
    total: int = 0
    speed: float = 0
    error: str = ''
    attempts: int = 0
    etag: str = ''
    modified: str = ''
    final: str = ''
    digest: str = ''
    engine: str = ''
    phase: str = ''
    cancel_requested: bool = False
    updated: float = 0
    def dict(self):
        return asdict(self)
