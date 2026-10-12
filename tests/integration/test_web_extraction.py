import threading
import pytest
from mediaharvester.config import Settings
from mediaharvester.extractors import ExtractorRegistry, format_options
from .helpers import download, probe


@pytest.mark.parametrize('page',['html5-video','multiple-source','iframe-video','nested-iframe','video-poster','multiple-videos','relative-url','redirected-media'])
def test_html_video_actual_download(tmp_path,fixture_server,local_engine,page):
    results=ExtractorRegistry(dict(Settings.defaults,auto_browser_cookies=False)).analyze(fixture_server.url+'/pages/'+page)
    videos=[m for m in results if m.kind=='video']
    assert videos
    result=download(tmp_path,videos[0],format_options(videos[0].formats)[0][1] if videos[0].formats else '')
    assert {s['codec_type'] for s in probe(result)['streams']}=={'video','audio'}


@pytest.mark.parametrize('page',['javascript-video','lazy-loaded-video'])
def test_dynamic_video_deep_download(tmp_path,fixture_server,local_engine,page):
    results=ExtractorRegistry(dict(Settings.defaults,auto_browser_cookies=False)).analyze(fixture_server.url+'/pages/'+page,deep=True)
    assert any(m.kind=='video' for m in results)
    media=next(m for m in results if m.kind=='video')
    result=download(tmp_path,media,format_options(media.formats)[0][1] if media.formats else '')
    assert any(s['codec_type']=='video' for s in probe(result)['streams'])


def test_large_html_rejected(fixture_server,local_network):
    with pytest.raises(ValueError,match='5 MB'):
        ExtractorRegistry(Settings.defaults).analyze(fixture_server.url+'/pages/large')
