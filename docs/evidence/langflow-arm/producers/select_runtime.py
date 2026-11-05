"""Select compact evidence from the fixed successful ARM/AMD candidate CI run."""
import hashlib, io, json, re, subprocess, sys, zipfile, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/private/tmp/arc-langflow-arm.tlmz8anp')
OUT = ROOT / 'ci/runtime'
API = 'repos/qife422/ai-review-console/actions/'
RUN = 41979142562
SOURCE = 'e6f6fe7b908b7fab1b4f85e9f5a4fa22890fc923'
ZIP_LIMIT = 16 * 1024 * 1024
assert not OUT.exists(), 'Refusing to overwrite selection'

def get(path, limit=ZIP_LIMIT):
    proc = subprocess.Popen(['gh', 'api', '--allow-escape-sequences', API + path], stdout=subprocess.PIPE)
    data = proc.stdout.read(limit + 1)
    if len(data) > limit:
        proc.kill(); proc.wait(); raise ValueError('API response exceeds bound')
    assert proc.wait() == 0, 'GitHub API request failed'
    return data

def sha(data): return hashlib.sha256(data).hexdigest()
def encoded(obj): return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
def usage(root):
    paths = list(root.rglob('*'))
    assert not any(p.is_symlink() for p in paths)
    return sum(p.stat().st_size for p in paths if p.is_file()), sum(p.is_file() for p in paths)
def source(artifact, name, data, method):
    return {'artifact_id': artifact, 'member_path': name, 'original_bytes': len(data),
            'original_sha256': sha(data), 'method': method}

run_raw=get(f'runs/{RUN}'); jobs_raw=get(f'runs/{RUN}/jobs'); run=json.loads(run_raw); jobs=json.loads(jobs_raw)['jobs']
assert run['id']==RUN and run['head_sha']==SOURCE and run['conclusion']=='success'
assert len(jobs)==5 and all(j['conclusion']=='success' for j in jobs), 'Expected verify and four successful lanes'
def candidate_job(all_jobs, label):
    matches = [j for j in all_jobs if 'candidate' in j['name'] and j['labels'] == [label]]
    assert len(matches) == 1, 'Expected unique candidate job for ' + label
    return matches[0]
arm_job = candidate_job(jobs, 'ubuntu-24.04-arm')
amd_job = candidate_job(jobs, 'ubuntu-latest')
for job, state in ((arm_job, 'skipped'), (amd_job, 'success')):
    gui = next(s for s in job['steps'] if s['name']=='Keyboard upload to decision and downloadable reports')
    assert gui['conclusion']==state, 'Unexpected GUI scope or result' 
artifacts_raw=get(f'runs/{RUN}/artifacts'); artifacts=json.loads(artifacts_raw)['artifacts']
by_name={a['name']: a for a in artifacts}; assert len(by_name)==len(artifacts)
outputs={}; refs={}
outputs['run.json']=encoded({'id':RUN,'source':SOURCE,'url':run['html_url'],'conclusion':run['conclusion'],
  'jobs':[{'id':j['id'],'name':j['name'],'labels':j['labels'],'conclusion':j['conclusion'],'steps':[{'name':s['name'],'conclusion':s['conclusion']} for s in j['steps']]} for j in jobs]})
refs['run.json']=[{'api':'runs and jobs','run_bytes':len(run_raw),'run_sha256':sha(run_raw),'jobs_bytes':len(jobs_raw),'jobs_sha256':sha(jobs_raw),'method':'selected run, jobs and step fields'}]

def artifact(name):
    a=by_name[name]; assert not a['expired'] and a['size_in_bytes'] <= ZIP_LIMIT
    assert a['workflow_run']['head_sha']==SOURCE and a['workflow_run']['id']==RUN
    assert re.fullmatch(r'sha256:[0-9a-f]{64}', a['digest'])
    blob=get(f"artifacts/{a['id']}/zip")
    assert len(blob)==a['size_in_bytes'] and 'sha256:'+sha(blob)==a['digest'], 'Artifact transport mismatch'
    z=zipfile.ZipFile(io.BytesIO(blob)); names=[i.filename for i in z.infolist()]
    assert len(names)==len(set(names)), 'Duplicate ZIP members'
    return a,z

def member(a,z,path):
    info=z.getinfo(path); assert not info.is_dir() and info.file_size <= 4*1024*1024
    b=z.read(info); assert len(b)==info.file_size
    return b, source(a['id'],path,b,'original member bytes')
def raw(a,z,name,path):
    b,r=member(a,z,path); outputs[name]=b; refs[name]=[r]; return b

def compare(inv, arch):
    pins=Path('compliance/langflow-candidate.in').read_bytes()
    canon=lambda n:re.sub(r'[-_.]+','-',n).lower()
    lines=[s for s in pins.decode().splitlines() if s and not s.startswith('#')]
    expected={canon(s.split('==')[0]):s.split('==')[1] for s in lines}
    py=[p for p in inv['packages'] if p['type']=='pypi']
    actual={canon(p['name']):p['version'] for p in py}
    assert len(lines)==len(expected) and len(py)==len(actual)
    lockpath=Path('compliance/langflow-candidate'+('-arm64' if arch=='arm64' else '')+'.lock')
    lock=lockpath.read_bytes()
    return {'image_id':inv['identity']['id'],'architecture':inv['identity']['architecture'],
      'pins_path':'compliance/langflow-candidate.in','pins_sha256':sha(pins),'lock_path':str(lockpath),'lock_sha256':sha(lock),
      'qualification':'Actual installed name/version set compared with pins; lock hash identifies source input, not installed wheel bytes.',
      'expected_count':len(expected),'actual_count':len(actual), 'missing':sorted(expected.keys()-actual.keys()),
      'extra':sorted(actual.keys()-expected.keys()),'changed':[{'name':k,'expected':expected[k],'actual':actual[k]} for k in sorted(expected.keys() & actual.keys()) if expected[k]!=actual[k]]}

for arch in ('arm64','amd64'):
    a,z=artifact('workflow-browser-verification-candidate-'+arch)
    workflow=raw(a,z,arch+'-workflow.json','workflow.json')
    assert json.loads(workflow)['langflow_version']=='1.13.1'
    if arch=='arm64': raw(a,z,'arm64-probe.json','release/dependency-compatibility.stdout')
    inv_b,inv_ref=member(a,z,'release/images/langflow-inventory.json'); inv=json.loads(inv_b)
    assert inv['identity']['architecture']==arch
    if arch=='arm64': outputs['arm64-inventory.json']=inv_b;refs['arm64-inventory.json']=[inv_ref]
    comp=compare(inv,arch)
    assert comp['expected_count']==334 and comp['actual_count']==334 and not any(comp[k] for k in ('missing','extra','changed'))
    outputs[arch+'-comparison.json']=encoded(comp);refs[arch+'-comparison.json']=[inv_ref,{'path':comp['pins_path'],'sha256':comp['pins_sha256']},{'path':comp['lock_path'],'sha256':comp['lock_sha256']}]
    summ_b,summ_ref=member(a,z,'release/images/summary.json'); summ=json.loads(summ_b)
    if arch=='arm64': outputs['arm64-image-summary.json']=summ_b;refs['arm64-image-summary.json']=[summ_ref]
    m_b,m_ref=member(a,z,'release/manifest.json'); m=json.loads(m_b)
    lic_b,lic_ref=member(a,z,'release/licenses/langflow.json'); lic=json.loads(lic_b); lr=lic['result']
    assert m['collection_state']=='collected' and m['images']['langflow']==inv['identity']['id']==lic['image_id']
    assert m['os_identity']['id']=='debian' and m['os_identity']['version_id']=='12'
    assert m['native_materials']['state']=='not_collected_this_image'
    assert lr['legal_approval'] is False, 'License collection is not legal approval'
    names=('Langflow-LICENSE.txt','sqlite-vec-LICENSE-MIT.txt','sqlite-vec-LICENSE-APACHE.txt'); notices=[]
    for n in names:
        p=next(x for x in lr['project_files'] if x['path']=='/app/licenses/'+n); local=Path('licenses')/n; lb=local.read_bytes()
        assert p['state']=='recorded' and p['sha256']==sha(lb) and p['bytes']==len(lb), 'Notice mismatch: '+n
        assert sha(p['text'].encode('utf-8'))==p['sha256'], 'Notice text hash mismatch: '+n
        notices.append({**{k:v for k,v in p.items() if k!='text'},'repository_path':str(local),'repository_sha256':sha(lb),'exact_hash_match':True,'text_bytes_hash_match':True})
    compact={'collector':{k:m.get(k) for k in ('images','os_identity','native_materials','system_materials','collection_state','audits','release_acceptance','source_inputs')},
      'scan':{**{k:summ.get(k) for k in ('result','unique_queries','observed_unique_advisory_ids','mapping_unknown','query_unknown','detail_unknown')},
              'images':{k:{x:v for x,v in p.items() if x!='findings'} for k,p in summ['images'].items()}},
      'license':{'image_id':lic['image_id'],'legal_approval':lr['legal_approval'],'project_files':notices,'selected_not_installed':lr['selected_not_installed']}}
    outputs[arch+'-summary.json']=encoded(compact);refs[arch+'-summary.json']=[m_ref,summ_ref,lic_ref]+[{'path':x['repository_path'],'sha256':x['repository_sha256']} for x in notices]

unit,uz=artifact('unit-verification'); ub,ur=member(unit,uz,'arc-unit.xml'); xml=ET.fromstring(ub)
verify=next(j for j in jobs if j['name']=='verify'); log=get(f"jobs/{verify['id']}/logs"); lines=[re.sub(r'\x1b\[[0-9;]*m','',line) for line in log.decode(errors='replace').splitlines() if 'Tests ' in line or 'Test Files ' in line]
outputs['tests.json']=encoded({'suites':[x.attrib for x in xml.findall('testsuite')],'frontend_log_lines':lines})
refs['tests.json']=[ur,{'api':f"jobs/{verify['id']}/logs",'original_bytes':len(log),'original_sha256':sha(log),'method':'selected Vitest summary lines, ANSI removed'}]
selection={'run':RUN,'source':SOURCE,'method':'GitHub API; ZIP checked against API digest and held only in memory; derived fields labeled','artifacts':[{k:a[k] for k in ('id','name','size_in_bytes','digest')} for a in artifacts if a['name'] in ('unit-verification','workflow-browser-verification-candidate-amd64','workflow-browser-verification-candidate-arm64')],
  'files':[{'path':n,'selected_bytes':len(b),'selected_sha256':sha(b),'sources':refs[n]} for n,b in outputs.items()]}
outputs['selection.json']=encoded(selection)
size=sum(map(len,outputs.values())); ci_size,ci_files=usage(ROOT/'ci'); total,_=usage(ROOT)
assert len(outputs)<=16 and size<=350*1024 and ci_size+size<=600*1024 and ci_files+len(outputs)<=40
assert total+size<=1024*1024 and 40437825+total+size<=40*1024*1024
OUT.mkdir()
try:
    for name,data in outputs.items():
        if name=='selection.json': continue
        with (OUT/name).open('xb') as f:f.write(data)
    with (OUT/'selection.json').open('xb') as f:f.write(outputs['selection.json'])
except BaseException:
    print('Selection incomplete: selection.json absent unless final write succeeded',file=sys.stderr);raise
print(json.dumps({'files':len(outputs),'bytes':size,'path':str(OUT)},indent=2))
