"""Preserve a bounded fresh CI subset and exact prior-byte references; never overwrite."""
import argparse
import base64
import difflib
import hashlib
import json
import re
import shutil
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

CI = Path('/private/tmp/arc-runtime-maintenance.wT9huB/ci')
SOURCE = '185848006c2ea97ad24bead72f726c3a0d467dd4'
RUN = 41588865769
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('archive', type=Path)
parser.add_argument('destination', type=Path)
parser.add_argument('--arch', choices=['amd64', 'arm64'], required=True)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def byte_delta(before, after):
    """Exact line-aligned byte edits; copied offsets are relative to the old raw value/file."""
    left = before.splitlines(keepends=True)
    right = after.splitlines(keepends=True)
    offsets = [0]
    for line in left:
        offsets.append(offsets[-1] + len(line))
    ops, rebuilt = [], []
    for tag, a, b, c, d in difflib.SequenceMatcher(None, left, right).get_opcodes():
        if tag == 'equal':
            start, end = offsets[a], offsets[b]
            ops.append({'copy_prior_bytes': [start, end]})
            rebuilt.append(before[start:end])
        elif tag in {'replace', 'insert'}:
            inserted = b''.join(right[c:d])
            ops.append({'insert_original_bytes_base64': base64.b64encode(inserted).decode('ascii')})
            rebuilt.append(inserted)
    reconstructed = b''.join(rebuilt)
    if reconstructed != after:
        raise ValueError('Exact byte edit replay mismatch')
    return ops, reconstructed


def value_spans(raw):
    """Top-level object values, retaining exact UTF8 byte spans, not canonicalized JSON."""
    text = raw.decode('utf-8')
    decoder = json.JSONDecoder()
    pos = text.index('{') + 1
    values = {}
    while True:
        while text[pos].isspace():
            pos += 1
        if text[pos] == '}':
            break
        key, pos = decoder.raw_decode(text, pos)
        while text[pos].isspace():
            pos += 1
        if text[pos] != ':':
            raise ValueError('Unexpected JSON object separator')
        pos += 1
        while text[pos].isspace():
            pos += 1
        begin = pos
        _, pos = decoder.raw_decode(text, pos)
        start_byte = len(text[:begin].encode('utf-8'))
        end_byte = len(text[:pos].encode('utf-8'))
        if key in values:
            raise ValueError('Duplicate vulnerability ID')
        values[key] = {'raw': raw[start_byte:end_byte], 'start': start_byte, 'end': end_byte}
        while text[pos].isspace():
            pos += 1
        if text[pos] == ',':
            pos += 1
        elif text[pos] != '}':
            raise ValueError('Unexpected JSON item separator')
    return values


def needed(name):
    if name.endswith('/http-records.json'):
        return False  # Full records are hash-verified inside the ZIP, not selected in this delta.
    if name in {'workflow.json', 'runner-capacity.txt', 'release/manifest.json',
                'browser/result.json', 'chinese-browser-font.txt', 'chinese-browser-font-version.txt'}:
        return True
    if name.startswith(('release/system/', 'release/native/')):
        return True
    if name.startswith(('release/api-pip-check.', 'release/langflow-pip-check.',
                        'release/dependency-compatibility.')):
        return True
    if name.startswith('release/rhel/'):
        return name.endswith('.json') or name.endswith('langflow-redhat-metadata.stdout')
    if name.startswith('release/images/'):
        return name.endswith(('-inventory.json', '/summary.json', '/manifest.json',
                              '/package-mappings.json', '/http-records.json', '/web.cdx.json'))
    return name == 'release/licenses/manifest.json'


preexisting = {}
if args.destination.exists() or args.destination.is_symlink():
    allowed = {'release/native/materials.json', 'release/native/manifest.json'}
    if args.destination.is_symlink():
        raise ValueError('Refuse symlink destination')
    for p in args.destination.rglob('*'):
        if p.is_symlink():
            raise ValueError('Refuse symlink in priority extraction')
        if p.is_file():
            name = str(p.relative_to(args.destination))
            if name not in allowed:
                raise ValueError('Only the two pre-extracted native originals may already exist')
            preexisting[name] = p
prior = {}
for arch in [args.arch, 'arm64' if args.arch == 'amd64' else 'amd64']:
    base = CI / ('final-2e45bee-' + arch)
    selection = json.loads((base / 'selection.json').read_text())
    for record in selection['selected']:
        path = base / record['path']
        if sha(path.read_bytes()) != record['sha256']:
            raise ValueError('Frozen prior selected bytes changed')
        prior.setdefault(record['sha256'], str(path.relative_to(CI)))

with ZipFile(args.archive) as archive:
    infos = [i for i in archive.infolist() if not i.is_dir()]
    if len(infos) > 650 or sum(i.file_size for i in infos) > 65 * 1024 * 1024:
        raise ValueError('ZIP capacity')
    entries = {}
    for item in infos:
        path = PurePosixPath(item.filename)
        if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                or str(path) != item.filename or item.filename in entries
                or stat.S_ISLNK(item.external_attr >> 16) or item.file_size > 8 * 1024 * 1024):
            raise ValueError('Unsafe ZIP member')
        h = hashlib.sha256()
        count = 0
        with archive.open(item) as stream:
            while chunk := stream.read(65536):
                count += len(chunk)
                h.update(chunk)
        if count != item.file_size:
            raise ValueError('ZIP size mismatch')
        entries[item.filename] = {'path': item.filename, 'bytes': count, 'sha256': h.hexdigest()}
    manifests = []
    for name in entries:
        if not name.endswith('/manifest.json'):
            continue
        m = json.loads(archive.read(name))
        seen = set()
        for f in m.get('files', []):
            target = str(PurePosixPath(name).parent / f['path'])
            if target in seen or '..' in PurePosixPath(f['path']).parts:
                raise ValueError('Unsafe manifest declaration')
            seen.add(target)
            actual = entries.get(target)
            if not actual or (actual['bytes'], actual['sha256']) != (f['bytes'], f['sha256']):
                raise ValueError('Declared hash mismatch')
        if name == 'release/manifest.json':
            if seen != {n for n in entries if n.startswith('release/') and n != name}:
                raise ValueError('Root manifest set mismatch')
        manifests.append({'path': name, 'verified_declared_files': len(seen)})
    selected, references, omitted, file_reuse = [], [], [], []
    for name, item in entries.items():
        if name in preexisting:
            raw = preexisting[name].read_bytes()
            if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
                raise ValueError('Priority native originals mismatch')
            selected.append(item | {'preextracted': True})
            continue
        if item['sha256'] in prior:
            references.append(item | {'prior_selected_path': prior[item['sha256']],
                                      'method': 'exact complete file SHA256 byte equality'})
        elif (name in {'release/licenses/api.json', 'release/licenses/langflow.json',
                       'release/licenses/web.json'}
              or (args.arch == 'arm64' and name == 'release/images/package-mappings.json')):
            previous = CI / ('final-2e45bee-' + args.arch) / name
            # ARM generic licenses were intentionally not selected; AMD originals are shared
            # raw input only for an exact byte delta, never called whole-file equality.
            if not previous.is_file():
                previous = CI / 'final-2e45bee-amd64' / name
            before = previous.read_bytes()
            raw = archive.read(name)
            ops, rebuilt = byte_delta(before, raw)
            file_reuse.append(item | {
                'prior_selected_path': str(previous.relative_to(CI)),
                'prior_file_sha256': sha(before), 'ops': ops,
                'method': 'Exact byte delta from prior original bytes plus original inserted bytes; not whole-file equality.',
                'reconstructed_sha256': sha(rebuilt),
            })
        elif needed(name):
            selected.append(item)
        elif name != 'release/images/vulnerabilities.json':
            omitted.append(item | {'reason': 'not selected in bounded delta; verified in ZIP only'})

    # New provider JSON may remove IDs while each retained original object is unchanged.
    name = 'release/images/vulnerabilities.json'
    vulnerability_reuse = None
    fragments = {}
    if entries[name]['sha256'] not in prior:
        previous = CI / ('final-2e45bee-' + args.arch) / name
        previous_raw = previous.read_bytes()
        old = value_spans(previous_raw)
        raw = archive.read(name)
        fresh = value_spans(raw)
        mappings, rebuilt = [], []
        for key, span in fresh.items():
            row = {'id': key, 'bytes': len(span['raw']), 'sha256': sha(span['raw']),
                   'new_value_start_byte': span['start'], 'new_value_end_byte': span['end']}
            if key in old and span['raw'] == old[key]['raw']:
                row.update(prior_selected_path=str(previous.relative_to(CI)),
                           prior_value_start_byte=old[key]['start'],
                           prior_value_end_byte=old[key]['end'],
                           method='exact original JSON value byte span equality; not whole-file equality')
                chosen = old[key]['raw']
            elif key in old:
                ops, chosen = byte_delta(old[key]['raw'], span['raw'])
                row.update(prior_selected_path=str(previous.relative_to(CI)),
                           prior_value_start_byte=old[key]['start'],
                           prior_value_end_byte=old[key]['end'],
                           ops=ops,
                           parsed_JSON_data_changed=(json.loads(old[key]['raw']) != json.loads(span['raw'])),
                           method='Exact original byte delta within old value span; inserted bytes are original new bytes, not semantic substitution.')
            else:
                if not re.fullmatch(r'[A-Za-z0-9:_-]+', key):
                    raise ValueError('Unexpected provider ID')
                fragment = 'vulnerability-entries/' + sha(span['raw']) + '.json'
                fragments[fragment] = span['raw']
                row.update(new_fragment_path=fragment,
                           method='new original JSON value byte fragment, not complete response JSON')
                chosen = span['raw']
            mappings.append(row)
            rebuilt.append(b'  ' + json.dumps(key).encode() + b': ' + chosen)
        reconstruction = b'{\n' + b',\n'.join(rebuilt) + b'\n}\n' if fresh else b'{}\n'
        if reconstruction != raw:
            raise ValueError('Original vulnerability byte reconstruction failed')
        vulnerability_reuse = {
            'new_member': name, 'new_bytes': len(raw), 'new_sha256': sha(raw),
            'prior_file_sha256': sha(previous_raw),
            'ordered_ids': list(fresh), 'removed_prior_ids': sorted(old.keys() - fresh.keys()),
            'entries': mappings, 'new_fragment_files': len(fragments),
            'reconstruction': 'For ordered IDs, emit {\\n + join(b"  "+JSON(id)+b": "+original_value_bytes,b",\\n") + \\n}\\n. Exact whole-file bytes and SHA256 verified against ZIP; no new original path is fabricated.',
        }
    report = {
        'source_commit': SOURCE, 'run_id': RUN, 'arch': args.arch,
        'archive': {'name': args.archive.name, 'bytes': args.archive.stat().st_size,
                    'sha256': sha(args.archive.read_bytes()), 'formal_evidence': False},
        'verified_all_zip_files': len(entries), 'verified_all_zip_bytes': sum(x['bytes'] for x in entries.values()),
        'verified_manifests': manifests, 'selected_original_members': selected,
        'exact_file_byte_delta_references': file_reuse,
        'exact_complete_file_prior_references': references, 'vulnerability_original_value_reuse': vulnerability_reuse,
        'verified_not_selected': omitted,
        'scope': 'Only selected original members, explicitly labelled original fragments and prior selected bytes are candidates. Unselected archive members are not formal payload. ARM has no native/browser lane.',
    }
    raw_report = (json.dumps(report, indent=2) + '\n').encode()
    fresh_usage = [p for p in (CI / 'delta').rglob('*') if p.is_file()]
    selected_usage = [p for p in CI.rglob('*') if p.is_file() and 'private' not in p.relative_to(CI).parts]
    added = sum(x['bytes'] for x in selected if not x.get('preextracted')) + sum(map(len, fragments.values())) + len(raw_report)
    count = sum(not x.get('preextracted') for x in selected) + len(fragments) + 1
    projected = {
        'new_original_files': len(selected), 'new_original_bytes': sum(x['bytes'] for x in selected),
        'new_fragment_files': len(fragments), 'metadata_bytes': len(raw_report),
        'fresh_delta_bytes': sum(p.stat().st_size for p in fresh_usage) + added,
        'round_nonprivate_bytes': sum(p.stat().st_size for p in selected_usage) + added,
        'round_nonprivate_files': len(selected_usage) + count,
        'new_value_entries_reused': sum('prior_selected_path' in e for e in (vulnerability_reuse or {}).get('entries', [])),
        'removed_provider_ids': (vulnerability_reuse or {}).get('removed_prior_ids'),
    }
    print(json.dumps({'arch': args.arch, 'projection': projected, 'verified_manifests': manifests}))
    if (projected['fresh_delta_bytes'] > 3_200_000 or projected['round_nonprivate_bytes'] > 20 * 1024**2
            or projected['round_nonprivate_files'] > 200
            or sum(p.stat().st_size for p in CI.parent.rglob('*') if p.is_file()) + added > 40 * 1024**2
            or shutil.disk_usage(CI).free - added < 1024**3):
        raise ValueError('Stop: delta/round/temp/headroom capacity preflight failed')
    if args.apply:
        args.destination.mkdir(parents=True, exist_ok=bool(preexisting))
        for item in selected:
            if item.get('preextracted'):
                continue
            target = args.destination / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as out, archive.open(item['path']) as stream:
                shutil.copyfileobj(stream, out, length=65536)
        for name, raw in fragments.items():
            target = args.destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as out:
                out.write(raw)
        with (args.destination / 'selection.json').open('xb') as out:
            out.write(raw_report)
