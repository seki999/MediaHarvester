import threading
import pytest
from yt_dlp import YoutubeDL
from yt_dlp.utils import ExtractorError
from mediaharvester.instagram import InstagramMediaIE
from mediaharvester.extractors import YtDlpExtractor


def test_photo_uses_largest_actual_candidate():
    with YoutubeDL({'quiet':True}) as ydl:
        ie=InstagramMediaIE(ydl)
        result=ie._extract_product_media({'image_versions2':{'candidates':[
            {'url':'https://example.com/small.jpg','width':320,'height':400},
            {'url':'https://example.com/full.jpg','width':3000,'height':3981}]}})
        assert result['mh_image']['url']=='https://example.com/full.jpg'
        assert result['mh_image']['width']==3000
        ie.raise_no_formats('There is no video in this post',expected=True)


def test_no_photo_does_not_hide_errors():
    with YoutubeDL({'quiet':True}) as ydl:
        ie=InstagramMediaIE(ydl)
        ie._extract_product_media({})
        with pytest.raises(ExtractorError):
            ie.raise_no_formats('No available media',expected=True)


def test_carousel_photos_are_downloadable_images(monkeypatch):
    entries=[{'id':str(i),'mh_image':{'url':f'https://example.com/{i}.jpg','width':3000,'height':3981}}
             for i in range(4)]
    monkeypatch.setattr('mediaharvester.extractors.run_job',lambda *a,**kw:{'entries':entries})
    result=YtDlpExtractor().extract('https://www.instagram.com/p/example/',threading.Event())
    assert len(result)==4
    assert all(m.kind=='image' and not m.formats and m.width==3000 for m in result)
    assert len({m.title for m in result})==4
