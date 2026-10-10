"""Pinned DNS transport: every connection and redirect is checked, including yt-dlp."""
import ipaddress
import socket
from urllib.parse import urlsplit
import httpx
import httpcore

class SecurityError(ValueError):
    pass

def validate_url(url: str) -> str:
    if any(ord(c)<33 or ord(c)==127 for c in url):
        raise SecurityError('URL 不允许空白或控制字符，请使用百分号编码')
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise SecurityError('仅允许不含账号密码的 HTTP/HTTPS URL')
    try:
        p.port
    except ValueError as exc:
        raise SecurityError('无效端口') from exc
    if p.hostname.lower() == 'localhost':
        raise SecurityError('禁止访问本机或内网')
    try:
        address = ipaddress.ip_address(p.hostname)
    except ValueError:
        return url
    if not address.is_global:
        raise SecurityError('禁止访问本机、内网、链路本地或元数据地址')
    return url

def public_addresses(host: str, port: int):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise SecurityError('DNS 返回非公网地址，已阻止请求')
    return addresses

class SafeNetwork(httpcore.SyncBackend):
    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if isinstance(host, bytes):
            host = host.decode()
        addresses = public_addresses(host, port)
        return super().connect_tcp(addresses[0][4][0], port, timeout, local_address, socket_options)

class SafeTransport(httpx.HTTPTransport):
    def __init__(self):
        super().__init__(retries=0)
        self._pool._network_backend = SafeNetwork()
    def handle_request(self, request):
        validate_url(str(request.url))
        return super().handle_request(request)

def client():
    return httpx.Client(transport=SafeTransport(), trust_env=False, follow_redirects=True,
                        max_redirects=5, timeout=httpx.Timeout(20, connect=10),
                        headers={'User-Agent': 'MediaHarvester/0.1', 'Accept-Encoding': 'identity'})
