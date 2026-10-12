import pytest
from PIL import Image
from mediaharvester.config import Settings
from mediaharvester.extractors import ExtractorRegistry, HtmlImageExtractor
from .helpers import download


@pytest.mark.parametrize('ext', ['jpg','png','webp','gif','avif'])
def test_image_download_decode_and_hash(tmp_path, fixture_server, local_network, media_root, ext):
    media = ExtractorRegistry(Settings.defaults).analyze(fixture_server.url + '/image.' + ext)[0]
    result = download(tmp_path, media)
    assert result.read_bytes() == (media_root / f'image.{ext}').read_bytes()
    with Image.open(result) as image:
        assert image.size == (64,48)
        image.verify()


def test_image_candidates_largest_deduplicated(fixture_server, local_network):
    with local_network() as client:
        html=client.get(fixture_server.url+'/pages/images').text
    candidates=HtmlImageExtractor().extract_html(html,fixture_server.url)
    assert [c.url.rsplit('/',1)[1] for c in candidates] == ['image.jpg','image.png','image.gif','image.avif','image.webp']
