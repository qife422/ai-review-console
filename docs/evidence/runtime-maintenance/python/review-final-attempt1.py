"""Derive bounded final review from existing selected CI bytes and existing ZIPs only."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path('/private/tmp/arc-runtime-maintenance.wT9huB')
OUT=ROOT/'python/final-runtime-review.json'
OLD=Path('/private/tmp/arc-release-followup.rLeRu5/ci/final-a64ab47/selected/release')
SOURCE='2e45bee8c61dfab347edd107aebb6a3488567761'
inputs={}
def read(path):
    raw=path.read_bytes()
    inputs[str(path)]={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    return raw
def load(path):return json.loads(read(path))
def norm(name):return re.sub(r'[-_.]+','-',name).lower()
def alias_groups(ids,docs):
    parent={}
    def find(x):
        parent.setdefault(x,x)
        if parent[x]!=x:parent[x]=find(parent[x])
        return parent[x]
    def union(a,b):parent[find(b)]=find(a)
    for vid in ids:
        rec=docs[vid];assert rec['status']=='fetched'
        doc=rec['document'];assert doc['id']==vid
        for a in [vid]+doc.get('aliases',[]):union(vid,a)
    grouped={}
    for v in ids:grouped.setdefault(find(v),[]).append(v)
    aliases=sorted(parent)
    return len(grouped),aliases

def findings_summary(summary,docs,old_findings):
    results=[];allids=set()
    for row in summary['images']['langflow']['findings']:
        ids=set(row['vulnerability_ids']);allids|=ids
        count,aliases=alias_groups(ids,docs)
        old=old_findings.get(norm(row['package']))
        previous=set(old['vulnerability_ids']) if old else set()
        results.append({'package':row['package'],'version':row['version'],'advisory_ids':sorted(ids),'advisory_count':len(ids),'alias_connected_groups':count,'aliases_union':aliases,'old_version':old['version'] if old else None,'added_ids_vs_prior_query':sorted(ids-previous),'absent_ids_vs_prior_query':sorted(previous-ids),'same_version_and_id_set_as_prior_query':bool(old and row['version']==old['version'] and ids==previous)})
    count,_=alias_groups(allids,docs)
    return {'packages':results,'package_count':len(results),'unique_advisory_ids':len(allids),'alias_connected_groups':count}

def rpm_rows(raw):
    rows=[]
    for line in raw.decode().splitlines():
        fields=line.split('\t');assert len(fields)==4,repr(line)
        rows.append(dict(name=fields[0],evr=fields[1],arch=fields[2],signature=fields[3]))
    assert len({(x['name'],x['evr'],x['arch']) for x in rows})==len(rows)
    return rows

def nevr(rows):return {(x['name'],x['evr'],x['arch']) for x in rows}

def workflow_review(v):
    assert v['result']=='passed' and v['langflow_version']=='1.11.6' and v['component_count']==5
    assert v['stored_flow_hashes_before']==v['stored_flow_hashes_after']
    assert {x['decision'] for x in v['cases']}=={'approved','rejected','changes_requested'}
    assert {x['source_format'] for x in v['cases']}|{v['markdown_intake']['source_format']}=={'txt','docx','pdf','md'}
    assert len(v['cases'])==3 and all({r['format'] for r in x['reports']}=={'json','html','pdf'} for x in v['cases'])
    assert all(x.get('intake_langflow_job_id') and x.get('report_langflow_job_id') for x in v['cases'])
    retry=v['failure_retry'];assert retry['same_key_upload_and_retry_deduplicated']
    assert retry['first_job']['state']==retry['retry_job']['state']=='failed'
    assert retry['audit_event_counts']=={'document_received':1,'intake_failed':2,'intake_retry_requested':1}
    assert v['markdown_intake']['intake_job']['state']=='succeeded'
    return {'result':'passed','component_count':5,'document_formats':4,'decisions':3,'report_downloads':9,'both_real_flow_job_ids_present':True,'stored_flow_hashes_unchanged':True,'failure_retry_deduplicated':True,'benchmark':v['benchmark']}

def probe_review(v):
    assert v['baseline_mode'] is False and v['synthetic_only'] is True and v['network']=='forbidden'
    assert v['datamodel']['valid_payloads']==1 and v['datamodel']['rejected_payloads']==3
    assert v['oauthlib']['jsonp_parameter_removed'] and all(v['oauthlib'][k]=='passed' for k in ['pkce_request','requests_oauthlib_prepare','state_rejection','token_and_revocation'])
    o=v['otel'];assert o['oversized_tracestate_discarded'] and o['in_memory_spans']==5
    assert all(o[k]=='passed' for k in ['fastapi_instrumentation','propagation','thread_context'])
    g=o['tracestate_ingress'];assert g['limit_bytes']==8192 and g['all_discarded'] and {c['case'] for c in g['cases']}=={'single','split'}
    assert all(c['combined_bytes']==8351 and c['discarded'] and c['trace_id_preserved'] for c in g['cases'])
    expected={'opentelemetry.trace.span':'67886d3802f7d87adcc6bc26d790ecef0b1fb89b1aed3e28f7c6d73b0b739e38','opentelemetry.trace.propagation.tracecontext':'ac6fbcf1610a51ebf9d9161e42e9e98d4e22a50552c57bb37596a62963e00776'}
    assert {a['module']:a['sha256'] for a in o['actual_imported_sources']}==expected
    assert v['scratch']['bytes']<=v['scratch_limit_bytes'] and v['scratch']['files']<=v['scratch_limit_files']
    return {'security_and_compatibility_assertions':'passed','tracestate_ingress':g,'actual_imported_sources':o['actual_imported_sources'],'versions':v['versions'],'scratch':v['scratch']}

assert not OUT.exists()
old_summary=load(OLD/'images/summary.json')
old_findings={norm(x['package']):x for x in old_summary['images']['langflow']['findings']}
old_rhel=load(OLD/'rhel/summary.json')
old_rpm=load(OLD/'rhel/rpm-mappings.json')['packages']
old_evr={(x['package'],x['version_with_epoch'],x['architecture']) for x in old_rpm}
pins={norm(n):v for n,v in re.findall(r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s\\]+)',read(Path('docker/langflow.Dockerfile')).decode())}
assert len(pins)==52
report={'schema':'arc.final-runtime-independent-review.v1','source_commit':SOURCE,'ci_run_id':41586599463,'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'method':'No network, build, installation, container startup, scan or duplicate artifact download. Parse selected existing JSON/XML/text; read existing ZIP member in memory only for actual interpreter version and verify against child manifest. RPM before/after comparison is within each current build image.','prior_sealed_packet_manifest_sha256':'0466646bd5eecd32768e9fc61bf138815853292049a41a95dc1d98927e2081ef','prior_query':{'source':'a64ab476c8acfaa36a3d6cc260a4c6c286bad380','root':str(OLD),'rhel_advisory_ids':old_rhel['observed_unique_advisory_ids'],'package_scan_at':old_summary['started_at'],'rhel_scan_at':old_rhel['started_at']},'architectures':{}}
allpypi={};rpm_evr_normalized={};map_hashes={}
for arch,machine in [('amd64','x86_64'),('arm64','aarch64')]:
    base=ROOT/f'ci/final-2e45bee-{arch}';p=base/'release'
    selection=load(base/'selection.json');assert selection['source_commit']==SOURCE
    manifest=load(p/'manifest.json');assert manifest['collection_state']=='collected' and manifest['runner_machine']==machine
    inventory=load(p/'images/langflow-inventory.json');assert inventory['identity']['id']==manifest['images']['langflow'] and inventory['identity']['architecture']==arch
    python_packages=[x for x in inventory['packages'] if x['type']=='pypi']
    installed={norm(x['name']):x['version'] for x in python_packages};assert len(installed)==len(python_packages)
    assert all(installed.get(n)==v for n,v in pins.items())
    allpypi[arch]=installed
    commands={x['stdout'].removesuffix('.stdout'):x for x in manifest['commands']}
    for label in ['api-pip-check','langflow-pip-check','dependency-compatibility']:
        assert commands[label]['exit_code']==0 and commands[label]['stop_reason'] is None
    for name in ['api','langflow']:
        assert read(p/f'{name}-pip-check.stdout').decode().strip()=='No broken requirements found.'
    probe=probe_review(load(p/'dependency-compatibility.stdout'))
    workflow=workflow_review(load(base/'workflow.json'))
    with zipfile.ZipFile(ROOT/f'ci/private/{arch}-41586599463.zip') as z:
        member='release/images/langflow-python.stdout';raw=z.read(member);iv=json.loads(raw)
        child=json.loads(z.read('release/images/manifest.json'))
        entry=next(x for x in child['files'] if x['path']=='langflow-python.stdout')
        assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
        assert iv['python_version'].startswith('3.14.8 ')
        interpreter={'python_version':iv['python_version'],'interpreter':iv['interpreter'],'archive':str(ROOT/f'ci/private/{arch}-41586599463.zip'),'member':member,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'verified_against_child_manifest':True,'not_extracted':True}
    sm=load(p/'system/manifest.json');assert sm['status']=='completed'
    assert all(x['exit_code']==0 and x['stop_reason'] is None for x in sm['commands'])
    before=rpm_rows(read(p/'system/rpm-before.stdout'));after=rpm_rows(read(p/'system/rpm-after.stdout'))
    b={(x['name'],x['arch']):x for x in before if x['name']!='gpg-pubkey'};a={(x['name'],x['arch']):x for x in after if x['name']!='gpg-pubkey'}
    changed=[{'package':k[0],'arch':k[1],'before':b[k]['evr'],'after':a[k]['evr'],'after_signature':a[k]['signature']} for k in sorted(a.keys()&b.keys()) if a[k]['evr']!=b[k]['evr']]
    added=[a[k] for k in sorted(a.keys()-b.keys())];removed=[b[k] for k in sorted(b.keys()-a.keys())]
    assert all(x['after_signature'].startswith('RSA/SHA256,') for x in changed) and all(x['signature'].startswith('RSA/SHA256,') for x in added)
    rh=load(p/'rhel/summary.json');rm=load(p/'rhel/rpm-mappings.json')['packages']
    rr={(x['package'],x['version_with_epoch'],x['architecture']) for x in rm}
    default_rpm={(x['name'],x['version'],x['arch']) for x in inventory['packages'] if x['type']=='rpm'}
    assert nevr(after)==rr and default_rpm=={(n,v.split(':',1)[1],ar) for n,v,ar in rr}
    mappings=load(p/'images/package-mappings.json')['mappings']
    default_unknown=[x for x in mappings if x['image']=='langflow' and x['mapping_status']!='mapped']
    assert len(default_unknown)==len(default_rpm)==rh['rpm_entries']==227
    assert {(x['package']['name'],x['package']['version'],x['package']['arch']) for x in default_unknown}==default_rpm
    assert rh['mapped_software_packages']==224 and rh['metadata_only_public_keys']==3
    assert rh['mapping_unknown']==rh['query_unknown']==rh['detail_unknown']==rh['observed_unique_advisory_ids']==0
    assert rh['image_id']==manifest['images']['langflow'] and manifest['audits']=={'package_scan_exit_code':2,'redhat_supplement_exit_code':0}
    rp=[x for x in rm if x['package']!='gpg-pubkey'];assert all(x['mapping_status']=='mapped' and x['vendor']=='Red Hat, Inc.' for x in rp)
    rpm_evr_normalized[arch]={(x['package'],x['version_with_epoch']) for x in rp}
    binding=load(p/'rhel/product-bindings.json')
    rhmanifest=load(p/'rhel/manifest.json');mapentry=next(x for x in rhmanifest['files'] if x['path']=='repository-to-cpe.json');map_hashes[arch]=mapentry['sha256']
    images=load(p/'images/summary.json');docs=load(p/'images/vulnerabilities.json');findings=findings_summary(images,docs,old_findings)
    assert findings['package_count']==5 and findings['unique_advisory_ids']==81 and findings['alias_connected_groups']==59
    assert all(x['same_version_and_id_set_as_prior_query'] for x in findings['packages'])
    if arch=='arm64':
        assert manifest['native_materials_profile']=='arm-backend' and manifest['native_materials']['state']=='not_collected_on_arm_backend' and manifest['native_materials']['distribution_approval'] is False
        assert 'native-materials' not in commands
    else:
        assert manifest['native_materials_profile']=='complete' and commands['native-materials']['exit_code']==0
    report['architectures'][arch]={'images':manifest['images'],'interpreter':interpreter,'pinned_versions':{'count':52,'all_exact_installed':True,'versions':pins},'pypi_package_count':len(installed),'pip_checks':'passed','offline_probe':probe,'workflow':workflow,'system':{'os_before':sm['os_before'],'os_after':sm['os_after'],'commands_all_exit_zero':True,'repository_policy':sm['repositories'],'redhat_release_key_sha256':sm['redhat_release_key_sha256'],'rpm_rows_before':len(before),'rpm_rows_after':len(after),'software_before':len(b),'software_after':len(a),'existing_software_version_changes':len(changed),'changes':changed,'added':added,'removed':removed,'three_public_key_nevras_unchanged':nevr([x for x in before if x['name']=='gpg-pubkey'])==nevr([x for x in after if x['name']=='gpg-pubkey']),'before_exact_matches_prior_amd64_rpm_set':nevr(before)==old_evr if arch=='amd64' else None},'rhel_supplement':{k:rh[k] for k in ['result','rpm_entries','mapped_software_packages','metadata_only_public_keys','unique_queries','observed_unique_advisory_ids','mapping_unknown','query_unknown','detail_unknown','database_snapshot_date','started_at']},'rpm_coverage':{'default_inventory_equals_rhel_without_epoch':True,'system_after_full_epoch_nevra_equals_rhel':True,'default_227_unknowns_exactly_same_rpm_set':True,'same_exact_image_id':True,'ecosystems':binding['ecosystems'],'all_software_vendor_redhat':True,'repository_map_sha256':map_hashes[arch]},'langflow_remaining_python':findings,'all_images_finding_counts':{n:{k:x[k] for k in ['observed_unique_advisory_ids','unknown_packages','detail_unknown','matched_binary_or_python_packages']} for n,x in images['images'].items()},'package_scan_time':images['started_at'],'native_materials_scope':manifest.get('native_materials',{'state':'collected_on_amd64','legal_approval':False})}
assert map_hashes['amd64']==map_hashes['arm64']
unit=ROOT/'ci/final-2e45bee-unit/arc-unit.xml';xml=ET.fromstring(read(unit));suites=list(xml.iter('testsuite'))
counts={k:sum(int(x.attrib.get(k,0)) for x in suites) for k in ['tests','errors','failures','skipped']}
assert counts=={'tests':188,'errors':0,'failures':0,'skipped':0}
excerpt=load(ROOT/'ci/verify-count-excerpt.json');assert any('Tests  29 passed (29)' in s for s in excerpt['lines'])
report['unit_verification']={'python_junit':counts,'frontend_tests':29,'frontend_count_basis':excerpt,'scope':'Verify job is AMD64; ARM lane ran real workflow and offline probes, not this188-test unit suite.'}
report['architecture_comparison']={'amd64_only_pypi':{n:v for n,v in allpypi['amd64'].items() if n not in allpypi['arm64']},'arm64_only_pypi':{n:v for n,v in allpypi['arm64'].items() if n not in allpypi['amd64']},'shared_pypi_version_differences':{n:[allpypi['amd64'][n],allpypi['arm64'][n]] for n in allpypi['amd64'].keys()&allpypi['arm64'].keys() if allpypi['amd64'][n]!=allpypi['arm64'][n]},'same_rpm_name_full_evr_set_ignoring_arch':rpm_evr_normalized['amd64']==rpm_evr_normalized['arm64'],'same_official_repository_map_bytes':True}
report['qualifications']=['The prior sealed packet remains unchanged; this is a new source/image/query-time record.','60 changed software versions plus1 added package are established by same-image build RPM before/after records, not by subtracting cross-date OSV counts.','Prior23RHSA IDs and current0IDs are different query times and installed versions; do not call this23independent CVEs fixed or proof of exploitability.','Default scanner exit2 remains recorded; its227RPM unknowns are exactly covered by the same-image supplemental224software+3metadata keys, with no mapping/query/detail unknown.','Current API126, PostgreSQL130 and Web4 IDs remain package findings; current Web4 libexpat findings mean the old Web0 statement is historical only.','No-match is not absolute security; native/static embedded libraries, vendor source correspondence and complete binary redistribution obligations are outside package-query closure.','AMD64 browser and native evidence does not prove ARM UI/native materials; ARM Linux cloud runs do not constitute a local Mac host validation.','No release acceptance, residual-risk acceptance, real-data access, deployment, cleanup or base-Langflow upgrade is granted.']
report['input_fingerprints']=list(inputs.values())
producer=Path(__file__).read_bytes();report['producer']={'path':str(Path(__file__).resolve()),'sha256':hashlib.sha256(producer).hexdigest(),'actual_command':f'python3 -B {Path(__file__).resolve()}','argv':sys.argv}
raw=(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode();assert len(raw)<100*1024,len(raw)
with OUT.open('xb') as stream:stream.write(raw)
print(json.dumps({'output':str(OUT),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'unit':counts,'frontend':29,'architectures':{a:{'pins':52,'python':v['interpreter']['python_version'],'rpm_changes':v['system']['existing_software_version_changes'],'rhel_ids':v['rhel_supplement']['observed_unique_advisory_ids'],'python_ids':v['langflow_remaining_python']['unique_advisory_ids'],'python_alias_groups':v['langflow_remaining_python']['alias_connected_groups']} for a,v in report['architectures'].items()},'arch_diff':report['architecture_comparison']}))
