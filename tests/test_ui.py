from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from mediaharvester.config import Settings
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.ui import Window
from mediaharvester.models import Media
from dataclasses import asdict
import pytest
from PySide6.QtCore import Qt

@pytest.mark.parametrize('fail_image',[False,True])
def test_enqueue_removes_only_successful_results(tmp_path,monkeypatch,fail_image):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    app=QApplication.instance() or QApplication([])
    settings=Settings(tmp_path/'settings.json')
    repo=Repository(tmp_path/'db'); manager=DownloadManager(repo,settings.values)
    window=Window(manager,settings)
    monkeypatch.setattr(window,'fetch_thumbnail',lambda *args:None)
    video=Media('https://example.com/v.mp4','','Video','video','mp4')
    image=Media('https://example.com/i.png','','Image','image','png')
    keep=Media('https://example.com/keep.mp4','','Keep','video','mp4')
    window.media=[video,image,keep]; window.populate_results()
    # Populate the gallery without making network requests.
    window.show_thumbnail(1,b'',(window.generation,100,200,1000))
    old_generation=window.generation
    window.results.cellWidget(2,6).setCurrentIndex(2)
    window.results.item(0,0).setCheckState(Qt.CheckState.Checked)
    window.results.item(1,0).setCheckState(Qt.CheckState.Checked)
    added=[]
    def add(media,*args):
        if fail_image and media['kind']=='image': raise OSError('database failure')
        added.append(media)
    monkeypatch.setattr(manager,'add',add)
    try:
        window.enqueue()
        assert [m['title'] for m in added]==(['Video'] if fail_image else ['Video','Image'])
        assert window.media==([image,keep] if fail_image else [keep])
        assert window.results.rowCount()==len(window.media)
        assert window.results.cellWidget(len(window.media)-1,6).currentText()=='m4a'
        assert window.gallery.count()==int(fail_image)
        if fail_image:
            assert window.gallery.item(0).data(Qt.ItemDataRole.UserRole)==0
            assert window.results.item(0,0).checkState()==Qt.CheckState.Checked
        # An old thumbnail must not update a different media after row removal.
        window.show_thumbnail(0,b'',(old_generation,999,999,999))
        assert keep.width==0
        window.sort_results()
        assert video not in window.media
        window.filter_results()
        assert window.results.rowCount()==len(window.media)
    finally:
        window.close()
        QTimer.singleShot(5000,app.quit)
        app.exec()
        assert window.closed

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
