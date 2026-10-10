# Windows 发布

```powershell
.\.venv\Scripts\python -m pip install -r requirements-build.txt
.\build_exe.ps1
# 先运行 dist\onedir\MediaHarvester\MediaHarvester.exe
.\build_exe.ps1 -OneFile
# dist\onefile\MediaHarvester.exe
```

辅助程序通过 `tools/` 或 PATH 查找，打包工作目录不影响定位。
数据库、设置、日志始终写入 LOCALAPPDATA，不写入 onefile 解包目录。
FFmpeg、FFprobe、aria2 不默认随包分发。正式发布若附带它们，应同时提供许可证、
适用构建的完整对应源码与链接/替换说明。当前机器 FFmpeg 来自 WinGet Gyan.FFmpeg，
它属于环境组件，开发版本不复制进 EXE。

onedir 推荐用于 LGPL Qt 可替换组件的分发；onefile 是技术构建产物，
公开发布前需根据实际模块核查 LGPL/GPL 义务。保留第三方 notices 与依赖版本清单。

验证 EXE 不需要 Python 解释器参与启动；彻底没有 Python、FFmpeg、aria2 的干净 Windows VM
仍需另行验收。当前宿主有 Python，不能把宿主 smoke 等同于干净机器测试。
