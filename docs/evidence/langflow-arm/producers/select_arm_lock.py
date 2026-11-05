"""Read one successful ARM lock artifact ZIP from stdin; never persist transport."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path('/private/tmp/arc-langflow-arm.tlmz8anp')
OUT = ROOT / 'ci/lock'
EXPECTED = {
    'build-installation.json', 'build-resolution.json', 'capacity.txt',
    'installation.json', 'langflow-candidate-build-tools.lock',
    'langflow-candidate.lock', 'provenance.json', 'resolution.json',
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def usage(path):
    paths = list(path.rglob('*'))
    assert not any(p.is_symlink() for p in paths)
    return sum(p.stat().st_size for p in paths if p.is_file()), sum(p.is_file() for p in paths)

assert len(sys.argv) == 2 and sys.argv[1].isdigit(), 'Pass verified artifact ID'
artifact = int(sys.argv[1])
assert not OUT.exists(), 'Never overwrite existing selected evidence'
blob = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
assert len(blob) <= 2 * 1024 * 1024, 'ZIP transport bound'
z = zipfile.ZipFile(io.BytesIO(blob))
infos = z.infolist()
assert len(infos) == len(EXPECTED) and {i.filename for i in infos} == EXPECTED
assert all(not i.is_dir() and i.file_size <= 600 * 1024 for i in infos)
assert sum(i.file_size for i in infos) <= 600 * 1024
contents = {i.filename: z.read(i) for i in infos}
provenance = json.loads(contents['provenance.json'])
assert provenance['source'] == '38edc84d99ed583882e91c1ba57c1fcd7c8fc4dd'
assert str(provenance['run']) == '41978766690' and provenance['arch'] == 'arm64'
for name in ('installation.json', 'build-installation.json'):
    receipt = json.loads(contents[name])
    assert receipt['environment']['platform_machine'] == 'aarch64'
    assert receipt['installed_set_matches_pins'] is True and receipt['pip_check'] == 'passed'
selection = {
    'run': 41978766690, 'source': provenance['source'], 'artifact_id': artifact,
    'transport_bytes': len(blob), 'transport_sha256': digest(blob), 'transport_retained': False,
    'selection': [{'member': n, 'bytes': len(b), 'sha256': digest(b)}
                  for n, b in sorted(contents.items())],
    'scope': 'Exact selected members; ZIP, resolver reports, archives and environments not retained.',
}
contents['selection.json'] = (json.dumps(selection, indent=2) + '\n').encode()
selected_size = sum(map(len, contents.values()))
ci_bytes, ci_count = usage(ROOT / 'ci')
total_bytes, _ = usage(ROOT)
assert ci_bytes + selected_size <= 600 * 1024 and ci_count + len(contents) <= 40
assert total_bytes + selected_size <= 1024 * 1024
assert 40437825 + total_bytes + selected_size <= 40 * 1024 * 1024
OUT.mkdir()
for name, data in contents.items():
    with (OUT / name).open('xb') as stream:
        stream.write(data)
print(json.dumps({'files': len(contents), 'bytes': selected_size,
                  'installation': json.loads(contents['installation.json']),
                  'artifact_id': artifact}, indent=2))
