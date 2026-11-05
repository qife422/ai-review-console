"""Bounded in-memory ZIP verification and explicit candidate/default selection."""
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

ROOT = Path('/private/tmp/arc-langflow-candidate.qya6psom')
OLD = Path('/private/tmp/arc-runtime-maintenance.wT9huB')
SOURCE = '32eb636efa77e33ad8088c474ac54f427ab503cf'
spec = json.load(sys.stdin)
out = ROOT / 'ci' / spec['mode']
if out.exists():
    raise ValueError('Never replace an earlier packet')
payload = {}
report = {'source': SOURCE, 'run': spec['run'], 'jobs': spec['jobs'],
          'scope': 'Explicit selected originals and qualified derived fields; ZIPs remain memory-only.',
          'archives': [], 'derived': {}}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


for item in spec['artifacts']:
    artifact = item['metadata']
    assert artifact['workflow_run']['head_sha'] == SOURCE
    assert artifact['workflow_run']['id'] == spec['run']
    assert artifact['size_in_bytes'] <= 8 * 1024**2
    with urllib.request.urlopen(item['url'], timeout=45) as response:
        raw = response.read(8 * 1024**2 + 1)
    assert len(raw) == artifact['size_in_bytes']
    assert 'sha256:' + sha(raw) == artifact['digest']
    with ZipFile(io.BytesIO(raw)) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        assert len(infos) <= 650 and sum(i.file_size for i in infos) <= 65 * 1024**2
        members = {}
        for info in infos:
            path = PurePosixPath(info.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename
            assert str(path) == info.filename and info.filename not in members
            assert not stat.S_ISLNK(info.external_attr >> 16) and info.file_size <= 8 * 1024**2
            content = archive.read(info)
            assert len(content) == info.file_size
            members[info.filename] = {'path': info.filename, 'bytes': len(content), 'sha256': sha(content)}
        checks = []
        for name in members:
            if not name.endswith('/manifest.json'):
                continue
            doc = json.loads(archive.read(name))
            declared = set()
            for record in doc.get('files', []):
                assert '..' not in PurePosixPath(record['path']).parts
                target = str(PurePosixPath(name).parent / record['path'])
                assert target not in declared
                declared.add(target)
                assert (members[target]['bytes'], members[target]['sha256']) == (record['bytes'], record['sha256'])
            if name == 'release/manifest.json':
                assert declared == {n for n in members if n.startswith('release/') and n != name}
            checks.append({'manifest': members[name], 'verified_files': len(declared)})
        public = {k: v for k, v in artifact.items() if k not in {'archive_download_url'}}
        report['archives'].append({'artifact': public, 'member_count': len(members),
                                   'expanded_bytes': sum(v['bytes'] for v in members.values()),
                                   'manifest_checks': checks, 'members': list(members.values())})
        if spec['mode'] == 'candidate':
            assert sum(v['bytes'] for v in members.values()) <= 850000 and len(members) <= 40
            for name in members:
                payload[name] = archive.read(name)
        elif artifact['name'] == 'unit-verification':
            report['derived']['unit'] = {'original': members['arc-unit.xml'],
                'suites': [dict(x.attrib) for x in ET.fromstring(archive.read('arc-unit.xml'))]}
        else:
            arch = artifact['name'].split('-')[-1]
            main = json.loads(archive.read('release/manifest.json'))
            summary = json.loads(archive.read('release/images/summary.json'))
            rhel = json.loads(archive.read('release/rhel/summary.json'))
            flow = json.loads(archive.read('workflow.json'))
            derived = {'original_manifest': members['release/manifest.json'],
                'source_inputs': main['source_inputs'], 'images': main['images'],
                'commands': main['commands'], 'collection_state': main['collection_state'],
                'audits': main['audits'], 'workflow_original': members['workflow.json'],
                'workflow': {k: flow.get(k) for k in ['langflow_version','component_count','result','stored_flow_hashes_before','stored_flow_hashes_after']},
                'scan': {'original': members['release/images/summary.json'],
                    'union': summary['observed_unique_advisory_ids'],
                    'unknown': {k:summary[k] for k in ['mapping_unknown','query_unknown','detail_unknown']},
                    'images': {n:{k:v for k,v in row.items() if k not in {'findings','upstream_severity_labels'}} for n,row in summary['images'].items()}},
                'rhel': {'original': members['release/rhel/summary.json'],
                    **{k:rhel[k] for k in ['image_id','rpm_entries','mapped_software_packages','metadata_only_public_keys','observed_unique_advisory_ids','mapping_unknown','query_unknown','detail_unknown']}}}
            if 'release/native/materials.json' in members:
                native = json.loads(archive.read('release/native/materials.json'))
                previous_path = OLD / 'ci/native-close/amd64/release/native/materials.json'
                previous = json.loads(previous_path.read_bytes())
                bodyrefs = []
                for image in native['images']:
                    for entry in image.get('result', {}).get('files', []):
                        if entry.get('state') != 'recorded':
                            continue
                        text = entry['text'].encode()
                        assert sha(text) == entry['sha256']
                        old_entries = [e for im in previous['images'] for e in im.get('result',{}).get('files',[]) if e.get('path') == entry['path'] and e.get('text') == entry['text']]
                        assert len(old_entries) == 1
                        bodyrefs.append({k:v for k,v in entry.items() if k != 'text'} | {'prior_original':str(previous_path), 'prior_original_sha256':sha(previous_path.read_bytes()), 'exact_text_bytes_equal': True})
                derived['native'] = {k:native[k] for k in ['starting_budget','remaining_budget','current_invocation_read_files','current_invocation_input_bytes','goal_known_input_bytes','baseline','mode']}
                derived['native'].update(original=members['release/native/materials.json'], exact_body_references=bodyrefs)
            report['derived'][arch] = derived

if 'log' in spec:
    log = spec['log'].copy()
    tail = log.pop('tail_utf8').encode()
    assert len(tail) == 16384
    payload['failure-joblog-tail.stdout'] = tail
    log['selected_tail_sha256'] = sha(tail)
    report['job_log_selection'] = log
    report['failure'] = {'step': 'Initialize isolated synthetic stores and Flows',
        'signal': 'unknown flag: --no-build', 'exit_code': 1,
        'classification': 'Workflow Compose run CLI error; not Langflow runtime compatibility evidence',
        'not_executed': ['storage-init','migrate','flow-init','business validation','candidate verifier','GUI','scan','licenses']}
if 'verify_excerpt' in spec:
    report['verify_excerpt'] = spec['verify_excerpt']
payload['selection.json'] = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
existing = [p for p in (ROOT / 'ci').rglob('*') if p.is_file()]
newbytes = sum(map(len, payload.values()))
limit = 150000 if spec['mode'] == 'default-baseline' else 850000
assert newbytes <= limit
assert sum(p.stat().st_size for p in existing) + newbytes <= 1024**2
assert len(existing) + len(payload) <= 50
combined = sum(p.stat().st_size for r in [ROOT,OLD] for p in r.rglob('*') if p.is_file())
assert combined + newbytes <= 40 * 1024**2
assert sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) + newbytes <= 3 * 1024**2
assert shutil.disk_usage(ROOT).free - newbytes > 1024**3
out.mkdir()
for name, content in payload.items():
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(content)
print(json.dumps({'root':str(out),'bytes':newbytes,'files':len(payload),'ci_total_bytes':sum(p.stat().st_size for p in existing)+newbytes,'ci_total_files':len(existing)+len(payload)}))
