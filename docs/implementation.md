# 交付模块清单

| 模块 | 实现 |
|---|---|
| `app.py` / `main.py` | QApplication、应用数据路径、单实例锁、启动错误日志、冻结 worker 分流 |
| `config.py` | JSON 设置原子保存、有效范围校验、LOCALAPPDATA、PATH/解包目录辅助程序定位 |
| `models.py` | Media、持久化 Task、全部要求的状态值、轨道/后处理阶段 |
| `extractors.py` | 可注册解析器、真实 Content-Type 直链识别、yt-dlp 元数据/播放列表、HTML 图片候选/去重、实际格式组合 |
| `security.py` | URL 协议/账号检查、非公网禁止、连接时 DNS 检查和固定 IP、每次重定向重新检查 |
| `proxy.py` | 临时随机认证代理、公网目标固定、yt-dlp/aria2/Chromium 的统一网络边界 |
| `database.py` | SQLite WAL/FULL、线程安全事务、schema v1、新版本数据库拒绝降级打开 |
| `download.py` | 并发调度、HTTP Range/If-Range、重试、暂停/取消/继续、任务恢复、提交日志、SHA-256 并发去重、媒体验证 |
| `aria2.py` | 原生多连接、RPC 真实进度、控制文件持久化、可信验证标识变化时重启、受控退出后的控制文件恢复 |
| `worker.py` | yt-dlp Python API 子进程、真实格式选择、音轨合并、音频转换、分轨累计进度、重新解析和强验证标识续传 |
| `media.py` | 可取消 FFmpeg 直接文件音频转换、FFprobe 本地媒体轨验证 |
| `files.py` | Windows 名称安全化、流式 SHA-256、重名编号且不覆盖已有文件 |
| `processes.py` | Windows Job Object，父进程退出时结束受管下载进程和后代 |
| `ui.py` | 8 项导航、解析/格式/筛选/缩略图、下载表与多选操作、历史、设置、深浅主题、后台关闭和通知 |
| `i18n.py` / `i18n/` | 中英静态控件、本地翻译资源和日文预留 |
| `mediaharvester.spec` / 构建脚本 | Windows onedir/onefile、测试前置、第三方许可证文本收集、辅助程序可选 |

后续建议优先做：干净 Windows VM 的回归、真实 HLS/DASH 与签名更新测试、
完整英文/日文动态提示、SQLite 独立事件历史、稳定的辅助程序发行包与源码/许可交付，
再加入感知哈希和浏览器 Native Messaging 扩展。
