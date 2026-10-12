import json
import sys
import pytest
from mediaharvester.worker import worker_main
from mediaharvester.extractors import format_options


@pytest.mark.parametrize('carousel',[False,True])
def test_instagram_raw_video_gets_format_ids(tmp_path,monkeypatch,carousel):
    video={'id':'fixture-video','title':'Self-owned fixture','formats':[{
        'url':'https://example.com/fixture.mp4','ext':'mp4','vcodec':'avc1','acodec':'aac','height':360}]}
    image={'id':'fixture-photo','mh_image':{'url':'https://example.com/photo.jpg','width':64,'height':48}}
    raw={'_type':'playlist','id':'mixed','entries':[image,video]} if carousel else video
    monkeypatch.setattr('mediaharvester.instagram.InstagramMediaIE.extract',lambda *args:raw)
    request,result,events=[tmp_path/n for n in ('request.json','result.json','events.jsonl')]
    request.write_text(json.dumps({'action':'extract','url':'https://www.instagram.com/p/fixture/'}),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['worker',str(request),str(result),str(events)])
    worker_main()
    info=json.loads(result.read_text('utf-8'))
    assert 'error' not in info,info
    entries=info.get('entries',[info])
    actual=next(e for e in entries if e.get('id')=='fixture-video')
    assert format_options(actual['formats'])
    if carousel: assert entries[0]['mh_image']['width']==64
