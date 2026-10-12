"""Compare raw upstream output with the application without personal credentials."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from mediaharvester.proxy import EngineProxy
from mediaharvester.worker import QuietLogger
from scripts.run_online_tests import sanitize, classify


def main():
    rows=json.loads((ROOT/'tests/fixtures/site_samples.yaml').read_text('utf-8'))
    results=[]
    for sample in rows:
        if sample['site'] not in ('Instagram Reels','Instagram video','Facebook Video','X / Twitter'):continue
        result={'id':sample['id'],'url':sample['url'],'version':yt_dlp.version.__version__}
        with EngineProxy() as proxy:
            opts=dict(quiet=True,logger=QuietLogger(),socket_timeout=8,proxy=proxy.url,retries=0,fragment_retries=0,
                      playlistend=1,enable_file_urls=False,impersonate=ImpersonateTarget(client='chrome'),
                      http_headers={'User-Agent':'MediaHarvester/0.1'})
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info=ydl.extract_info(sample['url'],download=False)
                    entries=list(info.get('entries') or [info])
                    result.update(status='PASS',entries=[{'type':e.get('_type'),'id':e.get('id'),
                                                        'format_count':len(e.get('formats') or []),
                                                        'thumbnail_count':len(e.get('thumbnails') or [])} for e in entries if e])
            except Exception as exc:
                result.update(status=classify(exc),reason=sanitize(exc))
        results.append(result)
        (ROOT/'reports/upstream-diagnostics.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(sample['id']+': '+result['status'],flush=True)


if __name__=='__main__':main()
