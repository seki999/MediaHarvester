import sqlite3
import threading
import time
import pytest
from mediaharvester.browser_cookies import browser_profiles,scoped_browser_cookies
from mediaharvester.worker import QuietLogger,run_job


def test_discover_profiles_without_searching_other_files(tmp_path):
    local=tmp_path/'local'; roaming=tmp_path/'roaming'
    for name in ('Default','Profile 2','unrelated'):
        path=local/'Google/Chrome/User Data'/name/'Network/Cookies'
        path.parent.mkdir(parents=True);path.touch()
    result=browser_profiles(local=local,roaming=roaming)
    assert len(result)==2
    assert all(p['browser']=='chrome' for p in result)
    assert browser_profiles('edge',local,roaming)==[]


def test_real_firefox_database_is_read_only_and_site_scoped(tmp_path):
    path=tmp_path/'cookies.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE moz_cookies(host TEXT,name TEXT,value TEXT,path TEXT,expiry INTEGER,isSecure INTEGER)')
        db.executemany('INSERT INTO moz_cookies VALUES (?,?,?,?,?,?)',[
            ('.example.com','session','test-secret','/',int(time.time())+3600,1),
            ('.unrelated.com','session','unrelated-secret','/',int(time.time())+3600,1)])
    before=path.read_bytes()
    jar=scoped_browser_cookies({'browser':'firefox','profile':str(tmp_path)},'https://example.com/',QuietLogger())
    assert len(jar)==1 and next(iter(jar)).domain=='.example.com'
    assert path.read_bytes()==before


def test_authentication_retry_and_remember_browser(monkeypatch):
    source={'browser':'firefox','profile':'test-profile'}
    calls=[]
    def worker(job,*args):
        calls.append(job)
        if not job.get('browser_cookie'):raise RuntimeError('login required')
        return {'id':'123'}
    monkeypatch.setattr('mediaharvester.worker._run_job',worker)
    monkeypatch.setattr('mediaharvester.browser_cookies.browser_profiles',lambda *args:[source])
    result=run_job({'action':'extract','url':'https://example.com/','auto_browser_cookies':True},threading.Event())
    assert result['mh_auth']==source and len(calls)==2


def test_missing_manual_export_does_not_block_auto(monkeypatch,tmp_path):
    captured=[]
    monkeypatch.setattr('mediaharvester.worker._run_job',lambda job,*a:captured.append(job) or {'id':'public'})
    run_job({'action':'extract','url':'https://example.com/','cookie_file':str(tmp_path/'missing.txt'),
             'auto_browser_cookies':True},threading.Event())
    assert captured[0]['cookie_file']==''


@pytest.mark.parametrize('enabled,error',[(False,'login required'),(True,'HTTP Error 410')])
def test_no_browser_read_without_login_failure(monkeypatch,enabled,error):
    def worker(*args):raise RuntimeError(error)
    def profiles(*args):raise AssertionError('Unexpected cookie discovery')
    monkeypatch.setattr('mediaharvester.worker._run_job',worker)
    monkeypatch.setattr('mediaharvester.browser_cookies.browser_profiles',profiles)
    with pytest.raises(RuntimeError,match=error):
        run_job({'action':'extract','auto_browser_cookies':enabled},threading.Event())
