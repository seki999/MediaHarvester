"""Bounded browser rendering in the isolated media worker."""
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit, urldefrag

from .security import validate_url


def browser_options():
    # PyInstaller places the optional browser alongside its other runtime data.
    bundled=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'ms-playwright'
    if bundled.is_dir():
        os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(bundled)
    options={}
    if not getattr(sys,'frozen',False) and sys.platform.startswith('linux'):
        # Useful on Linux development machines with distro-managed Chromium.
        system=shutil.which('chromium') or shutil.which('chromium-browser')
        if system: options['executable_path']=system
    return options


def render_page(job,proxy):
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise RuntimeError('深度解析需要 Playwright。源码版请安装 requirements-optional.txt 并运行 python -m playwright install chromium；EXE 请使用包含深度解析的新版。') from None
    options=browser_options()
    with sync_playwright() as p:
        try:
            browser=p.chromium.launch(headless=True,proxy=proxy.browser,**options,
                args=['--disable-quic','--proxy-bypass-list=<-loopback>',
                      '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'])
        except Exception:
            raise RuntimeError('深度解析浏览器无法启动。源码版请运行 python -m playwright install chromium 并检查系统依赖；EXE 请重新解压包含浏览器的完整发行包。') from None
        try:
            context=browser.new_context(service_workers='block',accept_downloads=False)
            context.set_default_timeout(5000)
            if job.get('cookie_file'):
                from .cookies import scoped_cookies
                cookies=[]
                for cookie in scoped_cookies(job['cookie_file'],job['url']):
                    entry=dict(name=cookie.name,value=cookie.value,secure=cookie.secure,
                               httpOnly=cookie.has_nonstandard_attr('HttpOnly'))
                    if cookie.domain_specified:
                        entry.update(domain=cookie.domain,path=cookie.path or '/')
                    else:
                        entry['url']=urlsplit(job['url']).scheme+'://'+cookie.domain+(cookie.path or '/')
                    if cookie.expires: entry['expires']=cookie.expires
                    cookies.append(entry)
                context.add_cookies(cookies)
            requests=0
            def route_request(route):
                nonlocal requests
                requests+=1
                try:
                    if requests>1000: raise ValueError('Request limit')
                    validate_url(route.request.url)
                    route.continue_()
                except Exception:
                    route.abort()
            # Context routes also cover frames and popups; no service-worker bypass.
            context.route('**/*',route_request)
            context.route_web_socket('**/*',lambda socket:socket.close())
            media=[]; seen=set()
            def remember(url,kind,mime=''):
                url=urldefrag(url)[0]
                try: validate_url(url)
                except ValueError: return
                if url not in seen and len(media)<500:
                    seen.add(url); media.append(dict(url=url,kind=kind,mime=mime))
            def response_received(response):
                mime=response.headers.get('content-type','').split(';')[0].lower()
                path=urlsplit(response.url).path.lower()
                if not response.ok: return
                if 'mpegurl' in mime or 'dash+xml' in mime or path.endswith(('.m3u8','.mpd')):
                    remember(response.url,'stream',mime)
                elif mime.startswith(('video/','audio/')) and mime!='video/mp2t' and not path.endswith(('.ts','.m4s')):
                    remember(response.url,mime.split('/')[0],mime)
            context.on('response',response_received)
            page=context.new_page()
            try:
                response=page.goto(job['url'],timeout=20000,wait_until='domcontentloaded')
            except Error:
                # Browsers abort navigations which become file downloads.
                if media:
                    return dict(html='',url=job['url'],base=job['url'],title='',media=media)
                raise
            if response and response.status>=400:
                raise ValueError(f'深度解析网页返回 HTTP {response.status}，请检查访问权限或先应用 Cookie')
            validate_url(page.url)
            for _ in range(5):
                page.evaluate('window.scrollBy(0, window.innerHeight)')
                page.wait_for_timeout(500)
            # currentSrc resolves JS-selected sources; computed styles include external CSS.
            sources=page.evaluate('''() => {
                const found=[];
                for (const el of Array.from(document.querySelectorAll('video,audio,video source,audio source,img')).slice(0,500)) {
                    const kind=el.tagName==='IMG'?'image':(el.closest('audio')?'audio':'video');
                    if(kind==='image' && ['srcset','data-srcset','data-original','data-src','data-lazy-src'].some(a=>el.hasAttribute(a))) continue;
                    const url=el.currentSrc || el.src;
                    if(url) found.push({url,kind});
                }
                for (const el of Array.from(document.querySelectorAll('*')).slice(0,2000)) {
                    const bg=getComputedStyle(el).backgroundImage;
                    for(const match of bg.matchAll(/url\\(["']?(.*?)["']?\\)/g))
                        found.push({url:new URL(match[1],document.baseURI).href,kind:'image'});
                }
                return found.slice(0,500);
            }''')
            for source in sources:
                kind=source['kind']
                if urlsplit(source['url']).path.lower().endswith(('.m3u8','.mpd')): kind='stream'
                remember(source['url'],kind)
            html=page.content()
            if len(html.encode('utf-8'))>5*1024*1024:
                raise ValueError('渲染后的网页超过 5 MB 解析上限')
            base=page.evaluate('document.baseURI')
            validate_url(base)
            return dict(html=html,url=page.url,base=base,title=page.title(),media=media)
        finally:
            browser.close()
