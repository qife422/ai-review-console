"""Verify fourth CI archives and select a <=400000-byte closure packet without replacement."""
import argparse
import hashlib
import json
import shutil
import stat
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
ROOT = Path('/private/tmp/arc-runtime-maintenance.wT9huB')
CI = ROOT / 'ci'
OUT = CI / 'native-close'
SOURCE = 'adb93c4b9f6af508188f696b8d7d1ef1dc5668ac'
RUN = 41760412382
metadata = json.loads((OUT / 'metadata.json').read_text())
payload, bindings, manifests, omitted, scans = {}, {}, [], {}, {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected(name, arch):
    if arch == 'unit':
        return name == 'arc-unit.xml'
    if name in {'workflow.json', 'release/dependency-compatibility.stdout',
                'release/images/summary.json', 'release/rhel/summary.json'}:
        return True
    return arch == 'amd64' and name in {
        'release/native/materials.json', 'release/native/manifest.json', 'browser/result.json'}


for artifact in metadata['artifacts']:
    if artifact['workflow_run']['head_sha'] != SOURCE or artifact['workflow_run']['id'] != RUN:
        raise ValueError('Artifact source binding mismatch')
    arch = 'unit' if artifact['name'] == 'unit-verification' else artifact['name'].split('-')[-1]
    path = CI / 'private' / (arch + '-' + str(RUN) + '.zip')
    rawzip = path.read_bytes()
    if len(rawzip) != artifact['size_in_bytes'] or 'sha256:' + sha(rawzip) != artifact['digest']:
        raise ValueError('Archive fingerprint mismatch')
    with ZipFile(path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > 650 or sum(i.file_size for i in infos) > 65 * 1024**2:
            raise ValueError('Archive expansion cap')
        allfiles = {}
        for i in infos:
            p = PurePosixPath(i.filename)
            if (p.is_absolute() or '..' in p.parts or '\\' in i.filename or str(p) != i.filename
                    or i.filename in allfiles or stat.S_ISLNK(i.external_attr >> 16)
                    or i.file_size > 8 * 1024**2):
                raise ValueError('Unsafe ZIP entry')
            h = hashlib.sha256()
            count = 0
            with z.open(i) as stream:
                while chunk := stream.read(65536):
                    h.update(chunk)
                    count += len(chunk)
            if count != i.file_size:
                raise ValueError('Member size mismatch')
            allfiles[i.filename] = {'path': i.filename, 'bytes': count, 'sha256': h.hexdigest()}
        for name in allfiles:
            if not name.endswith('/manifest.json'):
                continue
            doc = json.loads(z.read(name))
            declared = set()
            for item in doc.get('files', []):
                target = str(PurePosixPath(name).parent / item['path'])
                if '..' in PurePosixPath(item['path']).parts or target in declared:
                    raise ValueError('Unsafe manifest member')
                declared.add(target)
                actual = allfiles.get(target)
                if not actual or (actual['bytes'], actual['sha256']) != (item['bytes'], item['sha256']):
                    raise ValueError('Child manifest mismatch')
            if name == 'release/manifest.json' and declared != {
                n for n in allfiles if n.startswith('release/') and n != name}:
                raise ValueError('Root manifest set mismatch')
            manifests.append({'arch': arch, 'path': name, 'verified_declared_files': len(declared)})
        omitted[arch] = [v for n, v in allfiles.items() if not expected(n, arch)]
        for name in allfiles:
            if expected(name, arch):
                payload[arch + '/' + name] = z.read(name)
        if arch == 'unit':
            bindings[arch] = {'suites': [dict(x.attrib) for x in ET.fromstring(z.read('arc-unit.xml'))]}
            continue
        main = json.loads(z.read('release/manifest.json'))
        bindings[arch] = {
            'derived_from_original_member': 'release/manifest.json',
            'original_member_sha256': allfiles['release/manifest.json']['sha256'],
            'original_member_bytes': allfiles['release/manifest.json']['bytes'],
            'qualification': 'Explicit selected fields, not the original manifest or full packet.',
            'images': main['images'], 'source_inputs': main['source_inputs'],
            'collection_state': main['collection_state'], 'audits': main['audits'],
            'native_profile': main.get('native_materials_profile'),
            'native_scope': main.get('native_scope'),
            'native_state': main.get('native_materials'),
            'commands': main['commands'],
            'verification_method': 'GitHub source/run artifact binding, complete ZIP SHA/CRC, every child manifest declared SHA/size and release root exact member set, then explicit field selection.',
        }
        s = json.loads(z.read('release/images/summary.json'))
        r = json.loads(z.read('release/rhel/summary.json'))
        scans[arch] = {
            'provider_union': s['observed_unique_advisory_ids'],
            'default_unknown': {k: s[k] for k in ['mapping_unknown', 'query_unknown', 'detail_unknown']},
            'images': {n: {k: v for k, v in v.items() if k not in ['findings', 'upstream_severity_labels']}
                       for n, v in s['images'].items()},
            'rhel': {k: r[k] for k in ['rpm_entries', 'mapped_software_packages', 'metadata_only_public_keys',
                                     'observed_unique_advisory_ids', 'mapping_unknown', 'query_unknown', 'detail_unknown']},
        }
        inv = json.loads(z.read('release/images/langflow-inventory.json'))
        rpmmap = json.loads(z.read('release/rhel/rpm-mappings.json'))
        mappings = json.loads(z.read('release/images/package-mappings.json'))
        rpm_rows = {}
        software = {}
        for phase in ['before', 'after']:
            rows = [line.split('\t') for line in z.read('release/system/rpm-' + phase + '.stdout').decode().splitlines()]
            rpm_rows[phase] = rows
            software[phase] = {(x[0], x[2]): x[1] for x in rows if x[0] != 'gpg-pubkey'}
        primary = {(p['name'], p['version'], p['arch']) for p in inv['packages'] if p['type'] == 'rpm'}
        supplement = {(p['package'], p['version_with_epoch'].split(':', 1)[1], p['architecture'])
                      for p in rpmmap['packages']}
        after = {tuple(row[:3]) for row in rpm_rows['after']}
        complete_evr = {(p['package'], p['version_with_epoch'], p['architecture']) for p in rpmmap['packages']}
        unknown = [p for p in mappings['mappings'] if p['mapping_status'] != 'mapped']
        uncovered = [p for p in unknown if p['image'] != 'langflow' or p['package']['type'] != 'rpm']
        if (inv['identity']['id'] != r['image_id'] or r['image_id'] != main['images']['langflow']
                or primary != supplement or after != complete_evr):
            raise ValueError('Fresh same-image RPM/full-EVR coverage identity mismatch')
        before, after = software['before'], software['after']
        bindings[arch]['fresh_system_and_coverage'] = {
            'rpm_rows_before': len(rpm_rows['before']), 'rpm_rows_after': len(rpm_rows['after']),
            'software_evr_changed': sum(before[k] != after[k] for k in before.keys() & after.keys()),
            'software_added': sorted(n for n, _ in after.keys() - before.keys()),
            'software_removed': sorted(n for n, _ in before.keys() - after.keys()),
            'key_installed_evrs': {n: v for (n, _), v in after.items() if n in {
                'glibc', 'openssl-libs', 'pcre2', 'curl', 'expat', 'libxml2', 'python3.14', 'sqlite-libs'}},
            'exact_same_langflow_image_id': main['images']['langflow'],
            'default_RPM_set_equals_supplement': True,
            'post_update_full_EVR_set_equals_supplement': True,
            'primary_unknown_rows': len(unknown), 'other_uncovered_unknown_rows': len(uncovered),
            'default_exit_code_preserved': main['audits']['package_scan_exit_code'],
            'input_original_members': [allfiles[n] for n in [
                'release/system/rpm-before.stdout', 'release/system/rpm-after.stdout',
                'release/images/langflow-inventory.json', 'release/images/package-mappings.json',
                'release/rhel/rpm-mappings.json']],
            'scope': 'Derived from current source4 ZIP only. Detailed inventories/maps are not stored as new raw payload here; their original fingerprints are retained. This does not assess filesystem/embedded binaries or exploitability.'}

record = {
    'source': SOURCE, 'run': RUN, 'selected_original_members': [
        {'path': n, 'bytes': len(raw), 'sha256': sha(raw)} for n, raw in payload.items()],
    'verified_manifests': manifests, 'verified_not_selected': omitted,
    'bindings': bindings, 'observed_scans': scans,
    'scope': 'Fourth native-selector closure only. Whole functional CI runs, original member fingerprints and new summaries are retained; earlier full application evidence remains separately bound to its own source. Unselected ZIP members are not claimed as stored formal payload. No acceptance or distribution approval.'}
report = (json.dumps(record, indent=2) + '\n').encode()
existing = [p for p in OUT.rglob('*') if p.is_file()]
allci = [p for p in CI.rglob('*') if p.is_file() and 'private' not in p.relative_to(CI).parts]
added = sum(map(len, payload.values())) + len(report)
projection = {'new_packet_bytes': sum(p.stat().st_size for p in existing) + added,
              'whole_ci_bytes': sum(p.stat().st_size for p in allci) + added,
              'whole_ci_files': len(allci) + len(payload) + 1,
              'temp_bytes': sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) + added,
              'selected_original_files': len(payload)}
print(json.dumps({'projection': projection, 'scans': scans}))
if (projection['new_packet_bytes'] > 400000 or projection['whole_ci_bytes'] > 20 * 1024**2
        or projection['whole_ci_files'] > 200 or projection['temp_bytes'] > 40 * 1024**2
        or shutil.disk_usage(ROOT).free - added < 1024**3):
    raise ValueError('Stop before extraction: fourth/round/temp/headroom guard')
if args.apply:
    for name, raw in payload.items():
        target = OUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(raw)
    with (OUT / 'selection.json').open('xb') as f:
        f.write(report)
