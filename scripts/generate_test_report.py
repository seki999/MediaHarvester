"""Generate escaped, standalone Chinese HTML/Markdown/JSON reports from real evidence."""
import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def clean(value):
    if isinstance(value,dict):
        return {k:clean(v) for k,v in value.items() if k.lower() not in ('cookie','cookies','authorization','proxy-authorization','set-cookie')}
    if isinstance(value,list):return [clean(v) for v in value]
    if not isinstance(value,str):return value
    value=re.sub(r'(?im)\b(cookie|authorization|set-cookie|proxy-authorization)\s*[:=][^\r\n]+',r'\1: [REDACTED]',value)
    return re.sub(r'(https?://[^\s?\"<>]+)\?[^\s\"<>]+',r'\1?[REDACTED]',value)


def read_json(path,default):
    return json.loads(path.read_text('utf-8')) if path.exists() else default


def junit(path):
    if not path.exists():return []
    rows=[]
    for case in ET.parse(path).getroot().iter('testcase'):
        problem=case.find('failure')
        if problem is None:problem=case.find('error')
        skipped=case.find('skipped')
        status='FAIL' if problem is not None else 'SKIPPED' if skipped is not None else 'PASS'
        reason=(problem.text or problem.get('message','')) if problem is not None else skipped.get('message','') if skipped is not None else ''
        rows.append({'id':case.get('classname','')+'::'+case.get('name',''),'status':status,
                     'seconds':float(case.get('time',0)),'reason':clean(reason),'evidence':str(path.relative_to(ROOT))})
    return rows


def feature(row):
    name=row['id']
    for key,label in [('hls','HLS'),('dash','DASH'),('resume','续传/恢复'),('recovery','续传/恢复'),('http','HTTP'),
                      ('network','网络异常'),('retry','网络异常'),('cookie','Cookie/认证'),('security','安全'),('proxy','安全'),
                      ('invalid_url','安全'),('dns','安全'),('redirect_private','安全'),('image','图片'),('audio','音频'),
                      ('media','媒体验证'),('web_extraction','HTML/动态页面'),('ui','GUI'),('concurrency','并发'),('scheduler','并发'),
                      ('instagram','网站解析'),('playlist','网站解析'),('aria2','aria2')]:
        if key in name:return label
    return '其他单元/回归'


GAPS=[
 {'id':'real-login','status':'BLOCKED','reason':'未使用个人浏览器登录态；本地 Cookie 认证与合成 Firefox 数据库已覆盖，真实账号授权仍需用户合法登录态'},
 {'id':'shorts-images','status':'BLOCKED','reason':'YouTube Shorts、Instagram 单图/轮播未取得可验证授权的真实下载样例；照片最大候选和轮播处理有现有单元回归'},
 {'id':'source-limits','status':'BLOCKED','reason':'Wikimedia 直链返回 403；Vimeo/Reddit 要求认证，TikTok 拒绝当前 IP；未绕过限制'},
 {'id':'upstream-sites','status':'FAIL','reason':'Facebook 页面数据解析失败、X 样例未找到视频；上游 yt-dlp 同样复现，尚未证明样例或上游可修复'},
 {'id':'5gb-powerloss','status':'SKIPPED','reason':'未执行可选 5GB/长期压力、物理断电、磁盘缓存损坏；已执行 100MB/1GB 确定性续传与提交恢复'},
 {'id':'clean-vm','status':'SKIPPED','reason':'未在干净 Windows VM 验收，宿主仍安装 Python；EXE smoke 会移除 PATH 的 Python 和外部工具'},
 {'id':'python-311','status':'SKIPPED','reason':'本机仅实际运行 Python 3.13.14；CI 定义 3.11/3.13，云端工作流尚未执行'},
 {'id':'wide-matrix','status':'SKIPPED','reason':'尚未逐项完成全部 MIME/音频编码/DRM 制式、DASH 字幕、多 Representation、多天签名更新、TLS/DNS 故障组合与符号链接磁盘异常矩阵'},
 {'id':'stream-resume','status':'UNSUPPORTED','reason':'不能证明跨会话一致的 HLS/DASH 分片安全重新下载；不承诺复用旧分片或破解 DRM'},
 {'id':'silent-ytdlp','status':'UNSUPPORTED','reason':'仅视频格式且没有可配对音轨时，现有格式选择不提供选项；静音直链允许按预期验证'},
 {'id':'translation','status':'UNSUPPORTED','reason':'日文仅预留翻译结构；英文动态错误信息仍不完全本地化'},
]


def generate(reports):
    reports=Path(reports)
    manifest=read_json(reports/'run_manifest.json',{})
    local=junit(reports/'offline.xml')
    stress=junit(reports/'stress.xml')
    commands=manifest.get('commands',[])
    online=clean(read_json(reports/'online.json',[])) if any(c['id']=='online' for c in commands) else []
    baselines=[]
    for path in sorted((reports/'baseline').glob('*.xml')):baselines+=junit(path)
    before_failed={row['id']:row for row in baselines if row['status']=='FAIL'}
    fixes=read_json(reports/'fixes.json',[])
    for fix in fixes:
        cases=[row for row in local if any(test in row['id'] for test in fix['tests'])]
        fix['regression_cases']=len(cases)
        fix['after']='PASS' if cases and all(row['status']=='PASS' for row in cases) else 'NOT_VERIFIED'
    counts=Counter(r['status'] for r in local)
    online_counts=Counter(r['status'] for r in online)
    features=defaultdict(Counter)
    for row in local:features[feature(row)][row['status']]+=1
    groups=[]
    for label,counter in sorted(features.items()):
        denominator=counter['PASS']+counter['FAIL']
        groups.append({'protocol':label,**dict(counter),'rate':round(counter['PASS']/denominator*100,2) if denominator else None})
    downloaded=[r for r in online if r.get('stage')=='integrity' and r['status']=='PASS']
    attempted=[r for r in online if r.get('id') in ('mdn-mp4','mdn-webm','commons-audio','commons-image')]
    data={'date':datetime.now(timezone(timedelta(hours=9))).isoformat(),'environment':manifest.get('environment',read_json(reports/'baseline/environment.json',{})),
          'base_commit':'43d66e354027b9f617cc846fbb6234a3d99a0051','report_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'baseline':{'existing_suite_pass':70,'existing_suite_fail':0,'new_reproduced_failures':len(before_failed)},
          'summary':{'local_total':len(local),'local_counts':dict(counts),'local_executed_rate':round(100*counts['PASS']/max(1,counts['PASS']+counts['FAIL']),2),
                     'online_counts':dict(online_counts),'verified_online_downloads':len(downloaded),'online_download_attempts':len(attempted),
                     'online_all_attempt_rate':round(100*len(downloaded)/max(1,len(attempted)),2),'platform_extraction_pass':sum(r.get('extraction')=='PASS' for r in online),
                     'fixed_bugs':sum(f['after']=='PASS' for f in fixes)},
          'protocols':groups,'commands':commands,'fixes':fixes,'online':online,'local':local,'stress':stress,
          'before_failures':list(before_failed.values()),'unexecuted_or_unresolved':GAPS,
          'notes':['PASS 只代表该用例实际断言已通过；协议成功率只按执行用例计算，不能等同于所有场景覆盖率。',
                   '平台只有提取通过不等同下载通过；未确认授权或超预算的电影未下载。',
                   '本地 HTTP fixture 经测试依赖注入访问精确 loopback origin；正式安全策略没有私网豁免。',
                   '保留并测试了原有 extractors.py/ui.py/docs/artifacts.sha256 三处未提交修改，不将它们混入本次代码提交。',
                   '基线日志保留不覆盖。中途生成器路径错误和 GUI 视图断言错误属于测试工具问题，修正后独立重跑，未计为产品 Bug。'],
          'next_steps':['补充各平台短小授权样例与合法登录态，逐项复测 BLOCKED/UNAVAILABLE。','在干净 Windows VM 和 Python 3.11 执行同一套本地测试及 EXE smoke。','继续扩展完整故障组合、DASH 字幕与多清晰度、HLS 自动受限碎片重试。']}
    data['gui']=read_json(reports/'gui/result.json',{})
    data['exe']={kind:read_json(reports/f'exe-{kind}/result.json',{}) for kind in ('onedir','onefile')}
    data['stress_evidence_scope']='reports/stress.xml 是独立执行的有界压力测试记录；不计入默认本地用例数。'
    data['source_sha256']={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'mediaharvester').rglob('*.py')}
    data=clean(data)
    (reports/'latest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# MediaHarvester 实际自动化验证报告','',f'测试日期：{data["date"]}（Asia/Tokyo）',f'基线提交：`{data["base_commit"]}`；报告生成时提交：`{data["report_commit"]}`。',
           '',f'原有基线：70 PASS / 0 FAIL。新增稳定复现失败用例：{len(before_failed)}。确认修复 Bug：{data["summary"]["fixed_bugs"]}。',
           f'本地回归：{dict(counts)}，实际执行通过率 {data["summary"]["local_executed_rate"]}%。跳过不计通过。',
           f'公网完整下载：{len(downloaded)}/{len(attempted)} 个尝试，含受限资源的总体通过率 {data["summary"]["online_all_attempt_rate"]}%；其余状态见下表。',
           '', '## 环境','', '```json',json.dumps(data['environment'],ensure_ascii=False,indent=2),'```',
           '', '## 协议与模块用例','', '| 分类 | PASS | FAIL | SKIPPED | 执行通过率 |','|---|---:|---:|---:|---:|']
    for group in groups:lines.append(f'| {group["protocol"]} | {group.get("PASS",0)} | {group.get("FAIL",0)} | {group.get("SKIPPED",0)} | {group["rate"]}% |')
    lines+=['','## 网站与公开素材','', '| ID / 网站 | 状态 | 提取 | 下载字节 | 原因 |','|---|---|---|---:|---|']
    for row in online:lines.append('| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in (row['id']+' / '+row['site'],row['status'],row.get('extraction',''),row.get('bytes',''),row.get('reason','完整性验证通过')))+' |')
    lines+=['','## 修复前后','', '| Bug | 问题 | 修改文件 | 重测 |','|---|---|---|---|']
    for fix in fixes:lines.append(f'| {fix["id"]} | {fix["problem"]} | {", ".join(fix["files"])} | {fix["after"]}；{fix["regression_cases"]} 用例 |')
    lines+=['','## 公网完整性证据','']
    for row in downloaded:lines.append(f'- {row["id"]}：{row["bytes"]} 字节，SHA-256 `{row["sha256"]}`；{row.get("streams",row.get("dimensions"))}。')
    lines+=['','## 命令与构建证据','']
    for command in commands:lines.append(f'- {command["id"]}：{command["status"]}；`{command.get("command","")}`；日志 `{command.get("log","")}`。')
    lines+=['','## 未解决、未执行或能力边界','']
    for gap in GAPS:lines.append(f'- **{gap["status"]}** {gap["id"]}：{gap["reason"]}')
    lines+=['','## 复现命令','', '```powershell', '.venv\\Scripts\\python.exe scripts\\run_full_tests.py --mode offline',
            '.venv\\Scripts\\python.exe scripts\\run_full_tests.py --mode online', '.venv\\Scripts\\python.exe scripts\\run_full_tests.py --mode full --build',
            '.venv\\Scripts\\python.exe scripts\\run_full_tests.py --mode stress', '```','', '## 判定说明','']
    lines += ['- '+note for note in data['notes']]
    lines+=['','## 下一步','']+['- '+step for step in data['next_steps']]
    (reports/'latest.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    def table(headers,rows):
        return '<table><thead><tr>'+''.join(f'<th data-col="{i}">{html.escape(str(h))} ↕</th>' for i,h in enumerate(headers))+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(cell))+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table>'
    body=f'<h1>MediaHarvester 实际自动化验证</h1><p>{html.escape(data["date"])}</p>'
    body+=f'<p>原有基线 70/70；新增复现失败 {len(before_failed)}；已验证修复 {data["summary"]["fixed_bugs"]}。</p>'
    body+=f'<p>本地 {html.escape(str(dict(counts)))}；实际执行通过率 {data["summary"]["local_executed_rate"]}%。公网完整下载 {len(downloaded)}/{len(attempted)}；平台提取不计下载成功。</p>'
    body+='<h2>环境和提交</h2><pre>'+html.escape(json.dumps(data['environment'],ensure_ascii=False,indent=2))+'</pre>'
    body+='<h2>协议与模块</h2>'+table(['分类','PASS','FAIL','SKIPPED','执行通过率'],[(g['protocol'],g.get('PASS',0),g.get('FAIL',0),g.get('SKIPPED',0),str(g['rate'])+'%') for g in groups])
    body+='<h2>网站与完整性</h2><p>点击表头排序。PASS 表示真实下载并验证；SKIPPED/BLOCKED 不表示通过。</p>'
    body+=table(['ID / 网站','状态','提取','字节','SHA-256','原因'],[(r['id']+' / '+r['site'],r['status'],r.get('extraction',''),r.get('bytes',''),r.get('sha256',''),r.get('reason','完整性验证通过')) for r in online])
    body+='<h2>自动修复前后</h2>'+table(['Bug','触发与问题','修改文件','重测','对应测试'],[(f['id'],f['problem'],', '.join(f['files']),f['after'],', '.join(f['tests'])) for f in fixes])
    body+='<h2>命令、GUI 与 EXE</h2>'+table(['阶段','状态','秒','可复现命令','日志'],[(c['id'],c['status'],c.get('seconds',''),c.get('command',''),c.get('log','')) for c in commands])
    body+='<h2>未解决与未执行</h2>'+table(['ID','状态','原因'],[(g['id'],g['status'],g['reason']) for g in GAPS])
    body+='<h2>失败案例与堆栈</h2>'
    for row in online+local:
        if row['status'] not in ('PASS','SKIPPED'):
            body+='<details><summary>'+html.escape(row['id']+' / '+row['status'])+'</summary><pre>'+html.escape(json.dumps(row,ensure_ascii=False,indent=2))+'</pre></details>'
    body+='<h2>原始失败与修复证据</h2>'
    for row in before_failed.values():body+='<details><summary>'+html.escape(row['id'])+'</summary><pre>'+html.escape(row['reason'])+'</pre></details>'
    body+='<h2>判定说明</h2><ul>'+''.join('<li>'+html.escape(n)+'</li>' for n in data['notes'])+'</ul>'
    body+='<h2>下一步</h2><ul>'+''.join('<li>'+html.escape(n)+'</li>' for n in data['next_steps'])+'</ul>'
    document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MediaHarvester 测试报告</title><style>body{font:15px/1.65 system-ui,sans-serif;max-width:1400px;margin:32px auto;padding:0 24px;color:#17243b;background:#f4f7fc}h1,h2{color:#12306a}table{border-collapse:collapse;width:100%;margin:20px 0;background:white}th,td{padding:10px;border:1px solid #dbe2ed;text-align:left;word-break:break-word}th{background:#e4edfa;cursor:pointer}pre{white-space:pre-wrap;word-break:break-word;background:white;padding:16px}details{padding:8px;border-bottom:1px solid #cad4e2}</style><body>'+body+'''<script>document.querySelectorAll('th').forEach(th=>th.addEventListener('click',()=>{const table=th.closest('table'),body=table.tBodies[0],i=Number(th.dataset.col),direction=th.dataset.order==='asc'?-1:1;th.dataset.order=direction===1?'asc':'desc';[...body.rows].sort((a,b)=>direction*a.cells[i].textContent.localeCompare(b.cells[i].textContent,'zh-CN',{numeric:true})).forEach(row=>body.append(row));}));</script></body></html>'''
    (reports/'latest.html').write_text(document,encoding='utf-8')
    failures=reports/'failures';failures.mkdir(exist_ok=True)
    for row in online+local:
        name=re.sub(r'[^a-zA-Z0-9_-]','_',row['id'])[:160]
        path=failures/(name+'.json')
        if row['status'] in ('FAIL','BLOCKED','UNAVAILABLE','FLAKY'):
            path.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
        elif row['status']=='PASS' and path.exists():
            previous=read_json(path,{})
            previous.update(status='PASS',fix_status='resolved',retest=row)
            path.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Generated reports/latest.html, latest.md, latest.json')
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reports',type=Path,default=ROOT/'reports')
    generate(parser.parse_args().reports)
