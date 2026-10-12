"""Stable reproductions, executed before production fixes (see baseline/regressions.xml)."""
import json
import threading
from dataclasses import asdict
from pathlib import Path
import pytest
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager, HttpBackend
from mediaharvester.extractors import ExtractorRegistry, format_options
from mediaharvester.models import Media, Task, State
from mediaharvester.files import sha256
from .helpers import wait


@pytest.mark.parametrize('endpoint', ['bad-end', 'bad-total'])
def test_invalid_range_bounds(tmp_path, fixture_server, local_network, endpoint):
    task = Task(asdict(Media(fixture_server.url + '/binary/' + endpoint, '', 'file', 'audio', 'bin')), str(tmp_path), etag='"fixture-v1"')
    (tmp_path / 'payload.part').write_bytes(b'x' * 32)
    with pytest.raises(OSError, match='Content-Range'):
        HttpBackend().download(task, tmp_path, threading.Event(), lambda: None, {})


def test_weak_etag_with_last_modified_can_resume(tmp_path, fixture_server, local_network):
    from test_server.media_generator import binary_block
    task = Task(asdict(Media(fixture_server.url + '/binary/weak?size=131072', '', 'file', 'audio', 'bin')), str(tmp_path),
                etag='W/"weak"', modified='Fri, 09 Oct 2026 00:00:00 GMT')
    (tmp_path / 'payload.part').write_bytes(binary_block())
    result = HttpBackend().download(task, tmp_path, threading.Event(), lambda: None, {})
    assert result.read_bytes() == binary_block() * 2


def test_drm_audio_never_auto_paired():
    formats = [dict(format_id='v', vcodec='avc1', acodec='none', ext='mp4'),
               dict(format_id='a', vcodec='none', acodec='aac', ext='m4a', has_drm=True)]
    assert format_options(formats) == []


def test_direct_wrong_extension_corrected(fixture_server, local_network):
    media = ExtractorRegistry(Settings.defaults).analyze(fixture_server.url + '/video/wrong-extension.jpg')[0]
    assert media.kind == 'video' and media.ext == 'mp4'
    assert media.title.endswith('.mp4')


def test_content_disposition_unicode(fixture_server, local_network):
    media = ExtractorRegistry(Settings.defaults).analyze(fixture_server.url + '/video/disposition')[0]
    assert media.title == '测试_日本.mp4'


def test_video_with_expected_audio_rejects_silent_file(tmp_path, media_root, local_network, monkeypatch):
    def engine(job, *args, **kwargs):
        target = Path(job['temp']) / 'media.mp4'
        target.write_bytes((media_root / 'silent.mp4').read_bytes())
        return {'files': [str(target)]}
    monkeypatch.setattr('mediaharvester.download.run_job', engine)
    repo = Repository(tmp_path / 'db')
    settings = dict(Settings.defaults, directory=str(tmp_path), retries=0)
    manager = DownloadManager(repo, settings)
    try:
        media = asdict(Media('https://example.com/video', '', 'v', 'video', 'mp4', identity='v',
                             formats=[dict(format_id='av', vcodec='avc1', acodec='aac', ext='mp4')]))
        task = manager.add(media, 'av')
        wait(lambda: task.state in (State.COMPLETED, State.FAILED))
        assert task.state == State.FAILED
        assert '音' in task.error
    finally:
        manager.close(); repo.close()


def test_commit_recovery_restores_file_size(tmp_path):
    repo = Repository(tmp_path / 'db')
    task = Task(asdict(Media('https://example.com/file', '', 'v', 'audio', 'bin')), str(tmp_path), state=State.VERIFYING, total=9999)
    final = tmp_path / 'done.bin'
    final.write_bytes(b'complete')
    temp = tmp_path / '.mediaharvester' / task.id
    temp.mkdir(parents=True)
    (temp / 'commit.json').write_text(json.dumps({'path': str(final), 'digest': sha256(final)}), encoding='utf-8')
    repo.save(task)
    manager = DownloadManager(repo, dict(Settings.defaults, auto_resume=True))
    try:
        wait(lambda: manager.tasks[task.id].state == State.COMPLETED and task.id not in manager.running)
        restored = repo.all()[0]
        assert restored.total == restored.downloaded == len(b'complete')
    finally:
        manager.close(); repo.close()
