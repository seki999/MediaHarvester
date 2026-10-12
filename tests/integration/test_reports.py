from scripts.generate_test_report import clean
from scripts.run_online_tests import classify


def test_report_credentials_and_query_tokens_removed():
    original={'Cookie':'session=private','url':'https://example.com/video?token=private',
              'trace':'Authorization: Bearer private\nCookie: session=private\nfailed'}
    result=clean(original)
    assert 'Cookie' not in result and 'private' not in str(result)
    assert result['url']=='https://example.com/video?[REDACTED]'


def test_online_access_and_sample_failure_categories():
    assert classify('The web client only works when logged-in')=='BLOCKED'
    assert classify('Account authentication is required')=='BLOCKED'
    assert classify('No video could be found in this tweet')=='UNAVAILABLE'
    assert classify('Cannot parse data')=='FAIL'
