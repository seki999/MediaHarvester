"""Real Qt workflow with only test-scoped loopback networking; no user database."""
import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest
from mediaharvester.config import Settings,executable
from mediaharvester.database import Repository
from mediaharvester.download import DownloadManager
from mediaharvester.models import State, Media
from dataclasses import asdict
from mediaharvester.ui import Window
from test_server.main import TestServer
from test_server.media_generator import generate
from test_server.engine_runner import install


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'reports/gui')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    app=QApplication([])
    results=[]
    with tempfile.TemporaryDirectory(prefix='mh-gui-test-') as directory:
        root=Path(directory);generate(root/'media')
        with TestServer(root/'media') as server:
            install(server.url)
            import mediaharvester.extractors as extraction
            import mediaharvester.download as downloads
            import mediaharvester.security as security
            import mediaharvester.ui as ui
            extraction.validate_url=security.validate_url
            extraction.client=downloads.client=ui.client=security.client
            downloads.executable=lambda name:None if name=='aria2c' else executable(name)
            settings=Settings(root/'settings.json');settings.values.update(directory=str(root/'downloads'),auto_browser_cookies=False,notify=False,rate=0)
            repo=Repository(root/'tasks.db');manager=DownloadManager(repo,settings.values)
            window=Window(manager,settings);window.show();window.nav.setCurrentRow(1)
            def wait(predicate,timeout=25):
                end=time.monotonic()+timeout
                while not predicate():
                    if time.monotonic()>end:raise AssertionError('GUI deadline exceeded')
                    QTest.qWait(30)
            try:
                window.urls.setPlainText(server.url+'/video/direct.mp4\n'+server.url+'/image.png')
                button=next(b for b in window.findChildren(QPushButton) if b.text()=='解析 / 重新解析')
                QTest.mouseClick(button,Qt.MouseButton.LeftButton);wait(lambda:not window.busy)
                assert len(window.media)==2
                results.append('多行输入、后台真实解析、视频/图片分类')
                window.select_results(True)
                button=next(b for b in window.findChildren(QPushButton) if b.text()=='下载选中媒体')
                QTest.mouseClick(button,Qt.MouseButton.LeftButton)
                wait(lambda:len(manager.tasks)==2 and all(t.state==State.COMPLETED for t in manager.tasks.values()))
                assert len({t.digest for t in manager.tasks.values()})==2
                results.append('界面选中下载、实际下载、轨道/图片验证、数据库完成状态')
                window.nav.setCurrentRow(5);window.refresh()
                assert window.tasks.rowCount()==2
                QTest.qWait(80)  # Let Qt dispose replaced progress widgets and paint the completed view.
                window.grab().save(str(args.output/'workflow.png'))
                for index in range(8):window.nav.setCurrentRow(index)
                window.settings.values['language']='en_US';window.settings.values['theme']='light';window.apply_theme()
                assert window.nav.item(0).text()=='Home'
                window.settings.values['language']='zh_CN';window.settings.values['theme']='dark';window.apply_theme()
                window.settings.save();assert Settings(settings.path).values['theme']=='dark'
                results.append('任务历史、全部导航、主题、英文控件、设置持久化')
                settings.values['rate']=1024*1024
                task=manager.add(asdict(Media(server.url+'/binary/slow?size=10485760','','pause.bin','audio','bin')))
                wait(lambda:task.downloaded>=65536)
                window.nav.setCurrentRow(4);window.refresh();window.tasks.selectRow(0)
                window.task_action('pause');wait(lambda:task.state==State.PAUSED and task.id not in manager.running)
                assert 0<task.downloaded<10*1024*1024
                window.refresh();window.tasks.selectRow(0);window.task_action('resume')
                wait(lambda:task.state==State.DOWNLOADING)
                manager.cancel(task.id);wait(lambda:task.state==State.CANCELLED and task.id not in manager.running)
                results.append('真实慢速下载进度、界面暂停/继续、取消持久化')
                window.close();wait(lambda:window.closed)
                results.append('真实窗口正常关闭、任务保存、托盘关闭')
            finally:
                if not window.closed:
                    window.close();wait(lambda:window.closed)
    (args.output/'result.json').write_text(json.dumps({'status':'PASS','platform':app.platformName(),'checks':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Real Qt workflow PASS: '+app.platformName())


if __name__=='__main__':main()
