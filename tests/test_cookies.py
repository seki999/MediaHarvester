import pytest
from mediaharvester.cookies import scoped_cookies, remove_secrets


def test_cookie_scope_and_original_unchanged(tmp_path):
    path = tmp_path / 'cookies.txt'
    data = ('# Netscape HTTP Cookie File\n'
            '.example.com\tTRUE\t/\tTRUE\t0\tsession\tprivate\n'
            '.other.com\tTRUE\t/\tFALSE\t0\tsession\tunrelated\n')
    path.write_text(data)
    jar = scoped_cookies(path, 'https://video.example.com/watch')
    assert len(jar) == 1
    assert len(scoped_cookies(path, 'https://fakeexample.com/')) == 0
    assert len(scoped_cookies(path, 'http://example.com/')) == 0
    assert path.read_text() == data


def test_invalid_cookie_file_does_not_echo_contents(tmp_path):
    path = tmp_path / 'bad.txt'
    path.write_text('secret-value')
    with pytest.raises(ValueError) as error:
        scoped_cookies(path, 'https://example.com/')
    assert 'secret-value' not in str(error.value)


def test_nested_credentials_removed():
    result = remove_secrets({'formats': [{'cookies': 'secret', 'http_headers':
                           {'Cookie': 'secret', 'Authorization': 'secret', 'User-Agent': 'test'}}]})
    assert result == {'formats': [{'http_headers': {'User-Agent': 'test'}}]}
