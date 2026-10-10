from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.ui import Window
from mediaharvester.models import Media
from dataclasses import asdict

def test_gui_workflow(tmp_path,monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    app=QApplication.instance() or QApplication([])
    settings=Settings(tmp_path/'settings.json'); settings.values['directory']=str(tmp_path)
    repo=Repository(tmp_path/'db'); manager=DownloadManager(repo,settings.values)
    window=Window(manager,settings)
    media=Media('https://example.com/image.png','https://example.com','Image','image','png',1000,100,200)
    window.media=[media]; window.populate_results(); window.select_results(True)
    assert window.results.item(0,0).checkState().value==2
    window.min_width.setValue(200); assert window.results.isRowHidden(0)
    window.min_width.setValue(0); assert not window.results.isRowHidden(0)
    window.nav.setCurrentRow(4); window.refresh()
    task=manager.add(asdict(media)); manager.pause(task.id); window.refresh()
    assert window.tasks.rowCount()==1
    for index in range(8): window.nav.setCurrentRow(index)
    window.close()
    QTimer.singleShot(5000,app.quit)
    app.exec()
    assert window.closed
