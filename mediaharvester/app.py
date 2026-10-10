import logging
import sys
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import QApplication
from .config import DATA, Settings
from .database import Repository
from .download import DownloadManager
from .ui import Window

def main():
    handler=RotatingFileHandler(DATA/'app.log',maxBytes=2*1024*1024,backupCount=3,encoding='utf-8')
    logging.basicConfig(level=logging.WARNING,handlers=[handler],format='%(asctime)s %(levelname)s %(name)s %(message)s')
    app=QApplication(sys.argv)
    app.setApplicationName('MediaHarvester'); app.setOrganizationName('MediaHarvester')
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QMessageBox
    lock=QLockFile(str(DATA/'app.lock'))
    if not lock.tryLock(0):
        QMessageBox.information(None,'MediaHarvester','程序已运行，请使用已打开的窗口。')
        return
    settings=Settings(); repo=Repository(DATA/'tasks.sqlite3')
    manager=DownloadManager(repo,settings.values)
    window=Window(manager,settings); window.show()
    if '--smoke-output' in sys.argv:
        from PySide6.QtCore import QTimer
        from pathlib import Path
        output=Path(sys.argv[sys.argv.index('--smoke-output')+1]); output.mkdir(parents=True,exist_ok=True)
        def capture():
            window.nav.setCurrentRow(1)
            window.grab().save(str(output/'gui.png'))
            (output/'ok.txt').write_text('GUI booted; closing normally','utf-8')
            window.close()
        QTimer.singleShot(1200,capture)
    sys.exit(app.exec())
