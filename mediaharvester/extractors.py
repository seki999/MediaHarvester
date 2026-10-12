import re
import threading
import time
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit, urldefrag, unquote
from email.message import Message
from bs4 import BeautifulSoup
from .security import client, validate_url
from .models import Media
from .worker import run_job

def sniff_mime(prefix):
    """Recognize bounded file signatures only; this is not integrity verification."""
    if prefix.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if prefix.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if prefix.startswith((b'GIF87a',b'GIF89a')): return 'image/gif'
    if prefix[:4]==b'RIFF' and prefix[8:12]==b'WEBP': return 'image/webp'
    if prefix[4:8]==b'ftyp':
        if prefix[8:12] in (b'avif',b'avis'): return 'image/avif'
        return 'audio/mp4' if prefix[8:12] in (b'M4A ',b'M4B ') else 'video/mp4'
    if prefix.startswith(b'OggS'):
        return 'video/ogg' if b'theora' in prefix else 'audio/ogg'
    if prefix.startswith(b'ID3'): return 'audio/mpeg'
    return ''

class HtmlImageExtractor:
    def can_handle(self, url):
        return urlsplit(url).scheme in ('http', 'https')
    def extract_html(self, html, page, limit=200, prefer_original=True):
        soup = BeautifulSoup(html, 'lxml')
        urls = []
        for tag in soup.select('img, picture source'):
            candidates = []
            for attr in ('srcset', 'data-srcset'):
                for candidate in (tag.get(attr) or '').split(','):
                    parts = candidate.strip().split()
                    if parts:
                        try:
                            score = float(parts[1][:-1]) if len(parts)>1 else 0
                        except ValueError:
                            score = 0
                        candidates.append((score, parts[0]))
            if candidates:
                urls.append((max if prefer_original else min)(candidates)[1])
            else:
                for attr in ('data-original','data-src','data-lazy-src','src'):
                    if tag.get(attr):
                        urls.append(tag[attr]); break
        for tag in soup.select('[style]'):
            urls.extend(re.findall(r'url\([\s\'"]*([^\)\'"\s]+)', tag['style']))
        for tag in soup.select('style'):
            urls.extend(re.findall(r'url\([\s\'"]*([^\)\'"\s]+)',tag.get_text()))
        for tag in soup.select('meta[property="og:image"], meta[name="twitter:image"]'):
            if tag.get('content'):
                urls.append(tag['content'])
        result, seen = [], set()
        for raw in urls:
            url = urldefrag(urljoin(page, raw))[0]
            try:
                validate_url(url)
            except ValueError:
                continue
            if url in seen:
                continue
            seen.add(url)
            name = PurePosixPath(urlsplit(url).path).name or 'image'
            result.append(Media(url, page, name, 'image', name.rpartition('.')[2], source=urlsplit(page).hostname or ''))
            if len(result) >= limit:
                break
        return result

def format_options(formats):
    choices = []
    audios = [f for f in formats if f.get('acodec') not in (None,'none') and f.get('vcodec') == 'none'
              and not f.get('has_drm') and f.get('format_id')]
    for f in formats:
        if f.get('has_drm') or not f.get('format_id'):
            continue
        video = f.get('vcodec') not in (None,'none')
        audio = f.get('acodec') not in (None,'none')
        selector = str(f['format_id'])
        merge = video and not audio
        if merge:
            compatible = [a for a in audios if a.get('ext') == ('m4a' if f.get('ext') == 'mp4' else 'webm')]
            pool = compatible or audios
            if not pool:
                continue
            best = max(pool, key=lambda a: a.get('abr') or a.get('tbr') or 0)
            selector += '+' + str(best['format_id'])
        label = f"{f.get('height') or '未知'}p" if video or f.get('height') else '仅音频' if f.get('vcodec')=='none' and audio else '轨道信息未知（原始格式）'
        label += f" | {f.get('ext','未知')} | {f.get('vcodec','未知')} / {f.get('acodec','未知')} | {f.get('fps') or '未知'} fps"
        label += ' | 合并音轨' if merge else ''
        choices.append((label, selector))
    return choices

class YtDlpExtractor:
    def __init__(self,settings=None):
        self.settings=settings or {}
    def can_handle(self, url):
        return urlsplit(url).scheme in ('http','https')
    def extract(self, url, cancel, cookie_file=''):
        info = run_job({'action':'extract','url':url,'cookie_file':cookie_file,'auto_browser_cookies':self.settings.get('auto_browser_cookies',False),'cookie_browser':self.settings.get('cookie_browser','auto')}, cancel)
        results = []
        for index,entry in enumerate(info.get('entries', [info]),1):
            if not entry:
                continue
            if entry.get('has_drm'):
                raise ValueError('该媒体受 DRM 保护，不支持下载')
            if entry.get('mh_image'):
                image=entry['mh_image']
                results.append(Media(image['url'],url,f"Instagram_{entry.get('id') or info.get('id')}_{index:02d}",
                                     'image','jpg',width=image.get('width') or 0,height=image.get('height') or 0,
                                     thumbnail=image['url'],source='Instagram',identity=str(entry.get('id') or ''),
                                     headers={'Referer':'https://www.instagram.com/'},auth=info.get('mh_auth',{})))
                continue
            formats = entry.get('formats') or []
            if not format_options(formats):
                continue
            kind='audio' if formats and all(f.get('vcodec')=='none' for f in formats) else 'video'
            results.append(Media(entry.get('webpage_url') or url, url, entry.get('title') or 'video',
                                 kind, entry.get('ext') or '', thumbnail=entry.get('thumbnail') or '',
                                 source=entry.get('extractor') or '', duration=entry.get('duration') or 0,
                                 formats=formats, identity=str(entry.get('id') or ''),auth=info.get('mh_auth',{})))
        return results

class ExtractorRegistry:
    def __init__(self, settings):
        self.settings = settings
        self.plugins = [HtmlImageExtractor(), YtDlpExtractor(settings)]
    def analyze(self, url, cancel=None, deep=False, _context=None, _depth=0):
        cancel = cancel or threading.Event()
        validate_url(url)
        context=_context if _context is not None else {'seen':set(),'started':time.monotonic()}
        if cancel.is_set(): raise InterruptedError('解析已取消')
        if _depth>3 or url in context['seen'] or len(context['seen'])>=20:
            return []
        if time.monotonic()-context['started']>30: raise TimeoutError('网页解析超过 30 秒')
        context['seen'].add(url)
        if self.settings.get('cookie_file'):
            from .cookies import scoped_cookies
            try:
                available=len(scoped_cookies(self.settings['cookie_file'],url))
            except ValueError:
                if not self.settings.get('auto_browser_cookies'): raise
                available=0
            if available:
                return self.plugins[1].extract(url,cancel,self.settings['cookie_file'])
        started=context['started']
        with client() as c, c.stream('GET', url) as response:
            if response.is_error:
                # Some video sites reject ordinary HTML requests while their
                # extractor's browser-compatible request handler succeeds.
                return self.plugins[1].extract(url,cancel,self.settings.get('cookie_file',''))
            response.raise_for_status()
            mime = response.headers.get('content-type','').split(';')[0].lower()
            if mime in ('','application/octet-stream','application/ogg','video/ogg','audio/ogg'):
                prefix=next(response.iter_bytes(64*1024),b'')
                mime=sniff_mime(prefix) or mime
            if mime.startswith(('image/','video/','audio/')) and 'mpegurl' not in mime:
                kind = mime.split('/')[0]
                ext = mime.split('/')[1].replace('jpeg','jpg')
                ext={'quicktime':'mov','mpeg':'mp3','x-m4a':'m4a','x-wav':'wav','mp4':'m4a' if kind=='audio' else 'mp4'}.get(ext,ext)
                title = PurePosixPath(urlsplit(str(response.url)).path).name or f'media.{ext}'
                disposition=Message()
                disposition['Content-Disposition']=response.headers.get('content-disposition','')
                filename=disposition.get_filename()
                from .files import safe_name
                title=safe_name(filename or unquote(title))
                suffix=PurePosixPath(title).suffix
                if suffix.lower()!='.'+ext:
                    title=(title[:-len(suffix)] if suffix else title)+'.'+ext
                return [Media(str(response.url), url, title, kind, ext,
                              int(response.headers.get('content-length') or 0), source=urlsplit(url).hostname or '')]
            html = bytearray()
            if 'html' in mime:
                for chunk in response.iter_bytes():
                    if cancel.is_set():
                        raise InterruptedError('解析已取消')
                    if time.monotonic()-started>30:
                        raise TimeoutError('网页解析超过 30 秒')
                    html.extend(chunk)
                    if len(html)>5*1024*1024:
                        raise ValueError('网页超过 5 MB 解析上限')
        page_html=html.decode('utf-8',errors='replace')
        if deep:
            rendered = run_job({'action':'dynamic','url':url}, cancel, timeout=45)
            page_html=rendered['html']
        images = self.plugins[0].extract_html(page_html, url, self.settings['max_images'],self.settings.get('prefer_original',True)) if page_html else []
        soup=BeautifulSoup(page_html,'lxml')
        native=[]
        # Concrete HTML5 sources retain MIME detection, redirect guards and normal
        # stream extraction, including sources inserted by the optional browser.
        for tag in soup.select('video[src], audio[src], video source[src], audio source[src]'):
            candidate=urljoin(url,tag['src'])
            try: validate_url(candidate)
            except ValueError: continue  # blob/private URLs cannot become direct downloads.
            for item in self.analyze(candidate,cancel,_context=context,_depth=_depth+1):
                if item.kind in ('video','audio'):
                    item.page=url; item.headers['Referer']=url; native.append(item)
        if native:
            return list({(item.url,item.kind):item for item in native+images}.values())
        try:
            videos = self.plugins[1].extract(url,cancel)
        except InterruptedError:
            raise
        except Exception as exc:
            from .browser_cookies import login_error
            if login_error(str(exc)):
                raise
            frames=[]
            if 'unsupported url' in str(exc).lower():
                for tag in soup.select('iframe[src]'):
                    candidate=urljoin(url,tag['src'])
                    try: validate_url(candidate)
                    except ValueError: continue
                    frames.extend(self.analyze(candidate,cancel,_context=context,_depth=_depth+1))
            if frames:
                return list({(item.url,item.kind):item for item in frames+images}.values())
            if not images:
                raise
            videos = []
        return videos + images
