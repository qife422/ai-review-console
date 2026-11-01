"""Verify protected bytes and seal only a bounded explicit candidate selection."""
from pathlib import Path
from datetime import datetime, UTC
import hashlib
import json
import shutil

ROOT = Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN = Path('/private/tmp/arc-release-followup.rLeRu5')
CANDIDATE = ROOT/'artifacts/evidence-candidates/release-compatibility'
FORMAL = ROOT/'docs/evidence/release-compatibility'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write_x(p, obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:
        stream.write(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    checks=[]
    protected={
      'review_console.sqlite3':'980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f',
      'docs/UPGRADE_SPEC.md':'a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753',
      'docs/spec-baseline.json':'5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e',
      'docs/evidence/v02-release/manifest.json':'c2a9cba23f3653e7c507654631f74568ee7490f80212ffe382c92323a4547f36',
      'docs/evidence/v02-acceptance/manifest.json':'6e3fa0159c396b1d422b32d90ccabb772b82db5d5cbeddb6e385e0e54138ba1c',
    }
    for name,expected in protected.items():
        p=ROOT/name
        actual=sha(p)
        assert actual==expected,name
        checks.append({'path':name,'bytes':p.stat().st_size,'sha256':actual,'unchanged':True})
    payloads=[]
    for name in ('v02-release','v02-acceptance'):
        base=ROOT/'docs/evidence'/name
        manifest=json.loads((base/'manifest.json').read_text())
        count=size=0
        for f in manifest['files']:
            p=base/f['path']
            assert p.resolve().is_relative_to(base.resolve()) and not p.is_symlink()
            assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256'],str(p)
            count+=1; size+=f['bytes']
        payloads.append({'evidence':name,'verified_files':count,'verified_bytes':size,'all_unchanged':True})
    write_x(CANDIDATE/'environment/protection-check.json',{'checked_at':datetime.now(UTC).isoformat(),'method':'Read/hash fixed original files and every payload listed by both old sealed manifests; no writes to protected inputs','fixed':checks,'old_payloads':payloads,'historical_database_volumes':'not mounted, started, migrated or deleted this continuation; prior preservation applies only to prior recorded run'})
    for name in ('prepare_packet.py','protect_and_seal.py','render_followup.py'):
        target=CANDIDATE/'producers'/name
        if not target.exists():
            with target.open('xb') as stream: stream.write((RUN/name).read_bytes())
    files=[p for p in sorted(CANDIDATE.rglob('*')) if p.is_file()]
    if any(p.is_symlink() for p in CANDIDATE.rglob('*')):
        raise RuntimeError('No candidate symlinks')
    entries=[{'path':str(p.relative_to(CANDIDATE)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    total=sum(f['bytes'] for f in entries)
    assert total<100*1024**2 and len(entries)<1000
    assert shutil.disk_usage(FORMAL.parent).free>1024**3
    inputs=json.loads((CANDIDATE/'environment/source-inputs.json').read_text())['files']
    author=[f for f in inputs if not (f['path'].startswith(('licenses/','flows/','fixtures/documents/','review_core/assets/')) or f['path'].endswith(('package-lock.json','requirements.lock')))]
    temp_files=[p for p in RUN.rglob('*') if p.is_file()]
    temp_bytes=sum(p.stat().st_size for p in temp_files)
    assert temp_bytes<40*1024**2 and len(temp_files)<10000
    observed=json.loads((RUN/'final-observation.json').read_text())
    manifest={
      'evidence_id':'release-compatibility','classification':'sealed_evidence',
      'sealed_at':datetime.now(UTC).isoformat(),'display_date':'2026-10-31 America/Los_Angeles',
      'contract':'ARC-UPGRADE@0.1.0','spec_sha256':protected['docs/UPGRADE_SPEC.md'],
      'source_commit':observed['head_sha'],
      'source_inputs':'environment/source-inputs.json','ci':observed,
      'requirements':{'RELEASE-001':'bounded exact-image evidence and materials reviewed; unresolved findings remain','AC-19':'not_passed_residual_findings_and_distribution_conditions','affected_regression':'passed only within actual CI evidence scope','full_v02_last_verified':None,'final_human_acceptance':'pending','residual_risk_accepted':False},
      'prior_fixed_evidence':[x for x in checks if '/manifest.json' in x['path']],
      'capacity':{'method':'capacity/method-review.json','cache_state':'warning','local_build_pull_cache_growth':False,'cleanup_authorized':False,'raw_global_snapshot':'private source hash only; not public payload','exact_project_physical_capacity':'unproven'},
      'license':{'full_backend_distribution_approved':False,'zep_2_0_2':'exact release permission unresolved','native_and_ibm_driver_materials':'unresolved','native_batch_plan_paths':100,'native_batch_actual_paths':101,'native_batch_actual_hash_input_bytes':95522697,'deviation':'producer incorrectly applied path limit per image; stopped further reading; original outputs retained'},
      'source_measurement':{'all_fixed_input_files':len(inputs),'all_fixed_input_bytes':sum(f['bytes'] for f in inputs),'author_input_files':len(author),'author_input_bytes':sum(f['bytes'] for f in author),'method':'Fixed input set excluding vendored licenses/font assets, generated Flow/input document binaries and lockfiles for author comparison; Git tree remains authoritative','fixed_assets_dependencies_separately_classified':True},
      'limits':{'payload_bytes':100*1024**2,'payload_files':1000,'new_run_temp_bytes':40*1024**2,'global_temp_bytes':256*1024**2,'temp_files':10000,'cache_bytes':4*1024**3,'cache_files':100000,'docker_project_bytes':12*1024**3,'docker_wp_growth_bytes':3*1024**3,'amplification':'stop above1GiB AND100x measured author inputs; immutable vendor assets separate'},
      'artifact_condition':{'active_evidence':'sealed','cache_state':'warning','last_inventory_at':json.loads((CANDIDATE/'capacity/execution-check.json').read_text())['at'],'pending_cleanup':True,'pending_migration':False,'candidate':'retained','private_sources_zip_and_caches':'retained outside sealed payload; no deletion or whole-tree backup','new_run_temp_bytes_at_seal':temp_bytes,'new_run_temp_files_at_seal':len(temp_files),'no_artifact_amplification_guard_triggered':total<1024**3},
      'provenance':'selection.json and producer snapshots plus child commands/manifests; documented inline methods retained as such; only this explicit list grants formal identity',
      'limitations':['CI is Linux/amd64; new arm64 stack was not rebuilt','Native library/source matrix binds previous exact arm64 images, not new CI native byte correspondence','Old full fault/restore/performance evidence is not relabelled as rerun under new dependencies','No full filesystem, embedded/static binary or exploitability audit','No real data, paid model, production deployment, binary redistribution signoff or risk acceptance','Later documentation commits have separately recorded packaging impact, not these exact image IDs'],
      'files':entries,'payload_bytes':total,'payload_files':len(entries),
      'manifest_self_hash':'excluded; fixed by Git commit and current state after sealing',
    }
    write_x(CANDIDATE/'manifest.json',manifest)
    if FORMAL.exists(): raise RuntimeError('Never replace formal evidence')
    FORMAL.mkdir()
    for f in entries+[{'path':'manifest.json','sha256':sha(CANDIDATE/'manifest.json')}]:
        source=CANDIDATE/f['path']; target=FORMAL/f['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream: stream.write(source.read_bytes())
        assert sha(target)==f['sha256']
    print(json.dumps({'formal_root':str(FORMAL),'manifest_sha256':sha(FORMAL/'manifest.json'),'payload_files':len(entries),'payload_bytes':total,'protected_unchanged':True,'temp_bytes':temp_bytes,'author_input_bytes':sum(f['bytes'] for f in author)}))

if __name__=='__main__':main()
