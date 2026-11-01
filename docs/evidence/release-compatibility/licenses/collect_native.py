import importlib.metadata as m,hashlib,json,pathlib,re,sys,ctypes
limit=int(sys.argv[1]); remaining=limit; rows=[]; seen=set(); packages={}
selected={'psycopg-binary','psycopg2-binary','pillow','lxml'}
for d in m.distributions():
 name=re.sub('[-_.]+','-',d.metadata.get('Name','')).lower()
 if name not in selected or name in packages:continue
 packages[name]=d.version; root=pathlib.Path(d.locate_file('')).resolve()
 for f in d.files or []:
  p=pathlib.Path(d.locate_file(f)); resolved=p.resolve()
  if '.so' not in p.name or str(resolved) in seen:continue
  seen.add(str(resolved)); row={'package':name,'package_version':d.version,'path':str(p),'resolved':str(resolved),'sha256':None}
  if not resolved.is_relative_to(root):row['skip']='outside_declared_distribution_root'; rows.append(row); continue
  if len(rows)>=100:row['skip']='file_limit';rows.append(row);continue
  try:size=p.stat().st_size
  except OSError as e:row['skip']=type(e).__name__;rows.append(row);continue
  row['bytes']=size
  if size>remaining:row['skip']='shared_hash_input_limit'; rows.append(row);continue
  h=hashlib.sha256(); actual=0
  with p.open('rb') as stream:
   for b in iter(lambda:stream.read(65536),b''):
    actual+=len(b)
    if actual>remaining:break
    h.update(b)
  if actual>remaining:row['skip']='grew_over_hash_limit';rows.append(row);continue
  remaining-=actual;row['sha256']=h.hexdigest()
  if p.name.startswith(('libcrypto','libssl','libpq')):
   try:
    lib=ctypes.CDLL(str(p))
    if p.name.startswith('libpq'):
     fun=lib.PQlibVersion;fun.restype=ctypes.c_int;row['reported_version']=fun();row['version_method']='PQlibVersion'
    else:
     fun=lib.OpenSSL_version;fun.argtypes=[ctypes.c_int];fun.restype=ctypes.c_char_p;row['reported_version']=fun(0).decode();row['version_method']='OpenSSL_version(0)'
   except Exception as e:row['version_unavailable']=type(e).__name__
  rows.append(row)
features={}
try:
 from PIL import features as pf
 for name in pf.get_supported():
  try:features[name]=pf.version(name)
  except Exception as e:features[name]={'error':type(e).__name__}
except Exception as e:features={'import_error':type(e).__name__}
lxml={}
try:
 from lxml import etree
 for name in ['LXML_VERSION','LIBXML_VERSION','LIBXML_COMPILED_VERSION','LIBXSLT_VERSION','LIBXSLT_COMPILED_VERSION']:lxml[name]=getattr(etree,name,None)
except Exception as e:lxml={'import_error':type(e).__name__}
print(json.dumps({'packages':packages,'native_files':rows,'hash_input_limit':limit,'hashed_bytes':limit-remaining,'remaining_hash_bytes':remaining,'pillow_feature_versions':features,'lxml_versions':lxml,'qualification':'Runtime version strings and file SHA identify bytes; they do not prove corresponding source/build patches or distribution compliance.'}))
