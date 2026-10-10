"""Verify real yt-dlp/FFmpeg merge using two format fixtures backed by public media.

This checks the pipeline with controlled metadata, not a real site's split formats.
"""
import sys
import json
import tempfile
import threading
import subprocess
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mediaharvester.worker import run_job,worker_main
from mediaharvester.config import executable
import yt_dlp

url='https://media.w3.org/2010/05/sintel/trailer.mp4'
info=run_job({'action':'extract','url':url},threading.Event())
video=deepcopy(info['formats'][0]); video.update(format_id='v',vcodec='h264',acodec='none',ext='mp4')
audio=deepcopy(info['formats'][0]); audio.update(format_id='a',vcodec='none',acodec='aac',ext='m4a')
info['formats']=[video,audio]
with tempfile.TemporaryDirectory() as directory:
    temp=Path(directory)
    request,result,events=[temp/n for n in ('request.json','result.json','events.jsonl')]
    request.write_text(json.dumps({'action':'download','url':url,'selector':'v+a','identity':str(info['id']),'temp':directory,'container':'mkv'}),'utf-8')
    with patch.object(yt_dlp.YoutubeDL,'extract_info',return_value=info),patch.object(sys,'argv',['worker',str(request),str(result),str(events)]):
        worker_main()
    output=json.loads(result.read_text('utf-8')); assert 'error' not in output,output
    assert len(output['files'])==1,output
    probe=subprocess.run([executable('ffprobe'),'-v','error','-show_entries','stream=codec_type','-of','json',output['files'][0]],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams']
    assert {stream['codec_type'] for stream in streams}=={'video','audio'}
    phases=[json.loads(line) for line in events.read_text('utf-8').splitlines()]
    assert any(phase['state']=='MERGING' for phase in phases)
    print('Real two-input yt-dlp / FFmpeg merge passed with controlled format metadata; output has video and audio')
