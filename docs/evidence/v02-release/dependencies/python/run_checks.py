from pathlib import Path
import subprocess,json,hashlib,datetime,os,concurrent.futures
root=Path.cwd(); out=Path('/private/tmp/arc-v02-release-close.p3RyvK/python')
commands=[
 ('pip-check',['.venv/bin/pip','check']),
 ('audit-after',['.venv/bin/pip-audit','--requirement','requirements.lock','--no-deps','--disable-pip','--strict','--timeout','30','--progress-spinner','off','--cache-dir','/private/tmp/arc-v02-release-close.p3RyvK/tool-cache/python/audit','--format','json']),
 ('ruff',['.venv/bin/ruff','check','.']),
 ('pytest',['.venv/bin/pytest','--junitxml='+str(out/'pytest.xml')]),
]
inputs=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in map(Path,['pyproject.toml','requirements.lock','docker/langflow.Dockerfile'])]
def run(item):
 label,cmd=item; start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (out/(label+'.stdout')).open('xb') as stdout,(out/(label+'.stderr')).open('xb') as stderr:
  proc=subprocess.run(cmd,stdout=stdout,stderr=stderr,env=os.environ|{'PIP_CACHE_DIR':'/private/tmp/arc-v02-release-close.p3RyvK/tool-cache/python'},timeout=300)
 record={'command':cmd,'cwd':str(root),'started_at':start,'ended_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':proc.returncode,'inputs':inputs,'outputs':{suffix:{'name':label+'.'+suffix,'bytes':(out/(label+'.'+suffix)).stat().st_size,'sha256':hashlib.sha256((out/(label+'.'+suffix)).read_bytes()).hexdigest()} for suffix in ['stdout','stderr']}}
 (out/(label+'.record.json')).write_text(json.dumps(record,indent=2)+'\n'); return label,proc.returncode
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(run,commands): print(result,flush=True)
