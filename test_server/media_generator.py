"""Generate short, self-owned audio/video and deterministic binary fixtures."""
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image
from mediaharvester.config import executable


def generate(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    ffmpeg = executable('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('Controlled media fixtures require FFmpeg')

    def run(*args):
        argv=[a.as_posix() if isinstance(a, Path) else str(a) for a in args]
        subprocess.run([ffmpeg, '-nostdin', '-y', '-v', 'error', *argv],
                       check=True, capture_output=True, timeout=60, cwd=Path(args[-1]).parent)

    for height in (360, 720, 1080):
        source = root / f'video{height}.mp4'
        run('-f', 'lavfi', '-i', f'color=c=blue:s={height*16//9}x{height}:r=12:d=2',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-g', '12', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-ac', '2', '-shortest', source)
        folder = root / 'hls' / str(height)
        folder.mkdir(parents=True)
        run('-i', source, '-c', 'copy', '-hls_time', '1', '-hls_playlist_type', 'vod', folder / 'index.m3u8')
    run('-i', root / 'video360.mp4', '-c:v', 'libvpx-vp9', '-c:a', 'libopus', root / 'direct.webm')
    run('-i', root / 'video360.mp4', '-c', 'copy', root / 'direct.mov')
    run('-i', root / 'video360.mp4', '-an', '-c:v', 'copy', root / 'silent.mp4')
    for ext, codec in [('mp3', 'libmp3lame'), ('m4a', 'aac'), ('aac', 'aac'), ('opus', 'libopus'), ('webm', 'libopus')]:
        run('-i', root / 'video360.mp4', '-vn', '-c:a', codec, root / f'audio.{ext}')
    for ext in ('jpg', 'png', 'webp', 'gif', 'avif'):
        Image.new('RGB', (64, 48), 'red').save(root / f'image.{ext}')
    master = '#EXTM3U\n'
    for height in (360, 720, 1080):
        master += f'#EXT-X-STREAM-INF:BANDWIDTH={height*1000},RESOLUTION={height*16//9}x{height}\n{height}/index.m3u8\n'
    (root / 'hls/master.m3u8').write_text(master, encoding='utf-8')
    split=root/'hls/split'
    for name in ('video','en','ja','subs'): (split/name).mkdir(parents=True)
    run('-i', root/'video720.mp4', '-an', '-c:v','copy','-hls_time','1','-hls_playlist_type','vod',split/'video/index.m3u8')
    for language,frequency in [('en',440),('ja',880)]:
        run('-f','lavfi','-i',f'sine=frequency={frequency}:sample_rate=48000:duration=2','-c:a','aac','-ac','2',
            '-hls_time','1','-hls_playlist_type','vod',split/language/'index.m3u8')
    (split/'subs/caption.vtt').write_text('WEBVTT\n\n00:00.000 --> 00:01.800\nSelf-owned test caption\n',encoding='utf-8')
    (split/'subs/index.m3u8').write_text('#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:2,\ncaption.vtt\n#EXT-X-ENDLIST\n',encoding='utf-8')
    (split/'master.m3u8').write_text('#EXTM3U\n'
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTOSELECT=YES,URI="en/index.m3u8"\n'
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Japanese",LANGUAGE="ja",DEFAULT=NO,AUTOSELECT=YES,URI="ja/index.m3u8"\n'
        '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTOSELECT=YES,URI="subs/index.m3u8"\n'
        '#EXT-X-STREAM-INF:BANDWIDTH=200000,RESOLUTION=1280x720,CODECS="avc1.42c01f,mp4a.40.2",AUDIO="audio",SUBTITLES="subs"\nvideo/index.m3u8\n',encoding='utf-8')
    fmp4 = root / 'hls/fmp4'
    fmp4.mkdir()
    run('-i', root / 'video360.mp4', '-c', 'copy', '-hls_time', '1', '-hls_playlist_type', 'vod',
        '-hls_segment_type', 'fmp4', fmp4 / 'index.m3u8')
    dash = root / 'dash'
    dash.mkdir()
    run('-i', root / 'video720.mp4', '-c', 'copy', '-seg_duration', '1',
        '-use_template', '1', '-use_timeline', '1', '-adaptation_sets', 'id=0,streams=v id=1,streams=a',
        '-f', 'dash', dash / 'manifest.mpd')
    for name, args in [('list', ['-use_template', '0', '-use_timeline', '0']),
                       ('template', ['-use_template', '1', '-use_timeline', '0'])]:
        folder = root / 'dash' / name
        folder.mkdir()
        run('-i', root / 'video360.mp4', '-c', 'copy', '-seg_duration', '1', *args,
            '-adaptation_sets', 'id=0,streams=v id=1,streams=a', '-f', 'dash', folder / 'manifest.mpd')
    manifest = {str(p.relative_to(root)).replace('\\', '/'): {'size': p.stat().st_size,
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in root.rglob('*') if p.is_file()}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def binary_block():
    return bytes(range(256)) * 256
