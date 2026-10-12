import threading
import pytest
from mediaharvester.extractors import YtDlpExtractor, format_options
from .helpers import download, probe


@pytest.mark.parametrize('height', [360, 720, 1080])
def test_hls_selected_resolution_and_audio(tmp_path, fixture_server, local_engine, height):
    media = YtDlpExtractor().extract(fixture_server.url + '/hls/master.m3u8', threading.Event())[0]
    assert {f['height'] for f in media.formats} >= {360, 720, 1080}
    options = format_options(media.formats)
    selector = next(selector for label, selector in options if label.startswith(str(height)+'p'))
    result = download(tmp_path, media, selector)
    info = probe(result)
    assert any(s['codec_type']=='video' and s['height']==height for s in info['streams'])
    assert any(s['codec_type']=='audio' for s in info['streams'])
    assert abs(float(info['format']['duration'])-2)<.25


def test_hls_fmp4_real_merge(tmp_path, fixture_server, local_engine):
    media = YtDlpExtractor().extract(fixture_server.url + '/hls/fmp4/index.m3u8?token=fixture', threading.Event())[0]
    result = download(tmp_path, media, format_options(media.formats)[0][1])
    assert {s['codec_type'] for s in probe(result)['streams']} == {'video', 'audio'}


@pytest.mark.parametrize('path', ['broken', 'missing'])
def test_hls_invalid_or_missing_never_succeeds(fixture_server, local_engine, path, tmp_path):
    url = fixture_server.url + f'/hls/{path}.m3u8'
    with pytest.raises((RuntimeError, AssertionError)):
        media = YtDlpExtractor().extract(url, threading.Event())[0]
        download(tmp_path, media, format_options(media.formats)[0][1])


@pytest.mark.parametrize('language',['en','ja'])
def test_hls_separate_language_audio_and_subtitles(tmp_path,fixture_server,local_engine,language):
    media=YtDlpExtractor().extract(fixture_server.url+'/hls/split/master.m3u8',threading.Event())[0]
    assert {f.get('language') for f in media.formats if f.get('vcodec')=='none'} >= {'en','ja'}
    video=next(f for f in media.formats if f.get('height')==720)
    audio=next(f for f in media.formats if f.get('vcodec')=='none' and f.get('language')==language)
    result=download(tmp_path,media,str(video['format_id'])+'+'+str(audio['format_id']),subtitles=True)
    assert {s['codec_type'] for s in probe(result)['streams']}=={'video','audio'}
    assert list(tmp_path.glob('*.vtt'))


def test_hls_transient_segment_manual_retry_recovers(tmp_path,fixture_server,local_engine):
    media=YtDlpExtractor().extract(fixture_server.url+'/hls/transient/index.m3u8',threading.Event())[0]
    selector=format_options(media.formats)[0][1]
    with pytest.raises(AssertionError):download(tmp_path,media,selector)
    # Each fragment's first request fails; make subsequent requests available.
    for name in ('index0.ts','index1.ts'):fixture_server.counts['/hls/transient/'+name]=1
    result=download(tmp_path,media,selector)
    assert {s['codec_type'] for s in probe(result)['streams']}=={'video','audio'}
