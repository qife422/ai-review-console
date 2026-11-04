"""Read-only, offline replay of selected bytes and exact CI byte deltas in memory.

Use --ci-root for either the original run/ci or the same layout in a sealed packet.
No reconstructed payload is written, installed or executed.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ci-root', type=Path, required=True)
args = parser.parse_args()
root = args.ci_root.resolve()
cache = {}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:
        raise ValueError('Unsafe reference')
    local = root / relative
    if local.is_symlink() or not local.resolve().is_relative_to(root):
        raise ValueError('Reference escaped fixed packet')
    if relative not in cache:
        if local.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Reference read cap')
        cache[relative] = local.read_bytes()
    return cache[relative]


def expect(raw, record):
    if len(raw) != record['bytes'] or digest(raw) != record['sha256']:
        raise ValueError('Payload bytes or SHA256 mismatch')


def edits(old, ops):
    chunks = []
    for operation in ops:
        if set(operation) == {'copy_prior_bytes'}:
            start, end = operation['copy_prior_bytes']
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start <= end <= len(old):
                raise ValueError('Unsafe copy span')
            chunks.append(old[start:end])
        elif set(operation) == {'insert_original_bytes_base64'}:
            chunks.append(base64.b64decode(operation['insert_original_bytes_base64'], validate=True))
        else:
            raise ValueError('Unknown byte edit')
    result = b''.join(chunks)
    if len(result) > 8 * 1024 * 1024:
        raise ValueError('Reconstruction cap')
    return result


outcomes = []
for arch in ['amd64', 'arm64']:
    prefix = 'delta/final-185848-' + arch + '/'
    report = json.loads(read(prefix + 'selection.json'))
    original_count = 0
    for record in report['selected_original_members']:
        expect(read(prefix + record['path']), record)
        original_count += 1
    for record in report['exact_complete_file_prior_references']:
        expect(read(record['prior_selected_path']), record)
    for record in report['exact_file_byte_delta_references']:
        old = read(record['prior_selected_path'])
        if digest(old) != record['prior_file_sha256']:
            raise ValueError('Old whole-file fingerprint mismatch')
        rebuilt = edits(old, record['ops'])
        expect(rebuilt, record)
        if digest(rebuilt) != record['reconstructed_sha256']:
            raise ValueError('New reconstructed whole-file fingerprint mismatch')
    reuse = report.get('vulnerability_original_value_reuse')
    value_count = 0
    if reuse:
        values = {}
        for entry in reuse['entries']:
            if 'prior_selected_path' in entry:
                old = read(entry['prior_selected_path'])
                if digest(old) != reuse['prior_file_sha256']:
                    raise ValueError('Old provider file fingerprint mismatch')
                start, end = entry['prior_value_start_byte'], entry['prior_value_end_byte']
                if not 0 <= start <= end <= len(old):
                    raise ValueError('Provider value span invalid')
                raw = old[start:end]
                if 'ops' in entry:
                    raw = edits(raw, entry['ops'])
            else:
                raw = read(prefix + entry['new_fragment_path'])
            expect(raw, entry)
            if entry['id'] in values:
                raise ValueError('Duplicate provider ID')
            values[entry['id']] = raw
        if set(values) != set(reuse['ordered_ids']):
            raise ValueError('Provider key set mismatch')
        rebuilt = b'{\n' + b',\n'.join(
            b'  ' + json.dumps(key).encode() + b': ' + values[key]
            for key in reuse['ordered_ids']
        ) + b'\n}\n' if values else b'{}\n'
        if len(rebuilt) != reuse['new_bytes'] or digest(rebuilt) != reuse['new_sha256']:
            raise ValueError('Full new provider JSON fingerprint mismatch')
        value_count = len(values)
    outcomes.append({'arch': arch, 'selected_original_files': original_count,
                     'complete_file_references': len(report['exact_complete_file_prior_references']),
                     'file_byte_deltas': len(report['exact_file_byte_delta_references']),
                     'provider_values_replayed': value_count,
                     'result': 'passed_exact_bytes_sha256', 'writes': False})
print(json.dumps({'method': 'offline exact byte replay; no ZIP, network or semantic substitution',
                  'outcomes': outcomes, 'unique_reference_files_read': len(cache)}, indent=2))
