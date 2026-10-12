import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import httpx
import pytest
from mediaharvester.config import executable
from test_server.main import TestServer
from test_server.media_generator import generate


@pytest.fixture(scope='session')
def media_root(tmp_path_factory):
    if not executable('ffmpeg') or not executable('ffprobe'):
        pytest.skip('SKIPPED_ENVIRONMENT: FFmpeg/FFprobe required for generated media')
    root = tmp_path_factory.mktemp('controlled-media')
    generate(root)
    return root


@pytest.fixture(scope='session')
def fixture_server(media_root):
    with TestServer(media_root) as server:
        yield server


@pytest.fixture
def local_network(monkeypatch, fixture_server):
    # Inject only into consumers in this pytest process; production guards stay intact.
    from urllib.parse import urlsplit
    from mediaharvester.security import validate_url
    origin = fixture_server.url

    def guard(url):
        parsed = urlsplit(url)
        if f'{parsed.scheme}://{parsed.netloc}' == origin:
            return url
        return validate_url(url)

    def client():
        return httpx.Client(trust_env=False, timeout=2, follow_redirects=True, max_redirects=5,
                            headers={'Accept-Encoding': 'identity'},
                            event_hooks={'request': [lambda req: guard(str(req.url))]})

    for module in ('download', 'extractors', 'aria2'):
        monkeypatch.setattr(f'mediaharvester.{module}.client', client)
    monkeypatch.setattr('mediaharvester.extractors.validate_url', guard)
    monkeypatch.setattr('mediaharvester.download.executable', lambda name: None if name == 'aria2c' else executable(name))
    yield client


@pytest.fixture
def local_engine(monkeypatch, fixture_server, local_network):
    from mediaharvester.worker import kill_tree

    def run(job, cancel, progress=None, timeout=60):
        if job['action']=='dynamic':
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                pytest.skip('Optional Playwright is not installed')
            with sync_playwright() as playwright:
                if not Path(playwright.chromium.executable_path).exists():
                    pytest.skip('Optional Chromium is not installed')
        # Real yt-dlp worker, real authenticated proxy, real FFmpeg in an isolated process.
        with tempfile.TemporaryDirectory(prefix='mh-test-engine-') as directory:
            request, result, events = [Path(directory) / n for n in ('request.json', 'result.json', 'events.jsonl')]
            request.write_text(json.dumps(job), encoding='utf-8')
            stderr=Path(directory)/'stderr.txt'
            errors=stderr.open('wb')
            proc = subprocess.Popen([sys.executable, '-m', 'test_server.engine_runner', fixture_server.url,
                                     str(request), str(result), str(events)], stdout=subprocess.DEVNULL, stderr=errors,
                                    env=dict(os.environ,DEBUG='pw:browser') if job['action']=='dynamic' else None)
            start = time.monotonic()
            try:
                while proc.poll() is None:
                    if cancel.wait(.05): raise InterruptedError('test cancelled')
                    if time.monotonic() - start > (timeout or 60):
                        from scripts.run_online_tests import sanitize
                        raise TimeoutError('test worker timed out: '+sanitize(stderr.read_text('utf-8',errors='replace')))
                assert result.exists(), f'Worker exit {proc.returncode}'
                payload = json.loads(result.read_text('utf-8'))
                if 'error' in payload: raise RuntimeError(payload['error'])
                return payload
            finally:
                if proc.poll() is None: kill_tree(proc)
                errors.close()

    monkeypatch.setattr('mediaharvester.extractors.run_job', run)
    monkeypatch.setattr('mediaharvester.download.run_job', run)
    return run


def pytest_addoption(parser):
    parser.addoption('--stress', action='store_true', help='Enable bounded local large-file tests')


def pytest_collection_modifyitems(config, items):
    for item in items:
        if 'stress' in item.keywords and not config.getoption('--stress'):
            item.add_marker(pytest.mark.skip(reason='Explicit --stress required'))
