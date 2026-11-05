import json,hashlib,urllib.request,datetime,re
from pathlib import Path
from html.parser import HTMLParser
path=Path('/private/tmp/arc-langflow-transition.l7tcavqh/sources/debian-tracker-assessment.json')
d=json.loads(path.read_bytes());details=[]
for cve in ('CVE-2026-109518','CVE-2026-95209'):
 url='https://security-tracker.debian.org/tracker/'+cve
 with urllib.request.urlopen(url,timeout=30) as r:raw=r.read(262145);final=r.url
 assert len(raw)<=262144
 details.append({'id':cve,'url':url,'final_url':final,'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'method':'Official CVE HTML table/description read in memory; no raw body retained','selected_fact':('Official source-package table: apt bookworm2.6.1 vulnerable; bookworm security2.6.2 fixed. Fixed-version table bookworm2.6.2/DLA-4880-1. Upgrade identified, not applied.' if cve.endswith('109518') else 'CVE description explicitly disputed by multiple parties; no vulnerable/fixed package table or Debian release mapping present. Preserve unknown applicability, do not convert to false positive or fixed.')})
d['advisory_details']=details
d['upgrade_assessment']={'verified_actionable_source':'apt','installed':'2.6.1','bookworm_security_fixed':'2.6.2','affected_installed_binaries':['apt','libapt-pkg6.0'],'advisory':'CVE-2026-109518','official_announcement':'DLA-4880-1','qualification':'Tracker source and CVE tables identify a fix; apt repository availability/resolver/current image rebuild and rescan remain unverified. All other listed source-page main/security versions do not imply newer installed versions; main may be older than security or vice versa.'}
d['license_material_assessment']={
 'existing_material_can_support':[
 {'component':'APSW3.53.4.0','material':'Actual own-license1166B match to exact upstream LICENSE already recorded in environment/candidate-license-final-review.json','closure':'Own-license-text material gap already closed; embedded SQLite correspondence and distribution obligations remain open.'},
 {'component':'langflow-base/LFX1.13.1','material':'sources/langflow-1.13.1-license-source.json retains lossless exact-v1.13.1 root MIT1065B SHA48d4a7496209a9e1f2f549384251b69319360c3a38127cf513473590be383359; repo licenses/Langflow-LICENSE.txt differs only one trailing newline. Existing sources/base-pyproject.toml plus version metadata identify monorepo package context.','closure':'No new network read needed to identify/reproduce official MIT text. This does not establish dist-info own copies or exact image project-license delivery.'},
 {'component':'sqlite-vec0.1.9','material':'Existing sources/sqlite-vec-0.1.9-LICENSE-MIT.txt1068B SHA6ce72bbe12d975bd5286e5ab0a064c069693300c47bccbc57bec18485f1621ea; sources/sqlite-native-source-review.json identifies Apache10931B SHAa38070a94d4afd9cd710e3ce67bd1de78097cfe1784c1f0109ac95d3c196bfdc (body not retained).','closure':'MIT body identification needs no new read. Apache body was only hashed; do not claim retained delivery, license election or native source correspondence.'}],
 'necessary_new_read_or_evidence_if_closing_remaining_gaps':[
 'For exact new candidate image, bounded declared textual LICENSE/NOTICE selection and project-license text readback for base/LFX/sqlite-vec; a missing dist specimen is not license permission. No native binary reads are proposed.',
 'If Apache notice path is used or both upstream texts are delivered, retrieve exact-v0.1.9 LICENSE-APACHE body from https://raw.githubusercontent.com/asg017/sqlite-vec/v0.1.9/LICENSE-APACHE and check existing recorded hash; license-path choice remains explicit, not inferred here.',
 'Use exact selected wheel/sdist textual metadata and source build/provenance records to establish SQLite/native source/version/options correspondence; no native inspection or full source archive was performed by this review.',
 'Whole-backend redistribution still needs complete notices/corresponding-source and LGPL Psycopg/libpq/system obligations, frontend embedded dependencies and default/API vendor/FIPS separate review. No legal signoff or deployment acceptance inferred.'],
 'new_license_network_requests':0,'new_native_binary_reads':0,'modified_license_or_docs':False}
d['category_counts_qualification']='133 source/advisory pairs equal133 provider IDs in this bounded input. These categories are nonoverlapping tracker display groups, not CVSS severity or exploitable-CVE counts. The unlisted gnutls entry remains unknown even though description is disputed.'
raw=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode();assert len(raw)<=100*1024
path.write_bytes(raw)
print(json.dumps({'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'source_files':len(list(path.parent.iterdir())),'source_bytes':sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())}))
