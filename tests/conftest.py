"""Pytest is offline: only loopback sockets and explicitly mocked DNS are allowed."""
import ipaddress
import socket
import pytest


@pytest.fixture(autouse=True)
def offline_network_guard(monkeypatch):
    original_lookup=socket.getaddrinfo
    original_connect=socket.socket.connect
    original_connect_ex=socket.socket.connect_ex

    def loopback(host):
        if isinstance(host,bytes):host=host.decode()
        if host=='localhost':return True
        try:return ipaddress.ip_address(host).is_loopback
        except ValueError:return False

    def lookup(host,*args,**kwargs):
        if not loopback(host):raise socket.gaierror('Offline test forbids external DNS')
        return original_lookup(host,*args,**kwargs)

    def connect(stream,address):
        if isinstance(address,tuple) and not loopback(address[0]):raise OSError('Offline test forbids external socket')
        return original_connect(stream,address)

    def connect_ex(stream,address):
        if isinstance(address,tuple) and not loopback(address[0]):raise OSError('Offline test forbids external socket')
        return original_connect_ex(stream,address)

    monkeypatch.setattr(socket,'getaddrinfo',lookup)
    monkeypatch.setattr(socket.socket,'connect',connect)
    monkeypatch.setattr(socket.socket,'connect_ex',connect_ex)
