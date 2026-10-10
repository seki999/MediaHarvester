# 架构与恢复约束

`extractors.py` 注册静态图片与 yt-dlp 解析器；解析生成 Media，不直接下载。
`download.py` 是统一调度器，最多 16 个执行线程，实际并发由设置控制。
HTTP、aria2、yt-dlp 分别使用独立后端。Qt 主线程通过 Signals 接收解析结果，
通过 500 ms 定时刷新任务快照。解析、缩略图、下载、关闭等待都在后台执行。

SQLite schema v1: `tasks(id PRIMARY KEY, state, updated, data JSON)`。
JSON 存储原始页面、真实 URL、格式 ID、下载目录、进度、验证标识、重试次数、
最终路径与 SHA-256。WAL + synchronous FULL，每次状态变化和约 400 ms 进度写入事务。
启动把中断状态改为 PAUSED 或 PENDING；不删除临时数据。
当前 schema 明确版本为 1，未来变更需要添加迁移，不能降低版本直接打开数据库。

HTTP 续传需要强 ETag 或 Last-Modified，通过 If-Range 请求并核对 206 Content-Range。
200 表示重新下载；416 只在长度、验证标识都匹配时认为文件下载完。
缺少可信验证标识时重新下载。服务端错误有限指数退避；永久解析错误允许手动重试。

yt-dlp 每次重解析原网页和媒体 ID。只有所有轨道存在一致强 ETag、长度、编码、
格式 ID 时复用原生 .part 文件；不能证明一致的 HLS/DASH 数据移到 previous 子目录，
重新下载，避免错误拼接。旧格式 ID 不再可用会失败，用户应重新解析选择格式。

完成时先验证，再写入 fsync 的 commit.json，原子替换自行独占创建的目标文件，
最后提交 COMPLETED 到数据库。启动执行任务时检查提交日志，可修复重命名后、
数据库提交前的崩溃。实际断电依赖文件系统及硬件缓存，不承诺零损失。

直接请求使用 httpx/httpcore 的 DNS 固定 transport；连接到检查后的公网 IP，
TLS 仍验证原始主机。yt-dlp、aria2 和可选 Chromium 通过随机凭据的临时代理，
CONNECT 目标解析后固定公网地址。该代理只绑定回环、要求凭据、进程结束即关闭，
不提供任何下载任务控制 API。代理凭据和签名 URL 不写入应用日志。
FFmpeg/FFprobe 后处理仅允许本地文件/pipe 与明确媒体 demuxer；禁止把下载文件
误识别为可继续请求网络或引用其他本地文件的播放清单。RTMP 和直播录制不在首版范围。

未来浏览器扩展采用 Native Messaging，维护允许的扩展 ID，消息 schema、长度上限、
用户可见授权和 URL 公网策略；当前不开放本地任务控制服务。
