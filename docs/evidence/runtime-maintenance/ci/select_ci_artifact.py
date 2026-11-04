"""Verify complete bounded ZIP payloads, extract a fixed subset without replacement."""
import argparse
import hashlib
import json
import shutil
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("archive", type=Path)
parser.add_argument("destination", type=Path)
parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
ci = Path('/private/tmp/arc-runtime-maintenance.wT9huB/ci')
run = ci.parent


def selected(name, size):
    if name.startswith('release/system/'):
        return True  # Keep the complete small original system child packet, including empties.
    if not size:
        return False
    if name in {'workflow.json', 'runner-capacity.txt', 'services.json', 'release/manifest.json'}:
        return True
    if name.startswith(('release/api-pip-check.', 'release/langflow-pip-check.',
                        'release/dependency-compatibility.')):
        return True
    if name.startswith('release/rhel/'):
        return not name.endswith('.stdout') or name.endswith('langflow-redhat-metadata.stdout')
    if name.startswith('release/images/'):
        if args.arch == 'arm64':
            return name.endswith(('-inventory.json', '/summary.json', '/manifest.json',
                                  '/package-mappings.json', '/vulnerabilities.json',
                                  '/http-records.json'))
        return name.endswith('.json') and not name.endswith('.spdx.json')
    if args.arch == 'amd64':
        if name.startswith(('release/licenses/', 'release/native/')):
            return name.endswith('.json')
        if name.startswith('browser/'):
            return name in {'browser/result.json', 'browser/commands.log',
                            'browser/dashboard-1440-dark.png', 'browser/dashboard-1440-light.png',
                            'browser/dashboard-390-dark.png', 'browser/dashboard-390-light.png'}
        if name.startswith('chinese-browser-font'):
            return True
    return False


if args.destination.exists() or args.destination.is_symlink():
    raise ValueError('Destination must be new')
hashes = {}
with ZipFile(args.archive) as archive:
    infos = [i for i in archive.infolist() if not i.is_dir()]
    if len(infos) > 650 or sum(i.file_size for i in infos) > 65 * 1024 * 1024:
        raise ValueError('Archive preflight capacity exceeded')
    for info in infos:
        name = PurePosixPath(info.filename)
        if (name.is_absolute() or '..' in name.parts or '\\' in info.filename
                or str(name) != info.filename or info.filename in hashes
                or stat.S_ISLNK(info.external_attr >> 16) or info.file_size > 8 * 1024 * 1024):
            raise ValueError('Unsafe archive member')
        digest = hashlib.sha256()
        count = 0
        with archive.open(info) as stream:
            while chunk := stream.read(65536):
                count += len(chunk)
                if count > info.file_size:
                    raise ValueError('Archive member size mismatch')
                digest.update(chunk)
        hashes[info.filename] = {'path': info.filename, 'bytes': count,
                                'sha256': digest.hexdigest()}
    manifests = []
    for name in hashes:
        if not name.endswith('/manifest.json'):
            continue
        raw = json.loads(archive.read(name))
        declarations = raw.get('files', [])
        seen = set()
        for record in declarations:
            target = str(PurePosixPath(name).parent / record['path'])
            if target in seen or '..' in PurePosixPath(record['path']).parts:
                raise ValueError('Unsafe manifest declaration')
            seen.add(target)
            actual = hashes.get(target)
            if not actual or (actual['bytes'], actual['sha256']) != (record['bytes'], record['sha256']):
                raise ValueError('Child manifest hash mismatch: ' + target)
        if name == 'release/manifest.json':
            expected = {n for n in hashes if n.startswith('release/') and n != name}
            if seen != expected:
                raise ValueError('Root release manifest set mismatch')
        manifests.append({'path': name, 'verified_declared_files': len(seen)})
    if args.arch == 'arm64':
        # The large common official mapping is retained in the AMD packet if identical.
        omitted = 'release/rhel/repository-to-cpe.json'
    else:
        omitted = None
    choices = [r for name, r in hashes.items() if selected(name, r['bytes']) and name != omitted]
    existing = [p for p in ci.rglob('*') if p.is_file() and 'private' not in p.relative_to(ci).parts]
    files = len(existing) + len(choices) + 1
    size = sum(p.stat().st_size for p in existing) + sum(r['bytes'] for r in choices) + 256 * 1024
    all_usage = sum(p.stat().st_size for p in run.rglob('*') if p.is_file())
    if files > 200 or size > 20 * 1024 * 1024 or all_usage + size > 40 * 1024 * 1024:
        raise ValueError('Round extraction capacity exceeded')
    if shutil.disk_usage(run).free - size < 1024**3:
        raise ValueError('Insufficient host headroom')
    report = {
        'source_commit': '2e45bee8c61dfab347edd107aebb6a3488567761',
        'run_id': 41586599463, 'arch': args.arch,
        'archive': {'name': args.archive.name, 'bytes': args.archive.stat().st_size,
                    'sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                    'formal_evidence': False},
        'verified_all_zip_files': len(hashes),
        'verified_all_zip_bytes': sum(r['bytes'] for r in hashes.values()),
        'verified_manifests': manifests,
        'selected': choices,
        'verified_not_selected': [r for r in hashes.values() if r not in choices],
        'scope': 'Only selected original member bytes are evidence candidates. ZIP/unchecked claims are not formal evidence.',
        'projected_round_nonzip_files': files,
        'projected_round_nonzip_bytes_with_256KiB_metadata_reserve': size,
    }
    print(json.dumps({k: report[k] for k in ['arch', 'verified_all_zip_files',
          'verified_all_zip_bytes', 'verified_manifests', 'projected_round_nonzip_files',
          'projected_round_nonzip_bytes_with_256KiB_metadata_reserve']}))
    if args.apply:
        args.destination.mkdir(parents=True)
        for record in choices:
            target = args.destination / record['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as out, archive.open(record['path']) as stream:
                shutil.copyfileobj(stream, out, length=65536)
        with (args.destination / 'selection.json').open('x') as out:
            json.dump(report, out, indent=2)
