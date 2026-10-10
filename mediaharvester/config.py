import json
import os
import shutil
import sys
from pathlib import Path

DATA = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'MediaHarvester'
DATA.mkdir(parents=True, exist_ok=True)

def executable(name: str) -> str | None:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    bundled = root / 'tools' / (name + '.exe')
    return str(bundled) if bundled.exists() else shutil.which(name)

class Settings:
    defaults = dict(directory=str(Path.home() / 'Downloads' / 'MediaHarvester'), concurrency=3,
                    connections=4, rate=0, retries=4, retry_delay=2, auto_resume=False,
                    notify=True, theme='dark', language='zh_CN', max_images=200,
                    deduplicate=True, subtitles=False, thumbnail=False)
    defaults.update(default_quality='best',container='mp4',prefer_mp4=True,auto_merge=True,
                    image_width=0,image_height=0,prefer_original=True,naming='title',cookie_file='',auto_browser_cookies=True,cookie_browser='auto')
    def __init__(self, path=DATA / 'settings.json'):
        self.path = Path(path)
        self.values = self.defaults.copy()
        if self.path.exists():
            try:
                self.values.update(json.loads(self.path.read_text('utf-8')))
            except (ValueError, OSError):
                pass
        for key,minimum,maximum in [('concurrency',1,16),('connections',1,16),('retries',0,20),
                                    ('retry_delay',1,60),('max_images',1,2000),('rate',0,1000000000)]:
            try: self.values[key]=min(maximum,max(minimum,int(self.values[key])))
            except (ValueError,TypeError): self.values[key]=self.defaults[key]
    def save(self):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), 'utf-8')
        os.replace(temp, self.path)
