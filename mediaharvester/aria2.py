import subprocess
import time
import os
import socket
import secrets
import httpx
from pathlib import Path
from .config import executable
from .proxy import EngineProxy
from .security import client
from .worker import kill_tree
from .processes import attach_job,release_job

class Aria2Backend:
    def download(self,task,temp,cancel,update,settings):
        part=temp/'aria-payload'
        control=Path(str(part)+'.aria2')
        # Revalidate before aria2 uses its native control file.
        with client() as c:
            r=c.head(task.media['url']); r.raise_for_status()
            etag=r.headers.get('etag',''); modified=r.headers.get('last-modified','')
            same=(bool(etag) and etag==task.etag and not etag.startswith('W/')) or (not etag and bool(modified) and modified==task.modified)
            if part.exists() and (not same or not control.exists()):
                archive=temp/'previous'/str(time.time_ns()); archive.mkdir(parents=True)
                for old in (part,control,Path(str(control)+'__temp')):
                    if old.exists(): old.rename(archive/old.name)
            task.etag,task.modified=etag,modified
            task.total=int(r.headers.get('content-length') or 0)
            update()
        with EngineProxy() as proxy:
            with socket.socket() as port_socket:
                port_socket.bind(('127.0.0.1',0)); rpc_port=port_socket.getsockname()[1]
            secret=secrets.token_hex(24)
            def rpc(method,*params):
                with httpx.Client(trust_env=False,timeout=2) as rpc_client:
                    return rpc_client.post(f'http://127.0.0.1:{rpc_port}/jsonrpc',json={
                        'jsonrpc':'2.0','id':'mh','method':'aria2.'+method,'params':['token:'+secret,*params]}).json().get('result')
            args=[executable('aria2c'),'--continue=true','--auto-file-renaming=false','--allow-overwrite=true',
                  '--always-resume=false',
                  '--auto-save-interval=1','--enable-rpc=true','--rpc-listen-all=false',f'--rpc-listen-port={rpc_port}',f'--rpc-secret={secret}',
                  '--file-allocation=none','--max-tries=1','--timeout=20','--connect-timeout=10',
                  '--summary-interval=0','--console-log-level=error','--download-result=hide',
                  f'--split={settings["connections"]}',f'--max-connection-per-server={settings["connections"]}',
                  f'--all-proxy={proxy.browser["server"]}','--all-proxy-user=mh',f'--all-proxy-passwd={proxy.browser["password"]}',
                  f'--dir={temp}','--out=aria-payload']
            if task.etag and not task.etag.startswith('W/'):
                args.append('--header=If-Match: '+task.etag)
            elif task.modified:
                args.append('--header=If-Unmodified-Since: '+task.modified)
            if settings['rate']: args.append(f'--max-download-limit={settings["rate"]}')
            # URLs go through stdin; no shell interpolation or signed URL process argument.
            args+=['--input-file=-']
            proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            attach_job(proc)
            proc.stdin.write((task.media['url']+'\n  out=aria-payload\n').encode()); proc.stdin.close()
            try:
                while proc.poll() is None:
                    if cancel.wait(.4):
                        try:
                            rpc('forcePauseAll'); rpc('shutdown'); proc.wait(timeout=5)
                            self.recover_closed_control(control,task.total)
                        except Exception: pass
                        raise InterruptedError('任务已暂停')
                    try:
                        status=rpc('tellActive') or []
                        if status:
                            task.downloaded=int(status[0]['completedLength'])
                            task.total=int(status[0]['totalLength']); task.speed=int(status[0]['downloadSpeed']); update()
                        else:
                            stopped=rpc('tellStopped',0,1) or []
                            if stopped and stopped[0]['status']=='error':
                                rpc('shutdown')
                                proc.wait(timeout=5)
                                raise OSError('aria2 服务器或传输错误 '+str(stopped[0].get('errorCode','')))
                            if stopped and stopped[0]['status']=='complete':
                                rpc('shutdown')
                    except OSError: raise
                    except Exception: pass
                if proc.returncode!=0: raise OSError(f'aria2 下载失败，代码 {proc.returncode}')
            finally:
                if proc.poll() is None: kill_tree(proc)
                release_job(proc)
        if not part.exists() or part.stat().st_size==0: raise OSError('aria2 没有输出文件')
        task.downloaded=part.stat().st_size
        if task.total and task.downloaded!=task.total: raise OSError('aria2 文件长度不完整')
        update()
        return part
    @staticmethod
    def recover_closed_control(control,total):
        """aria2 Windows can leave its fully closed native control file before rename.

        Only use this after graceful engine shutdown. aria2 validates the control
        structure again on load. Missing control otherwise forces a safe restart.
        """
        pending=Path(str(control)+'__temp')
        if not pending.exists(): return
        data=pending.read_bytes()
        if len(data)>=34 and data[:10]==bytes.fromhex('00010000000000000000') and int.from_bytes(data[14:22],'big')==total:
            with pending.open('r+b') as stream: os.fsync(stream.fileno())
            os.replace(pending,control)
