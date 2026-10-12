import hashlib
import threading
from dataclasses import asdict
import pytest
from mediaharvester.download import HttpBackend
from mediaharvester.models import Media, Task
from test_server.media_generator import binary_block


@pytest.mark.parametrize('fraction', [.1,.5,.9])
@pytest.mark.parametrize('mode', ['normal','ignore','changed'])
def test_10mb_resume_full_hash(tmp_path, fixture_server, local_network, fraction, mode):
    payload=binary_block()*160
    task=Task(asdict(Media(fixture_server.url+'/binary/'+mode,'','resume','audio','bin')),str(tmp_path),etag='"fixture-v1"')
    (tmp_path/'payload.part').write_bytes(payload[:int(len(payload)*fraction)])
    result=HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    assert result.stat().st_size==len(payload)
    assert hashlib.sha256(result.read_bytes()).digest()==hashlib.sha256(payload).digest()


@pytest.mark.stress
@pytest.mark.parametrize('megabytes', [100,1024])
def test_large_local_resume_streaming_hash(tmp_path,fixture_server,local_network,megabytes):
    size=megabytes*1024*1024
    task=Task(asdict(Media(fixture_server.url+f'/binary/normal?size={size}','','large','audio','bin')),str(tmp_path),etag='"fixture-v1"')
    with (tmp_path/'payload.part').open('wb') as stream:
        for _ in range(size//65536//2): stream.write(binary_block())
    result=HttpBackend().download(task,tmp_path,threading.Event(),lambda:None,{})
    expected=hashlib.sha256()
    for _ in range(size//65536): expected.update(binary_block())
    from mediaharvester.files import sha256
    assert result.stat().st_size==size and sha256(result)==expected.hexdigest()
