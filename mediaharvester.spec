from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import os

datas, binaries, hiddenimports = collect_all('yt_dlp')
root=Path(SPECPATH)
datas += [(str(root/'mediaharvester'/'i18n'),'mediaharvester/i18n'),(str(root/'THIRD_PARTY_NOTICES.md'),'.')]
if (root/'licenses').exists(): datas.append((str(root/'licenses'),'licenses'))
# Tools are optional and must have their redistribution notices/sources supplied.
tools=root/'tools'
if tools.exists():
    datas.append((str(tools),'tools'))
onefile=os.environ.get('MH_ONEFILE')=='1'
a=Analysis(['main.py'],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,
           excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick','PySide6.QtPdf','PySide6.QtPdfWidgets','pytest','playwright','__main__'])
pyz=PYZ(a.pure)
if onefile:
    exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='MediaHarvester',console=False)
else:
    exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='MediaHarvester',console=False)
    coll=COLLECT(exe,a.binaries,a.datas,name='MediaHarvester')
