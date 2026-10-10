"""Read user-selected Netscape cookies without modifying their original file."""
from http.cookiejar import MozillaCookieJar, LoadError, Cookie
from pathlib import Path
from urllib.parse import urlsplit
import os
import re


def save_pasted_cookie(text,url,destination):
    """Convert a browser Cookie request header to a site-scoped local file."""
    from .security import validate_url
    validate_url(url)
    parts=urlsplit(url)
    if parts.scheme!='https':
        raise ValueError('请先输入该网站的 HTTPS 地址，再应用登录 Cookie')
    text=text.strip()
    if text.lower().startswith('cookie:'): text=text[7:].strip()
    if not text or len(text)>131072 or any(ord(c)<32 or ord(c)==127 for c in text):
        raise ValueError('请粘贴完整的一行 Cookie 请求头，内容不能包含换行')
    pairs=[]
    for part in text.split(';'):
        if not part.strip(): continue
        name,separator,value=part.strip().partition('=')
        if not separator or not re.fullmatch(r"[!#$%&'*+\-.^_`|~0-9a-zA-Z]+",name) or name.startswith('$'):
            raise ValueError('Cookie 格式不正确，请复制整行 name=value; name=value 内容')
        pairs.append((name,value.strip()))
    if not pairs or len(pairs)>200:
        raise ValueError('Cookie 内容为空或条目过多')
    host=parts.hostname.lower()
    # Instagram's authorized media API also uses i.instagram.com.
    domain='.instagram.com' if host=='instagram.com' or host.endswith('.instagram.com') else host
    target=Path(destination)
    target.parent.mkdir(parents=True,exist_ok=True)
    jar=MozillaCookieJar(str(target))
    if target.exists():
        try: jar.load(ignore_discard=True,ignore_expires=False)
        except (LoadError,OSError,ValueError):
            raise ValueError('本地 Cookie 保存文件无法读取，请通过设置选择新的 Cookie 文件') from None
    # Replace this site's entire previous header, including removed cookies.
    for old in list(jar):
        if old.domain==domain: jar.clear(old.domain,old.path,old.name)
    for name,value in pairs:
        jar.set_cookie(Cookie(0,name,value,None,False,domain,domain.startswith('.'),
                              domain.startswith('.'),'/',True,True,None,True,None,None,{}))
    temporary=target.with_suffix('.tmp')
    jar.filename=str(temporary)
    jar.save(ignore_discard=True,ignore_expires=False)
    os.replace(temporary,target)
    return host


def scoped_cookies(path, url):
    jar = MozillaCookieJar()
    if not path:
        return jar
    source = Path(path)
    if not source.is_file() or source.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('Cookie 文件不存在或超过 5 MB')
    original = MozillaCookieJar(str(source))
    try:
        original.load(ignore_discard=True, ignore_expires=True)
    except (LoadError, OSError, ValueError):
        raise ValueError('Cookie 文件无法读取，请导出 Netscape 格式') from None
    return filter_cookies(original,url)


def filter_cookies(original,url):
    jar=MozillaCookieJar()
    host = urlsplit(url).hostname.lower()
    for cookie in original:
        # Browser exporters use zero for cookies valid for the browser session.
        if cookie.expires == 0:
            cookie.expires = None
            cookie.discard = True
        if cookie.is_expired():
            continue
        domain = cookie.domain.lstrip('.').lower()
        matches = host == domain or (cookie.domain_specified and host.endswith('.' + domain))
        if matches and (not cookie.secure or urlsplit(url).scheme == 'https'):
            jar.set_cookie(cookie)
    return jar


def remove_secrets(value):
    if isinstance(value, dict):
        return {k: remove_secrets(v) for k, v in value.items()
                if k.lower() not in ('cookie', 'cookies', 'authorization', 'proxy-authorization', 'set-cookie')}
    if isinstance(value, list):
        return [remove_secrets(v) for v in value]
    return value
