import pytest
from mediaharvester.cookies import save_pasted_cookie,scoped_cookies


def test_header_roundtrip_and_instagram_api_scope(tmp_path):
    path=tmp_path/'ui-cookies.txt'
    save_pasted_cookie('Cookie: sessionid=test-value==; csrftoken=test-token',
                       'https://www.instagram.com/p/example/',path)
    jar=scoped_cookies(path,'https://i.instagram.com/api/v1/media/')
    assert {c.name:c.value for c in jar}=={'sessionid':'test-value==','csrftoken':'test-token'}
    assert not len(scoped_cookies(path,'https://unrelated.com/'))


def test_replace_current_site_preserves_other_site(tmp_path):
    path=tmp_path/'cookies.txt'
    save_pasted_cookie('a=old; removed=old','https://example.com/',path)
    save_pasted_cookie('b=other','https://other.com/',path)
    save_pasted_cookie('a=new','https://example.com/',path)
    assert {c.name:c.value for c in scoped_cookies(path,'https://example.com/')}=={'a':'new'}
    assert len(scoped_cookies(path,'https://other.com/'))==1


@pytest.mark.parametrize('text',['secret-without-name','Cookie: a=secret\nAuthorization: other',''])
def test_invalid_input_not_saved_or_echoed(tmp_path,text):
    path=tmp_path/'cookies.txt'
    with pytest.raises(ValueError) as error:
        save_pasted_cookie(text,'https://example.com/',path)
    assert 'secret' not in str(error.value)
    assert not path.exists()


def test_plain_http_cannot_receive_pasted_login(tmp_path):
    with pytest.raises(ValueError):
        save_pasted_cookie('session=private','http://example.com/',tmp_path/'cookies.txt')
