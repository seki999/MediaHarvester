import json
import pytest
from mediaharvester.resume import prepare_resume


HLS = {'id': '625', 'mode': 'hls-native', 'vcodec': 'vp9', 'duration': 120}
HTTP = {'id': '140', 'mode': 'restart'}


def checkpoint(temp):
    part = temp / 'media.f625.mp4.part'
    part.write_bytes(b'completed fragments')
    state = temp / 'media.f625.mp4.ytdl'
    state.write_text(json.dumps({'downloader': {'current_fragment': {'index': 31}}}))
    return part, state


def test_hls_survives_restart_even_when_audio_has_no_etag(tmp_path):
    prepare_resume(tmp_path, 'video', [HLS, HTTP], True)
    part, state = checkpoint(tmp_path)
    audio = tmp_path / 'media.f140.m4a.part'
    audio.write_bytes(b'unverified audio')
    assert prepare_resume(tmp_path, 'video', [HLS, HTTP], True)
    assert part.read_bytes() == b'completed fragments'
    assert json.loads(state.read_text())['downloader']['current_fragment']['index'] == 31
    assert not audio.exists()


def test_migrate_legacy_empty_proof_with_native_checkpoint(tmp_path):
    (tmp_path / 'resume-proof.json').write_text(json.dumps({'identity': 'video', 'formats': []}))
    part, state = checkpoint(tmp_path)
    assert not prepare_resume(tmp_path, 'video', [HLS, HTTP], True)
    assert part.exists() and state.exists()
    # The migrated proof also survives the next restart.
    assert not prepare_resume(tmp_path, 'video', [HLS, HTTP], True)


@pytest.mark.parametrize('identity,proof', [('other', HLS), ('video', dict(HLS, vcodec='av1'))])
def test_changed_identity_or_format_does_not_append(tmp_path, identity, proof):
    prepare_resume(tmp_path, 'video', [HLS], True)
    part, state = checkpoint(tmp_path)
    assert prepare_resume(tmp_path, identity, [proof], True)
    assert not part.exists() and not state.exists()
    assert next((tmp_path / 'previous').rglob('*.part')).read_bytes() == b'completed fragments'


def test_corrupt_legacy_checkpoint_is_preserved_in_archive(tmp_path):
    (tmp_path / 'resume-proof.json').write_text(json.dumps({'identity': 'video', 'formats': []}))
    part, state = checkpoint(tmp_path)
    state.write_text('{broken')
    assert prepare_resume(tmp_path, 'video', [HLS], True)
    assert not part.exists()
    assert next((tmp_path / 'previous').rglob('*.part')).read_bytes() == b'completed fragments'


def test_http_validator_change_still_restarts(tmp_path):
    proof = {'id': 'http', 'etag': 'old', 'length': 100}
    prepare_resume(tmp_path, 'video', [proof])
    (tmp_path / 'media.mp4.part').write_bytes(b'old')
    assert prepare_resume(tmp_path, 'video', [dict(proof, etag='new')])
    assert not (tmp_path / 'media.mp4.part').exists()
