import subprocess
import threading
import pytest
from mediaharvester.config import executable
from mediaharvester.media import FFmpegManager

def test_real_audio_conversion_and_verification(tmp_path):
    ffmpeg=executable('ffmpeg')
    if not ffmpeg or not executable('ffprobe'): pytest.skip('Optional FFmpeg not installed')
    source=tmp_path/'tone.wav'
    subprocess.run([ffmpeg,'-nostdin','-y','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.3',str(source)],check=True)
    manager=FFmpegManager(); cancel=threading.Event()
    result=manager.convert_audio(source,tmp_path,'mp3',cancel)
    assert result.suffix=='.mp3' and result.stat().st_size>0
    manager.verify(result,cancel,'audio')

def test_invalid_media_rejected(tmp_path):
    if not executable('ffprobe'): pytest.skip('Optional FFprobe not installed')
    bad=tmp_path/'bad.mp4'; bad.write_text('<html>expired</html>')
    with pytest.raises(ValueError): FFmpegManager().verify(bad,threading.Event(),'video')
