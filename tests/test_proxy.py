import base64
import httpx
import pytest
from mediaharvester.proxy import EngineProxy

def test_proxy_authentication():
    with EngineProxy() as proxy:
        with httpx.Client(proxy=proxy.browser['server'],trust_env=False) as c:
            response=c.get('http://example.com')
            assert response.status_code==407

def test_proxy_denies_private_targets():
    with EngineProxy() as proxy:
        with httpx.Client(proxy=proxy.url,trust_env=False,timeout=2) as c:
            with pytest.raises(httpx.HTTPError): c.get('http://127.0.0.1:12345/private')
