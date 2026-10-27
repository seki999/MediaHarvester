"""Preserve native HLS checkpoints independently of HTTP range validators."""
import json
import os
import time


def prepare_resume(temp, identity, formats, multi=False):
    path = temp / 'resume-proof.json'
    try:
        old = json.loads(path.read_text('utf-8'))
    except (OSError, ValueError):
        old = {}
    previous = {f['id']: f for f in old.get('formats', [])}
    restarted = False
    for proof in formats:
        prefix = 'media.f' + proof['id'] + '.' if multi else 'media.'
        files = [p for p in temp.glob('media*') if p.is_file() and p.name.startswith(prefix)]
        same_identity = old.get('identity') == identity
        safe = same_identity and proof == previous.get(proof['id']) and proof.get('mode') != 'restart'
        # Older releases saved an empty proof for HLS. Migrate only an exact
        # format's native checkpoint, after the worker revalidates the video ID.
        if same_identity and old.get('formats') == [] and proof.get('mode') == 'hls-native' and multi:
            for checkpoint in files:
                if checkpoint.suffix != '.ytdl':
                    continue
                try:
                    index = json.loads(checkpoint.read_text('utf-8'))['downloader']['current_fragment']['index']
                    part = checkpoint.with_suffix('.part')
                    safe = isinstance(index, int) and index > 0 and part.exists() and part.stat().st_size > 0
                except (OSError, ValueError, KeyError, TypeError):
                    safe = False
                if safe:
                    break
        if files and not safe:
            archive = temp / 'previous' / str(time.time_ns())
            archive.mkdir(parents=True)
            for item in files:
                item.rename(archive / item.name)
            restarted = True
    pending = path.with_suffix('.tmp')
    with pending.open('w', encoding='utf-8') as stream:
        json.dump({'identity': identity, 'formats': formats}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)
    return restarted
