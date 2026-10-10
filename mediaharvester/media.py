import json
import subprocess
import time
from pathlib import Path
from .config import executable
from .worker import kill_tree
from .processes import attach_job,release_job

class FFmpegManager:
    def convert_audio(self,source,temp,codec,cancel):
        ffmpeg=executable('ffmpeg')
        if not ffmpeg: raise ValueError('音频转换需要 FFmpeg；请安装并加入 PATH')
        encoders={'mp3':'libmp3lame','m4a':'aac','opus':'libopus'}
        if codec not in encoders: raise ValueError('不支持的音频格式')
        output=Path(temp)/('converted.'+codec)
        proc=subprocess.Popen([ffmpeg,'-nostdin','-y','-v','error','-protocol_whitelist','file,pipe',
            '-format_whitelist','mov,matroska,webm,ogg,mp3,flac,wav,mpegts,aac',
            '-i',str(source),'-vn','-c:a',encoders[codec],str(output)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
        attach_job(proc)
        try:
            while proc.poll() is None:
                if cancel.wait(.1): raise InterruptedError('音频转换已暂停')
            if proc.returncode or not output.exists() or not output.stat().st_size:
                raise ValueError('FFmpeg 音频转换失败，请确认源文件包含音频轨')
            return output
        finally:
            if proc.poll() is None: kill_tree(proc)
            release_job(proc)
    def verify(self,path,cancel,kind):
        probe=executable('ffprobe')
        if not probe:
            return  # Transport length/hash verification still applies; decode verification unavailable.
        proc=subprocess.Popen([probe,'-v','error','-protocol_whitelist','file,pipe',
            '-format_whitelist','mov,matroska,webm,ogg,mp3,flac,wav,mpegts,aac',
            '-show_entries','stream=codec_type,codec_name,width,height','-of','json',str(path)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
        attach_job(proc)
        started=time.monotonic()
        try:
            while proc.poll() is None:
                if cancel.wait(.1): raise InterruptedError('媒体验证已暂停')
                if time.monotonic()-started>30: raise TimeoutError('媒体校验超时')
            stdout,stderr=proc.communicate()
            if proc.returncode: raise ValueError('FFprobe 媒体验证失败，文件不是有效媒体')
            streams=json.loads(stdout).get('streams',[])
            if not any(s.get('codec_type')==kind for s in streams):
                raise ValueError('下载文件没有预期媒体轨道')
        finally:
            if proc.poll() is None: kill_tree(proc)
            release_job(proc)
