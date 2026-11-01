from pathlib import Path
import json,hashlib,datetime
out=Path(__file__).resolve().parent
api=json.loads((out/'baseline-api-license-texts.json').read_text())
lf=json.loads((out/'baseline-langflow-license-texts.json').read_text())
os_resolutions={
 'base-files':'GPL-2.0-or-later for package programs; bundled license texts retain their own terms',
 'debian-archive-keyring':'Keys not copyrighted; Debian support files GPL-2.0-or-later',
 'gcc-12-base':'GCC GPL-3.0-or-later; file-specific exceptions and additional terms in copyright',
 'libgcc-s1':'GPL-3.0-or-later WITH GCC-exception-3.1 for libgcc runtime; retain full multi-file copyright',
 'libstdc++6':'GPL-3.0-or-later WITH GCC-exception-3.1 for libstdc++ runtime; retain full multi-file copyright',
 'libc-bin':'glibc utilities GPL-2.0-or-later; other bundled files retain listed terms',
 'libc6':'glibc library predominantly LGPL-2.1-or-later; per-file additional notices retained',
 'libcrypt1':'Overall LGPL-2.1-or-later plus per-file BSD/public-domain etc.',
 'libgcrypt20':'Library LGPL-2.1-or-later; manual/tools GPL-2.0-or-later; extra contribution notices',
 'libgssapi-krb5-2':'MIT Kerberos BSD-style license and per-file notices; documents CC-BY-SA-3.0',
 'libk5crypto3':'MIT Kerberos BSD-style license and per-file notices; documents CC-BY-SA-3.0',
 'libkrb5-3':'MIT Kerberos BSD-style license and per-file notices; documents CC-BY-SA-3.0',
 'libkrb5support0':'MIT Kerberos BSD-style license and per-file notices; documents CC-BY-SA-3.0',
 'libselinux1':'libselinux public domain; other utilities/contributions GPL-2.0/LGPL-2.1-or-later per copyright',
 'libsemanage-common':'LGPL-2.1-or-later, as stated in full copyright prose',
 'libsemanage2':'LGPL-2.1-or-later, as stated in full copyright prose',
 'libtasn1-6':'Library LGPL-2.1-or-later; build/tests/tools GPL-3.0-or-later',
}
lf_resolutions={'google-crc32c':'Apache-2.0','llm-sandbox':'MIT','lfx':'MIT (same-version Langflow monorepo root LICENSE, wheel omits text)','peewee':'MIT','smolagents':'Apache-2.0','langchain-mongodb':'MIT','agent-lifecycle-toolkit':'Apache-2.0 notice references canonical full text','uncurl':'Apache-2.0','twelvelabs':'Apache-2.0','zep-python':None}
rows=[]
for p in api['os_unknown_copyrights']:
 rows.append({'image':'api-baseline','package':p['name'],'state':'copyright_text_identified','resolution':os_resolutions[p['name']],'evidence':{'path':p['path'],'sha256':p['sha256'],'bytes':p['bytes']},'limit':'This is manual identification of complete prose/multi-file notices; not a single SPDX expression or complete binary-source distribution signoff.'})
for n,l in lf_resolutions.items():
 p=next(x for x in lf['packages'] if x['name']==n)
 rows.append({'image':'langflow-baseline','package':n,'version':p['version'],'state':'license_identified' if l else 'unresolved_exact_release_license','resolution':l,'evidence':[{'path':f['path'],'sha256':f['sha256'],'bytes':f['bytes']} for f in p['license_files']],'source': 'v1.11.6/src/lfx version and monorepo root LICENSE' if n=='lfx' else ('installed package license file' if l else 'Exact PyPI metadata/wheel, PyPI sdist and official v2.0.2 tag lack license; old oss branch license not inherited')})
report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Exact baseline image license metadata triage, applicable notices and remaining distribution work; not independent legal approval','baseline_images':{'api':'sha256:f0cf8dc583f3e7523675748fd1841dd708655ed3783f022fafb9955815a4c95a','langflow':'sha256:ff0f5cc380743034c05b4bfcf587be0e714da1610799f0c7c41d45902a5267c4','web':'sha256:827925e33497504894c22220231543a2eef36c4a7e5581d86349797d63220124'},'unknown_metadata_triage':rows,'summary':{'prior_api_unknown':17,'api_copyright_texts_identified':17,'prior_langflow_unknown':10,'langflow_license_identified':9,'langflow_exact_release_unresolved':['zep-python==2.0.2']},'special_cases':{'psycopg':'LGPL-3.0-only, no removal or relicensing; upstream license and exact-version source location identified; API binary extension includes 16 native shared libraries requiring their own notices/source handling before binary image redistribution','grandalf':'Exact 0.8 package LICENSE offers GPL-2.0 OR EPL-1.0. It is not GPL-only. Distribution requires selecting and meeting one permitted route.','frozendict':'LGPL v3 confirmed in package license text','crc32c':'LGPL-2.1-or-later plus BSD notices from google-crc32c and slice-by-8','psycopg2-binary':'LGPL v3-or-later with package-specific OpenSSL linking exception; preserve exact license, bundled native dependencies have their own terms','certifi':'MPL-2.0 with CA bundle source notice, file-level source obligations on redistribution; not identified by GPL-only text heuristic','fonts':'Noto OFL1.1 exact hash/notice preserved; IBM Plex OFL1.1 must accompany web fonts'},'binary_distribution_not_closed':['zep-python2.0.2 exact release permission','Exact native bundled-library notices and corresponding source delivery/access for redistributed image binaries','Final upgraded image versions/notices readback pending root build'],'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir()) if p.is_file() and p.name not in ['license-review.json','summarize_licenses.py']]}
(out/'license-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(report['summary'])
