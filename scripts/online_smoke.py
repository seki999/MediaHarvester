"""Explicit opt-in public media integration; does not modify user task database."""
import sys
import tempfile
import threading
import subprocess
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mediaharvester.config import Settings,executable
from mediaharvester.extractors import ExtractorRegistry,YtDlpExtractor,format_options
from mediaharvester.download import DownloadManager
from mediaharvester.database import Repository
from mediaharvester.worker import run_job
from tests.test_core import wait_for

if __name__=='__main__':
    url='https://media.w3.org/2010/05/sintel/trailer.mp4'
    with tempfile.TemporaryDirectory() as directory:
        settings=Settings.defaults.copy(); settings['directory']=directory
        results=ExtractorRegistry(settings).analyze(url)
        assert results and results[0].kind=='video'
        print('Real public MP4 detection passed')
        repo=Repository(Path(directory)/'db'); manager=DownloadManager(repo,settings)
        try:
            task=manager.add(asdict(results[0]))
            wait_for(lambda:task.state in ('COMPLETED','FAILED'),timeout=120)
            assert task.state=='COMPLETED',task.error
            print(f'Real {task.engine} download passed: {task.downloaded} bytes')
            ffprobe=executable('ffprobe')
            if ffprobe:
                result=subprocess.run([ffprobe,'-v','error','-show_entries','stream=codec_type','-of','json',task.final],capture_output=True,text=True,check=True)
                print('FFprobe verified downloaded media:',result.stdout.strip())
        finally:
            manager.close(); repo.close()
        videos=YtDlpExtractor().extract(url,threading.Event())
        assert videos and format_options(videos[0].formats)
        print('Real yt-dlp Python API extraction passed')
        images=ExtractorRegistry(settings).analyze('https://www.python.org/')
        images=[image for image in images if image.kind=='image']
        assert images
        repo=Repository(Path(directory)/'images.db'); manager=DownloadManager(repo,settings)
        try:
            image_tasks=[manager.add(asdict(image)) for image in images]
            wait_for(lambda:all(task.state in ('COMPLETED','FAILED') for task in image_tasks),timeout=90)
            assert all(task.state=='COMPLETED' for task in image_tasks),[task.error for task in image_tasks]
            print(f'Real HTML image extraction and batch download passed: {len(image_tasks)} images')
        finally: manager.close(); repo.close()
        selector=format_options(videos[0].formats)[0][1]
        output=Path(directory)/'yt'; output.mkdir()
        result=run_job(dict(action='download',url=url,selector=selector,identity=videos[0].identity,temp=str(output)),threading.Event(),timeout=120)
        assert len(result['files'])==1 and Path(result['files'][0]).stat().st_size==4372373
        print('Real yt-dlp download passed')
        if ffprobe:
            converted=Path(directory)/'audio'; converted.mkdir()
            result=run_job(dict(action='download',url=url,selector=selector,identity=videos[0].identity,temp=str(converted),audio='mp3'),threading.Event(),timeout=120)
            assert len(result['files'])==1 and result['files'][0].endswith('.mp3')
            subprocess.run([ffprobe,'-v','error',result['files'][0]],check=True)
            print('Real FFmpeg MP3 conversion passed')
