import pytest
from mediaharvester.config import Settings
from mediaharvester.extractors import ExtractorRegistry
from .helpers import download, probe


@pytest.mark.parametrize('ext', ['mp3','m4a','aac','opus','webm'])
def test_direct_audio_tracks_and_integrity(tmp_path, fixture_server, local_network, media_root, ext):
    media = ExtractorRegistry(Settings.defaults).analyze(fixture_server.url + '/audio.' + ext)[0]
    # WebM's MIME is video/webm even for an audio-only container; use known fixture expectation.
    if ext=='webm': media.kind='audio'
    result = download(tmp_path, media)
    assert result.read_bytes() == (media_root / f'audio.{ext}').read_bytes()
    streams=probe(result)['streams']
    assert {s['codec_type'] for s in streams} == {'audio'}
    assert streams[0]['channels']==2


@pytest.mark.parametrize('codec', ['mp3','m4a','opus'])
def test_video_audio_conversion(tmp_path, fixture_server, local_network, codec):
    media=ExtractorRegistry(Settings.defaults).analyze(fixture_server.url+'/video/direct.mp4')[0]
    result=download(tmp_path,media,audio=codec)
    assert result.suffix=='.'+codec
    assert {s['codec_type'] for s in probe(result)['streams']}=={'audio'}
