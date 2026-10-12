import threading
from mediaharvester.extractors import YtDlpExtractor,format_options
from .helpers import download,probe


def test_selected_playlist_entry_reextracted_and_downloaded(tmp_path,fixture_server,local_engine):
    media=YtDlpExtractor().extract(fixture_server.url+'/pages/multiple-videos',threading.Event())
    assert len(media)==2
    result=download(tmp_path,media[0],format_options(media[0].formats)[0][1])
    assert {s['codec_type'] for s in probe(result)['streams']}=={'video','audio'}
