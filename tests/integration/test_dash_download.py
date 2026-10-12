import threading
import pytest
from mediaharvester.extractors import YtDlpExtractor, format_options
from .helpers import download, probe


@pytest.mark.parametrize('path,height', [('manifest.mpd',720), ('list/manifest.mpd',360), ('template/manifest.mpd',360)])
def test_dash_separate_audio_video(tmp_path, fixture_server, local_engine, path, height):
    media = YtDlpExtractor().extract(fixture_server.url + '/dash/' + path, threading.Event())[0]
    assert any(f.get('vcodec')=='none' and f.get('acodec')!='none' for f in media.formats)
    selector = next(s for label, s in format_options(media.formats) if '+' in s)
    try:
        result = download(tmp_path, media, selector)
    except AssertionError:
        print(fixture_server.requests[-20:])
        raise
    info = probe(result)
    assert any(s['codec_type']=='video' and s['height']==height for s in info['streams'])
    assert any(s['codec_type']=='audio' for s in info['streams'])
    assert abs(float(info['format']['duration'])-2)<.25
