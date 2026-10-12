import pytest
from mediaharvester.config import Settings
from mediaharvester.extractors import ExtractorRegistry


def test_octet_stream_mp4_detected(fixture_server,local_network,monkeypatch):
    def no_engine(*args,**kwargs): raise AssertionError('Direct MP4 must not invoke website engine')
    monkeypatch.setattr('mediaharvester.extractors.run_job',no_engine)
    media=ExtractorRegistry(Settings.defaults).analyze(fixture_server.url+'/video/unknown-content-type')[0]
    assert media.kind=='video' and media.ext=='mp4'


@pytest.mark.parametrize('mime',['application/ogg','video/ogg','audio/ogg'])
def test_application_ogg_audio_detected(local_network,fixture_server,monkeypatch,mime):
    import httpx
    content=b'OggS'+b'\0'*24+b'\x01vorbis'+b'\0'*100
    monkeypatch.setattr('mediaharvester.extractors.client',lambda:httpx.Client(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,headers={'Content-Type':mime},content=content))))
    def no_engine(*args,**kwargs): raise AssertionError('Direct Ogg must not invoke website engine')
    monkeypatch.setattr('mediaharvester.extractors.run_job',no_engine)
    media=ExtractorRegistry(Settings.defaults).analyze('https://example.com/audio')[0]
    assert media.kind=='audio' and media.ext=='ogg'
