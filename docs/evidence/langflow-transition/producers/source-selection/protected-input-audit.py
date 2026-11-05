from pathlib import Path
import hashlib,json,datetime,subprocess,os,shutil,re
repo=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
temp=Path('/private/tmp/arc-langflow-transition.l7tcavqh')
prior=[Path('/private/tmp/arc-runtime-maintenance.wT9huB'),Path('/private/tmp/arc-langflow-candidate.qya6psom')]
revision='8e96a36d44119b577a34ebc7a16d110a856e927a'
def sha(b):return hashlib.sha256(b).hexdigest()
def inventory(path):
 if not path.exists():return {'path':str(path),'exists':False,'files':0,'bytes':0}
 count=size=links=0
 for d,dirs,files in os.walk(path,followlinks=False):
  for name in files:
   p=Path(d)/name
   if p.is_symlink():links+=1;continue
   count+=1;size+=p.stat().st_size
 return {'path':str(path),'exists':True,'files':count,'bytes':size,'symlink_files_excluded':links}
old=[inventory(p) for p in prior];current=inventory(temp);sources=inventory(temp/'sources')
limits={'new_temp_bytes':2097152,'combined_temp_bytes':41943040,'sources_bytes':131072,'sources_files':8}
assert current['bytes']+24000<=limits['new_temp_bytes']
assert sum(x['bytes'] for x in old)+current['bytes']+24000<=limits['combined_temp_bytes']
assert sources['bytes']<=limits['sources_bytes'] and sources['files']<=limits['sources_files']
fixed=[]
for rel,size,digest in [
 ('review_console.sqlite3',57344,'980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f'),
 ('docs/UPGRADE_SPEC.md',50489,'a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753'),
 ('docs/spec-baseline.json',8731,'5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e')]:
 raw=(repo/rel).read_bytes();fixed.append({'path':rel,'bytes':len(raw),'sha256':sha(raw),'expected_bytes':size,'expected_sha256':digest,'unchanged':len(raw)==size and sha(raw)==digest})
packets=[]
for name,digest in [
 ('v02-acceptance','6e3fa0159c396b1d422b32d90ccabb772b82db5d5cbeddb6e385e0e54138ba1c'),
 ('v02-release','c2a9cba23f3653e7c507654631f74568ee7490f80212ffe382c92323a4547f36'),
 ('release-compatibility','0466646bd5eecd32768e9fc61bf138815853292049a41a95dc1d98927e2081ef'),
 ('runtime-maintenance','5a400e77b5e3b28426f2efe99d723b48aee5e1e95d9c7e4a4c9665364963b724'),
 ('langflow-candidate','ca0a0b0b38c2ca735ae17b83c93cc022fd89899a8b8f0e82b978b1eb3b5a38ec')]:
 base=repo/'docs/evidence'/name;p=base/'manifest.json';raw=p.read_bytes();data=json.loads(raw)
 mismatches=[];total=0;seen=set()
 assert isinstance(data['files'],list)
 for row in data['files']:
  rel=row['path'];payload=(base/rel).resolve();assert payload.is_relative_to(base.resolve()) and rel not in seen;seen.add(rel)
  assert isinstance(row['bytes'],int) and re.fullmatch('[a-f0-9]{64}',row['sha256'])
  actual=payload.read_bytes();total+=len(actual)
  if len(actual)!=row['bytes'] or sha(actual)!=row['sha256']:mismatches.append(rel)
 packets.append({'packet':name,'manifest_path':str(p.relative_to(repo)),'manifest_bytes':len(raw),'manifest_sha256':sha(raw),'expected_manifest_sha256':digest,'manifest_unchanged':sha(raw)==digest,'payload_fields':'files[].path / bytes / sha256; paths relative to own manifest parent','payload_files':len(seen),'payload_bytes':total,'mismatch_count':len(mismatches),'mismatched_paths':mismatches,'unchanged':sha(raw)==digest and not mismatches})
default=[]
for rel in ['docker/langflow.Dockerfile','requirements.lock']:
 raw=(repo/rel).read_bytes();base=subprocess.check_output(['git','show',revision+':'+rel],cwd=repo)
 entry={'path':rel,'bytes':len(raw),'sha256':sha(raw),'baseline_revision':revision,'baseline_bytes':len(base),'baseline_sha256':sha(base),'unchanged':raw==base}
 if rel.endswith('Dockerfile'):
  pins=re.findall(rb'\b([A-Za-z0-9_.-]+)==([^\s\\]+)',raw);oldpins=re.findall(rb'\b([A-Za-z0-9_.-]+)==([^\s\\]+)',base)
  entry.update({'inline_exact_pin_count':len(pins),'inline_pins_unchanged':pins==oldpins,'independent_default_52_pin_file':'none: all52 pins are inline in this Dockerfile; candidate constraints is not default input'})
 default.append(entry)
report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exact_repo_path':str(repo),'source_command':'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /private/tmp/arc-langflow-transition.l7tcavqh/protected-input-audit.py','producer_sha256':sha(Path(__file__).read_bytes()),'method':'Read-only bounded fixed input and five manifest-listed payload byte/size/SHA256 comparison; git show only for exact baseline bytes. No DB contents emitted or DB execution, migration, Docker command, copying/archive or cleanup.','fixed_inputs':fixed,'sealed_packets':packets,'payload_files_total':sum(x['payload_files'] for x in packets),'all1155_payloads_and_five_manifests_unchanged':len(packets)==5 and sum(x['payload_files'] for x in packets)==1155 and all(x['unchanged'] for x in packets),'default_inputs':default,'all_protected_inputs_unchanged':all(x['unchanged'] for x in fixed+packets+default),'host_free_bytes':shutil.disk_usage(repo).free,'local_docker':'No local Docker command or daemon start/build/pull/prune performed by this audit; current round no local Docker run is caller-provided scope, not independently inferred from daemon state.','temporary_inventory_before_report_write':{'old_two':old,'new':current,'combined_bytes':sum(x['bytes'] for x in old)+current['bytes'],'sources':sources},'limits':limits,'paths':{'candidate':inventory(repo/'artifacts/evidence-candidates/langflow-transition'),'formal':inventory(repo/'docs/evidence/langflow-transition')},'cleanup_authorized':False,'old_evidence_or_database_modified':False}
raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();assert len(raw)<=12*1024
report['temporary_projected_after_this_report_write_bytes']=current['bytes']+len(raw)
raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();assert len(raw)<=12*1024
out=temp/'private/protected-input-review.json'
with out.open('xb') as f:f.write(raw)
print(json.dumps({'path':str(out),'bytes':len(raw),'sha256':sha(raw),'unchanged':report['all_protected_inputs_unchanged'],'payload_total':report['payload_files_total'],'combined_temp_bytes_after':sum(x['bytes'] for x in old)+current['bytes']+len(raw)}))
