import json,hashlib,urllib.request,concurrent.futures,collections,datetime
from pathlib import Path
from html.parser import HTMLParser
root=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
scan=root/'docs/evidence/langflow-candidate/ci/candidate/final/metadata/scan/summary.json'
findings=json.loads(scan.read_text())['images']['langflow']['findings']
groups={}
for x in findings:
 name=x['query']['package']['name'];g=groups.setdefault(name,{'installed_source_versions':set(),'binaries':set(),'ids':set()})
 g['installed_source_versions'].add(x['query']['version']);g['binaries'].add(x['package']);g['ids'].update(i.removeprefix('DEBIAN-') for i in x['vulnerability_ids'])
class Tables(HTMLParser):
 def __init__(self): super().__init__();self.section='';self.rows=[];self.heading=False;self.cell=False;self.text='';self.row=[];self.h=''
 def handle_starttag(self,t,a):
  if t=='h2':self.heading=True;self.h=''
  if t=='tr':self.row=[]
  if t in ('td','th'):self.cell=True;self.text=''
 def handle_data(self,d):
  if self.heading:self.h+=d
  if self.cell:self.text+=d
 def handle_endtag(self,t):
  if t=='h2':self.heading=False;self.section=self.h
  if t in ('td','th'):self.cell=False;self.row.append(' '.join(self.text.split()))
  if t=='tr':self.rows.append((self.section,self.row))
def fetch(name):
 url='https://security-tracker.debian.org/tracker/source-package/'+name
 with urllib.request.urlopen(url,timeout=45) as r:
  raw=r.read(1024*1024+1); final=r.url
 if len(raw)>1024*1024:raise RuntimeError('source page too large')
 p=Tables();p.feed(raw.decode());g=groups[name];versions={};records={};header=[]
 for section,row in p.rows:
  if not row:continue
  if section=='Available versions' and row[0].startswith('bookworm'):versions[row[0]]=row[1]
  if row[0]=='Bug':header=row
  if row[0] not in g['ids']:continue
  status=row[header.index('bookworm')] if 'bookworm' in header and len(row)==len(header) else 'resolved section; per-release fixed version not read'
  if 'postponed' in status:category='postponed_no_dsa'
  elif 'no DSA' in status:category='no_dsa'
  elif section=='Open unimportant issues':category='unimportant_unfixed'
  elif status=='fixed':category='bookworm_current_fixed_installed_not_retested'
  elif section=='Resolved issues':category='resolved_section_needs_per_release_check'
  else:category='open_or_undetermined'
  records[row[0]]={'id':row[0],'bookworm_status':status,'section':section,'category':category}
 for cve in g['ids']-records.keys():records[cve]={'id':cve,'category':'not_found_on_source_page'}
 return {'source':name,'url':url,'final_url':final,'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'installed_source_versions':sorted(g['installed_source_versions']),'binaries':sorted(g['binaries']),'available_bookworm_versions':versions,'advisories':[records[c] for c in sorted(records)]}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(fetch,sorted(groups)))
counts=collections.Counter(a['category'] for r in results for a in r['advisories'])
result={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Existing candidate OSV Debian findings only; source-package bookworm tracker status; not zero vulnerabilities or exploitability/acceptance','scan_input':str(scan.relative_to(root)),'scan_sha256':hashlib.sha256(scan.read_bytes()).hexdigest(),'method':'Official HTTPS source-package HTML, bounded <=1MiB per response, parsed table headers/rows and matched existing source/CVE pairs; raw response hashes retained, bodies not saved. No native binaries read. Available versions are tracker listings, not a current apt resolver or proof upgrades installed.','source_count':len(results),'binary_count':len(findings),'unique_provider_ids':len({a for f in findings for a in f['vulnerability_ids']}),'source_advisory_pairs':sum(len(r['advisories']) for r in results),'category_counts':dict(counts),'sources':results,'limitations':['No severity inference from no-DSA/postponed/unimportant; these are tracker policy/status, not risk acceptance.','Fixed on bookworm source page does not prove fixed installed version; candidate source version is retained for comparison and upgrades require new CI scan.','The large aggregate JSON was attempted in memory, exceeded the 64MiB bounded read and was not parsed, retained, or used. No complete rawhash is asserted for it.'],'license_material_assessment':{}}
path=Path('/private/tmp/arc-langflow-transition.l7tcavqh/sources/debian-tracker-assessment.json')
raw=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode();assert len(raw)<=100*1024
with path.open('xb') as f:f.write(raw)
print(json.dumps({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'categories':dict(counts),'needs_detail':[(r['source'],a['id']) for r in results for a in r['advisories'] if a['category'] in ('resolved_section_needs_per_release_check','not_found_on_source_page')]}))
