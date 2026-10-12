"""Bounded public checks. No personal cookies; metadata success is not download success.

The .yaml fixtures use JSON syntax (a YAML subset), avoiding a new dependency.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from mediaharvester.config import Settings, executable
from mediaharvester.extractors import ExtractorRegistry, YtDlpExtractor
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.models import State


def sanitize(message):
    message=re.sub(r'https?://\S+','[URL]',str(message))
    return re.sub(r'(?im)\b(cookie|authorization|set-cookie|proxy-authorization)\s*[:=][^\r\n]+',r'\1: [REDACTED]',message)[:4000]


def classify(error):
    text=str(error).lower()
    if any(w in text for w in ('401','403','429','login','logged-in','authentication','log in','sign in','captcha','geo','drm','blocked','认证','授权','登录')): return 'BLOCKED'
    if any(w in text for w in ('404','410','not found','not available','removed','deleted','does not exist','no video could be found')): return 'UNAVAILABLE'
    if any(w in text for w in ('timeout','timed out','dns','connection','network')): return 'FLAKY'
    if 'unsupported url' in text: return 'UNSUPPORTED'
    return 'FAIL'


def direct_case(sample):
    from mediaharvester.security import SafeTransport
    limit=sample['max_bytes']
    used=[0]
    class BudgetStream(httpx.SyncByteStream):
        def __init__(self,stream): self.stream=stream
        def __iter__(self):
            for chunk in self.stream:
                used[0]+=len(chunk)
                if used[0]>limit: raise ValueError('Online byte budget exceeded')
                yield chunk
        def close(self): self.stream.close()
    class BudgetTransport(SafeTransport):
        def handle_request(self,request):
            response=super().handle_request(request)
            response.stream=BudgetStream(response.stream)
            return response
    def client():
        return httpx.Client(transport=BudgetTransport(),trust_env=False,follow_redirects=True,
                            max_redirects=5,timeout=10,headers={'Accept-Encoding':'identity'})
    import mediaharvester.extractors as extraction
    import mediaharvester.download as downloads
    extraction.client=downloads.client=client
    downloads.executable=lambda name:None if name=='aria2c' else executable(name)
    settings=dict(Settings.defaults,retries=0,auto_browser_cookies=False,cookie_file='',notify=False)
    with tempfile.TemporaryDirectory(prefix='mh-online-') as directory:
        settings['directory']=directory
        # Preserve origin's access error; do not confuse a fallback engine's
        # unknown track metadata with a direct-file detection failure.
        with client() as c, c.stream('GET',sample['url']) as response:
            response.raise_for_status()
        media=ExtractorRegistry(settings).analyze(sample['url'])[0]
        assert media.kind==sample['kind'],f'Expected {sample["kind"]}, got {media.kind}'
        repo=Repository(Path(directory)/'tasks.db'); manager=DownloadManager(repo,settings)
        try:
            task=manager.add(asdict(media))
            end=time.monotonic()+60
            while task.state not in (State.COMPLETED,State.FAILED) or task.id in manager.running:
                if time.monotonic()>end: manager.cancel(task.id);raise TimeoutError('download timeout')
                time.sleep(.03)
            assert task.state==State.COMPLETED,task.error
            file=Path(task.final)
            result={'stage':'integrity','bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'engine':task.engine,
                    'database_state':repo.all()[0].state,'network_bytes':used[0]}
            if sample['kind']=='image':
                from PIL import Image
                with Image.open(file) as image: result['dimensions']=image.size;image.verify()
            else:
                if not executable('ffprobe'): raise RuntimeError('SKIPPED_ENVIRONMENT: FFprobe unavailable')
                probe=subprocess.run([executable('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(file)],capture_output=True,text=True,check=True,timeout=20)
                info=json.loads(probe.stdout)
                kinds={s['codec_type'] for s in info['streams']}
                assert sample['kind'] in kinds
                if sample.get('expected_audio'): assert 'audio' in kinds
                result['streams']=[{k:s.get(k) for k in ('codec_type','codec_name','height','channels')} for s in info['streams']]
                result['duration']=float(info['format'].get('duration',0))
            return result
        finally: manager.close();repo.close()


def execute(sample):
    result={k:sample.get(k) for k in ('id','site','url','source','license','kind')}
    result['date']=datetime.now(timezone(timedelta(hours=9))).isoformat()
    result['stage']='extraction';started=time.monotonic()
    try:
        if sample.get('download'):
            result.update(direct_case(sample));result['status']='PASS'
        elif not sample.get('url'):
            result.update(status='BLOCKED',reason='尚未取得此 URL 类型的可验证公开授权样例；没有执行网络请求')
        else:
            media=YtDlpExtractor({'auto_browser_cookies':False}).extract(sample['url'],threading.Event())
            assert media and media[0].formats,'No media/formats returned'
            result.update(extraction='PASS',title=media[0].title,duration=media[0].duration,formats=len(media[0].formats),
                          status='SKIPPED' if sample.get('license') else 'BLOCKED',stage='download',
                          reason='仅完成提取；本轮平台候选未执行下载，公开小素材另有直链验证' if sample.get('license') else '仅完成提取；未确认下载授权，未下载')
    except Exception as exc:
        import traceback
        result.update(status=classify(exc),reason=sanitize(exc),traceback=sanitize(traceback.format_exc()))
        if sample['site'] in ('Facebook Video','X / Twitter'):
            result['failure_owner']='upstream yt-dlp / sample; see upstream-diagnostics.json'
    result['seconds']=round(time.monotonic()-started,3)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sites',action='store_true',help='Also extract platform candidate metadata; no unlicensed downloads')
    parser.add_argument('--case',type=int)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/online.json')
    args=parser.parse_args()
    fixtures=ROOT/'tests/fixtures'
    samples=json.loads((fixtures/'public_video_urls.yaml').read_text('utf-8'))+json.loads((fixtures/'public_image_urls.yaml').read_text('utf-8'))
    if args.sites: samples+=json.loads((fixtures/'site_samples.yaml').read_text('utf-8'))
    if args.case is not None:
        result=execute(samples[args.case])
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    args.output.parent.mkdir(parents=True,exist_ok=True)
    results=[]
    # Fixed fixtures reserve <=42 MB media-response budget. Metadata-only tests
    # have process deadlines, zero retries and no playlist traversal beyond product limits.
    assert sum(s.get('max_bytes',0) for s in samples if s.get('download'))<=60_000_000
    stopped_sites=set()
    for index,sample in enumerate(samples):
        if sample['site'] in stopped_sites:
            result=dict(sample,status='BLOCKED',reason='本站已返回 429，停止本轮后续请求')
        else:
            with tempfile.TemporaryDirectory(prefix='mh-online-case-') as directory:
                output=Path(directory)/'result.json'
                command=[sys.executable,str(Path(__file__).resolve()),'--case',str(index),'--output',str(output)]
                if args.sites:command.append('--sites')
                proc=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                from mediaharvester.processes import attach_job,release_job
                from mediaharvester.worker import kill_tree
                attach_job(proc)
                try:
                    proc.wait(timeout=90 if sample.get('download') else 35)
                    result=json.loads(output.read_text('utf-8')) if output.exists() else dict(sample,status='FAIL',reason=f'Case process exit {proc.returncode}')
                except subprocess.TimeoutExpired:
                    kill_tree(proc);result=dict(sample,status='FLAKY',stage='extraction',reason='35 秒有界超时；没有持续重试')
                finally:release_job(proc)
        if '429' in result.get('reason',''):stopped_sites.add(sample['site'])
        results.append(result)
        args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'{sample["id"]}: {result["status"]}',flush=True)
    return 1 if any(r['status']=='FAIL' for r in results) else 0


if __name__=='__main__':sys.exit(main() or 0)
