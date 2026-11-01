import json,hashlib,subprocess,datetime,re
from pathlib import Path
import httpx
ROOT=Path('/private/tmp/arc-v02-release-close.p3RyvK');OUT=ROOT/'native';ids=json.loads((OUT/'images.json').read_text()); records=[];proof={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':'fac92ea797c96cd8d12581bf616d0295e8312186','images':ids,'claims':'native dependency consistency, exact selected pins, and pre-failure synthetic case/report preservation only'}
for name in ['api','langflow']:
 cmd=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python',ids[name],'-m','pip','check'];r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);records.append({'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0
pins=dict(re.findall(r'([a-zA-Z0-9_.-]+)==([a-zA-Z0-9_.+-]+)',Path('docker/langflow.Dockerfile').read_text()))
code='import sys,json,importlib.metadata as m;print(json.dumps({p:m.version(p) for p in json.loads(sys.argv[1])},sort_keys=True))'
cmd=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python',ids['langflow'],'-c',code,json.dumps(list(pins))];r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);assert r.returncode==0;rversions=json.loads(r.stdout);assert rversions==pins;proof['langflow_exact_pins']=rversions
before=json.loads((ROOT/'workflow.json').read_text());checks=[]
with httpx.Client(base_url='http://127.0.0.1:8080',timeout=10) as client:
 for case in before['cases']:
  r=client.get('/api/cases/'+case['case_id']);r.raise_for_status();d=r.json();assert d['decision_id']==case['decision_id'];assert d['document_hash']==case['source_sha256']
  report_checks=[]
  for expected in case['reports']:
   artifact=next(x for x in d['reports'] if x['format']==expected['format']);response=client.get('/api/cases/'+case['case_id']+'/report/'+expected['format'],params={'report_id':artifact.get('report_id',artifact.get('id'))});response.raise_for_status();actual=hashlib.sha256(response.content).hexdigest();assert actual==expected['sha256'] and len(response.content)==expected['bytes'];report_checks.append({'format':expected['format'],'sha256':actual,'bytes':len(response.content)})
  checks.append({'case_id':case['case_id'],'decision_id':case['decision_id'],'document_hash':d['document_hash'],'reports':report_checks})
 for section in ['markdown_intake','failure_retry']:
  case=before[section];caseid=case['case_id'];r=client.get('/api/cases/'+caseid);r.raise_for_status();checks.append({'case_id':caseid,'state':r.json()['status'],'preserved':True})
proof.update(preserved_cases=checks,commands=records,result='passed')
(OUT/'preservation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'result':'passed','cases_preserved':len(checks),'reports_preserved':sum(len(c.get('reports',[])) for c in checks),'pins':len(pins)},ensure_ascii=False))
