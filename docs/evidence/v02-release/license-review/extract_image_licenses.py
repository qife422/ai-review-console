import importlib.metadata as m, pathlib, json, hashlib, sys, re
image=sys.argv[1]
unknown_api=['base-files','debian-archive-keyring','gcc-12-base','libc-bin','libc6','libcrypt1','libgcc-s1','libgcrypt20','libgssapi-krb5-2','libk5crypto3','libkrb5-3','libkrb5support0','libselinux1','libsemanage-common','libsemanage2','libstdc++6','libtasn1-6']
names={'api':['psycopg','psycopg-binary','certifi','lxml','pillow'], 'langflow':['google-crc32c','llm-sandbox','lfx','peewee','smolagents','langchain-mongodb','agent-lifecycle-toolkit','uncurl','twelvelabs','zep-python','frozendict','grandalf','crc32c','psycopg','psycopg2-binary','langflow']}[image]
normalize=lambda s:re.sub('[-_.]+','-',s).lower()
rows=[]; seen=set(); byte_count=0
for d in m.distributions():
 n=d.metadata.get('Name','')
 if normalize(n) not in names or (normalize(n),d.version) in seen:continue
 seen.add((normalize(n),d.version)); files=[]
 for f in d.files or []:
  p=d.locate_file(f); s=str(f)
  if any(t in p.name.lower() for t in ['license','copying','notice','copyright','authors']) and p.is_file():
   data=p.read_bytes()
   if len(data)>150000 or len(files)>60:continue
   byte_count+=len(data)
   if byte_count>6*1024*1024:raise RuntimeError('License text cap')
   files.append({'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'text':data.decode(errors='replace')})
 bundled=[]
 for f in d.files or []:
  if '.libs/' in str(f) and (str(f).endswith('.so') or '.so.' in str(f)):
   p=d.locate_file(f)
   bundled.append({'path':str(p),'bytes':p.stat().st_size})
 rows.append({'name':n,'version':d.version,'license_expression':d.metadata.get('License-Expression'),'license_metadata':d.metadata.get('License'),'classifiers':d.metadata.get_all('Classifier') or [],'project_urls':d.metadata.get_all('Project-URL') or [],'license_files':files,'bundled_libraries':bundled})
os_files=[]
if image=='api':
 for n in unknown_api:
  p=pathlib.Path('/usr/share/doc')/n/'copyright'
  data=p.read_bytes() if p.is_file() else b''
  os_files.append({'name':n,'path':str(p),'exists':p.exists(),'is_symlink':p.is_symlink(),'resolved':str(p.resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'text':data.decode(errors='replace')})
print(json.dumps({'image_alias':image,'packages':rows,'os_unknown_copyrights':os_files},ensure_ascii=False))
