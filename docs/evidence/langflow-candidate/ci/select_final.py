"""Verify the successful candidate ZIP in memory and select its qualified closure."""
import hashlib
import io
import json
import re
import shutil
import stat
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

root=Path('/private/tmp/arc-langflow-candidate.qya6psom')
old=Path('/private/tmp/arc-runtime-maintenance.wT9huB')
out=root/'ci/candidate/final'
spec=json.load(sys.stdin)
artifact=spec['artifact']
assert not out.exists()
assert artifact['workflow_run']['head_sha']==spec['source']=='e73ab92321483403fafd03e721182c5426ae6359'
assert artifact['workflow_run']['id']==spec['run']==41943564415
assert all(j['status']=='completed' and j['conclusion']=='success' for j in spec['jobs'])
assert artifact['size_in_bytes']<=8*1024**2
with urllib.request.urlopen(spec['url'],timeout=45) as response:
    raw=response.read(8*1024**2+1)
sha=lambda data:hashlib.sha256(data).hexdigest()
assert len(raw)==artifact['size_in_bytes'] and 'sha256:'+sha(raw)==artifact['digest']
payload={};members={};refs=[];omitted=[]
with ZipFile(io.BytesIO(raw)) as archive:
    infos=[i for i in archive.infolist() if not i.is_dir()]
    assert len(infos)<=50 and sum(i.file_size for i in infos)<=1024**2
    for info in infos:
        p=PurePosixPath(info.filename)
        assert not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename
        assert str(p)==info.filename and info.filename not in members
        assert not stat.S_ISLNK(info.external_attr>>16)
        data=archive.read(info)
        assert len(data)==info.file_size
        member={'path':info.filename,'bytes':len(data),'sha256':sha(data)}
        members[info.filename]=member
        if info.filename in {'metadata/arc-unit.xml','metadata/services.json','metadata/runtime.log'}:
            omitted.append(member)
        elif info.filename=='inventory.json' and data==(root/'ci/candidate/second/inventory.json').read_bytes():
            refs.append(member|{'exact_original_reference':'ci/candidate/second/inventory.json','comparison':'Complete bytes equal, not semantic equivalence'})
        else:
            payload[info.filename]=data
    unit=[dict(x.attrib) for x in ET.fromstring(archive.read('metadata/arc-unit.xml'))]
    inventory=json.loads(archive.read('inventory.json'))
    flow=json.loads(archive.read('metadata/workflow.json'))
    scan=json.loads(archive.read('metadata/scan/summary.json'))
    native=json.loads(archive.read('native-license-texts.json'))
    identity=json.loads(archive.read('identity.json'))
    gui=json.loads(archive.read('gui/result.json'))
    normalized=lambda name:re.sub(r'[-_.]+','-',name).lower()
    packages={normalized(p['name']):p['version'] for p in inventory['packages']}
    native_records=[f for f in native['files'] if f['state']=='recorded']
    assert native['read_files']==len(native_records)
    assert native['input_bytes']==sum(f['bytes'] for f in native_records)
    for f in native_records:
        if 'text' in f:
            assert len(f['text'].encode())==f['bytes'] and sha(f['text'].encode())==f['sha256']
    assert 0<=native['read_files']<=6 and native['read_files']<=7 and native['input_bytes']<=256*1024
    observed={'distribution_count':len(inventory['packages']),
        'inventory_scope':'Python distribution metadata only; never divide by baseline mixed RPM+Python inventory count.',
        'python':inventory['python'],'psycopg_implementation':inventory['psycopg_implementation'],'libpq_runtime_version':inventory['libpq_runtime_version'],
        'prior_five_packages':{n:{'installed':n in packages,'version':packages.get(n)} for n in ['chromadb','couchbase','filelock','pillow','setuptools']},
        'target_names':{n:{'installed':n in packages,'version':packages.get(n)} for n in ['langflow','langflow-base','lfx','lfx-ibm','lfx-bundles','zep-python','zep-cloud','ibm-db','psycopg','psycopg-binary','psycopg2-binary']},
        'gui':gui,'unit':{'original':members['metadata/arc-unit.xml'],'suites':unit,'qualification':'Derived counts and fingerprint only; this current XML is not selected.'},
        'workflow':{'result':flow['result'],'runtime':flow['langflow_version'],'components':flow['component_count'],
            'source_formats':sorted({c['source_format'] for c in flow['cases']}|{flow['markdown_intake']['source_format']}),
            'decisions':[c['decision'] for c in flow['cases']],'report_count':sum(len(c['reports']) for c in flow['cases']),
            'same_stored_flow_hashes':flow['stored_flow_hashes_before']==flow['stored_flow_hashes_after'],
            'negative_retry':flow['failure_retry']['result']},
        'scan':scan,
        'native_actual':{'read_files':native['read_files'],'input_bytes':native['input_bytes'],
            'records':[{k:v for k,v in f.items() if k!='text'} for f in native['files']],
            'prior_cumulative':{'files':7,'input_bytes':26796382,'text_bytes':3971111,'known_goal_input_bytes':135835179},
            'derived_remaining':{'files':7-native['read_files'],'input_bytes':26796382-native['input_bytes'],'text_bytes':3971111-native['input_bytes'],
                                 'known_goal_input_bytes':135835179+native['input_bytes']},
            'accounting':'Actual declared-file reads charged once, input bytes also reserved conservatively against remaining text capacity. This does not include ordinary metadata/scan hashing or grant full native distribution approval.'}}
    assert identity['source']==spec['source']
    assert scan['images']['langflow']['image_id']==identity['image_id']
report={'source':spec['source'],'run':spec['run'],'jobs':spec['jobs'],
    'artifact':{k:v for k,v in artifact.items() if k!='archive_download_url'},
    'method':'Bounded ZIP memory download; complete ZIP SHA/bytes and all member CRC/bytes/path checks; selected originals are byte-exact. No ZIP saved.',
    'producer_sha256':sha(Path(__file__).read_bytes()),'selected_originals':[members[n] for n in payload],
    'exact_references':refs,'verified_not_selected':omitted,'observed':observed,
    'qualification':'Isolated candidate only. Default baseline remains separately bound to source32eb636; full release acceptance and distribution are not approved by this experiment.'}
payload['selection.json']=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode()
existing=[p for p in (root/'ci').rglob('*') if p.is_file()]
added=sum(map(len,payload.values()))
projection={'new_bytes':added,'new_files':len(payload),'ci_bytes':sum(p.stat().st_size for p in existing)+added,'ci_files':len(existing)+len(payload),
    'newtemp_bytes':sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+added,
    'combined_bytes':sum(p.stat().st_size for r in [root,old] for p in r.rglob('*') if p.is_file())+added}
assert projection['ci_bytes']<=1024**2 and projection['ci_files']<=50
assert projection['newtemp_bytes']<=3*1024**2 and projection['combined_bytes']<=40*1024**2
assert shutil.disk_usage(root).free-added>1024**3
out.mkdir()
for name,data in payload.items():
    path=out/name
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
print(json.dumps({'projection':projection,'root':str(out),'observed':observed}))
