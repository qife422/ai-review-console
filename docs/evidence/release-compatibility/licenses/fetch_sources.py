import urllib.request,urllib.error,json,hashlib,datetime,pathlib,concurrent.futures
root=pathlib.Path(__file__).resolve().parent
pairs=[('psycopg','3.3.5'),('psycopg','3.3.4'),('psycopg-c','3.3.5'),('psycopg2','2.9.12'),('pillow','13.0.0'),('pillow','12.3.0'),('lxml','6.1.2'),('lxml','6.1.1'),('reportlab','4.5.1'),('certifi','2026.10.23'),('ibm-db','3.2.9'),('zep-python','2.0.0')]
urls=[(f'https://pypi.org/pypi/{n}/{v}/json','pypi') for n,v in pairs]+[(u,'text') for u in [
'https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2.sha256',
'https://ftp.postgresql.org/pub/source/v17.9/postgresql-17.9.tar.bz2.sha256',
'https://github.com/openssl/openssl/releases/download/openssl-3.5.8/openssl-3.5.8.tar.gz.sha256',
'https://github.com/openssl/openssl/releases/download/openssl-3.5.6/openssl-3.5.6.tar.gz.sha256',
'https://www.openssl.org/source/old/1.1.1/openssl-1.1.1k.tar.gz.sha256',
'https://raw.githubusercontent.com/getzep/zep-python/v2.0.0/LICENSE',
'https://raw.githubusercontent.com/getzep/zep-python/v2.0.0/pyproject.toml',
'https://raw.githubusercontent.com/getzep/zep-python/v2.0.2/pyproject.toml',
'https://raw.githubusercontent.com/psycopg/psycopg/3.3.5/tools/build/wheel_linux_before_all.sh',
]]
def fetch(pair):
 url,kind=pair; r={'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AI-Review-Console-release-license-verification'}),timeout=15) as f:b=f.read(180*1024+1)
  if len(b)>180*1024:raise ValueError('per-response limit')
  r|={'state':'retrieved','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
  if kind=='pypi':
   d=json.loads(b);r['package']={k:d['info'].get(k) for k in ['name','version','license','license_expression','requires_dist','project_urls']};r['source_archives']=[{'url':u['url'],'filename':u['filename'],'bytes':u['size'],'sha256':u['digests']['sha256']} for u in d['urls'] if u['packagetype']=='sdist']
  else:r['text']=b.decode()
 except Exception as e:r|={'state':'unavailable','error_type':type(e).__name__,'reason':str(e)}
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch,urls))
size=sum(r.get('bytes',0) for r in rows);assert size<2*1024*1024
p=root/'official-source-access.json';p.write_text(json.dumps({'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'remote_response_bytes':size,'scope':'Source reference archive hashes and exact license candidate data; archives not downloaded and source-to-binary correspondence not verified.','requests':rows},ensure_ascii=False,indent=2)+'\n')
for r in rows:
 if r.get('package'):print(r['package']['name'],r['package']['version'],[(s['filename'],s['sha256']) for s in r['source_archives']])
 else:print(r['state'],r['url'],r.get('text','')[:130])
print('bytes',size)
