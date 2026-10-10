import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QStackedWidget,
    QPushButton,QPlainTextEdit,QLabel,QTableWidget,QTableWidgetItem,QComboBox,QSpinBox,QLineEdit,
    QCheckBox,QFormLayout,QFileDialog,QHeaderView,QAbstractItemView,QProgressBar,QSystemTrayIcon,
    QListWidgetItem,QMessageBox,QScrollArea)
from .extractors import ExtractorRegistry,format_options
from .models import State
from .config import DATA, executable
from .security import client

log=logging.getLogger(__name__)
NAV=['首页','URL 解析','视频下载','图片下载','下载任务','已完成','下载历史','设置']
EN=['Home','Analyze URLs','Videos','Images','Downloads','Completed','History','Settings']

def size(value):
    if not value: return '未知'
    for unit in ('B','KB','MB','GB','TB'):
        if value<1024: return f'{value:.1f} {unit}'
        value/=1024
    return f'{value:.1f} PB'

class Events(QObject):
    analysis=Signal(object,str)
    thumbnail=Signal(int,bytes,object)
    completed=Signal(str)
    shutdown=Signal()

class Window(QMainWindow):
    def __init__(self,manager,settings):
        super().__init__()
        self.manager,self.settings=manager,settings
        self.pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='analysis')
        self.events=Events()
        self.events.analysis.connect(self.analyzed)
        self.events.thumbnail.connect(self.show_thumbnail)
        self.events.completed.connect(self.notify_complete)
        self.events.shutdown.connect(self.finish_close)
        self.manager.notify=lambda t:self.events.completed.emit(t.media['title'])
        self.cancel_analysis=threading.Event()
        self.media=[]; self.generation=0; self.busy=False; self.closing=False; self.closed=False
        self.thumbnail_cache={}
        self.setWindowTitle('MediaHarvester')
        self.resize(1280,820)
        root=QWidget(); self.setCentralWidget(root)
        layout=QHBoxLayout(root)
        self.nav=QListWidget(); self.nav.addItems(NAV); self.nav.setFixedWidth(155)
        layout.addWidget(self.nav)
        self.stack=QStackedWidget(); layout.addWidget(self.stack,1)
        home=QWidget(); h=QVBoxLayout(home)
        title=QLabel('MediaHarvester'); title.setStyleSheet('font-size:30px;font-weight:600'); h.addWidget(title)
        h.addWidget(QLabel('输入网页地址，选择真实媒体格式，然后下载。\n任务、进度和临时文件会自动保存。'))
        start=QPushButton('开始解析 URL'); start.clicked.connect(lambda:self.nav.setCurrentRow(1)); h.addWidget(start)
        self.dependencies=QLabel(); self.dependencies.setWordWrap(True); h.addWidget(self.dependencies); h.addStretch(); self.stack.addWidget(home)
        self.analysis_page=self.create_analysis(); self.stack.addWidget(self.analysis_page)
        for text in ('视频格式在 URL 解析页选择；这里显示视频下载任务。','图片可在 URL 解析页筛选并批量选择。'):
            page=QWidget(); box=QVBoxLayout(page); box.addWidget(QLabel(text))
            button=QPushButton('前往解析'); button.clicked.connect(lambda:self.nav.setCurrentRow(1)); box.addWidget(button); box.addStretch()
            self.stack.addWidget(page)
        self.task_page=self.create_tasks(); self.stack.addWidget(self.task_page)
        for text in ('已完成文件','完整任务历史（包含失败与取消）'):
            page=QWidget(); box=QVBoxLayout(page); box.addWidget(QLabel(text)); self.stack.addWidget(page)
        self.stack.addWidget(self.create_settings())
        self.nav.currentRowChanged.connect(self.navigate)
        self.nav.setCurrentRow(0)
        self.tray=QSystemTrayIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowDown),self)
        self.tray.setToolTip('MediaHarvester'); self.tray.show()
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(500)
        self.apply_theme(); self.refresh()

    def create_analysis(self):
        page=QWidget(); box=QVBoxLayout(page)
        label=QLabel('解析网页中的视频、音频和图片'); label.setStyleSheet('font-size:22px'); box.addWidget(label)
        self.urls=QPlainTextEdit(); self.urls.setPlaceholderText('https://example.com/video\n每行一个 HTTP/HTTPS 地址'); self.urls.setMaximumHeight(110); box.addWidget(self.urls)
        login_row=QHBoxLayout()
        cookie_label=QLabel('登录 Cookie（需要时粘贴）'); login_row.addWidget(cookie_label)
        self.cookie_input=QLineEdit(); self.cookie_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.cookie_input.setMaxLength(131072)
        self.cookie_input.setPlaceholderText('粘贴开发者工具里的整行 Cookie，先在上方填写该网站地址')
        login_row.addWidget(self.cookie_input,1)
        apply_cookie=QPushButton('应用 Cookie'); apply_cookie.clicked.connect(self.apply_cookie); login_row.addWidget(apply_cookie)
        clear_cookie=QPushButton('停用 Cookie'); clear_cookie.clicked.connect(self.disable_cookie); login_row.addWidget(clear_cookie)
        cookie_tip='获取 Cookie：浏览器登录网站后按 F12 → Network（网络）→ 刷新 → 点击该网站请求 → Headers（标头）→ Request Headers 中复制完整 Cookie（name=value; name=value），粘贴后点“应用 Cookie”；不要只复制 sessionid 的值。'
        for widget in (cookie_label,self.cookie_input,apply_cookie,clear_cookie):
            widget.setToolTip(cookie_tip)
        box.addLayout(login_row)
        self.cookie_status=QLabel('仅保存在本机；多个网站请分别粘贴并应用。'); self.cookie_status.setWordWrap(True); box.addWidget(self.cookie_status)
        row=QHBoxLayout()
        for label,callback in [('粘贴',self.paste),('解析 / 重新解析',self.analyze),('清空',self.urls.clear),('取消解析',self.cancel_analysis.set)]:
            b=QPushButton(label); b.clicked.connect(callback); row.addWidget(b)
        self.deep=QCheckBox('深度解析（可选 Playwright）'); row.addWidget(self.deep); box.addLayout(row)
        import sys
        if getattr(sys,'frozen',False):
            self.deep.setEnabled(False); self.deep.setText('深度解析（此版本未安装）')
        self.analysis_status=QLabel('等待 URL'); self.analysis_status.setWordWrap(True); box.addWidget(self.analysis_status)
        filters=QHBoxLayout()
        self.kind=QComboBox(); self.kind.addItems(['全部','video','image','audio']); filters.addWidget(self.kind)
        self.extension=QLineEdit(); self.extension.setPlaceholderText('格式过滤，如 jpg'); filters.addWidget(self.extension)
        self.min_width=QSpinBox(); self.min_width.setRange(0,100000); self.min_width.setPrefix('宽 ≥ '); filters.addWidget(self.min_width)
        self.min_height=QSpinBox(); self.min_height.setRange(0,100000); self.min_height.setPrefix('高 ≥ '); filters.addWidget(self.min_height)
        self.min_width.setValue(self.settings.values['image_width']); self.min_height.setValue(self.settings.values['image_height'])
        self.min_size=QSpinBox(); self.min_size.setRange(0,1000000); self.min_size.setSuffix(' KB ≥'); filters.addWidget(self.min_size)
        self.hide_duplicates=QCheckBox('隐藏重复 URL'); self.hide_duplicates.setChecked(True); filters.addWidget(self.hide_duplicates)
        box.addLayout(filters)
        self.results=QTableWidget(0,8)
        self.results.setHorizontalHeaderLabels(['选择 / 预览','类型','标题 / 来源','尺寸 / 时长','格式 / 大小','画质 / 格式选择','音频输出','原始地址'])
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results.setColumnWidth(0,110); self.results.setColumnWidth(2,230); self.results.setColumnWidth(5,320)
        self.results.setSortingEnabled(False); box.addWidget(self.results,1)
        self.gallery=QListWidget(); self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setIconSize(QSize(90,65)); self.gallery.setMaximumHeight(125)
        self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust); box.addWidget(self.gallery)
        self.gallery.itemChanged.connect(self.gallery_changed)
        actions=QHBoxLayout()
        for label,callback in [('全选',lambda:self.select_results(True)),('取消全选',lambda:self.select_results(False)),
                               ('按分辨率排序',self.sort_results),('下载选中媒体',self.enqueue)]:
            b=QPushButton(label); b.clicked.connect(callback); actions.addWidget(b)
        box.addLayout(actions)
        self.custom_name=QLineEdit(); self.custom_name.setPlaceholderText('自定义文件名（仅选择单项时应用，默认保留原标题）'); box.addWidget(self.custom_name)
        for widget in (self.kind,self.extension,self.min_width,self.min_height,self.min_size,self.hide_duplicates):
            if isinstance(widget,QComboBox): widget.currentIndexChanged.connect(self.filter_results)
            elif isinstance(widget,QLineEdit): widget.textChanged.connect(self.filter_results)
            elif isinstance(widget,QSpinBox): widget.valueChanged.connect(self.filter_results)
            else: widget.toggled.connect(self.filter_results)
        return page

    def paste(self):
        from PySide6.QtWidgets import QApplication
        self.urls.setPlainText(QApplication.clipboard().text())
    def apply_cookie(self):
        if self.busy:
            self.cookie_status.setText('请等待解析完成或取消解析后，再应用 Cookie'); return
        urls=[line.strip() for line in self.urls.toPlainText().splitlines() if line.strip()]
        if not urls:
            self.cookie_status.setText('请先在上方填写需要登录的网站地址'); return
        hosts={urlsplit(url).hostname for url in urls}
        if len(hosts)!=1:
            self.cookie_status.setText('应用 Cookie 时请先只保留同一个网站的地址，之后可恢复多个网站链接'); return
        try:
            from .cookies import save_pasted_cookie
            path=DATA/'cookies'/'ui-cookies.txt'
            host=save_pasted_cookie(self.cookie_input.text(),urls[0],path)
            self.settings.values['cookie_file']=str(path); self.settings.save()
            self.setting_widgets['cookie_file'].setText(str(path))
            self.cookie_input.clear()
            self.cookie_status.setText(f'{host} 的 Cookie 已应用，下次自动使用。请点击解析 / 重新解析。')
        except (ValueError,OSError):
            self.cookie_status.setText('无法应用：请检查网站地址，并粘贴完整 Cookie 请求头（name=value; name=value）。')
    def disable_cookie(self):
        if self.busy:
            self.cookie_status.setText('请先等待或取消解析'); return
        self.cookie_input.clear(); self.settings.values['cookie_file']=''; self.settings.save()
        self.setting_widgets['cookie_file'].clear()
        self.cookie_status.setText('手动 Cookie 已停用。自动读取浏览器登录态仍按设置运行。')
    def analyze(self):
        if self.busy: return
        urls=list(dict.fromkeys(s.strip() for s in self.urls.toPlainText().splitlines() if s.strip()))
        if not urls: self.analysis_status.setText('请输入 URL'); return
        if len(urls)>50: self.analysis_status.setText('单次最多解析 50 个 URL'); return
        self.busy=True; self.cancel_analysis.clear(); self.analysis_status.setText('正在解析，界面仍可操作…')
        deep=self.deep.isChecked(); values=self.settings.values.copy()
        def work():
            media,errors=[],[]
            for i,url in enumerate(urls):
                if self.cancel_analysis.is_set(): break
                try: media.extend(ExtractorRegistry(values).analyze(url,self.cancel_analysis,deep))
                except Exception as exc:
                    import re
                    message=re.sub(r'https?://\S+','[URL]',str(exc))[:500]
                    errors.append(f'第 {i+1} 个 URL：{message}'); log.warning('Analysis: %s',message)
            self.events.analysis.emit(media,'\n'.join(errors))
        self.pool.submit(work)
    def analyzed(self,media,error):
        self.busy=False
        self.media=media; self.generation+=1
        self.populate_results()
        self.analysis_status.setText(f'找到 {len(media)} 项媒体。'+ ('\n'+error if error else ''))
        generation=self.generation
        for i,item in enumerate(media):
            if item.kind=='image' or item.thumbnail:
                self.pool.submit(self.fetch_thumbnail,i,item,generation)
    def fetch_thumbnail(self,i,item,generation):
        try:
            from io import BytesIO
            from PIL import Image
            url=item.url if item.kind=='image' else item.thumbnail
            headers={k:v for k,v in item.headers.items() if k.lower() in ('referer','user-agent')}
            with client() as c,c.stream('GET',url,headers=headers) as r:
                r.raise_for_status(); content=bytearray()
                for chunk in r.iter_bytes():
                    if self.closing or generation!=self.generation: return
                    content.extend(chunk)
                    if len(content)>8*1024*1024: return
            with Image.open(BytesIO(content)) as image:
                width,height=image.size
                if width*height>40_000_000: return
                image.thumbnail((120,90)); out=BytesIO(); image.convert('RGB').save(out,'JPEG')
                self.events.thumbnail.emit(i,out.getvalue(),(generation,width,height,len(content)))
        except Exception:
            pass
    def show_thumbnail(self,i,data,meta):
        generation,width,height,length=meta
        if generation!=self.generation or i>=len(self.media): return
        pixmap=QPixmap(); pixmap.loadFromData(data); icon=QIcon(pixmap)
        self.results.item(i,0).setIcon(icon)
        item=self.media[i]
        self.thumbnail_cache[item.url]=(data,width,height,length)
        if item.kind=='image':
            item.width,item.height,item.size=width,height,length
            self.results.item(i,3).setText(f'{width} × {height}')
            self.results.item(i,4).setText(f'{item.ext} / {size(length)}')
            gallery_item=QListWidgetItem(icon,item.title[:20]); gallery_item.setToolTip(item.url)
            gallery_item.setData(Qt.ItemDataRole.UserRole,i)
            gallery_item.setFlags(gallery_item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            gallery_item.setCheckState(self.results.item(i,0).checkState())
            self.gallery.addItem(gallery_item)
        self.filter_results()
    def gallery_changed(self,item):
        index=item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index,int) and index<len(self.media): self.results.item(index,0).setCheckState(item.checkState())
    def populate_results(self):
        self.gallery.clear(); self.results.setRowCount(len(self.media))
        for i,item in enumerate(self.media):
            choice=QTableWidgetItem(''); choice.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable); choice.setCheckState(Qt.CheckState.Unchecked)
            self.results.setItem(i,0,choice)
            for column,text in [(1,item.kind),(2,item.title+'\n'+item.source),(3,f'{item.duration:.0f} 秒' if item.duration else '未知'),
                                (4,f'{item.ext or "未知"} / {size(item.size)}'),(7,item.url)]:
                cell=QTableWidgetItem(text); cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable); self.results.setItem(i,column,cell)
            formats=QComboBox()
            options=format_options(item.formats)
            if not self.settings.values['auto_merge']: options=[o for o in options if '+' not in o[1]]
            by_id={str(f.get('format_id')):f for f in item.formats}
            video_options=[o for o in options if by_id.get(o[1].split('+')[0],{}).get('vcodec') not in (None,'none')]
            video_options.sort(key=lambda o:(by_id[o[1].split('+')[0]].get('height') or 0,
                               self.settings.values['prefer_mp4'] and by_id[o[1].split('+')[0]].get('ext')=='mp4',
                               by_id[o[1].split('+')[0]].get('tbr') or 0),reverse=True)
            if video_options:
                formats.addItem('最佳画质 | '+video_options[0][0],video_options[0][1])
                formats.addItem('最低画质 | '+video_options[-1][0],video_options[-1][1])
            for label,selector in options: formats.addItem(label,selector)
            quality=self.settings.values.get('default_quality','best')
            if quality=='lowest' and video_options: formats.setCurrentIndex(1)
            elif quality.isdigit() and video_options:
                suitable=[o for o in video_options if (by_id[o[1].split('+')[0]].get('height') or 0)<=int(quality)]
                if suitable: formats.setCurrentIndex(formats.findData(suitable[0][1]))
            if not item.formats: formats.addItem('原始文件','')
            self.results.setCellWidget(i,5,formats)
            audio=QComboBox(); audio.addItems(['原始音频','mp3','m4a','opus']); self.results.setCellWidget(i,6,audio)
            self.results.setRowHeight(i,65)
        for i,item in enumerate(self.media):
            if item.url in self.thumbnail_cache:
                data,width,height,length=self.thumbnail_cache[item.url]
                self.show_thumbnail(i,data,(self.generation,width,height,length))
        self.filter_results()
    def filter_results(self):
        seen=set()
        for i,m in enumerate(self.media):
            hidden=(self.kind.currentIndex()>0 and self.kind.currentText()!=m.kind) or (self.extension.text().strip() and self.extension.text().strip().lower()!=m.ext.lower())
            if m.kind=='image':
                hidden=hidden or m.width<self.min_width.value() or m.height<self.min_height.value() or m.size<self.min_size.value()*1024
            hidden=hidden or (self.hide_duplicates.isChecked() and m.url in seen)
            seen.add(m.url); self.results.setRowHidden(i,bool(hidden))
    def select_results(self,selected):
        for i in range(len(self.media)):
            if not self.results.isRowHidden(i): self.results.item(i,0).setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)
        for i in range(self.gallery.count()):
            item=self.gallery.item(i); index=item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(self.results.item(index,0).checkState())
    def sort_results(self):
        self.media.sort(key=lambda m:m.width*m.height,reverse=True)
        self.generation+=1; self.populate_results()
    def enqueue(self):
        selected=[i for i in range(len(self.media)) if not self.results.isRowHidden(i) and self.results.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected: self.analysis_status.setText('请勾选要下载的媒体'); return
        for i in selected:
            item=self.media[i]; selector=self.results.cellWidget(i,5).currentData() or ''
            audio_widget=self.results.cellWidget(i,6)
            audio=audio_widget.currentText() if audio_widget.currentIndex()>0 else ''
            if audio and ('+' in selector or any(f.get('format_id')==selector and f.get('vcodec') not in (None,'none') for f in item.formats)):
                self.analysis_status.setText('音频转换请先选择“仅音频”格式'); continue
            media=asdict(item)
            if '+' not in selector and any(str(f.get('format_id'))==selector and f.get('vcodec')=='none' for f in item.formats):
                media['kind']='audio'
            if audio: media['kind']='audio'
            if len(selected)==1 and self.custom_name.text().strip(): media['title']=self.custom_name.text().strip()
            self.manager.add(media,selector,audio)
        self.nav.setCurrentRow(4)

    def create_tasks(self):
        page=QWidget(); box=QVBoxLayout(page)
        self.task_title=QLabel('下载任务'); self.task_title.setStyleSheet('font-size:22px'); box.addWidget(self.task_title)
        actions=QHBoxLayout()
        for text,action in [('暂停','pause'),('继续 / 重试','resume'),('取消','cancel'),('删除记录','delete'),('打开文件','file'),('打开文件夹','folder')]:
            button=QPushButton(text); button.clicked.connect(lambda checked=False,a=action:self.task_action(a)); actions.addWidget(button)
        box.addLayout(actions)
        self.tasks=QTableWidget(0,9); self.tasks.setHorizontalHeaderLabels(['文件','类型 / 引擎','状态','进度','已下载 / 总量','速度','剩余时间','错误信息','ID'])
        self.tasks.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tasks.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tasks.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tasks.setColumnWidth(0,240); self.tasks.setColumnWidth(3,150); self.tasks.setColumnWidth(7,300); self.tasks.hideColumn(8)
        box.addWidget(self.tasks); return page
    def navigate(self,index):
        if index in (2,3,4,5,6):
            self.stack.setCurrentWidget(self.task_page)
            self.task_title.setText(NAV[index]); self.refresh()
        else: self.stack.setCurrentIndex(index)
    def task_action(self,action):
        ids=[self.tasks.item(index.row(),8).text() for index in self.tasks.selectionModel().selectedRows()]
        for id in ids:
            task=self.manager.tasks.get(id)
            if not task: continue
            if action in ('file','folder'):
                path=task.final if action=='file' else task.directory
                if path and Path(path).exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else: getattr(self.manager,action)(id)
        self.refresh()
    def refresh(self):
        with self.manager.lock:
            tasks=list(self.manager.tasks.values())
            index=self.nav.currentRow()
            visible=[t for t in tasks if (index!=5 or t.state==State.COMPLETED) and
                     (index!=4 or t.state!=State.COMPLETED) and (index!=2 or t.media['kind']=='video') and (index!=3 or t.media['kind']=='image')]
            selected={self.tasks.item(i.row(),8).text() for i in self.tasks.selectionModel().selectedRows()}
            self.tasks.setRowCount(len(visible))
            for row,t in enumerate(visible):
                values=[t.media['title'],t.media['kind']+' / '+t.engine,t.state+(' · '+t.phase if t.phase else ''),'',f'{size(t.downloaded)} / {size(t.total)}',
                        size(t.speed)+'/s' if t.speed else '—',f'{max(0,t.total-t.downloaded)/t.speed:.0f} 秒' if t.speed and t.total else '未知',t.error,t.id]
                for column,text in enumerate(values):
                    cell=QTableWidgetItem(str(text)); cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable); self.tasks.setItem(row,column,cell)
                bar=QProgressBar()
                if t.state==State.COMPLETED: bar.setValue(100)
                elif t.total: bar.setValue(min(99,int(t.downloaded*100/t.total)))
                else: bar.setRange(0,0) if t.state in (State.DOWNLOADING,State.MERGING) else bar.setValue(0)
                self.tasks.setCellWidget(row,3,bar)
                if t.id in selected:
                    self.tasks.selectionModel().select(self.tasks.model().index(row,0),self.tasks.selectionModel().SelectionFlag.Select|self.tasks.selectionModel().SelectionFlag.Rows)
            active=sum(t.state in (State.DOWNLOADING,State.MERGING,State.VERIFYING) for t in tasks)
            self.statusBar().showMessage(f'任务 {len(tasks)}  |  下载中 {active}  |  {size(sum(t.speed for t in tasks))}/s  |  {self.settings.values["directory"]}')
        self.dependencies.setText('FFmpeg: '+(executable('ffmpeg') or '未安装（合并 / 音频转换需要）')+'\naria2: '+(executable('aria2c') or '未安装，使用 httpx 可靠续传'))

    def create_settings(self):
        page=QWidget(); box=QVBoxLayout(page); form=QFormLayout(); self.setting_widgets={}
        for key,label in [('directory','下载文件夹'),('cookie_file','网站登录 Cookie 文件（可留空）'),('concurrency','最大并发任务'),('connections','单任务连接数'),('rate','每任务限速 B/s（0 不限）'),
                          ('retries','重试次数'),('retry_delay','退避初始秒数'),('max_images','单页最大图片数'),('auto_browser_cookies','需要登录时自动读取本机浏览器 Cookie'),('auto_resume','启动自动恢复'),
                          ('notify','完成通知'),('deduplicate','图片内容 SHA-256 去重'),('subtitles','下载字幕'),('thumbnail','保存视频封面')]:
            value=self.settings.values[key]
            if isinstance(value,bool): widget=QCheckBox(); widget.setChecked(value)
            elif isinstance(value,int):
                widget=QSpinBox(); widget.setRange(0,1000000000); widget.setValue(value)
                if key=='concurrency': widget.setRange(1,16)
                if key=='connections': widget.setRange(1,16)
                if key in ('retry_delay','max_images'): widget.setMinimum(1)
            else: widget=QLineEdit(value)
            self.setting_widgets[key]=widget; form.addRow(label,widget)
        for key,label in [('prefer_mp4','优先 MP4'),('auto_merge','自动合并音视频'),('prefer_original','优先页面明确原图')]:
            widget=QCheckBox(); widget.setChecked(self.settings.values[key]); self.setting_widgets[key]=widget; form.addRow(label,widget)
        for key,label in [('image_width','默认图片最小宽度'),('image_height','默认图片最小高度')]:
            widget=QSpinBox(); widget.setRange(0,100000); widget.setValue(self.settings.values[key]); self.setting_widgets[key]=widget; form.addRow(label,widget)
        cookies=QPushButton('选择 Cookie 文件'); cookies.clicked.connect(self.choose_cookies); form.addRow('',cookies)
        directory=QPushButton('选择下载文件夹'); directory.clicked.connect(self.choose_directory); form.addRow('',directory)
        for key,label,options in [('cookie_browser','读取登录态的浏览器',['auto','chrome','edge','firefox','brave','vivaldi']),('theme','主题',['dark','light','system']),('language','语言',['zh_CN','en_US','ja_JP']),
                                  ('default_quality','默认画质',['best','lowest','2160','1440','1080','720','480','360']),
                                  ('container','合并输出容器（编码不兼容时使用 MKV）',['mp4','mkv','webm']),
                                  ('naming','命名方式',['title','site','date'])]:
            widget=QComboBox(); widget.addItems(options); widget.setCurrentText(self.settings.values[key]); self.setting_widgets[key]=widget; form.addRow(label,widget)
        box.addLayout(form); save=QPushButton('保存设置'); save.clicked.connect(self.save_settings); box.addWidget(save)
        self.settings_status=QLabel('语言结构已预留；当前正文以简体中文为主。'); box.addWidget(self.settings_status); box.addStretch()
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page); return scroll
    def choose_cookies(self):
        path,_=QFileDialog.getOpenFileName(self,'选择当前网站的 Netscape Cookie 文件','','Cookie 文件 (*.txt);;所有文件 (*)')
        if path: self.setting_widgets['cookie_file'].setText(path)
    def choose_directory(self):
        path=QFileDialog.getExistingDirectory(self,'下载文件夹',self.settings.values['directory'])
        if path: self.setting_widgets['directory'].setText(path)
    def save_settings(self):
        try:
            values={}
            for key,widget in self.setting_widgets.items():
                values[key]=widget.isChecked() if isinstance(widget,QCheckBox) else widget.value() if isinstance(widget,QSpinBox) else widget.currentText() if isinstance(widget,QComboBox) else widget.text()
            directory=Path(values['directory']).expanduser().resolve(); directory.mkdir(parents=True,exist_ok=True)
            values['directory']=str(directory)
            self.settings.values.update(values); self.settings.save(); self.apply_theme(); self.settings_status.setText('设置已保存')
        except Exception as exc: self.settings_status.setText(str(exc))
    def apply_theme(self):
        from .i18n import localize,translate
        localize(self,self.settings.values['language'])
        dark=self.settings.values['theme']=='dark'
        if self.settings.values['theme']=='system':
            dark=self.palette().window().color().lightness()<128
        bg,fg,panel=('#171b24','#e7edf5','#242b37') if dark else ('#f5f7fb','#202938','#ffffff')
        self.setStyleSheet(f'QWidget {{background:{bg};color:{fg};font-family:"Segoe UI","Microsoft YaHei";font-size:13px;}} QPushButton {{background:{panel};border:1px solid #62738b;border-radius:5px;padding:7px 12px;}} QPushButton:hover {{border-color:#63b3ff;}} QLineEdit,QPlainTextEdit,QTableWidget,QListWidget,QComboBox,QSpinBox {{background:{panel};}} QHeaderView::section {{background:{panel};padding:7px;}} QProgressBar {{border:1px solid #62738b;text-align:center;}} QProgressBar::chunk {{background:#2785d7;}} QListWidget::item:selected {{background:#2785d7;}}')
        nav=EN if self.settings.values['language']=='en_US' else NAV
        for i,text in enumerate(nav): self.nav.item(i).setText(text)
        for table,labels in [(self.results,['选择 / 预览','类型','标题 / 来源','尺寸 / 时长','格式 / 大小','画质 / 格式选择','音频输出','原始地址']),
                             (self.tasks,['文件','类型 / 引擎','状态','进度','已下载 / 总量','速度','剩余时间','错误信息','ID'])]:
            table.setHorizontalHeaderLabels([translate(label,self.settings.values['language']) for label in labels])
    def notify_complete(self,title):
        if self.settings.values['notify']:
            self.tray.showMessage('MediaHarvester · 下载完成',title,QSystemTrayIcon.MessageIcon.Information,5000)
    def closeEvent(self,event):
        if self.closed: event.accept(); return
        event.ignore()
        if self.closing: return
        self.closing=True; self.timer.stop(); self.cancel_analysis.set(); self.generation+=1
        self.setEnabled(False); self.statusBar().showMessage('正在暂停任务并保存，稍候…')
        def shutdown():
            self.manager.close(); self.pool.shutdown(wait=True,cancel_futures=True); self.manager.repo.close(); self.events.shutdown.emit()
        threading.Thread(target=shutdown,daemon=True).start()
    def finish_close(self):
        self.closed=True; self.tray.hide(); self.close()
