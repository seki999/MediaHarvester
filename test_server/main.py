"""Loopback HTTP server with Range, faults, auth and HTML fixtures; test use only."""
import argparse
import contextlib
import mimetypes
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .media_generator import binary_block


class TestServer:
    __test__ = False

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.requests = []
        self.counts = Counter()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.respond(head=True)

            def do_GET(self):
                try:
                    self.respond()
                except (OSError, ConnectionError):
                    self.close_connection = True

            def send(self, code, data=b'', mime='text/plain', extra=None, head=False):
                self.send_response(code)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(data)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                if not head:
                    self.wfile.write(data)

            def respond(self, head=False):
                parsed = urlsplit(self.path)
                path, query = parsed.path, parse_qs(parsed.query)
                owner.counts[path] += 1
                # Store only non-sensitive fields for assertions.
                owner.requests.append({'path': path, 'method': self.command,
                                       'range': self.headers.get('Range'), 'if_range': self.headers.get('If-Range')})
                if path.startswith('/status/'):
                    code = int(path.rsplit('/', 1)[1])
                    return self.send(code, extra={'Retry-After': '1'}, head=head)
                if path == '/loop':
                    return self.send(302, extra={'Location': '/loop'}, head=head)
                if path.startswith('/redirect/'):
                    return self.send(int(path.rsplit('/', 1)[1]), extra={'Location': '/video/direct.mp4'}, head=head)
                if path.startswith('/auth/'):
                    if path.endswith('public'):
                        pass
                    elif path.endswith('redirect-after-login'):
                        if 'session=valid' not in self.headers.get('Cookie', ''):
                            return self.send(401, head=head)
                        return self.send(302, extra={'Location': '/video/direct.mp4'}, head=head)
                    elif path.endswith('cross-domain'):
                        return self.send(302, extra={'Location': f'http://localhost:{owner.server.server_port}/auth/cookie-required'}, head=head)
                    elif path.endswith(('session-expired', 'token-expired', 'invalid-cookie')) or 'session=valid' not in self.headers.get('Cookie', ''):
                        return self.send(401, head=head)
                    path = '/video/direct.mp4'
                if path.startswith('/pages/'):
                    pages = {
                        'html5-video': '<video src="/video/direct.mp4"></video>',
                        'multiple-source': '<video><source src="/video/direct.mp4" type="video/mp4"><source src="/video/direct.webm" type="video/webm"></video>',
                        'iframe-video': '<iframe src="/pages/html5-video"></iframe>',
                        'nested-iframe': '<iframe src="/pages/iframe-video"></iframe>',
                        'javascript-video': '<script>setTimeout(()=>{let v=document.createElement("video");v.src="/video/direct.mp4";document.body.append(v)},100)</script>',
                        'lazy-loaded-video': '<script>setTimeout(()=>{document.body.innerHTML=\'<video src="/video/direct.mp4"></video>\'},500)</script>',
                        'video-poster': '<video src="/video/direct.mp4" poster="/image.png"></video>',
                        'multiple-videos': '<video src="/video/direct.mp4"></video><video src="/video/direct.webm"></video>',
                        'video-audio': '<video src="/video/direct.mp4"></video><audio src="/audio.mp3"></audio>',
                        'relative-url': '<video src="../video/direct.mp4"></video>',
                        'redirected-media': '<video src="/redirect/302"></video>',
                        'images': '<img src="/image.jpg"><img src="/image.jpg"><picture><source srcset="/image.webp 64w, /image.png 128w"></picture><img data-src="/image.gif"><div style="background:url(/image.avif)"></div><meta property="og:image" content="/image.webp">',
                        'blob': '<video src="blob:http://example.com/id"></video>',
                    }
                    if path.endswith('large'):
                        return self.send(200, b' ' * (5*1024*1024+1), 'text/html', head=head)
                    return self.send(200, pages.get(path.rsplit('/', 1)[1], '').encode(), 'text/html; charset=utf-8', head=head)
                if path == '/hls/broken.m3u8':
                    return self.send(200, b'not a playlist', 'application/vnd.apple.mpegurl', head=head)
                if path == '/hls/missing.m3u8':
                    return self.send(200, b'#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nmissing.ts\n#EXT-X-ENDLIST\n', 'application/vnd.apple.mpegurl', head=head)
                if path.startswith('/hls/transient/'):
                    if path.endswith('.ts') and owner.counts[path]==1:
                        return self.send(503,extra={'Retry-After':'1'},head=head)
                    path=path.replace('/hls/transient/','/hls/360/')
                size = int(query.get('size', [10*1024*1024])[0])
                binary = path.startswith('/binary/')
                if binary:
                    data, mime = None, 'application/octet-stream'
                    total = size
                else:
                    aliases = {'/video/direct.mp4': 'video360.mp4', '/video/direct.webm': 'direct.webm',
                               '/video/direct.mov': 'direct.mov', '/video/no-extension': 'video360.mp4',
                               '/video/wrong-extension.jpg': 'video360.mp4', '/video/chunked': 'video360.mp4',
                               '/video/no-content-length': 'video360.mp4', '/video/unknown-content-type': 'video360.mp4',
                               '/video/disposition': 'video360.mp4', '/video/redirect': 'video360.mp4'}
                    relative = aliases.get(path, path.lstrip('/'))
                    file = (owner.root / relative).resolve()
                    if not file.is_relative_to(owner.root) or not file.is_file():
                        return self.send(404, head=head)
                    data = file.read_bytes()
                    total = len(data)
                    mime = mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
                    if file.suffix == '.m3u8': mime = 'application/vnd.apple.mpegurl'
                    if file.suffix == '.mpd': mime = 'application/dash+xml'
                    if path.endswith('unknown-content-type'): mime = 'application/octet-stream'
                etag = 'W/"weak"' if path.endswith('weak') else '"changed"' if path.endswith('changed') else '"fixture-v1"'
                start, end = 0, total-1
                range_header = self.headers.get('Range')
                if range_header and not path.endswith(('ignore', 'changed')):
                    start = int(range_header.split('=')[1].split('-')[0])
                    if start >= total:
                        return self.send(416, extra={'Content-Range': f'bytes */{total}', 'ETag': etag}, head=head)
                    if path.endswith('bad-end'): end = start-1
                    if path.endswith('bad-total'): end = total
                    if path.endswith('short-range'): end = min(total-1, start+65535)
                    self.send_response(206)
                    self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
                else:
                    self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('ETag', etag)
                self.send_header('Last-Modified', 'Fri, 09 Oct 2026 00:00:00 GMT')
                if path.endswith('disposition'):
                    self.send_header('Content-Disposition', "attachment; filename*=UTF-8''%E6%B5%8B%E8%AF%95_%E6%97%A5%E6%9C%AC.mp4")
                chunked = path.endswith('chunked')
                if chunked: self.send_header('Transfer-Encoding', 'chunked')
                elif not path.endswith('no-content-length'):
                    self.send_header('Content-Length', str(max(0, end-start+1)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                if head: return
                block = binary_block()
                for pos in range(start, max(start, end+1), 65536):
                    length = min(65536, end-pos+1)
                    chunk = (block[pos % len(block):] + block)[:length] if binary else data[pos:pos+length]
                    if chunked: self.wfile.write(f'{len(chunk):x}\r\n'.encode()+chunk+b'\r\n')
                    else: self.wfile.write(chunk)
                    self.wfile.flush()
                    if path.endswith('slow'): time.sleep(.004)
                    if path.endswith('drop') and pos >= 65536:
                        self.connection.shutdown(2)
                        return
                if chunked: self.wfile.write(b'0\r\n\r\n')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    with TestServer(args.root) as server:
        print(server.url, flush=True)
        with contextlib.suppress(KeyboardInterrupt):
            while True: time.sleep(1)
