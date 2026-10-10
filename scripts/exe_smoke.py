"""Launch the EXE directly with Python removed from PATH; test frozen worker too."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('exe')
args=parser.parse_args()
exe=Path(args.exe).resolve()
env=os.environ.copy(); env['PATH']=str(Path(os.environ.get('SYSTEMROOT','C:/Windows'))/'System32')
with tempfile.TemporaryDirectory(prefix='mh-exe-smoke-') as directory:
    temp=Path(directory); env['LOCALAPPDATA']=str(temp/'local')
    completed=subprocess.run([str(exe),'--smoke-output',str(temp/'ui')],env=env,timeout=45)
    if (temp/'ui'/'fatal.txt').exists(): raise RuntimeError((temp/'ui'/'fatal.txt').read_text('utf-8'))
    assert completed.returncode==0 and (temp/'ui'/'ok.txt').exists()
    snapshot=Path(__file__).resolve().parents[1]/'docs'/'screenshots'/exe.parent.name
    snapshot.mkdir(parents=True,exist_ok=True)
    import shutil
    shutil.copyfile(temp/'ui'/'gui.png',snapshot/'gui.png')
    print('Frozen GUI started without Python on PATH, screenshot captured, normal shutdown passed')
    request,result,events=[temp/n for n in ('request.json','result.json','events.jsonl')]
    request.write_text(json.dumps({'action':'extract','url':'https://media.w3.org/2010/05/sintel/trailer.mp4'}),'utf-8')
    subprocess.run([str(exe),'--worker',str(request),str(result),str(events)],env=env,timeout=90,check=True)
    info=json.loads(result.read_text('utf-8'))
    assert 'error' not in info,info
    assert info.get('formats')
    print('Frozen yt-dlp Python API extracted real public media without Python on PATH')
    output=temp/'download'; output.mkdir()
    request.write_text(json.dumps({'action':'download','url':'https://media.w3.org/2010/05/sintel/trailer.mp4',
                                  'identity':str(info['id']),'selector':str(info['formats'][0]['format_id']),'temp':str(output)}),'utf-8')
    subprocess.run([str(exe),'--worker',str(request),str(result),str(events)],env=env,timeout=120,check=True)
    response=json.loads(result.read_text('utf-8'))
    assert 'error' not in response,response
    assert len(response['files'])==1 and Path(response['files'][0]).stat().st_size==4372373
    print('Frozen yt-dlp downloaded 4372373 bytes without Python on PATH or external tools')
