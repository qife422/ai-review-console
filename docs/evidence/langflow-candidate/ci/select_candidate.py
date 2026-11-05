"""Select one fully hash-checked candidate artifact from memory without replacement."""
import hashlib
import io
import json
import shutil
import stat
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

root = Path('/private/tmp/arc-langflow-candidate.qya6psom')
old = Path('/private/tmp/arc-runtime-maintenance.wT9huB')
spec = json.load(sys.stdin)
artifact = spec['artifact']
assert artifact['workflow_run']['head_sha'] == spec['source']
assert artifact['workflow_run']['id'] == spec['run']
assert spec['packet'] in {'second', 'third', 'fourth'}
out = root / 'ci/candidate' / spec['packet']
assert not out.exists()
assert artifact['size_in_bytes'] <= 8 * 1024**2
with urllib.request.urlopen(spec['url'], timeout=45) as response:
    raw = response.read(8 * 1024**2 + 1)
assert len(raw) == artifact['size_in_bytes']
assert 'sha256:' + hashlib.sha256(raw).hexdigest() == artifact['digest']
payload = {}
with ZipFile(io.BytesIO(raw)) as archive:
    infos = [i for i in archive.infolist() if not i.is_dir()]
    assert len(infos) <= 45 and sum(i.file_size for i in infos) <= 850000
    for info in infos:
        path = PurePosixPath(info.filename)
        assert not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename
        assert str(path) == info.filename and info.filename not in payload
        assert not stat.S_ISLNK(info.external_attr >> 16) and info.file_size <= 850000
        payload[info.filename] = archive.read(info)
        assert len(payload[info.filename]) == info.file_size
report = {'source':spec['source'],'run':spec['run'],'jobs':spec['jobs'],
          'artifact':{k:v for k,v in artifact.items() if k!='archive_download_url'},
          'method':'Memory-only bounded ZIP download; complete ZIP SHA/size, every member CRC/size/path checked; all original members selected without replacement.',
          'selected_originals':[{'path':n,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in payload.items()],
          'qualification':'Experimental candidate only; no default runtime change or full release acceptance.',
          'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
if 'metadata/arc-unit.xml' in payload:
    report['unit_suites']=[dict(x.attrib) for x in ET.fromstring(payload['metadata/arc-unit.xml'])]
if 'metadata/workflow.json' in payload:
    flow=json.loads(payload['metadata/workflow.json'])
    report['workflow']={'version':flow['langflow_version'],'components':flow['component_count'],'result':flow['result'],
        'source_formats':sorted({c['source_format'] for c in flow['cases']} | {flow['markdown_intake']['source_format']}),
        'decisions':[c['decision'] for c in flow['cases']],
        'report_count':sum(len(c['reports']) for c in flow['cases']),
        'same_stored_flow_hashes':flow['stored_flow_hashes_before']==flow['stored_flow_hashes_after'],
        'negative_retry':flow['failure_retry']}
for name in ['identity.json','summary.json','api.json','gui/result.json']:
    if name in payload:
        report[name]=json.loads(payload[name])
if 'inventory.json' in payload:
    inventory=json.loads(payload['inventory.json'])
    report['inventory_scope']={k:v for k,v in inventory.items() if k!='packages'}
    report['distribution_count']=len(inventory['packages'])
payload['selection.json']=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode()
files=[p for p in (root/'ci').rglob('*') if p.is_file()]
added=sum(map(len,payload.values()))
assert sum(p.stat().st_size for p in files)+added<=1024**2 and len(files)+len(payload)<=50
assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+added<=3*1024**2
assert sum(p.stat().st_size for r in [root,old] for p in r.rglob('*') if p.is_file())+added<=40*1024**2
assert shutil.disk_usage(root).free-added>1024**3
out.mkdir()
for name,content in payload.items():
    target=out/name
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:
        stream.write(content)
print(json.dumps({'root':str(out),'bytes':added,'files':len(payload),'ci_bytes':sum(p.stat().st_size for p in files)+added,'ci_files':len(files)+len(payload),'gui':report.get('gui/result.json'),'workflow':report.get('workflow'),'distribution_count':report.get('distribution_count')}))
