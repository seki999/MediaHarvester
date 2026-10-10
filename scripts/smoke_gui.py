"""Capture a real Windows Qt window, then close through its normal shutdown path."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.ui import Window

with tempfile.TemporaryDirectory() as directory:
    app=QApplication([])
    settings=Settings(Path(directory)/'settings.json')
    repo=Repository(Path(directory)/'db'); manager=DownloadManager(repo,settings.values)
    window=Window(manager,settings); window.show(); window.nav.setCurrentRow(1)
    def capture():
        output=Path(__file__).resolve().parents[1]/'docs'/'screenshots'
        output.mkdir(parents=True,exist_ok=True)
        window.grab().save(str(output/'main.png'))
        window.close()
    if '--online-preview' in sys.argv:
        window.urls.setPlainText('https://media.w3.org/2010/05/sintel/trailer.mp4\nhttps://www.python.org/')
        window.events.analysis.connect(lambda media,error:QTimer.singleShot(2000,capture))
        window.analyze()
        QTimer.singleShot(45000,window.close)
    else:
        QTimer.singleShot(1500,capture)
        QTimer.singleShot(10000,app.quit)
    app.exec()
    assert window.closed
    print('Windows GUI started, screenshot saved, clean shutdown passed')
