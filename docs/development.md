# 开发

使用 Python 3.11+，当前验证环境为 Windows / Python 3.13。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts\smoke_gui.py
.\.venv\Scripts\python scripts\online_smoke.py
```

单元测试本地服务器通过显式 monkeypatch 注入仅测试用 client，生产没有允许内网开关。
在线 smoke 依赖 W3C 公共样例可达，不作为单元测试要求。
依赖上界约束保护兼容性；升级时保存新环境 freeze，执行续传、Qt 和打包回归。
httpx transport 使用 httpcore 的内部 network_backend 注入，升级 httpcore 要重点复测。
yt-dlp 建议经常升级正式版本，并对目标站点做人工验证，不固定声称支持所有网站。
PySide6 固定 6.8.3：最初安装的 6.12 在本机 PyInstaller 产物中出现 DLL 加载失败，
固定版本重新构建后通过 EXE 启动与真实下载验证。不要未经打包回归就放宽 Qt 版本。
