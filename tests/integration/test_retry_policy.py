from datetime import datetime,timezone,timedelta
from email.utils import format_datetime
import httpx
import pytest
from mediaharvester.download import retry_policy


@pytest.mark.parametrize('value,allowed,delay',[('7',True,7),('bad',True,2),('3600',False,2)])
def test_retry_after_seconds(value,allowed,delay):
    response=httpx.Response(503,request=httpx.Request('GET','https://example.com'),headers={'Retry-After':value})
    assert retry_policy(httpx.HTTPStatusError('503',request=response.request,response=response),2)==(allowed,delay)


def test_retry_after_date_and_exponential_floor():
    value=format_datetime(datetime.now(timezone.utc)+timedelta(seconds=10))
    response=httpx.Response(503,request=httpx.Request('GET','https://example.com'),headers={'Retry-After':value})
    allowed,delay=retry_policy(httpx.HTTPStatusError('503',request=response.request,response=response),2)
    assert allowed and 8<=delay<=10
