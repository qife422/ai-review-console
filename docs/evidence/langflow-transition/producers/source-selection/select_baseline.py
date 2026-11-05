import hashlib, io, json, subprocess, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/private/tmp/arc-langflow-transition.l7tcavqh')
OUT=ROOT/'ci/baseline'
assert not any(OUT.iterdir())
assert sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) < 2*1024*1024
API='repos/qife422/ai-review-console/actions/'
def get(p): return subprocess.check_output(['gh','api','--allow-escape-sequences',API+p])
def sha(b): return hashlib.sha256(b).hexdigest()
def jsonbytes(x): return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def source(a,n,b,method): return {'artifact_id':a,'member_path':n,'original_bytes':len(b),'original_sha256':sha(b),'method':method}
run=json.loads(get('runs/41951752227')); jobs=json.loads(get('runs/41951752227/jobs'))
assert run['head_sha']=='8ac0c79b8f0099e5dd7baed799b92a76692f3e67' and run['conclusion']=='success'
metadata={'run_id':run['id'],'source':run['head_sha'],'conclusion':run['conclusion'],'html_url':run['html_url'],'jobs':[{'id':j['id'],'name':j['name'],'conclusion':j['conclusion'],'steps':[{'name':s['name'],'conclusion':s['conclusion']} for s in j['steps']]} for j in jobs['jobs']]}
outputs={}; provenance={}
outputs['run.json']=jsonbytes(metadata)
provenance['run.json']=[{'method':'selected run/job fields from GitHub API','url':run['url'],'jobs_url':run['jobs_url']}]
for arch,aid in [('amd64',13381093938),('arm64',13381362265)]:
 rawzip=get(f'artifacts/{aid}/zip'); z=zipfile.ZipFile(io.BytesIO(rawzip)); assert len(rawzip)<5*1024*1024
 def read(n): return z.read(n)
 def add_raw(out,n):
  b=read(n); outputs[out]=b; provenance[out]=[source(aid,n,b,'original member bytes')]
 add_raw(arch+'-workflow.json','workflow.json')
 add_raw(arch+'-probe.json','release/dependency-compatibility.stdout')
 refs=[]
 def derive(n):
  b=read(n); refs.append(source(aid,n,b,'selected fields from JSON; findings and inventories omitted')); return json.loads(b)
 m=derive('release/manifest.json'); img=derive('release/images/summary.json'); rh=derive('release/rhel/summary.json'); lic=derive('release/licenses/manifest.json')
 licenses={}
 for image in ['api','langflow','web']:
  d=derive('release/licenses/'+image+'.json'); result=d['result']; licenses[image]={'image_id':d['image_id'],'collection_state':d['collection_state'],'project_files': [{k:v for k,v in f.items() if k not in ('text','content','base64')} for f in result.get('project_files',[])]}
 result={'collector':{k:m.get(k) for k in ('images','os_identity','system_materials','native_materials','collection_state','audits','release_acceptance','source_inputs')},'image_summary':{**{k:img.get(k) for k in ('result','unique_queries','observed_unique_advisory_ids','mapping_unknown','query_unknown','detail_unknown')},'images':{k:{x:v for x,v in d.items() if x!='findings'} for k,d in img['images'].items()}},'rhel_summary':rh,'license_manifest':lic,'license_project_files':licenses}
 outputs[arch+'-summary.json']=jsonbytes(result); provenance[arch+'-summary.json']=refs
z=zipfile.ZipFile(io.BytesIO(get('artifacts/13381500876/zip'))); b=z.read('arc-unit.xml'); xml=ET.fromstring(b)
outputs['unit-summary.json']=jsonbytes({'root':xml.tag,'attributes':xml.attrib,'suites':[x.attrib for x in xml.findall('testsuite')]})
provenance['unit-summary.json']=[source(13381500876,'arc-unit.xml',b,'XML suite attributes only; original exceeds 30 KiB')]
log=get('jobs/126997067335/logs'); lines=[x for x in log.decode(errors='replace').splitlines() if 'Tests ' in x or 'Test Files ' in x]
outputs['frontend-summary.json']=jsonbytes({'matching_log_lines':lines})
provenance['frontend-summary.json']=[{'api':'jobs/126997067335/logs','original_bytes':len(log),'original_sha256':sha(log),'method':'selected Vitest Tests and Test Files lines; log held in memory only'}]
selection={'run_id':run['id'],'source_sha':run['head_sha'],'method':'gh api HTTPS authenticated; artifact ZIP held in memory; original member bytes or explicitly selected derived fields','files':[{'path':n,'selected_bytes':len(b),'selected_sha256':sha(b),'sources':provenance[n]} for n,b in outputs.items()]}
outputs['selection.json']=jsonbytes(selection)
print('sizes',[(k,len(v)) for k,v in outputs.items()]); assert len(outputs)<=10 and sum(map(len,outputs.values()))<=120*1024
assert sum(p.stat().st_size for p in (ROOT/'ci').rglob('*') if p.is_file())+sum(map(len,outputs.values()))<=1024*1024
assert sum(1 for p in (ROOT/'ci').rglob('*') if p.is_file())+len(outputs)<=50
assert sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())+sum(map(len,outputs.values()))<=2*1024*1024
for n,b in outputs.items():
 with (OUT/n).open('xb') as f: f.write(b)
print('selected',len(outputs),'files',sum(map(len,outputs.values())),'bytes')
print('frontend',lines)
print('unit',outputs['unit-summary.json'].decode())
