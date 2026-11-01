from pathlib import Path
import json,hashlib,re,datetime
root=Path(__file__).resolve().parent
src=json.loads((root/'official-source-access.json').read_text()); extra=json.loads((root/'additional-official-source-access.json').read_text()); sources=src['requests']+extra['requests']
archives={}
for r in sources:
 p=r.get('package')
 if p and r.get('source_archives'):archives[(p['name'].replace('_','-').lower(),p['version'])]=r['source_archives']
checks={}
for r in sources:
 if r.get('state')=='retrieved' and r['url'].endswith('.sha256'):
  checks[r['url']]={'upstream_archive_sha256':r['text'].split()[0],'checksum_response_sha256':r['sha256'],'checksum_url':r['url'],'fetched_at':r['retrieved_at'],'downloaded_archive':False,'binary_correspondence_verified':False}
rows=[]; images={}; total=0
for image in ['api','langflow']:
 d=json.loads((root/f'{image}-native.stdout').read_text()); record=json.loads((root/f'{image}-native.record.json').read_text());images[image]=record|{'packages':d['packages'],'pillow_feature_versions':d['pillow_feature_versions'],'lxml_versions':d['lxml_versions']}; total+=d['hashed_bytes']
 for f in d['native_files']:
  owner=f['package'];version=f['package_version'];base=Path(f['path']).name;row=f|{'image':image,'image_id':record['image_id'],'library_version':None,'license_identity':'see exact owner package license plus bundled-component terms','upstream_source_archives':archives.get((owner,version),[]),'corresponding_source_complete':False,'remaining_items':[]}
  if owner=='psycopg-binary':row['upstream_source_archives']=archives.get(('psycopg-c',version),[]);row['license_file']='psycopg_binary-3.3.5.dist-info/licenses/LICENSE.txt (LGPL-3.0-only for binding; bundled library own terms)'
  if owner=='psycopg2-binary':row['upstream_source_archives']=archives.get(('psycopg2',version),[]);row['license_file']='psycopg2_binary-2.9.12.dist-info/licenses/LICENSE (LGPL-3.0-or-later + package OpenSSL exception; bundled library own terms)'
  if owner=='pillow':row['license_file']=f'pillow-{version}.dist-info/licenses/LICENSE (MIT-CMU plus named native notices)'
  if owner=='lxml':row['license_file']=f'lxml-{version}.dist-info/licenses/LICENSE.txt and LICENSES.txt (BSD + embedded component terms)'
  v=f.get('reported_version')
  if isinstance(v,int):
   row['library_version']=f'{v//10000}.{v%10000}'
   row['license_identity']='PostgreSQL License'
   u=f"https://ftp.postgresql.org/pub/source/v{row['library_version']}/postgresql-{row['library_version']}.tar.bz2.sha256";row['native_upstream_reference']=checks.get(u)
   row['remaining_items']=['Validate upstream source against actual wheel builder patches/options; include libpq notice with distributed artifact.']
  elif isinstance(v,str) and v.startswith('OpenSSL'):
   ver=v.split()[1];row['library_version']=ver
   row['license_identity']='Apache-2.0' if ver.startswith('3.') else 'OpenSSL AND SSLeay (pre-3.0 dual terms)'
   u=f'https://github.com/openssl/openssl/releases/download/openssl-{ver}/openssl-{ver}.tar.gz.sha256' if ver.startswith('3.') else f'https://www.openssl.org/source/old/1.1.1/openssl-{ver}.tar.gz.sha256'
   row['native_upstream_reference']=checks.get(u);row['remaining_items']=['Validate actual builder source/patches and carry native license notices.']
   if 'FIPS' in v:row['remaining_items'].append('FIPS/vendor source package revision, module and patches unknown; upstream1.1.1k checksum does NOT identify vendor corresponding source.')
  elif owner=='pillow':
   mapping={'libfreetype':'freetype2','liblcms':'littlecms2','libwebp':'webp','libavif':'avif','libjpeg':'libjpeg_turbo','libopenjp2':'jpg_2000','libtiff':'libtiff','libzlib_ng':'zlib_ng'}
   for prefix,key in mapping.items():
    if base.startswith(prefix):row['library_version']=d['pillow_feature_versions'].get(key);row['version_method']='PIL.features version of linked module; verify mapping/patches';break
   row['remaining_items']=['Map this exact native path/hash to Pillow named bundled notice; identify source archive/hash and build patches of this component, not just Pillow parent sdist.']
  elif owner=='lxml':
   row['linked_runtime_versions']=d['lxml_versions'];row['remaining_items']=['Match static libxml/libxslt build input, patches/options and per-file notices; parent lxml sdist is not complete proof.']
  else:row['remaining_items']=['Exact native source version/patch provenance not established by filename/SONAME; obtain wheel builder manifest/source package and applicable per-file notice.']
  if row['library_version'] is None:row['source_version_state']='not_independently_identified'
  else:row['source_version_state']='runtime_version_identified_build_correspondence_unverified'
  rows.append(row)
report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Existing Linux/arm64 exact images, not newer or AMD64 images; no build/pull/install or image export.','images':images,'native_file_matrix':rows,'source_archive_method':'Exact PyPI version JSON source distribution URL/hash, or official upstream checksum text; archives were not downloaded and correspondence not verified.','source_access_records':['official-source-access.json','additional-official-source-access.json'],'source_reference_hashes':checks,'limits':{'planned_paths_batch':100,'observed_paths_batch':len(rows),'path_limit_deviation':'producer applied100 per image, total101; one extra path read; no further collection or deletion; raw output retained','planned_hash_input_bytes':209715200,'actual_hash_input_bytes':total,'per_image_json_bytes':[{'image':n,'bytes':(root/f'{n}-native.stdout').stat().st_size} for n in images]},'zep_candidate_resolution':{'current_requirement':'zep-python==2.0.2; selected extras of langflow-base0.11.6 and lfx-bundles1.1.2; official lfx-bundles1.2.0 still exact2.0.2','current_license':'unresolved; previously verified exact wheel/sdist/tag lacks declaration','candidate_1.5.0':'same-name exact tag Apache2 confirmed, but violates exact2.0.2 and httpx<0.25 conflicts with current stack','candidate_2.0.0_rc6':'same-name exact tag and Apache2 identify a prerelease; violates exact2.0.2 and no prerelease substitution authorized','candidate_v2.0.0_tag':'REJECTED as identity proof: upstream pyproject name zep-cloud, so its Apache2 cannot license different PyPI zep-python2.0.0','compatible_licensed_candidate_in_current_reverse_constraints':None,'closure_condition':'Exact2.0.2 upstream permission evidence, or explicitly scoped supported runtime without Zep extra and corresponding verification; no message/issue sent.'},'amd64_ibm_driver':{'python_package':'ibm_db3.2.9','python_source_archives':archives.get(('ibm-db','3.2.9'),[]),'python_source_license':'Apache-2.0 exact tag and PyPI confirmed previously','native_driver_version':None,'native_driver_license':None,'remaining_items':['Read actual AMD64 clidriver declared files, version and license texts; ARM64 absence cannot substitute.','Verify distribution permission for driver separately from Python binding; exact driver source/access and included notices remain unknown.'],'conditional_use':'Same-version official README distinguishes LUW from paid Db2 Connect rights for z/OS/i; no such integration enabled or paid license accepted.'},'conclusions':{'source_and_static':'Exact third-party attribution, project/font licenses and actual frontend bundle license texts identified; two missing exact license texts now copied into licenses/; final image inclusion requires readback.','full_backend_binary_distribution':'NOT_APPROVED; actual native identity and official source references advanced, but Zep and vendor/native corresponding-source/material obligations remain explicit.','legal_approval':False},'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(root.iterdir()) if p.is_file() and p.name!='native-distribution-matrix.json']}
(root/'native-distribution-matrix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('matrix',len(rows),'paths',total,'hash-input-bytes','recorded native known versions',sum(r['library_version'] is not None for r in rows))
print('temp',sum(p.stat().st_size for p in root.iterdir() if p.is_file()),'bytes',sum(p.is_file() for p in root.iterdir()),'files')
