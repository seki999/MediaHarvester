import logging
import os
import re
import threading
import time
import httpx
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from .models import Task, State
from .security import client
from .files import publish, sha256, safe_name
from .worker import run_job
from .config import executable

log=logging.getLogger(__name__)
TERMINAL={State.COMPLETED,State.CANCELLED}

def retry_policy(exc, delay):
    """Stop on access limits/permanent errors; respect bounded server backoff."""
    if not isinstance(exc,httpx.HTTPStatusError):
        return not isinstance(exc,(ValueError,RuntimeError)),delay
    code=exc.response.status_code
    if code not in (408,425,500,502,503,504):
        return False,delay
    value=exc.response.headers.get('retry-after','')
    if value:
        try:
            seconds=float(value)
        except ValueError:
            try:
                date=parsedate_to_datetime(value)
                if date.tzinfo is None: date=date.replace(tzinfo=timezone.utc)
                seconds=(date-datetime.now(timezone.utc)).total_seconds()
            except (ValueError,TypeError,OverflowError):
                seconds=0
        # Long backoff is left for manual retry instead of blocking a worker indefinitely.
        if seconds>60: return False,delay
        delay=max(delay,max(0,seconds))
    return True,delay

class HttpBackend:
    def download(self, task, temp, cancel, update, settings):
        part=temp/'payload.part'
        offset=part.stat().st_size if part.exists() else 0
        headers={k:v for k,v in task.media.get('headers',{}).items()
                 if k.lower() in ('referer','user-agent')}
        validator=task.etag if task.etag and not task.etag.startswith('W/') else task.modified
        strong_etag=bool(task.etag and not task.etag.startswith('W/'))
        if offset and validator:
            headers.update({'Range':f'bytes={offset}-','If-Range':validator})
        elif offset:
            offset=0  # Without a validator, bytes cannot safely be appended.
        with client() as c, c.stream('GET',task.media['url'],headers=headers) as r:
            etag=r.headers.get('etag','')
            modified=r.headers.get('last-modified','')
            if r.status_code==416:
                match=re.fullmatch(r'bytes \*/(\d+)',r.headers.get('content-range',''))
                same=etag==task.etag if strong_etag else modified==task.modified and bool(modified)
                if match and offset==int(match[1]) and same:
                    task.downloaded=task.total=offset
                    update()
                    return part
                task.etag=task.modified=''
                part.unlink(missing_ok=True)
                raise OSError('Range 无效，已准备安全重新下载')
            r.raise_for_status()
            if r.status_code==206:
                match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',r.headers.get('content-range',''))
                if (not match or int(match[1])!=offset or 'Range' not in headers
                        or not offset<=int(match[2])<int(match[3])):
                    raise OSError('服务器返回无效 Content-Range')
                expected_length=int(match[2])-offset+1
                if r.headers.get('content-length') and int(r.headers['content-length'])!=expected_length:
                    raise OSError('服务器返回无效 Content-Range 长度')
                same=etag==task.etag if strong_etag else modified==task.modified and bool(modified)
                if not same:
                    task.etag=task.modified=''
                    part.unlink(missing_ok=True)
                    raise OSError('媒体验证标识改变，已准备安全重新下载')
                task.total=int(match[3])
            else:
                offset=0
                task.total=int(r.headers.get('content-length') or 0)
            task.etag,task.modified=etag,modified
            task.downloaded=offset
            update()
            started,last=time.monotonic(),time.monotonic()
            with part.open('ab' if offset else 'wb') as f:
                for chunk in r.iter_bytes(64*1024):
                    if cancel.is_set():
                        f.flush(); os.fsync(f.fileno())
                        raise InterruptedError('下载已暂停')
                    f.write(chunk)
                    task.downloaded+=len(chunk)
                    elapsed=max(time.monotonic()-started,.001)
                    task.speed=(task.downloaded-offset)/elapsed
                    rate=settings.get('rate',0)
                    if rate:
                        wait=(task.downloaded-offset)/rate-elapsed
                        if wait>0 and cancel.wait(wait):
                            f.flush(); os.fsync(f.fileno())
                            raise InterruptedError('下载已暂停')
                    if time.monotonic()-last>.4:
                        f.flush(); os.fsync(f.fileno()); update(); last=time.monotonic()
                f.flush(); os.fsync(f.fileno())
            if cancel.is_set():
                raise InterruptedError('下载已暂停')
            if task.total and task.downloaded!=task.total:
                raise OSError('下载数据长度不完整')
            if not task.downloaded:
                raise OSError('服务器返回空文件')
            update()
        return part

class DownloadManager:
    def __init__(self, repository, settings, notify=lambda t:None):
        self.repo,self.settings,self.notify=repository,settings,notify
        self.lock=threading.RLock()
        self.tasks={t.id:t for t in repository.all()}
        self.running={}
        self.closed=False
        self.pool=ThreadPoolExecutor(max_workers=16,thread_name_prefix='download')
        for task in self.tasks.values():
            if task.cancel_requested and task.state!=State.COMPLETED:
                task.state=State.CANCELLED; self.repo.save(task)
            if task.state not in TERMINAL | {State.FAILED,State.PAUSED}:
                task.state=State.PENDING if settings['auto_resume'] else State.PAUSED
                task.speed=0
                self.repo.save(task)
            if task.state==State.COMPLETED and (not task.final or not Path(task.final).exists()):
                task.state=State.FAILED
                task.error='已完成文件不存在，请重试'
                self.repo.save(task)
            elif task.state==State.COMPLETED and task.total and Path(task.final).stat().st_size!=task.total:
                task.state=State.FAILED; task.error='已完成文件长度改变，请手动检查后重试'
                self.repo.save(task)
        self.scheduler=threading.Thread(target=self._schedule,daemon=True)
        self.scheduler.start()
    def add(self, media, selector='',audio=''):
        task=Task(media=media,directory=self.settings['directory'],selector=selector,audio=audio)
        with self.lock:
            self.tasks[task.id]=task
            self.repo.save(task)
        return task
    def _schedule(self):
        while not self.closed:
            with self.lock:
                for task in list(self.tasks.values()):
                    if len(self.running)>=self.settings['concurrency']:
                        break
                    if task.state==State.PENDING and task.id not in self.running:
                        event=threading.Event()
                        self.running[task.id]=event
                        self.pool.submit(self._execute,task,event)
            time.sleep(.2)
    def save(self, task):
        self.repo.save(task)
    def _execute(self, task, cancel):
        temp=Path(task.directory)/'.mediaharvester'/task.id
        try:
            temp.mkdir(parents=True,exist_ok=True)
            while True:
                try:
                    if cancel.is_set(): raise InterruptedError()
                    task.state=State.DOWNLOADING
                    task.error=''
                    self.save(task)
                    # Commit journal bridges a crash between rename and database commit.
                    journal=temp/'commit.json'
                    if journal.exists():
                        import json
                        commit=json.loads(journal.read_text('utf-8'))
                        final=Path(commit['path'])
                        if final.exists() and sha256(final)==commit['digest']:
                            task.final=str(final); task.digest=commit['digest']; task.state=State.COMPLETED
                            task.downloaded=task.total=final.stat().st_size; task.speed=0
                            self.save(task); return
                    if task.selector and task.media.get('formats'):
                        task.engine='yt-dlp'
                        if ('+' in task.selector or task.audio) and not executable('ffmpeg'):
                            raise ValueError('需要 FFmpeg；请安装并加入 PATH，或放到 tools 文件夹')
                        def progress(data):
                            if cancel.is_set(): return
                            for key in ('state','downloaded','total','speed','phase'):
                                if key in data: setattr(task,key,data[key])
                            self.save(task)
                        result=run_job(dict(action='download',url=task.media['url'],selector=task.selector,
                                            identity=task.media['identity'],temp=str(temp),audio=task.audio,
                                            rate=self.settings['rate'],subtitles=self.settings['subtitles'],
                                            thumbnail=self.settings['thumbnail'],cookie_file=self.settings.get('cookie_file',''),browser_cookie=task.media.get('auth',{}),auto_browser_cookies=self.settings.get('auto_browser_cookies',False),cookie_browser=self.settings.get('cookie_browser','auto'),container=self._container(task)),cancel,progress,timeout=0)
                        if len(result['files'])!=1:
                            raise ValueError('媒体引擎没有产生唯一完整文件')
                        source=Path(result['files'][0])
                        title=safe_name(task.media['title'])
                        if self.settings.get('naming')=='site': title=safe_name(task.media['source']+' - '+title)
                        elif self.settings.get('naming')=='date': title=time.strftime('%Y-%m-%d')+' - '+title
                        name=title if title.lower().endswith(source.suffix.lower()) else title+source.suffix
                    else:
                        if executable('aria2c') and task.media['kind']!='image':
                            from .aria2 import Aria2Backend
                            task.engine='aria2'
                            source=Aria2Backend().download(task,temp,cancel,lambda:self.save(task),self.settings)
                        else:
                            task.engine='httpx'
                            source=HttpBackend().download(task,temp,cancel,lambda:self.save(task),self.settings)
                        name=safe_name(task.media['title'])
                        if '.' not in name: name+='.'+task.media['ext']
                        if task.audio:
                            from .media import FFmpegManager
                            task.state=State.MERGING; task.phase='转换音频'; self.save(task)
                            source=FFmpegManager().convert_audio(source,temp,task.audio,cancel)
                            name=str(Path(name).with_suffix('.'+task.audio))
                    if cancel.is_set(): raise InterruptedError()
                    task.state=State.VERIFYING
                    self.save(task)
                    if task.media['kind']=='image':
                        with Image.open(source) as image:
                            extension=(image.format or '').lower().replace('jpeg','jpg')
                            image.verify()
                        if extension:
                            task.media['ext']=extension
                            name=str(Path(name).with_suffix('.'+extension))
                    elif task.media.get('ext')!='bin':
                        from .media import FFmpegManager
                        verifier=FFmpegManager()
                        verifier.verify(source,cancel,'audio' if task.audio else task.media['kind'])
                        selected=[f for f in task.media.get('formats',[]) if str(f.get('format_id')) in task.selector.split('+')]
                        if not task.audio and task.media['kind']=='video' and any(f.get('acodec') not in (None,'none') for f in selected):
                            verifier.verify(source,cancel,'audio')
                    if source.stat().st_size==0: raise ValueError('空文件')
                    task.digest=sha256(source,cancel)
                    # Deduplication and commit form one critical section: simultaneous
                    # tasks with identical bytes must not publish two files.
                    with self.lock:
                        if cancel.is_set(): raise InterruptedError()
                        if self.settings['deduplicate'] and task.media['kind']=='image':
                            duplicate=next((t for t in self.tasks.values() if t.id!=task.id and t.state==State.COMPLETED and t.digest==task.digest and Path(t.final).exists()),None)
                            if duplicate:
                                source.unlink(); task.final=duplicate.final
                            else:
                                task.final=self._commit(source,task,temp,name)
                        else:
                            task.final=self._commit(source,task,temp,name)
                        task.state=State.COMPLETED; task.speed=0
                        task.downloaded=task.total=Path(task.final).stat().st_size
                        self.save(task)
                    self.notify(task)
                    break
                except InterruptedError:
                    if task.state!=State.CANCELLED: task.state=State.PAUSED
                    task.speed=0; self.save(task); break
                except Exception as exc:
                    task.speed=0
                    task.error=re.sub(r'https?://\S+','[URL]',str(exc))[:800]
                    log.warning('Task %s: %s',task.id,task.error)
                    task.attempts+=1
                    retry,delay=retry_policy(exc,min(60,self.settings['retry_delay']*2**(task.attempts-1)))
                    if not retry or task.attempts>self.settings['retries']:
                        task.state=State.FAILED; self.save(task); break
                    task.state=State.WAITING_RETRY; self.save(task)
                    if cancel.wait(delay):
                        if task.state!=State.CANCELLED: task.state=State.PAUSED
                        self.save(task); break
        finally:
            with self.lock:
                if task.cancel_requested and task.state!=State.COMPLETED:
                    task.state=State.CANCELLED; task.speed=0; self.save(task)
                self.running.pop(task.id,None)
    def _commit(self, source,task,temp,name):
        import json
        # Native engines close their files, but close alone does not flush disk caches.
        with source.open('r+b') as stream: os.fsync(stream.fileno())
        # Reserve the destination to make journal recovery deterministic without overwrites.
        directory=Path(task.directory)
        base=directory/safe_name(name)
        for i in range(10000):
            target=base if i==0 else base.with_name(f'{base.stem} ({i}){base.suffix}')
            try:
                fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                os.close(fd); break
            except FileExistsError: continue
        else: raise OSError('重名文件过多')
        journal=temp/'commit.json'
        with journal.open('w',encoding='utf-8') as stream:
            json.dump({'path':str(target),'digest':task.digest},stream)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(source,target)
        # Keep downloaded subtitles and thumbnails alongside the final media.
        for sidecar in temp.glob('media.*'):
            if sidecar.is_file() and sidecar!=source and sidecar.suffix.lower() in ('.jpg','.png','.webp','.vtt','.srt','.ass'):
                suffix=sidecar.name[len('media'):]
                publish(sidecar,directory,target.stem+suffix)
        return str(target)
    def _container(self,task):
        requested=self.settings.get('container','mp4')
        selected=[f for f in task.media.get('formats',[]) if str(f.get('format_id')) in task.selector.split('+')]
        if requested=='mp4':
            if any(f.get('ext') not in ('mp4','m4a') for f in selected):
                return 'mkv'
        if requested=='webm' and any(f.get('ext') not in ('webm','opus') for f in selected):
            return 'mkv'
        return requested
    def pause(self,id):
        with self.lock:
            task=self.tasks[id]
            if id in self.running:
                task.state=State.PAUSING; self.running[id].set()
            elif task.state not in TERMINAL: task.state=State.PAUSED
            self.save(task)
    def resume(self,id):
        with self.lock:
            task=self.tasks[id]
            if id not in self.running and task.state not in TERMINAL:
                task.state=State.PENDING; task.attempts=0; self.save(task)
    def cancel(self,id):
        with self.lock:
            task=self.tasks[id]
            if task.state==State.COMPLETED: return
            task.cancel_requested=True
            task.state=State.CANCELLED
            if id in self.running: self.running[id].set()
            self.save(task)
    def delete(self,id):
        with self.lock:
            if id in self.running: return False
            self.repo.delete(id); self.tasks.pop(id,None); return True
    def close(self):
        self.closed=True
        self.scheduler.join()
        with self.lock:
            for event in self.running.values(): event.set()
        self.pool.shutdown(wait=True)
