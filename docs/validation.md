# 实际验证记录

日期：2026-10-10；Windows 11 10.0.26200，Python 3.13.14，PySide6 6.8.3，
yt-dlp 2026.8.19，PyInstaller 6.22.3，FFmpeg/FFprobe 9.0.1（WinGet Gyan），
aria2 1.37.0 官方 Windows 64 位构建（仅开发测试用），Playwright 1.63.0。

| 命令 / 验证 | 真实结果 |
|---|---|
| `.venv\Scripts\python -m pytest -q` | 最终套件 52 项通过，包含本地 HTTP、Range、416、忽略 Range、验证标识变化、连接中断、关闭重启、SQLite、格式组合、Qt、aria2、去重、有限重试、取消与迟到进度的竞态 |
| `.venv\Scripts\python scripts\smoke_gui.py --online-preview` | 真正 Windows Qt 窗口启动；显示 W3C MP4 和 python.org 两张图片；异步缩略图，截图，正常关闭 |
| `.venv\Scripts\python scripts\online_smoke.py` | 真实公共 MP4：4,372,373 字节；HTTP 下载成功，FFprobe 同时识别 video/audio；真实 yt-dlp API 解析和下载成功；MP3 转换成功；两张 HTML 图片批量下载成功 |
| 设置开发 aria2 PATH 后运行 `online_smoke.py` | 真实 aria2 下载成功、媒体验证成功；两项 aria2 单元测试也验证暂停与续传 |
| `.venv\Scripts\python scripts\merge_smoke.py` | 真实 yt-dlp + FFmpeg 两输入流复制合并成功，FFprobe 检出视频和音频；输入格式元数据为受控测试 fixture，不能等同于真实网站分离轨道在线验收 |
| 可选 Playwright worker，URL `https://www.python.org/` | Chromium 真实渲染成功，HTML 58,306 字符，得到两个图片候选；通过认证公网代理，无头导航与有限滚动 |
| `build_exe.ps1` | Windows onedir 构建成功 |
| `build_exe.ps1 -OneFile` | Windows onefile 构建成功 |
| `scripts\exe_smoke.py dist\onedir\MediaHarvester\MediaHarvester.exe` | 移除 PATH 的 Python/FFmpeg/aria2 后，EXE GUI 启动和正常关闭成功；冻结的 yt-dlp 解析和 4,372,373 字节下载成功 |
| `scripts\exe_smoke.py dist\onefile\MediaHarvester.exe` | 同样通过 GUI、真实解析和下载；独立 EXE 直接启动，不依赖开发 Python 进程提供解释器 |

初始 Qt 6.12 打包产物出现 DLL 加载失败；固定 PySide6 6.8.3 后解决。
最初 yt-dlp 的源站 403 已通过一致的请求配置修复。
aria2 的 Windows 原生控制文件曾留下已关闭的 `__temp` 文件，现仅在正常关闭后
安全恢复重命名，并交由 aria2 再次验证；无法取得控制文件时安全重新下载。

## 未验证或限制

- 未做物理断电、磁盘写缓存故障、突然结束父进程的全系统压力实验；测试模拟了数据库中断状态及原子提交崩溃窗口。
- 未在完全没有安装 Python 的干净 Windows VM 验收。已移除 PATH 中 Python，并直接启动打包 EXE；宿主机器仍安装 Python。
- 未逐站验证登录、地域限制、实际 HLS/DASH 分片、播放列表和动态签名长期恢复；不承诺所有 yt-dlp 网站可用。
- 合并路径已用真实 FFmpeg 验证，但真实网站分离视频/音频的在线覆盖仍应补充。
- 本次 EXE 不含 FFmpeg、FFprobe、aria2、Playwright 或 Chromium；合并/转换需额外工具，深度解析使用源码环境。
- 日文仅翻译结构；英文主要静态控件可用，部分动态提示仍为中文。感知哈希、文件覆盖/跳过策略、外部 CSS 遍历未实现。
- 实际截图验证使用宿主显示缩放；未逐一切换 125% 和 150% 做完整视觉验收。

所有网络测试均针对公开样例；不把在线可达性作为自动化单元测试必要条件。

## 手动 Cookie 导入验证（2026-10-10）

新增当前网站 Cookie 筛选、原文件不变、HTTPS 安全 Cookie 范围、错误不泄露内容和嵌套任务元数据去凭据测试。全套 55 项通过。用户提供的 Netscape 文件读取成功；指定网页使用 Cookie 实测仍返回 HTTP 410，因此没有宣称该网页已支持或下载成功。Cookie 只在本地临时副本中使用。

补充实测：安装官方 yt-dlp curl-cffi 浏览器请求依赖后，目标地址解析成功，240p MP4 完整下载 35,404,051 字节。FFprobe 验证 H.264 视频 426×240、AAC 音频、655.8 秒。问题不只是 Cookie，原构建缺少该网络请求依赖；同时补充普通 HTML 请求被拒时转交网站视频引擎的处理。

最终 EXE 验证：单文件版不带 Cookie 成功解析 8 个格式，并按默认最高画质选择 1080p HLS，完整下载 233,823,080 字节，FFprobe 验证 1080p 视频、音频及 655.901667 秒时长。两种打包版均通过 GUI 启动和 W3C 真实视频解析 / 下载回归。全套 55 项测试通过。

1080p 实际输出进一步通过 FFmpeg 全片音视频解码检查，退出码 0，无解码错误。

## Instagram 照片验证（2026-10-10）

目标照片帖使用用户提供的有效 Instagram Cookie，经网站授权接口解析出四张实际照片。全部完成下载并通过 Pillow 文件验证，尺寸分别为 3000×3981、3000×3981、2987×3963、3000×3976；字节数分别为 1,240,733、1,229,315、899,167、1,491,035。新增照片候选选择、轮播转换、无照片时保留访问错误的测试。修复原来视频格式校验丢弃照片条目的问题。

新增 58 项测试全部通过。Instagram 新版单文件 EXE 实测解析出四张照片，无 Cookie / Authorization 字段残留，并逐张下载通过 Pillow 校验。因旧版 EXE 正在运行，构建输出使用 dist/instagram-onefile 和 dist/instagram-onedir 独立目录，避免强制关闭用户程序。

## 自动浏览器登录态（2026-10-10）

新增标准 Windows 浏览器配置发现、真实 Firefox SQLite 只读读取及域名筛选、登录失败后重试、未开启或非登录错误不读取浏览器的测试。实机发现 Chrome、Edge 各一个配置；两者读取时因数据库被占用失败，没有强制关闭用户浏览器，也没有宣称实机自动读取已成功。

最终 64 项测试全部通过。新版 EXE 通过临时标准 Firefox SQLite 配置发现、真实数据库读取、公开 W3C 视频解析、输出凭据字段清理测试；登录失败后重试流程由单元测试验证。原手动 Cookie 文件在此次验证时已不在原路径，因此没有宣称新版自动读取真实浏览器并访问私人 Instagram 已端到端成功。旧 Cookie 文件缺失时仍继续自动发现的回归通过。

新增界面 Cookie 粘贴、隐藏输入、应用后清空、设置保存和停用操作已通过 Qt 功能验证。新增请求头转换、Instagram API 域名范围、多站保存与本网站覆盖、错误不泄露 Cookie、禁止 HTTP 传递凭据的回归测试。未使用用户实际 Cookie 值进行此次测试。
