"""Discover standard Windows browser profiles; never inspect password stores."""
import os
from pathlib import Path
from http.cookiejar import MozillaCookieJar
from .cookies import filter_cookies


def browser_profiles(preferred='auto', local=None, roaming=None):
    local=Path(local or os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    roaming=Path(roaming or os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))
    roots=[('chrome',local/'Google/Chrome/User Data'),
           ('edge',local/'Microsoft/Edge/User Data'),
           ('brave',local/'BraveSoftware/Brave-Browser/User Data'),
           ('vivaldi',local/'Vivaldi/User Data'),
           ('firefox',roaming/'Mozilla/Firefox/Profiles')]
    profiles=[]
    for browser,root in roots:
        if preferred not in ('auto',browser) or not root.is_dir():
            continue
        try:
            for profile in root.iterdir():
                if not profile.is_dir(): continue
                if browser!='firefox' and profile.name!='Default' and not profile.name.startswith('Profile '): continue
                databases=[profile/'cookies.sqlite'] if browser=='firefox' else [profile/'Network/Cookies',profile/'Cookies']
                database=next((p for p in databases if p.is_file()),None)
                if database:
                    profiles.append((database.stat().st_mtime,{'browser':browser,'profile':str(profile)}))
        except OSError:
            continue
    return [p for _,p in sorted(profiles,key=lambda pair:pair[0],reverse=True)[:16]]


def scoped_browser_cookies(source,url,logger):
    from yt_dlp.cookies import extract_cookies_from_browser
    if source.get('browser') not in ('chrome','edge','firefox','brave','vivaldi'):
        raise ValueError('不支持的浏览器')
    try:
        original=extract_cookies_from_browser(source['browser'],source['profile'],logger=logger)
    except Exception:
        raise ValueError('浏览器 Cookie 无法读取：可能被占用或受系统加密保护；请正常退出浏览器后重试，或手动导入 Cookie') from None
    jar=filter_cookies(original,url)
    if not len(jar):
        raise ValueError('该浏览器中没有此网站可读取的有效 Cookie：请确认已登录；也可能受系统加密保护')
    return jar


def login_error(message):
    message=message.lower()
    return any(text in message for text in (
        'login required','login_required','log in','logged-in','sign in',
        'registered users','requires authentication','cookies for the authentication',
        '需要登录','登录状态','登录后'))
