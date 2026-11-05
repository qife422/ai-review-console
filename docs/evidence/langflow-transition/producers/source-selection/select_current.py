import hashlib,io,json,re,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/private/tmp/arc-langflow-transition.l7tcavqh'); OUT=ROOT/'ci/current'; assert not any(OUT.iterdir())
API='repos/qife422/ai-review-console/actions/'
def get(x): return subprocess.check_output(['gh','api','--allow-escape-sequences',API+x])
def sha(x): return hashlib.sha256(x).hexdigest()
def jb(x): return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def ref(a,n,b,method): return {'artifact_id':a,'member_path':n,'original_bytes':len(b),'original_sha256':sha(b),'method':method}
out={}; refs={}; aid=13382177124
run=json.loads(get('runs/41953014467')); jobs=json.loads(get('runs/41953014467/jobs'))
assert run['head_sha']=='a1190a38e998ce9683495a07028a1b9e589303cf' and run['conclusion']=='success'
out['run.json']=jb({'run_id':run['id'],'source':run['head_sha'],'conclusion':run['conclusion'],'url':run['html_url'],'jobs':[{'id':j['id'],'name':j['name'],'conclusion':j['conclusion'],'steps':[{'name':s['name'],'conclusion':s['conclusion']} for s in j['steps']]} for j in jobs['jobs']]}); refs['run.json']=[{'method':'selected GitHub API run and job fields','run_url':run['url'],'jobs_url':run['jobs_url']}]
zipbytes=get(f'artifacts/{aid}/zip'); z=zipfile.ZipFile(io.BytesIO(zipbytes)); assert len(zipbytes)<5*1024*1024
def raw(name,member):
 b=z.read(member);out[name]=b;refs[name]=[ref(aid,member,b,'original member bytes')];return b
def derived(member):
 b=z.read(member);return json.loads(b),ref(aid,member,b,'selected fields; omitted unrelated inventory and text')
raw('workflow.json','workflow.json');raw('probe.json','release/dependency-compatibility.stdout');raw('image-summary.json','release/images/summary.json');inv=json.loads(raw('langflow-inventory.json','release/images/langflow-inventory.json'))
m,mref=derived('release/manifest.json'); lic,lref=derived('release/licenses/langflow.json');
packages=inv['packages']; py=[p for p in packages if p['type']=='pypi']; canon=lambda n: re.sub(r'[-_.]+','-',n).lower(); actual={canon(p['name']):p['version'] for p in py}; baseline=Path('compliance/langflow-candidate.in').read_bytes(); expected={canon(line.split('==')[0]):line.split('==')[1] for line in baseline.decode().splitlines() if line and not line.startswith('#')}; assert len(py)==len(actual)
compare={'image_id':inv['identity']['id'],'expected_path':'compliance/langflow-candidate.in','expected_sha256':sha(baseline),'expected_count':len(expected),'actual_count':len(actual),'missing':sorted(set(expected)-set(actual)),'extra':sorted(set(actual)-set(expected)),'changed':[{'name':k,'expected':expected[k],'actual':actual[k]} for k in sorted(expected.keys() & actual.keys()) if expected[k]!=actual[k]],'apt_rows':[p for p in packages if p['name'] in ('apt','libapt-pkg6.0') and p['type']=='deb']}
out['inventory-comparison.json']=jb(compare);refs['inventory-comparison.json']=[ref(aid,'release/images/langflow-inventory.json',z.read('release/images/langflow-inventory.json'),'normalized name and exact version comparison; selected APT rows'),{'path':'compliance/langflow-candidate.in','original_bytes':len(baseline),'original_sha256':sha(baseline)}]
result=lic['result']; names=['Langflow-LICENSE.txt','sqlite-vec-LICENSE-MIT.txt','sqlite-vec-LICENSE-APACHE.txt']; project=[]
for name in names:
 p=next(x for x in result['project_files'] if x['path']=='/app/licenses/'+name); repo=Path('licenses')/name; rb=repo.read_bytes(); text=p.get('text','').encode(); project.append({**{k:v for k,v in p.items() if k!='text'},'repository_path':str(repo),'repository_sha256':sha(rb),'exact_hash_match':p.get('sha256')==sha(rb),'text_bytes_hash_match':sha(text)==p.get('sha256')})
selected=[]
for p in result['selected_packages']:
 if p['name'].lower() not in ('langflow-base','lfx','apsw','sqlite-vec','psycopg','ibm-watsonx-ai','ibm-cloud-sdk-core'): continue
 selected.append({k:v for k,v in p.items() if k!='license_files'} | {'license_files':[{k:v for k,v in f.items() if k!='text'} for f in p.get('license_files',[])]})
out['collector-license-summary.json']=jb({'collector':{k:m.get(k) for k in ('images','os_identity','system_materials','native_materials','collection_state','audits','release_acceptance','source_inputs')},'license':{'image_id':lic['image_id'],'collection_state':lic['collection_state'],'legal_approval':result['legal_approval'],'limitations':result['limitations'],'project_files':project,'selected_packages':selected,'selected_not_installed':result['selected_not_installed']}});refs['collector-license-summary.json']=[mref,lref]
uz=zipfile.ZipFile(io.BytesIO(get('artifacts/13381667891/zip'))); ub=uz.read('arc-unit.xml');u=ET.fromstring(ub);log=get('jobs/127001150301/logs');lines=[re.sub(r'\x1b\[[0-9;]*m','',x) for x in log.decode(errors='replace').splitlines() if 'Tests ' in x or 'Test Files ' in x];out['tests-summary.json']=jb({'python_suites':[e.attrib for e in u.findall('testsuite')],'frontend_log_lines':lines});refs['tests-summary.json']=[ref(13381667891,'arc-unit.xml',ub,'XML suite attributes only'),{'api':'jobs/127001150301/logs','original_bytes':len(log),'original_sha256':sha(log),'method':'selected Vitest summary lines, ANSI removed'}]
selection={'run_id':run['id'],'source_sha':run['head_sha'],'method':'gh API HTTPS authenticated; ZIP and unselected material held in memory; no native collection','files':[{'path':n,'selected_bytes':len(b),'selected_sha256':sha(b),'sources':refs[n]} for n,b in out.items()]};out['selection.json']=jb(selection)
print('sizes',[(k,len(v)) for k,v in out.items()]); assert len(out)<=15 and sum(map(len,out.values()))<=350*1024
assert sum(p.stat().st_size for p in (ROOT/'ci').rglob('*') if p.is_file())+sum(map(len,out.values()))<=1024*1024
assert sum(1 for p in (ROOT/'ci').rglob('*') if p.is_file())+len(out)<=50
assert sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())+sum(map(len,out.values()))<=2*1024*1024
for n,b in out.items():
 with (OUT/n).open('xb') as f:f.write(b)
print('comparison',compare);print('project',project);print('tests',out['tests-summary.json'].decode());print('total',sum(map(len,out.values())))
