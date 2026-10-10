# Third-party software

MediaHarvester source is MIT licensed. Bundled dependencies retain their licenses.

| Dependency | License | Source |
|---|---|---|
| PySide6 / Qt | LGPL-3.0 / GPL-3.0 / commercial (module-dependent) | https://code.qt.io/pyside/pyside-setup.git / https://code.qt.io/qt/ |
| yt-dlp | Unlicense (some bundled code has other notices) | https://github.com/yt-dlp/yt-dlp |
| httpx / httpcore | BSD-3-Clause | https://github.com/encode/httpx / https://github.com/encode/httpcore |
| BeautifulSoup4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| lxml | BSD-3-Clause; libxml2/libxslt MIT | https://github.com/lxml/lxml |
| Pillow | MIT-CMU | https://github.com/python-pillow/Pillow |
| PyInstaller | GPL-2.0-or-later with distribution exception | https://github.com/pyinstaller/pyinstaller |
| aria2 (optional, not included) | GPL-2.0-or-later | https://github.com/aria2/aria2 |
| FFmpeg (optional, not included) | LGPL/GPL depending on build | https://ffmpeg.org/ |

Release builders must retain complete dependency license texts and applicable Qt LGPL notices,
provide corresponding source where required, permit replacement/relinking of LGPL libraries,
and inspect licenses of any optional bundled tools. Prefer onedir for replaceable Qt libraries.
The build includes license files in `licenses/`, collected from installed distributions and Qt sources.
The Qt LGPL/GPL texts originate from the official Qt 6.8.3 qtbase source repository:
https://github.com/qt/qtbase/tree/v6.8.3/LICENSES
Onefile is a technical packaging demonstration and requires a license compliance review before redistribution.

- curl_cffi / curl-impersonate: https://github.com/lexiforest/curl_cffi ; installed distribution license files are retained in licenses/curl_cffi.
- CFFI and pycparser runtime dependency licenses are retained in licenses.
