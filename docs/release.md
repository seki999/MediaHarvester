# Windows 发布

```powershell
.\.venv\Scripts\python -m pip install -r requirements-build.txt
.\build_exe.ps1
# 先运行 dist\onedir\MediaHarvester\MediaHarvester.exe
.\build_exe.ps1 -OneFile
# dist\onefile\MediaHarvester.exe
```

构建默认包含深度解析：脚本先将 Playwright Chromium 下载到忽略目录
`.dev-tools/ms-playwright`，验证浏览器能够启动并执行 JavaScript，再运行测试和打包。
PyInstaller 会同时保留 Playwright 驱动、Chromium 和浏览器随附的许可证文件；
源码依赖许可证由 `collect_notices.py` 收集。首次构建需要访问 Playwright 官方下载源。
浏览器显著增大发行包体积，推荐先使用 onedir；分发时请保留完整目录，不能只复制 EXE。
onefile 每次启动需要解压浏览器，启动速度与磁盘占用会增加。
构建机无需安装用户 Chrome，发行包也不依赖用户浏览器版本。

源码浏览器自检：`python scripts/smoke_deep.py`。Linux 开发可使用系统 Chromium，
或运行 `python -m playwright install --with-deps chromium` 安装浏览器及系统依赖。
Windows 打包必须在 Windows 上运行，Linux GUI/浏览器测试不能代替 Windows 发行包验收。

辅助程序通过 `tools/` 或 PATH 查找，打包工作目录不影响定位。
数据库、设置、日志始终写入 LOCALAPPDATA，不写入 onefile 解包目录。
FFmpeg、FFprobe、aria2 不默认随包分发。正式发布若附带它们，应同时提供许可证、
适用构建的完整对应源码与链接/替换说明。当前机器 FFmpeg 来自 WinGet Gyan.FFmpeg，
它属于环境组件，开发版本不复制进 EXE。

onedir 推荐用于 LGPL Qt 可替换组件的分发；onefile 是技术构建产物，
公开发布前需根据实际模块核查 LGPL/GPL 义务。保留第三方 notices 与依赖版本清单。

验证 EXE 不需要 Python 解释器参与启动；彻底没有 Python、FFmpeg、aria2 的干净 Windows VM
仍需另行验收。当前宿主有 Python，不能把宿主 smoke 等同于干净机器测试。
