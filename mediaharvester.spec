from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import os

datas, binaries, hiddenimports = collect_all('yt_dlp')
browser_datas,browser_binaries,browser_imports=collect_all('playwright')
datas+=browser_datas; binaries+=browser_binaries; hiddenimports+=browser_imports
root=Path(SPECPATH)
browser_path=Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH',str(root/'.dev-tools'/'ms-playwright')))
if not browser_path.is_dir() or not any(browser_path.glob('chromium-*')):
    raise RuntimeError('Install Chromium with build_exe.ps1 before building the EXE')
datas.append((str(browser_path),'ms-playwright'))
datas += [(str(root/'mediaharvester'/'i18n'),'mediaharvester/i18n'),(str(root/'THIRD_PARTY_NOTICES.md'),'.')]
datas.append((str(root/'mediaharvester'/'assets'),'mediaharvester/assets'))
if (root/'licenses').exists(): datas.append((str(root/'licenses'),'licenses'))
# Tools are optional and must have their redistribution notices/sources supplied.
tools=root/'tools'
if tools.exists():
    datas.append((str(tools),'tools'))
onefile=os.environ.get('MH_ONEFILE')=='1'
a=Analysis(['main.py'],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,
           excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick','PySide6.QtPdf','PySide6.QtPdfWidgets','pytest','__main__'])
pyz=PYZ(a.pure)
if onefile:
    exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='MediaHarvester',console=False,icon=str(root/'mediaharvester'/'assets'/'app.ico'))
else:
    exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='MediaHarvester',console=False,icon=str(root/'mediaharvester'/'assets'/'app.ico'))
    coll=COLLECT(exe,a.binaries,a.datas,name='MediaHarvester')
