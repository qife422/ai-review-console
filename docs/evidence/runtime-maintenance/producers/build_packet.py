"""Select and seal bounded maintenance evidence without changing old packets."""
from pathlib import Path
from datetime import datetime, UTC
import hashlib
import json
import shutil
import subprocess

ROOT=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN=Path('/private/tmp/arc-runtime-maintenance.wT9huB')
CANDIDATE=ROOT/'artifacts/evidence-candidates/runtime-maintenance'
FORMAL=ROOT/'docs/evidence/runtime-maintenance'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def write_x(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def prepare():
    if CANDIDATE.exists() or FORMAL.exists():raise RuntimeError('Never replace candidates or sealed evidence')
    sources=[(RUN/'plan.json','environment/plan.json'),(RUN/'architecture-plan.json','environment/architecture-plan.json'),(RUN/'final-observation.json','environment/final-observation.json')]
    for folder in ('capacity','python','licenses','system','ci'):
        for p in sorted((RUN/folder).rglob('*')):
            relative=p.relative_to(RUN)
            if not p.is_file():continue
            if p.is_symlink():raise RuntimeError('No source symlinks')
            if folder=='ci' and ('private' in relative.parts or p.suffix=='.zip'):continue
            if p.name=='microdnf-3.10.1-dnf-main.c':continue
            sources.append((p,str(relative)))
    for name in ('collect_release_ci.py','apply_system_updates.py','verify_native_materials.py','verify_dependency_compatibility.py','verify_image_licenses.py','scan_images_osv.py'):
        sources.append((ROOT/'scripts'/name,'producers/'+name))
    sources.append((RUN/'build_packet.py','producers/build_packet.py'))
    size=sum(p.stat().st_size for p,_ in sources)
    if size>=100*1024**2 or len(sources)>=1000:raise RuntimeError('Evidence size/count guard')
    if shutil.disk_usage(CANDIDATE.parent).free<1024**3:raise RuntimeError('1GiB headroom guard')
    CANDIDATE.mkdir(parents=True)
    for original,relative in sources:
        target=CANDIDATE/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(original.read_bytes())
        assert sha(target)==sha(original)
    prior=json.loads((ROOT/'docs/evidence/release-compatibility/environment/source-inputs.json').read_text())
    paths={x['path'] for x in prior['files']}
    paths|={'scripts/apply_system_updates.py','scripts/verify_native_materials.py','tests/test_apply_system_updates.py','tests/test_verify_native_materials.py','compliance/native-baseline.json','.dockerignore'}
    inputs=[{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in sorted(paths)]
    write_x(CANDIDATE/'environment/source-inputs.json',{'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'method':'Prior explicit input set plus new maintenance scripts/tests, fixed continuation and Docker context; source Git tree authoritative','files':inputs})
    write_x(CANDIDATE/'selection.json',{'classification':'candidate_until_outer_manifest','method':'Explicit bounded source responses, diagnostic outputs and selected CI originals/deltas; CI private ZIPs and normalized C copy excluded, original official APKINDEX archives kept as fixed supplier inputs','sources':[{'source':str(p),'path':r,'bytes':p.stat().st_size,'sha256':sha(p)} for p,r in sources]})
    print(json.dumps({'candidate':str(CANDIDATE),'selected_files':len(sources),'selected_bytes':size}))

def seal():
    obs=json.loads((RUN/'final-observation.json').read_text())
    assert obs['code_ci_conclusion']=='success'
    protected={
      'review_console.sqlite3':'980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f',
      'docs/UPGRADE_SPEC.md':'a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753',
      'docs/spec-baseline.json':'5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e',
      'docs/evidence/v02-acceptance/manifest.json':'6e3fa0159c396b1d422b32d90ccabb772b82db5d5cbeddb6e385e0e54138ba1c',
      'docs/evidence/v02-release/manifest.json':'c2a9cba23f3653e7c507654631f74568ee7490f80212ffe382c92323a4547f36',
      'docs/evidence/release-compatibility/manifest.json':'0466646bd5eecd32768e9fc61bf138815853292049a41a95dc1d98927e2081ef',
    }
    for name,expected in protected.items():assert sha(ROOT/name)==expected,name
    old=[]
    for name in ('v02-acceptance','v02-release','release-compatibility'):
        base=ROOT/'docs/evidence'/name;packet=json.loads((base/'manifest.json').read_text())
        for item in packet['files']:
            p=base/item['path'];assert p.resolve().is_relative_to(base.resolve()) and not p.is_symlink()
            assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],str(p)
        old.append({'evidence':name,'verified_payload_files':len(packet['files']),'verified_payload_bytes':sum(f['bytes'] for f in packet['files']),'unchanged':True})
    write_x(CANDIDATE/'environment/protection-check.json',{'at':datetime.now(UTC).isoformat(),'method':'Hash fixed original files and every payload explicitly listed by all3old sealed manifests; no writes to protected inputs','fixed_files':[{'path':p,'sha256':h,'unchanged':True} for p,h in protected.items()],'old_packets':old,'historical_volumes':'not started/mounted/migrated/deleted; no new host Docker inventory possible'})
    files=[p for p in sorted(CANDIDATE.rglob('*')) if p.is_file()]
    assert not any(p.is_symlink() for p in CANDIDATE.rglob('*'))
    entries=[{'path':str(p.relative_to(CANDIDATE)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    payload=sum(x['bytes'] for x in entries)
    temp=[p for p in RUN.rglob('*') if p.is_file()];temp_bytes=sum(p.stat().st_size for p in temp)
    assert payload<100*1024**2 and len(entries)<1000
    assert temp_bytes<40*1024**2 and len(temp)<10000
    ci_files=[p for p in (CANDIDATE/'ci').rglob('*') if p.is_file()]
    assert len(ci_files)<=200 and sum(p.stat().st_size for p in ci_files)<=20*1024**2
    for folder,max_files,max_bytes in [('python',20,3*1024**2),('licenses',50,3*1024**2),('system',30,2*1024**2)]:
        selected=[p for p in (CANDIDATE/folder).rglob('*') if p.is_file()]
        assert len(selected)<=max_files and sum(p.stat().st_size for p in selected)<=max_bytes,folder
    inputs=json.loads((CANDIDATE/'environment/source-inputs.json').read_text())['files']
    author=[f for f in inputs if not(f['path'].startswith(('licenses/','flows/','fixtures/documents/','review_core/assets/')) or f['path'].endswith(('package-lock.json','requirements.lock')))]
    manifest={'evidence_id':'runtime-maintenance','classification':'sealed_evidence','sealed_at':datetime.now(UTC).isoformat(),'display_date':'2026-11-03 America/Los_Angeles','main_runtime_validation_date':'2026-11-02 America/Los_Angeles','native_final_source_validation_date':'2026-11-03 America/Los_Angeles','contract':'ARC-UPGRADE@0.1.0','spec_sha256':protected['docs/UPGRADE_SPEC.md'],'source_commit':obs['source_commit'],'source_inputs':'environment/source-inputs.json','observations':obs,'acceptance':{'RELEASE-001':'Actual system maintenance/scan and license materials collected with explicit unresolved scope','AC-19':'not_passed_remaining_findings_and_distribution_conditions','full_v02_last_verified':None,'final_human_acceptance':'pending','residual_risk_accepted':False},'provenance':'selection.json, original CI sources/deltas with archive-level child hashes, producer snapshots and exact methods; only these selected bytes have sealed identity','source_measurement':{'fixed_input_files':len(inputs),'fixed_input_bytes':sum(f['bytes'] for f in inputs),'author_input_files':len(author),'author_input_bytes':sum(f['bytes'] for f in author),'vendor_assets_dependencies_separately_classified':True},'artifact_condition':{'active_evidence':'sealed','cache_state':'warning; local Docker unavailable so no fresh complete inventory','pending_cleanup':True,'pending_migration':False,'host_docker_start_build_pull':False,'historical_cleanup_authorized':False,'temp_bytes_at_seal':temp_bytes,'temp_files_at_seal':len(temp),'candidate':'retained','private_zip_and_other_temp':'retained outside payload; no cleanup or whole-tree backup'},'limits':json.loads((RUN/'plan.json').read_text())['limits'],'documentation_followup':'environment/documentation-impact.json; only docs/evidence after tested code, [skip ci] is skipped and not claimed as success','artifact_disposition':[{'artifact_id':'runtime-maintenance','classification':'sealed_evidence','action':'retain-active','reason':'Bound verification and next-step review'},{'artifact_id':'runtime-maintenance-candidate','classification':'evidence_candidate','action':'retain-active','reason':'Promotion source retained; no cleanup authority'},{'artifact_id':'private-ci-transport-and-temp','classification':'ephemeral_run_output','action':'cleanup-pending-authorization','reason':'Excluded transports and producer drafts retained outside formal payload'},{'artifact_id':'historical-docker-cache','classification':'regenerable_cache','action':'cleanup-pending-authorization','reason':'Prior capacity warning; current inventory unavailable; no mutation'}],'prior_evidence':old,'limitations':['CI native Linux amd64 and Linux ARM backend, not Mac host verification','ARM browser and targeted native materials intentionally not executed; AMD carries the one shared input budget','Package metadata and vendor queries are not complete filesystem/static/embedded vulnerability or exploitability coverage','No candidateLangflow version installation/GUI/migration validation is claimed','Recipe/version matches and ELF build-id do not themselves prove complete vendor corresponding source or binary distribution permission','Original negative/retry run does not prove recovery of a successful case; old fullfault/restore/performance evidence remains scoped to its old environment','Post-code documentation bytes are not those exact tested image bytes; immutable Git commit and recorded impact bind followup'],'files':entries,'payload_files':len(entries),'payload_bytes':payload,'manifest_self_hash':'excluded; fixed by Git and CURRENT_STATE after sealing'}
    write_x(CANDIDATE/'manifest.json',manifest)
    if FORMAL.exists():raise RuntimeError('Never replace sealed evidence')
    FORMAL.mkdir()
    for entry in entries+[{'path':'manifest.json','sha256':sha(CANDIDATE/'manifest.json')}]:
        source=CANDIDATE/entry['path'];target=FORMAL/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(source.read_bytes())
        assert sha(target)==entry['sha256']
    print(json.dumps({'formal':str(FORMAL),'manifest_sha256':sha(FORMAL/'manifest.json'),'payload_files':len(entries),'payload_bytes':payload,'temp_bytes':temp_bytes,'protected_old_payloads':sum(x['verified_payload_files'] for x in old)}))

if __name__=='__main__':
    import sys
    if sys.argv[1:] == ['prepare']:prepare()
    elif sys.argv[1:] == ['seal']:seal()
    else:raise SystemExit('Use prepare or seal')
