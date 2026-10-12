import hashlib
import threading
from dataclasses import asdict
import pytest
from mediaharvester.config import Settings
from mediaharvester.download import HttpBackend
from mediaharvester.extractors import ExtractorRegistry
from mediaharvester.models import Media, Task
from .helpers import download, probe


@pytest.mark.parametrize('endpoint,filename', [
    ('direct.mp4', 'video360.mp4'), ('direct.webm', 'direct.webm'), ('direct.mov', 'direct.mov'),
    ('no-extension?id=123', 'video360.mp4'), ('wrong-extension.jpg', 'video360.mp4'),
    ('chunked', 'video360.mp4'), ('no-content-length', 'video360.mp4'), ('disposition', 'video360.mp4')])
def test_http_complete_hash_and_tracks(tmp_path, fixture_server, local_network, endpoint, filename, media_root):
    media = ExtractorRegistry(Settings.defaults).analyze(fixture_server.url + '/video/' + endpoint)[0]
    result = download(tmp_path, media)
    assert hashlib.sha256(result.read_bytes()).digest() == hashlib.sha256((media_root / filename).read_bytes()).digest()
    info = probe(result)
    assert {s['codec_type'] for s in info['streams']} == {'video', 'audio'}
    assert abs(float(info['format']['duration']) - 2) < .2


@pytest.mark.parametrize('code', [301, 302, 303, 307, 308])
def test_redirect_download(tmp_path, fixture_server, local_network, media_root, code):
    media = ExtractorRegistry(Settings.defaults).analyze(fixture_server.url + f'/redirect/{code}')[0]
    result = download(tmp_path, media)
    assert result.read_bytes() == (media_root / 'video360.mp4').read_bytes()


def test_unknown_content_type_bytes_still_verified(tmp_path, fixture_server, local_network, media_root):
    url = fixture_server.url + '/video/unknown-content-type'
    task = Task(asdict(Media(url, '', 'unknown', 'video', 'mp4')), str(tmp_path))
    result = HttpBackend().download(task, tmp_path, threading.Event(), lambda: None, {})
    assert result.read_bytes() == (media_root / 'video360.mp4').read_bytes()
    assert probe(result)['streams']


def test_filename_collision_never_overwrites(tmp_path, fixture_server, local_network):
    media = Media(fixture_server.url + '/video/direct.mp4', '', '日本_测试.mp4', 'video', 'mp4')
    first = download(tmp_path, media)
    second = download(tmp_path, media)
    assert first != second and first.read_bytes() == second.read_bytes()
