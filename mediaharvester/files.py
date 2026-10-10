import hashlib
import os
import re
from pathlib import Path

def safe_name(title: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip(' .')[:140] or 'media'
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))}:
        name = '_' + name
    return name

def sha256(path,cancel=None):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            if cancel and cancel.is_set(): raise InterruptedError('校验已暂停')
            h.update(chunk)
    return h.hexdigest()

def publish(source: Path, directory: Path, name: str):
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / safe_name(name)
    for i in range(10000):
        target = base if i == 0 else base.with_name(f'{base.stem} ({i}){base.suffix}')
        try:
            # Windows rename fails if destination exists; never overwrite another task.
            if os.name == 'nt':
                os.rename(source, target)
            else:
                os.link(source, target)
                source.unlink()
            return target
        except FileExistsError:
            continue
    raise OSError('重名文件过多')
