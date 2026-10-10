import threading
from io import BytesIO
from dataclasses import asdict
from PIL import Image
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager,HttpBackend
from mediaharvester.models import Media,State
from test_core import wait_for

def test_simultaneous_image_content_dedup(tmp_path,monkeypatch):
    image=Image.new('RGB',(16,16),'blue'); stream=BytesIO(); image.save(stream,'PNG'); content=stream.getvalue()
    barrier=threading.Barrier(2)
    def download(self,task,temp,cancel,update,settings):
        output=temp/'payload.part'; output.write_bytes(content)
        task.downloaded=task.total=len(content); update(); barrier.wait(timeout=5)
        return output
    monkeypatch.setattr(HttpBackend,'download',download)
    repo=Repository(tmp_path/'db'); settings=Settings.defaults.copy(); settings['directory']=str(tmp_path)
    manager=DownloadManager(repo,settings)
    tasks=[manager.add(asdict(Media(f'https://example.com/image?q={i}','https://example.com',f'image{i}.png','image','png'))) for i in range(2)]
    try:
        wait_for(lambda:all(t.state==State.COMPLETED for t in tasks))
        assert tasks[0].final==tasks[1].final
        assert len(list(tmp_path.glob('*.png')))==1
    finally: manager.close(); repo.close()

def test_retry_is_bounded_and_progress_saved(tmp_path,monkeypatch):
    attempts=[]
    def fail(self,task,temp,cancel,update,settings):
        task.downloaded=123; update(); attempts.append(task.id)
        raise OSError('temporary network outage')
    monkeypatch.setattr(HttpBackend,'download',fail)
    repo=Repository(tmp_path/'db'); settings=Settings.defaults.copy(); settings.update(directory=str(tmp_path),retries=1,retry_delay=1)
    manager=DownloadManager(repo,settings)
    task=manager.add(asdict(Media('https://example.com/a','https://example.com','a.png','image','png')))
    try:
        wait_for(lambda:task.state==State.FAILED)
        assert len(attempts)==2 and task.attempts==2 and repo.all()[0].downloaded==123
    finally: manager.close(); repo.close()
