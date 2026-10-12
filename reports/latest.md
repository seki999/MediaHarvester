# MediaHarvester 实际自动化验证报告

测试日期：2026-10-12T11:56:59.186054+09:00（Asia/Tokyo）
基线提交：`43d66e354027b9f617cc846fbb6234a3d99a0051`；报告生成时提交：`5b6703841441e8815c1454bc21eae3662c99fc1d`。

原有基线：70 PASS / 0 FAIL。新增稳定复现失败用例：24。确认修复 Bug：13。
本地回归：{'PASS': 208, 'SKIPPED': 2}，实际执行通过率 100.0%。跳过不计通过。
公网完整下载：2/4 个尝试，含受限资源的总体通过率 50.0%；其余状态见下表。

## 环境

```json
{
  "date": "2026-10-12T11:54:40.098488+09:00",
  "timezone": "Asia/Tokyo",
  "python": "3.13.14 (tags/v3.13.14:fd17997, Jun 10 2026, 13:03:48) [MSC v.1944 64 bit (AMD64)]",
  "os": "Windows-11-10.0.26200-SP0",
  "packages": {
    "PySide6": "6.8.3",
    "yt-dlp": "2026.8.19",
    "httpx": "0.28.1",
    "curl-cffi": "0.16.3",
    "playwright": "1.63.0",
    "pytest": "9.1.1",
    "pyinstaller": "6.22.3",
    "ruff": "0.17.0"
  },
  "tools": {
    "ffmpeg": {
      "path": "C:\\Users\\seki9\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-9.0.1-full_build\\bin\\ffmpeg.EXE",
      "version": "ffmpeg version 9.0.1-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers"
    },
    "ffprobe": {
      "path": "C:\\Users\\seki9\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-9.0.1-full_build\\bin\\ffprobe.EXE",
      "version": "ffprobe version 9.0.1-full_build-www.gyan.dev Copyright (c) 2007-2026 the FFmpeg developers"
    },
    "aria2c": {
      "path": null
    }
  },
  "commit": "5b6703841441e8815c1454bc21eae3662c99fc1d",
  "branch": "codex/automation-validation"
}
```

## 协议与模块用例

| 分类 | PASS | FAIL | SKIPPED | 执行通过率 |
|---|---:|---:|---:|---:|
| Cookie/认证 | 23 | 0 | 0 | 100.0% |
| DASH | 3 | 0 | 0 | 100.0% |
| GUI | 1 | 0 | 0 | 100.0% |
| HLS | 9 | 0 | 0 | 100.0% |
| HTML/动态页面 | 10 | 0 | 0 | 100.0% |
| HTTP | 40 | 0 | 0 | 100.0% |
| aria2 | 1 | 0 | 0 | 100.0% |
| 其他单元/回归 | 27 | 0 | 0 | 100.0% |
| 图片 | 10 | 0 | 0 | 100.0% |
| 媒体验证 | 2 | 0 | 0 | 100.0% |
| 安全 | 22 | 0 | 0 | 100.0% |
| 续传/恢复 | 23 | 0 | 2 | 100.0% |
| 网站解析 | 9 | 0 | 0 | 100.0% |
| 网络异常 | 14 | 0 | 0 | 100.0% |
| 音频 | 14 | 0 | 0 | 100.0% |

## 网站与公开素材

| ID / 网站 | 状态 | 提取 | 下载字节 | 原因 |
|---|---|---|---:|---|
| mdn-mp4 / MDN | PASS |  | 1128375 | 完整性验证通过 |
| mdn-webm / MDN | PASS |  | 554058 | 完整性验证通过 |
| commons-audio / Wikimedia Commons | BLOCKED |  |  | Client error '403 Forbidden' for url '[URL] For more information check: [URL] |
| commons-image / Wikimedia Commons | BLOCKED |  |  | Client error '403 Forbidden' for url '[URL] For more information check: [URL] |
| YoutubeIE-0 / YouTube | SKIPPED | PASS |  | 仅完成提取；本轮平台候选未执行下载，公开小素材另有直链验证 |
| VimeoIE-0 / Vimeo | BLOCKED |  |  | ERROR: [vimeo] 17466681: The web client only works when logged-in. Use --cookies, --cookies-from-browser, --username and --password, --netrc-cmd, or --netrc (vimeo) to provide account credentials. See  [URL]  for how to manually pass cookies |
| DailymotionIE-0 / Dailymotion | SKIPPED | PASS |  | 仅完成提取；本轮平台候选未执行下载，公开小素材另有直链验证 |
| TwitchVodIE-0 / Twitch VOD | BLOCKED | PASS |  | 仅完成提取；未确认下载授权，未下载 |
| TwitchClipsIE-0 / Twitch Clips | BLOCKED | PASS |  | 仅完成提取；未确认下载授权，未下载 |
| TikTokIE-0 / TikTok | BLOCKED |  |  | ERROR: [TikTok] 6748451240264420610: Your IP address is blocked from accessing this post |
| InstagramIE-1 / Instagram Reels | BLOCKED | PASS |  | 仅完成提取；未确认下载授权，未下载 |
| InstagramIE-0 / Instagram video | BLOCKED | PASS |  | 仅完成提取；未确认下载授权，未下载 |
| FacebookIE-0 / Facebook Video | FAIL |  |  | ERROR: [facebook] 3676516585958356: Cannot parse data; please report this issue on  [URL] , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U |
| TwitterIE-0 / X / Twitter | UNAVAILABLE |  |  | ERROR: [twitter] 643211948184596480: No video could be found in this tweet |
| BiliBiliIE-0 / Bilibili | SKIPPED | PASS |  | 仅完成提取；本轮平台候选未执行下载，公开小素材另有直链验证 |
| NiconicoIE-0 / Niconico | BLOCKED | PASS |  | 仅完成提取；未确认下载授权，未下载 |
| ArchiveOrgIE-1 / Internet Archive | SKIPPED | PASS |  | 仅完成提取；本轮平台候选未执行下载，公开小素材另有直链验证 |
| RedditIE-0 / Reddit | BLOCKED | PASS |  | 仅完成提取；未确认下载授权，未下载 |
| YouTube-Shorts / YouTube Shorts | BLOCKED |  |  | 尚未取得此 URL 类型的可验证公开授权样例；没有执行网络请求 |
| Instagram-single-image / Instagram single image | BLOCKED |  |  | 尚未取得此 URL 类型的可验证公开授权样例；没有执行网络请求 |
| Instagram-carousel / Instagram carousel | BLOCKED |  |  | 尚未取得此 URL 类型的可验证公开授权样例；没有执行网络请求 |
| Wikimedia-page / Wikimedia Commons | SKIPPED | PASS |  | 仅完成提取；本轮平台候选未执行下载，公开小素材另有直链验证 |

## 修复前后

| Bug | 问题 | 修改文件 | 重测 |
|---|---|---|---|
| MH-001 | 206 未验证 Content-Range 结束位置和分段长度；异常响应先追加文件才失败 | mediaharvester/download.py | PASS；2 用例 |
| MH-002 | DRM 音轨参与自动视频配对 | mediaharvester/extractors.py | PASS；1 用例 |
| MH-003 | 错误或缺失扩展名未根据媒体类型规范化 | mediaharvester/extractors.py | PASS；9 用例 |
| MH-004 | 忽略 Content-Disposition 的 UTF-8 文件名 | mediaharvester/extractors.py | PASS；1 用例 |
| MH-005 | 选择包含音轨的视频下载后无音轨仍标为完成 | mediaharvester/download.py, mediaharvester/media.py | PASS；1 用例 |
| MH-006 | 提交日志恢复只更新状态，保留了旧下载字节数和总大小 | mediaharvester/download.py | PASS；1 用例 |
| MH-007 | 权限拒绝、永久错误和限速仍自动重复请求；缺少 Retry-After 处理 | mediaharvester/download.py | PASS；9 用例 |
| MH-008 | HTML5/iframe/动态视频源解析缺口，以及 generic 多媒体页面下载失败 | mediaharvester/extractors.py | PASS；10 用例 |
| MH-009 | 未知 MIME 的 MP4 和 application/ogg 未识别为直链；video/ogg 声音文件被误分类 | mediaharvester/extractors.py | PASS；4 用例 |
| MH-010 | Windows 短命子进程已退出时 Job Object 绑定失败导致误报 | mediaharvester/processes.py | PASS；1 用例 |
| MH-011 | Instagram 原始视频格式未由 yt-dlp 生成 format_id，导致 Reels/视频被丢弃 | mediaharvester/worker.py | PASS；2 用例 |
| MH-012 | 重新解析多视频页面时比较播放列表父 ID，无法下载已选子项 | mediaharvester/worker.py | PASS；3 用例 |
| MH-013 | Playwright 隐式浏览器上下文在视频页面清理时阻塞；显式关闭上下文后解除超时 | mediaharvester/worker.py | PASS；2 用例 |

## 公网完整性证据

- mdn-mp4：1128375 字节，SHA-256 `0cd83d944a6ca7822b4a8306cecc60a36e859b041f6702c6a1ad9ead78924451`；[{'codec_type': 'video', 'codec_name': 'h264', 'height': 540, 'channels': None}, {'codec_type': 'audio', 'codec_name': 'aac', 'height': None, 'channels': 2}]。
- mdn-webm：554058 字节，SHA-256 `c6f8a348953395598a9a73b9bab1676436410797bce9f398f4be1531d6e76dda`；[{'codec_type': 'video', 'codec_name': 'vp8', 'height': 540, 'channels': None}, {'codec_type': 'audio', 'codec_name': 'vorbis', 'height': None, 'channels': 2}]。

## 命令与构建证据

- offline：FAIL；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/offline.xml`；日志 `reports\offline.txt`。
- static：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe -m ruff check --select E9,F63,F7,F82 mediaharvester scripts test_server tests`；日志 `reports\static.txt`。
- online：FAIL；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe scripts/run_online_tests.py --sites`；日志 `reports\online.txt`。
- gui：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe scripts/gui_workflow.py`；日志 `reports\gui.txt`。
- build-onedir：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist/validation-onedir mediaharvester.spec`；日志 `reports\build-onedir.txt`。
- exe-onedir：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe scripts/exe_smoke.py dist/validation-onedir/MediaHarvester/MediaHarvester.exe`；日志 `reports\exe-onedir.txt`。
- build-onefile：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist/validation-onefile mediaharvester.spec`；日志 `reports\build-onefile.txt`。
- exe-onefile：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe scripts/exe_smoke.py dist/validation-onefile/MediaHarvester.exe`；日志 `reports\exe-onefile.txt`。
- offline-final：PASS；`.venv/Scripts/python.exe -m pytest -q --junitxml=reports/offline-final.xml`；日志 `reports/offline-final.xml`。
- gui-final：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe scripts/gui_workflow.py`；日志 `reports\gui-final.txt`。
- exe-onedir-final：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe scripts/exe_smoke.py dist/validation-onedir/MediaHarvester/MediaHarvester.exe --output reports/exe-onedir`；日志 `reports\exe-onedir-final.txt`。
- build-onedir-final：PASS；`C:\Users\seki9\Documents\MediaHarvester\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist/validation-onedir mediaharvester.spec`；日志 `reports\build-onedir-final.txt`。
- stress：PASS；`.venv/Scripts/python.exe -m pytest tests/integration/test_resume.py --stress -q --junitxml=reports/stress.xml`；日志 `reports/stress.xml`。
- source-audit：PASS；`python scripts/verify_build.py EXE --output report.json`；日志 `reports/exe-onedir/source-audit.json; reports/exe-onefile/source-audit.json`。

## 未解决、未执行或能力边界


代码修改文件：.github/workflows/validation.yml, .gitignore, README.md, docs/automated-testing.md, docs/validation.md, mediaharvester/download.py, mediaharvester/extractors.py, mediaharvester/media.py, mediaharvester/processes.py, mediaharvester/worker.py, pyproject.toml, requirements-dev.txt, requirements-lock.txt, scripts/diagnose_sites.py, scripts/exe_smoke.py, scripts/generate_test_report.py, scripts/gui_workflow.py, scripts/run_full_tests.py, scripts/run_online_tests.py, scripts/verify_build.py, test_server/__init__.py, test_server/engine_runner.py, test_server/main.py, test_server/media_generator.py, test_server/network_faults.py, tests/conftest.py, tests/fixtures/public_image_urls.yaml, tests/fixtures/public_video_urls.yaml, tests/fixtures/site_samples.yaml, tests/integration/__init__.py, tests/integration/conftest.py, tests/integration/helpers.py, tests/integration/test_audio.py, tests/integration/test_concurrency.py, tests/integration/test_content_detection.py, tests/integration/test_cookie_auth.py, tests/integration/test_dash_download.py, tests/integration/test_hls_download.py, tests/integration/test_http_download.py, tests/integration/test_images.py, tests/integration/test_network_failure.py, tests/integration/test_playlist_download.py, tests/integration/test_playlist_identity.py, tests/integration/test_process_lifecycle.py, tests/integration/test_regressions.py, tests/integration/test_reports.py, tests/integration/test_resume.py, tests/integration/test_retry_policy.py, tests/integration/test_security.py, tests/integration/test_site_extractors.py, tests/integration/test_tls.py, tests/integration/test_transport_faults.py, tests/integration/test_web_extraction.py

- **BLOCKED** real-login：未使用个人浏览器登录态；本地 Cookie 认证与合成 Firefox 数据库已覆盖，真实账号授权仍需用户合法登录态
- **BLOCKED** shorts-images：YouTube Shorts、Instagram 单图/轮播未取得可验证授权的真实下载样例；照片最大候选和轮播处理有现有单元回归
- **BLOCKED** source-limits：Wikimedia 直链返回 403；Vimeo/Reddit 要求认证，TikTok 拒绝当前 IP；未绕过限制
- **FAIL** upstream-sites：Facebook 页面数据解析失败、X 样例未找到视频；上游 yt-dlp 同样复现，尚未证明样例或上游可修复
- **SKIPPED** 5gb-powerloss：未执行可选 5GB/长期压力、物理断电、磁盘缓存损坏；已执行 100MB/1GB 确定性续传与提交恢复
- **SKIPPED** clean-vm：未在干净 Windows VM 验收，宿主仍安装 Python；EXE smoke 会移除 PATH 的 Python 和外部工具
- **SKIPPED** python-311：本机仅实际运行 Python 3.13.14；CI 定义 3.11/3.13，云端工作流尚未执行
- **SKIPPED** wide-matrix：尚未逐项完成全部 MIME/音频编码/DRM 制式、DASH 字幕、多 Representation、多天签名更新、TLS/DNS 故障组合与符号链接磁盘异常矩阵
- **UNSUPPORTED** stream-resume：不能证明跨会话一致的 HLS/DASH 分片安全重新下载；不承诺复用旧分片或破解 DRM
- **UNSUPPORTED** silent-ytdlp：仅视频格式且没有可配对音轨时，现有格式选择不提供选项；静音直链允许按预期验证
- **UNSUPPORTED** translation：日文仅预留翻译结构；英文动态错误信息仍不完全本地化

## 复现命令

```powershell
.venv\Scripts\python.exe scripts\run_full_tests.py --mode offline
.venv\Scripts\python.exe scripts\run_full_tests.py --mode online
.venv\Scripts\python.exe scripts\run_full_tests.py --mode full --build
.venv\Scripts\python.exe scripts\run_full_tests.py --mode stress
```

## 判定说明

- PASS 只代表该用例实际断言已通过；协议成功率只按执行用例计算，不能等同于所有场景覆盖率。
- 平台只有提取通过不等同下载通过；未确认授权或超预算的电影未下载。
- 本地 HTTP fixture 经测试依赖注入访问精确 loopback origin；正式安全策略没有私网豁免。
- 保留并测试了原有 extractors.py/ui.py/docs/artifacts.sha256 三处未提交修改，不将它们混入本次代码提交。
- 基线日志保留不覆盖。中途生成器路径错误和 GUI 视图断言错误属于测试工具问题，修正后独立重跑，未计为产品 Bug。

## 下一步

- 补充各平台短小授权样例与合法登录态，逐项复测 BLOCKED/UNAVAILABLE。
- 在干净 Windows VM 和 Python 3.11 执行同一套本地测试及 EXE smoke。
- 继续扩展完整故障组合、DASH 字幕与多清晰度、HLS 自动受限碎片重试。
