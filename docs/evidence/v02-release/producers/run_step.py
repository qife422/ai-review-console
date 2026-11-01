from pathlib import Path
from datetime import datetime, timezone
import argparse, subprocess, json, time, os, hashlib
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--timeout',type=int,default=300);p.add_argument('cmd',nargs=argparse.REMAINDER);a=p.parse_args()
root=Path(__file__).resolve().parent; out=root/'steps';out.mkdir(exist_ok=True)
assert a.label.replace('-','').isalnum();paths={ext:out/(a.label+'.'+ext) for ext in ['stdout','stderr','record.json']};assert not any(x.exists() for x in paths.values())
def size():
 total=count=0
 for base,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if (Path(base)/d)!=root/'tool-cache']
  for f in files:total+=(Path(base)/f).lstat().st_size;count+=1
 return total,count
start=datetime.now(timezone.utc).isoformat();begin=time.monotonic();reason=None
with paths['stdout'].open('xb') as stdout,paths['stderr'].open('xb') as stderr:
 proc=subprocess.Popen(a.cmd,stdout=stdout,stderr=stderr,env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1'})
 while proc.poll() is None:
  b,n=size()
  if time.monotonic()-begin>a.timeout:reason='timeout'
  if b>240*1048576 or n>9500 or paths['stdout'].stat().st_size>40*1048576 or paths['stderr'].stat().st_size>20*1048576:reason='capacity_guard'
  if reason:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill()
   break
  time.sleep(.4)
 code=proc.wait()
record={'command':a.cmd,'cwd':os.getcwd(),'started_at':start,'ended_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,'exit_code':code,'stop_reason':reason,'files':{k:{'path':str(v),'bytes':v.stat().st_size,'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for k,v in paths.items() if k!='record.json'}}
paths['record.json'].write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(code)
