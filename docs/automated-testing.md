# 可重复自动化验证

使用源码虚拟环境，不操作用户数据库、下载目录或个人 Cookie。完整下载测试都在临时目录运行；只有脱敏证据、截图和报告留下。先安装 `requirements-dev.txt`，并提供 FFmpeg 和 FFprobe。可选 Playwright/Chromium 未安装时，动态页面用例明确跳过。

```powershell
.venv\Scripts\python.exe scripts\run_full_tests.py
.venv\Scripts\python.exe scripts\run_full_tests.py --mode offline
.venv\Scripts\python.exe scripts\run_full_tests.py --mode online
.venv\Scripts\python.exe scripts\run_full_tests.py --mode full --build
.venv\Scripts\python.exe scripts\run_full_tests.py --mode stress
```

省略模式时执行本地回归及小型在线 smoke；`offline` 不访问公网，`online` 另外执行平台候选信息提取，`full` 包含真实 Qt 工作流，`--build` 另外构建两种 Windows EXE 并 smoke；`stress` 只执行有界本地 100 MB/1 GB 测试。线上媒体响应预算合计最多 42 MB，最多四个直链下载，每个案例有进程截止时间、零自动重试。平台候选仅提取，不下载未确认授权内容；遇到 429 停止本站后续请求。旧 `online_smoke.py` 与 EXE smoke 的固定 W3C 素材流量独立记录，不包含在上述 42 MB 预算中。

```powershell
.venv\Scripts\python.exe -m pytest tests\integration\test_hls_download.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_dash_download.py -q
.venv\Scripts\python.exe -m pytest tests\integration\test_resume.py --stress -q
.venv\Scripts\python.exe scripts\gui_workflow.py
.venv\Scripts\python.exe scripts\generate_test_report.py
```

`test_server/media_generator.py` 生成自有两秒视频、音频、多格式图片、360/720/1080p TS HLS、fMP4、分离语言音轨/字幕及三种 DASH。`test_server/main.py` 提供 HTTP Range、重定向、错误、认证、HTML5、iframe、动态页面和确定性二进制文件。服务器不导入产品入口，loopback 注入仅存在于测试消费者及独立测试 worker，正式安全校验不提供允许私网的开关。pytest 的自动 fixture 还会阻止外部 DNS 和非 loopback 连接，避免测试意外依赖公网。

## 模块与证据对应

| 模块 | 本轮覆盖 |
|---|---|
| extractors / models | Content-Type、文件签名、Content-Disposition、HTML5/iframe/动态、图片候选、DRM 配对、真实格式选择 |
| download / files | 10 MB 部分续传、100 MB/1 GB 哈希、Range/验证标识、断开、暂停恢复、并发命名、SHA-256、提交恢复、禁止缺失预期音轨假成功 |
| worker / media | 真实 yt-dlp + 安全代理 + FFmpeg、HLS/DASH 分轨合并、语言音轨、字幕旁文件、音频转换、播放列表子项、Instagram 视频格式规范化 |
| cookies / browser_cookies | 合成登录服务器、Path/Secure/Domain、跨站隔离、手动粘贴、Netscape 原文件保护、合成 Firefox 数据库只读、失败重试逻辑 |
| security / proxy | 生产 loopback 阻止、非 HTTP URL、私网 DNS、混合 DNS、认证代理、私网目标、Windows 名称与凭据字段清理 |
| database / processes | WAL/FULL、重启恢复、提交日志、已完成文件丢失、取消竞态、Job Object 短命进程 |
| ui / app / config | 现有 offscreen Qt 单元；真实 Windows 多行解析、选择下载、进度、暂停/继续/取消、导航/历史、设置、主题、语言和正常关闭 |
| spec / EXE | 两种独立输出，移除 Python 和外部工具 PATH 的真实启动与 W3C 提取/下载；不代表干净 VM 已验收 |

本地每个成功媒体用例验证真实文件、哈希、大小及数据库；视频另做 FFprobe 轨道和时长断言。协议通过率仅针对执行用例，不代表整个需求矩阵的所有组合已经覆盖。

报告在 `reports/latest.html`、`reports/latest.md`、`reports/latest.json`，HTML 网站表可点击表头排序。`reports/baseline/` 保留原始基线与修复前复现，不覆盖。`reports/failures/` 保存失败阶段和脱敏堆栈。源码 SHA-256、初始提交、版本与实际命令写入报告。

GitHub Actions 在 PR/Push 执行本地测试、真实 HLS/DASH、安全、适合 CI 的 Qt 和 Ruff 错误检查；线上测试只手动触发，不阻塞普通 PR，不读取个人 Cookie。工作流定义 Python 3.11/3.13，云端是否通过以 Actions 实际运行记录为准。

## 已知边界

真实平台授权下载率尚不足以验证 ≥90% 的目标。已完成提取的长电影、尚未确认授权的短片、被限制的站点不会伪报下载成功。DRM、直播录制、跨会话流分片复用、全套日文、5 GB/长期压力、物理断电、全部 TLS/DNS/磁盘故障组合、DASH 字幕/多清晰度、真实账号端到端及干净 Windows VM，均按实际证据注明未执行或不支持。
