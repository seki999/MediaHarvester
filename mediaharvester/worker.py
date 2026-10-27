"""Isolated yt-dlp/browser process. Cancellation terminates its complete process tree."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from .security import validate_url
from .config import executable
from .processes import attach_job,release_job

class QuietLogger:
    def debug(self, message, **kwargs): pass
    def info(self, message, **kwargs): pass
    def warning(self, message, **kwargs): pass
    def error(self, message, **kwargs): pass

def kill_tree(process):
    if os.name == 'nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        os.killpg(process.pid,signal.SIGKILL)
    process.wait()

def run_job(job, cancel, progress=None, timeout=180):
    from .browser_cookies import browser_profiles,login_error
    if job.get('auto_browser_cookies') and job.get('cookie_file') and not job.get('browser_cookie'):
        from .cookies import scoped_cookies
        try:
            scoped_cookies(job['cookie_file'],job['url'])
        except ValueError:
            # An old export being moved/deleted must not disable auto discovery.
            job=dict(job,cookie_file='')
    try:
        return _run_job(job,cancel,progress,timeout)
    except RuntimeError as original:
        if not job.get('auto_browser_cookies') or not login_error(str(original)):
            raise
        sources=browser_profiles(job.get('cookie_browser','auto'))
        if not sources:
            raise RuntimeError('此媒体需要登录；未找到受支持的本机浏览器 Cookie。请在 Chrome、Edge 或 Firefox 登录后重试，或手动导入 Cookie。') from None
        for source in sources:
            if cancel.is_set(): raise InterruptedError('任务已暂停')
            if progress: progress({'phase':'正在尝试 '+source['browser']+' 的网站登录态'})
            try:
                retry=dict(job,browser_cookie=source,auto_browser_cookies=False)
                result=_run_job(retry,cancel,progress,timeout)
                if job['action']=='extract': result['mh_auth']=source
                return result
            except RuntimeError:
                continue
        raise RuntimeError('此媒体需要登录；已尝试本机浏览器，但没有可用的授权会话。请确认账号有查看权限，正常退出浏览器后重试；若浏览器加密保护阻止读取，请手动导入 Cookie。') from None


def _run_job(job, cancel, progress=None, timeout=180):
    with tempfile.TemporaryDirectory(prefix='mh-job-') as temp:
        request, result, events = [Path(temp)/n for n in ('request.json','result.json','events.jsonl')]
        request.write_text(json.dumps(job), 'utf-8')
        args = [sys.executable, '--worker'] if getattr(sys,'frozen',False) else [sys.executable,'-m','mediaharvester.worker']
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        proc = subprocess.Popen(args + [str(request),str(result),str(events)], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=flags,start_new_session=os.name!='nt')
        attach_job(proc)
        start, offset = time.monotonic(), 0
        try:
            while proc.poll() is None:
                if cancel.wait(.15):
                    raise InterruptedError('任务已暂停')
                if timeout and time.monotonic()-start>timeout:
                    raise TimeoutError('解析超时')
                if events.exists() and progress:
                    with events.open('r',encoding='utf-8') as stream:
                        stream.seek(offset)
                        for line in stream:
                            try: progress(json.loads(line))
                            except ValueError: pass
                        offset=stream.tell()
            if not result.exists():
                raise RuntimeError('媒体引擎异常退出')
            payload=json.loads(result.read_text('utf-8'))
            if 'error' in payload:
                raise RuntimeError(payload['error'])
            return payload
        finally:
            if proc.poll() is None:
                kill_tree(proc)
            release_job(proc)

def worker_main():
    req, result, events = map(Path, sys.argv[-3:])
    job=json.loads(req.read_text('utf-8'))
    from .proxy import EngineProxy
    proxy=EngineProxy().__enter__()
    try:
        validate_url(job['url'])
        if job['action']=='dynamic':
            from .dynamic import render_page
            payload=render_page(job,proxy)
        else:
            import yt_dlp
            from yt_dlp.networking.impersonate import ImpersonateTarget
            def emit(data):
                with events.open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(data)+'\n')
            track_bytes={}
            expected=[0]
            def hook(d):
                info_dict=d.get('info_dict') or {}
                phase='音频轨' if info_dict.get('vcodec')=='none' else '视频轨' if info_dict.get('acodec')=='none' else '媒体'
                track_bytes[d.get('filename','media')]=d.get('downloaded_bytes',0)
                total=expected[0] or (d.get('total_bytes') or d.get('total_bytes_estimate') or 0 if '+' not in job.get('selector','') else 0)
                emit({'downloaded':sum(track_bytes.values()), 'total':total,
                      'speed':d.get('speed') or 0, 'state':'DOWNLOADING','phase':phase})
            opts=dict(quiet=True,logger=QuietLogger(),socket_timeout=20, proxy=proxy.url,
                      impersonate=ImpersonateTarget(client='chrome'),
                      retries=0,fragment_retries=0, playlistend=100, enable_file_urls=False,
                      hls_prefer_native=True,http_headers={'User-Agent':'MediaHarvester/0.1'},
                      postprocessor_args={'ffmpeg_i':['-protocol_whitelist','file,pipe',
                          '-format_whitelist','mov,matroska,webm,ogg,mp3,flac,wav,mpegts,aac']})
            if job.get('referer'):
                opts['http_headers']['Referer']=validate_url(job['referer'])
            if job.get('browser_cookie') or job.get('cookie_file'):
                from .cookies import scoped_cookies
                if job.get('browser_cookie'):
                    from .browser_cookies import scoped_browser_cookies
                    jar=scoped_browser_cookies(job['browser_cookie'],job['url'],QuietLogger())
                else:
                    jar=scoped_cookies(job['cookie_file'],job['url'])
                cookie_copy=req.parent/'cookies.txt'
                jar.filename=str(cookie_copy)
                jar.save(ignore_discard=True,ignore_expires=False)
                opts['cookiefile']=str(cookie_copy)
            ffmpeg=executable('ffmpeg')
            if ffmpeg: opts['ffmpeg_location']=str(Path(ffmpeg).parent)
            if job['action']=='download':
                opts.update(format=job['selector'],outtmpl=str(Path(job['temp'])/'media.%(ext)s'),
                            continuedl=True, noplaylist=True,progress_hooks=[hook],
                            postprocessor_hooks=[lambda d:emit({'state':'MERGING','phase':'转换音频' if job.get('audio') else '合并 / 后处理'})],
                            ratelimit=job.get('rate') or None, writesubtitles=job.get('subtitles',False),
                            writethumbnail=job.get('thumbnail',False), merge_output_format=job.get('container','mkv'))
                if job.get('audio'):
                    opts['postprocessors']=[{'key':'FFmpegExtractAudio','preferredcodec':job['audio']}]
            with yt_dlp.YoutubeDL(opts) as ydl:
                from urllib.parse import urlsplit
                from .instagram import InstagramMediaIE
                if job['action']=='extract' and urlsplit(job['url']).hostname in ('www.instagram.com','instagram.com') and InstagramMediaIE.suitable(job['url']):
                    # Process raw photo metadata before yt-dlp's video-only
                    # format validation discards carousel photo entries.
                    info=InstagramMediaIE(ydl).extract(job['url'])
                else:
                    info=ydl.extract_info(job['url'],download=False)
                if info.get('has_drm'):
                    raise ValueError('该媒体受 DRM 保护，不支持下载')
                if job['action']=='download':
                    if info.get('is_live'):
                        raise ValueError('当前版本不支持直播录制')
                    if str(info.get('id') or '') != job.get('identity',''):
                        raise ValueError('媒体内容标识改变，已停止续传')
                    temp=Path(job['temp'])
                    selected=[f for f in info.get('formats',[]) if str(f.get('format_id')) in job['selector'].split('+')]
                    for selected_format in selected:
                        validate_url(selected_format['url'])
                        if selected_format.get('has_drm'):
                            raise ValueError('该媒体受 DRM 保护，不支持下载')
                        if selected_format.get('protocol') not in (None,'http','https','m3u8','m3u8_native','http_dash_segments'):
                            raise ValueError('下载协议不在受保护的 HTTP/HLS/DASH 后端范围内')
                    sizes=[f.get('filesize') or f.get('filesize_approx') or 0 for f in selected]
                    expected[0]=sum(sizes) if sizes and all(sizes) else 0
                    from .security import client
                    proof=[]
                    for format_id in job['selector'].split('+'):
                        f=next((f for f in info.get('formats',[]) if str(f.get('format_id'))==format_id),None)
                        if not f:
                            raise ValueError('所选媒体格式已不存在，已停止续传')
                        if f.get('protocol') in ('m3u8','m3u8_native'):
                            proof.append(dict(id=format_id,mode='hls-native',
                                              **{k:f.get(k) for k in ('vcodec','acodec','ext','width','height')},
                                              duration=info.get('duration')))
                            continue
                        if f.get('protocol') not in ('http','https'):
                            proof.append({'id':format_id,'mode':'restart'}); continue
                        try:
                            with client() as c:
                                r=c.head(f['url']); r.raise_for_status()
                            etag=r.headers.get('etag','')
                            length=int(r.headers.get('content-length') or 0)
                            if not etag or etag.startswith('W/') or not length:
                                proof.append({'id':format_id,'mode':'restart'}); continue
                            proof.append({'id':format_id,'etag':etag,'length':length,
                                          'vcodec':f.get('vcodec'),'acodec':f.get('acodec'),'ext':f.get('ext')})
                        except Exception:
                            proof.append({'id':format_id,'mode':'restart'})
                    from .resume import prepare_resume
                    if prepare_resume(temp,job['identity'],proof,'+' in job['selector']):
                        emit({'state':'DOWNLOADING','downloaded':0,'total':0,'speed':0})
                    ydl.process_ie_result(info, download=True)
                    paths=[str(p) for p in temp.glob('media.*') if p.suffix in ('.mp4','.webm','.mkv','.m4a','.mp3','.opus','.ogg','.flac','.wav')]
                    payload={'files':paths}
                else:
                    from .cookies import remove_secrets
                    payload=remove_secrets(ydl.sanitize_info(info))
    except Exception as exc:
        # Never return signed URLs, cookies or Authorization in diagnostics.
        message=str(exc)
        import re
        message=re.sub(r'https?://\S+', '[URL]',message)
        payload={'error':message[:800]}
    finally:
        proxy.__exit__()
    result.write_text(json.dumps(payload), 'utf-8')

if __name__=='__main__':
    worker_main()
