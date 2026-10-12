"""Reproducible test modes with bounded commands and persistent sanitized evidence."""
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.run_online_tests import sanitize
from mediaharvester.config import executable


def run(name,argv,timeout=600,env=None):
    started=time.monotonic()
    print(f'Running {name}',flush=True)
    output=ROOT/'reports'/f'{name}.txt'
    task_env=dict(os.environ,PYTHONUTF8='1',**(env or {}))
    process=subprocess.Popen(argv,cwd=ROOT,env=task_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    from mediaharvester.processes import attach_job,release_job
    from mediaharvester.worker import kill_tree
    attach_job(process)
    try:
        try:
            raw,_=process.communicate(timeout=timeout)
            text=raw.decode('utf-8',errors='replace')
            status='PASS' if process.returncode==0 else 'FAIL'
        except subprocess.TimeoutExpired:
            kill_tree(process);raw,_=process.communicate()
            text=raw.decode('utf-8',errors='replace')+'\nBounded command timeout'
            status='FAIL'
    finally:release_job(process)
    output.write_text(sanitize_full(text),encoding='utf-8')
    print(f'{name}: {status} ({time.monotonic()-started:.1f}s)',flush=True)
    return {'id':name,'status':status,'command':subprocess.list2cmdline(argv),'seconds':round(time.monotonic()-started,3),'log':str(output.relative_to(ROOT))}


def sanitize_full(text):
    # Preserve complete stack traces, while removing credential header lines.
    import re
    text=re.sub(r'(?im)\b(cookie|authorization|set-cookie|proxy-authorization)\s*[:=][^\r\n]+',r'\1: [REDACTED]',text)
    return re.sub(r'(https?://[^\s?]+)\?[^\s]+',r'\1?[REDACTED]',text)


def environment():
    packages={}
    for name in ('PySide6','yt-dlp','httpx','curl-cffi','playwright','pytest','pyinstaller','ruff'):
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]='MISSING'
    tools={}
    for name in ('ffmpeg','ffprobe','aria2c'):
        binary=executable(name)
        tools[name]={'path':binary}
        if binary:
            p=subprocess.run([binary,'--version' if name=='aria2c' else '-version'],capture_output=True,text=True,timeout=10)
            tools[name]['version']=p.stdout.splitlines()[0] if p.stdout else 'UNKNOWN'
    return {'date':datetime.now(timezone(timedelta(hours=9))).isoformat(),'timezone':'Asia/Tokyo','python':sys.version,
            'os':platform.platform(),'packages':packages,'tools':tools,
            'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['offline','online','full','stress'],default=None,
                        help='Omit for offline regression plus small online smoke')
    parser.add_argument('--build',action='store_true',help='Build both EXE variants and run smoke in full mode')
    args=parser.parse_args()
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    manifest={'mode':args.mode or 'offline + online smoke','environment':environment(),'commands':[]}
    def record(result):
        manifest['commands'].append(result)
        (reports/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.mode in (None,'offline','full'):
        record(run('offline',[sys.executable,'-m','pytest','-q','--junitxml=reports/offline.xml'],600,
                   {'QT_QPA_PLATFORM':'offscreen'} if os.name!='nt' else None))
        record(run('static',[sys.executable,'-m','ruff','check','--select','E9,F63,F7,F82','mediaharvester','scripts','test_server','tests']))
    if args.mode=='stress':
        record(run('stress',[sys.executable,'-m','pytest','tests/integration/test_resume.py','--stress','-q','--junitxml=reports/stress.xml'],180))
    if args.mode in (None,'online','full'):
        argv=[sys.executable,'scripts/run_online_tests.py']
        if args.mode in ('online','full'):argv.append('--sites')
        record(run('online',argv,900))
    if args.mode=='full':
        record(run('gui',[sys.executable,'scripts/gui_workflow.py'],60,
                   {'QT_QPA_PLATFORM':'offscreen'} if os.name!='nt' else None))
        if args.build:
            if os.name!='nt':record({'id':'exe','status':'SKIPPED','reason':'Windows EXE builds require Windows'})
            else:
                for kind,flag in [('onedir','0'),('onefile','1')]:
                    result=run('build-'+kind,[sys.executable,'-m','PyInstaller','--noconfirm','--distpath',f'dist/validation-{kind}','mediaharvester.spec'],600,{'MH_ONEFILE':flag})
                    record(result)
                    if result['status']=='PASS':
                        path=f'dist/validation-{kind}/'+('MediaHarvester/MediaHarvester.exe' if kind=='onedir' else 'MediaHarvester.exe')
                        record(run('exe-'+kind,[sys.executable,'scripts/exe_smoke.py',path,'--output',f'reports/exe-{kind}'],300))
    from scripts.generate_test_report import generate
    generate(reports)
    return int(any(r['status']=='FAIL' for r in manifest['commands']))


if __name__=='__main__':sys.exit(main())
