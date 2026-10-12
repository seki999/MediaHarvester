"""Subprocess dependency injection confined to the exact fixture server origin.

No product flags or private-network exception are added to the application.
"""
import socket
import sys
from urllib.parse import urlsplit
import httpx


def install(origin):
    import mediaharvester.security as security
    import mediaharvester.proxy as proxy
    import mediaharvester.worker as worker
    original_validate = security.validate_url
    original_addresses = security.public_addresses
    allowed = urlsplit(origin)

    def validate(url):
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.hostname, parsed.port) == (allowed.scheme, allowed.hostname, allowed.port) and not parsed.username and not parsed.password:
            return url
        return original_validate(url)

    def addresses(host, port):
        if (host, port) == (allowed.hostname, allowed.port):
            return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return original_addresses(host, port)

    class Transport(httpx.HTTPTransport):
        def handle_request(self, request):
            validate(str(request.url))
            return super().handle_request(request)

    def client():
        return httpx.Client(transport=Transport(), trust_env=False, follow_redirects=True,
                            max_redirects=5, timeout=5, headers={'Accept-Encoding': 'identity'})

    security.validate_url = proxy.validate_url = worker.validate_url = validate
    security.public_addresses = proxy.public_addresses = addresses
    security.client = proxy.client = client


if __name__ == '__main__':
    install(sys.argv[1])
    from mediaharvester.worker import worker_main
    worker_main()
