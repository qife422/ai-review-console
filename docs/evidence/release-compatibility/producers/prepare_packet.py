"""Select a bounded delta packet; never alter previously sealed evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, UTC

ROOT = Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN = Path('/private/tmp/arc-release-followup.rLeRu5')
DEST = ROOT / 'artifacts/evidence-candidates/release-compatibility'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if DEST.exists():
        raise RuntimeError('Selection destination must not exist')
    selections = [(RUN / 'plan.json', 'environment/plan.json'), (RUN/'final-observation.json','environment/final-observation.json')]
    for folder in ('python', 'licenses'):
        selections += [(p, folder + '/' + p.name) for p in sorted((RUN/folder).iterdir()) if p.is_file()]
    selections += [(RUN/'capacity'/p, 'capacity/'+p) for p in ('summary.json', 'method-review.json', 'execution-check.json')]
    ci = RUN/'ci'
    if not ci.is_dir():
        raise RuntimeError('Exact CI delta evidence is required before selecting')
    selections += [(p, 'ci/'+str(p.relative_to(ci))) for p in sorted(ci.rglob('*')) if p.is_file() and p.suffix != '.zip']
    for name in ('collect_release_ci.py','verify_image_licenses.py','verify_dependency_compatibility.py','scan_images_osv.py','scan_release.py'):
        selections.append((ROOT/'scripts'/name, 'producers/'+name))
    selections.append((RUN/'prepare_packet.py', 'producers/prepare_packet.py'))
    if any(p.is_symlink() for p,_ in selections):
        raise RuntimeError('No symlink selection')
    total = sum(p.stat().st_size for p,_ in selections)
    if total >= 100*1024**2 or len(selections)>=1000:
        raise RuntimeError('100MiB/1000 files guard')
    if shutil.disk_usage(DEST.parent).free < 1024**3:
        raise RuntimeError('1GiB local headroom guard')
    DEST.mkdir(parents=True)
    for source, relative in selections:
        target = DEST/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
        assert sha(source)==sha(target)
    prior = json.loads((ROOT/'docs/evidence/v02-release/environment/source-inputs.json').read_text())
    paths = {f['path'] for f in prior['files']}
    paths |= {'README.md', 'pyproject.toml', 'licenses/dnspython-2.9.0-ISC.txt', 'licenses/FastMCP-3.4.10-LICENSE.txt', 'licenses/Langflow-LICENSE.txt','scripts/verify_dependency_compatibility.py','tests/test_dependency_compatibility.py'}
    inputs = [{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in sorted(paths)]
    (DEST/'environment/source-inputs.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'captured_at':datetime.now(UTC).isoformat(),'method':'Prior explicit107 input set plus new probe/tests/license material and packaging README; exact Git tree is authoritative','files':inputs},ensure_ascii=False,indent=2)+'\n')
    (DEST/'selection.json').write_text(json.dumps({'classification':'candidate_until_outer_manifest','method':'explicit small run outputs, producer snapshots and exact CI selected artifact; no global Docker raw snapshot, cache, build tree, ZIP or database','global_docker_raw_private_only':{'sha256':sha(RUN/'capacity/docker-system-df.json'),'bytes':(RUN/'capacity/docker-system-df.json').stat().st_size,'method':'GET Docker Engine Unix socket /v1.51/system/df; project-scoped derived outputs selected'},'prior_sealed_evidence':{'path':'docs/evidence/v02-release/manifest.json','sha256':sha(ROOT/'docs/evidence/v02-release/manifest.json')},'sources':[{'path':str(p),'selected_as':r,'bytes':p.stat().st_size,'sha256':sha(p)} for p,r in selections]},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'selected_files':len(selections),'selected_bytes':total,'candidate':str(DEST)}))

if __name__=='__main__':
    main()
