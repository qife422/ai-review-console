"""Select bounded candidate observations; verify protection and seal immutable bytes."""
from pathlib import Path
from datetime import datetime, UTC
import hashlib
import json
import shutil
import subprocess

ROOT=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN=Path('/private/tmp/arc-langflow-candidate.qya6psom')
OLD_TEMP=Path('/private/tmp/arc-runtime-maintenance.wT9huB')
CANDIDATE=ROOT/'artifacts/evidence-candidates/langflow-candidate'
FORMAL=ROOT/'docs/evidence/langflow-candidate'
SOURCE_FILES=['.github/workflows/langflow-candidate.yml','compliance/langflow-candidate-constraints.txt','docker/compose.candidate.yml','docker/langflow-candidate.Dockerfile','frontend/scripts/verify-langflow-ui-cli.mjs','scripts/verify_langflow_candidate.py','scripts/bootstrap_langflow.py','scripts/validate_langflow.py','tests/test_langflow_expected_version.py','tests/test_candidate_native_licenses.py']
FIXED={'review_console.sqlite3':'980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f','docs/UPGRADE_SPEC.md':'a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753','docs/spec-baseline.json':'5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e','docs/evidence/v02-acceptance/manifest.json':'6e3fa0159c396b1d422b32d90ccabb772b82db5d5cbeddb6e385e0e54138ba1c','docs/evidence/v02-release/manifest.json':'c2a9cba23f3653e7c507654631f74568ee7490f80212ffe382c92323a4547f36','docs/evidence/release-compatibility/manifest.json':'0466646bd5eecd32768e9fc61bf138815853292049a41a95dc1d98927e2081ef','docs/evidence/runtime-maintenance/manifest.json':'5a400e77b5e3b28426f2efe99d723b48aee5e1e95d9c7e4a4c9665364963b724'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:f.write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def copy_x(p,t):
    assert p.is_file() and not p.is_symlink()
    t.parent.mkdir(parents=True,exist_ok=True)
    with t.open('xb') as f:f.write(p.read_bytes())
    assert sha(p)==sha(t)

def prepare():
    assert not CANDIDATE.exists() and not FORMAL.exists()
    obs=json.loads((RUN/'final-observation.json').read_text())
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==obs['source_commit']
    ci=[p for p in (RUN/'ci').rglob('*') if p.is_file()]
    sources=[p for p in (RUN/'sources').rglob('*') if p.is_file()]
    assert len(ci)<=50 and sum(p.stat().st_size for p in ci)<=1048576
    assert len(sources)<=12 and sum(p.stat().st_size for p in sources)<=262144
    chosen=[(RUN/n,'environment/'+n) for n in ['plan.json','budget-decision.json','final-observation.json']]
    chosen += [(p,str(p.relative_to(RUN))) for p in sorted(sources+ci)]
    chosen += [(ROOT/p,'producers/'+p) for p in SOURCE_FILES]
    chosen += [(Path(__file__),'producers/seal_packet.py'),(RUN/'render_result.py','producers/render_result.py'),(RUN/'candidate-license-final-review.json','environment/candidate-license-final-review.json')]
    assert sum(p.stat().st_size for p,_ in chosen)<5*1024**2
    assert shutil.disk_usage(ROOT).free>=1024**3
    CANDIDATE.mkdir(parents=True)
    for p,target in chosen:copy_x(p,CANDIDATE/target)
    dump(CANDIDATE/'selection.json',{'classification':'candidate_until_manifest','method':'Explicit source originals and qualified derived CI observations. Private transports, pytest scratch and unselected full reports are excluded. No whole build tree backup.','files':[{'source':str(p),'path':t,'bytes':p.stat().st_size,'sha256':sha(p)} for p,t in chosen]})
    with (CANDIDATE/'README.md').open('x') as f:f.write(obs['report'])
    dump(CANDIDATE/'environment/source-inputs.json',{'candidate_source':obs['source_commit'],'method':'Explicit experiment inputs plus existing baseline inputs; previous Git commits authoritative','files':[{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in SOURCE_FILES+['licenses/Langflow-LICENSE.txt','requirements.lock','docker-compose.yml','.dockerignore']],'baseline_runtime':'1.11.6','baseline_functional_source':'32eb636efa77e33ad8088c474ac54f427ab503cf','effective_default_changes_after_baseline':'Only isolated candidate paths/probe utility and its tests; no default recipe/52pins/acceptedSpec/business logic changes','default_langflow_dockerfile_sha256':sha(ROOT/'docker/langflow.Dockerfile')})
    dest=RUN/'final-docs';assert not dest.exists();dest.mkdir()
    impact=[]
    for name,content in obs['docs'].items():
        assert 'PLACEHOLDER' not in content
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as f:f.write(content)
        impact.append({'path':name,'tested_sha256':sha(ROOT/name),'planned_sha256':None if name=='docs/CURRENT_STATE.md' else sha(p)})
    dump(CANDIDATE/'environment/documentation-impact.json',{'tested_candidate_source':obs['source_commit'],'actual_candidate_CI':obs['code_ci_run'],'files':impact,'scope':'Only six status/history/notice docs plus sealed evidence after actual experiment; no default adoption','packaging_effect':'README package metadata/API COPY; dependency doc/notices API/LF COPY. These later bytes are not the exact tested images.','workflow_policy':'Functional experiment fixes used explicit manual candidate workflow, which runs full unit/frontend and candidate checks. [skip ci] avoided unchanged default targeted-native repetition; baseline32eb actual CI remains separately scoped. Final docs commit skips repeated code CI; skipped is not passing.','current_state_hash':'Manifest pointer filled after seal; Git binds final CURRENT_STATE bytes','authorization':'User authorized isolated experiment, regression and GitHub sync; no default runtime replacement, backend publication, license-option selection or residual-risk acceptance'})
    print(json.dumps({'candidate':str(CANDIDATE),'selected_sources':len(chosen),'selected_source_bytes':sum(p.stat().st_size for p,_ in chosen)}))

def seal():
    obs=json.loads((RUN/'final-observation.json').read_text())
    for name,h in FIXED.items():assert sha(ROOT/name)==h,name
    old_recipe=subprocess.check_output(['git','show','afe6fc27188107fe07ccf3899bc92d4c0a0a013c:docker/langflow.Dockerfile'],cwd=ROOT)
    assert hashlib.sha256(old_recipe).hexdigest()==sha(ROOT/'docker/langflow.Dockerfile')
    old=[]
    for name in ['v02-acceptance','v02-release','release-compatibility','runtime-maintenance']:
        base=ROOT/'docs/evidence'/name;m=json.loads((base/'manifest.json').read_text())
        for item in m['files']:
            p=base/item['path'];assert p.resolve().is_relative_to(base.resolve()) and not p.is_symlink()
            assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],str(p)
        old.append({'packet':name,'manifest_sha256':sha(base/'manifest.json'),'verified_payload_files':len(m['files']),'unchanged':True})
    new_temp=[p for p in RUN.rglob('*') if p.is_file()]
    old_temp=[p for p in OLD_TEMP.rglob('*') if p.is_file()]
    new_bytes=sum(p.stat().st_size for p in new_temp);combined=new_bytes+sum(p.stat().st_size for p in old_temp)
    assert new_bytes<=3*1024**2 and combined<=40*1024**2
    dump(CANDIDATE/'environment/protection-check.json',{'at':datetime.now(UTC).isoformat(),'fixed_inputs':[{'path':p,'sha256':h,'unchanged':True} for p,h in FIXED.items()],'prior_packets':old,'original_database_or_volumes':'not started, attached, migrated or deleted','localDocker':'No daemon start/build/pull/prune; only help/config used','named_temporary_bytes':new_bytes,'prior_plus_current_named_temporary_bytes':combined,'cleanup_authorized':False})
    files=[p for p in sorted(CANDIDATE.rglob('*')) if p.is_file()]
    entries=[{'path':str(p.relative_to(CANDIDATE)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    assert len(entries)<1000 and sum(e['bytes'] for e in entries)<100*1024**2
    m={'evidence_id':'langflow-candidate','classification':'sealed_evidence','sealed_at':datetime.now(UTC).isoformat(),'display_date':'2026-11-04 America/Los_Angeles','contract':'ARC-UPGRADE@0.1.0','spec_sha256':FIXED['docs/UPGRADE_SPEC.md'],'candidate_version':'langflow-base1.13.1 / lfx1.13.1','source_commit':obs['source_commit'],'candidate_CI':obs['code_ci_run'],'observations':obs['facts'],'acceptance':{'RELEASE-001':'Isolated candidate experiment; see per-check actual evidence','AC-19':'not_passed_for_default_full_release','default_adoption':'not_performed','full_v02_last_verified':None,'final_acceptance':'pending','residual_risk_accepted':False,'backend_distribution_approval':False},'provenance':'selection.json, exact CI source/run/image IDs, qualified originals/derived subsets and producer snapshots. Unselected reports and transports are not claimed as retained.','prior_packets':old,'source_author_baseline_bytes':764861,'generated_payload_bytes':sum(e['bytes'] for e in entries),'artifact_condition':{'active_evidence':'sealed','cache_state':'warning: prior localDocker inventory not freshly verified','pending_cleanup':True,'pending_migration':False,'new_temp_bytes_at_seal':new_bytes,'prior_and_current_temp_bytes':combined,'no_history_cleanup':True},'artifact_disposition':[{'artifact':'langflow-candidate-evidence','classification':'sealed_evidence','action':'retain-active'},{'artifact':'candidate-promotion-source','classification':'evidence_candidate','action':'retain-active; no cleanup authority'},{'artifact':'pytest scratch and unselected ephemeral diagnostics','classification':'ephemeral_run_output','action':'retain outside formal payload; cleanup pending authorization'}],'limits':json.loads((RUN/'plan.json').read_text()),'documentation_followup':'environment/documentation-impact.json; final docs do not claim new image build','files':entries,'payload_files':len(entries),'payload_bytes':sum(e['bytes'] for e in entries),'manifest_self_hash':'Excluded; bound by Git and CURRENT_STATE'}
    dump(CANDIDATE/'manifest.json',m)
    assert not FORMAL.exists();FORMAL.mkdir()
    for e in entries+[{'path':'manifest.json'}]:copy_x(CANDIDATE/e['path'],FORMAL/e['path'])
    print(json.dumps({'formal':str(FORMAL),'manifest_sha256':sha(FORMAL/'manifest.json'),'payload_files':len(entries),'payload_bytes':m['payload_bytes'],'old_payloads_verified':sum(x['verified_payload_files'] for x in old),'new_temp_bytes':new_bytes,'combined_temp_bytes':combined}))

if __name__=='__main__':
    import sys
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['seal']:seal()
    else:raise SystemExit('prepare or seal')
