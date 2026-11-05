import urllib.request,lzma,hashlib,datetime,json,re
from pathlib import Path
base='https://deb.debian.org/debian-security/dists/bookworm-security/'
records=[];selected=[]
for relative in ['InRelease','main/binary-amd64/Packages.xz']:
 with urllib.request.urlopen(base+relative,timeout=40) as r:raw=r.read(4*1024*1024+1);final=r.url
 assert len(raw)<=4*1024*1024
 rec={'url':base+relative,'final_url':final,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 if relative=='InRelease':
  text=raw.decode();rec['selected_fields']={k:re.search('^'+k+': (.*)$',text,re.M).group(1) for k in ['Origin','Label','Suite','Codename','Date','Valid-Until'] if re.search('^'+k+': (.*)$',text,re.M)}
  rows=[l.strip() for l in text.split('SHA256:\n',1)[1].split('SHA512:',1)[0].splitlines() if l.strip().endswith('main/binary-amd64/Packages.xz')];rec['sha256_index_row']=rows
  expected=rows[0].split()[0] if rows else None
 else:
  rec['matches_inrelease_sha256']=hashlib.sha256(raw).hexdigest()==expected
  dec=lzma.LZMADecompressor();body=dec.decompress(raw,max_length=16*1024*1024+1);assert len(body)<=16*1024*1024 and dec.eof
  rec['decompressed_bytes']=len(body);rec['decompressed_sha256']=hashlib.sha256(body).hexdigest()
  for para in body.decode().split('\n\n'):
   fields={line.split(': ',1)[0]:line.split(': ',1)[1] for line in para.splitlines() if ': ' in line and not line.startswith(' ')}
   if fields.get('Package') in ('apt','libapt-pkg6.0'):
    selected.append({k:fields[k] for k in ['Package','Version','Architecture','Source','Depends','Filename','Size','SHA256'] if k in fields})
 records.append(rec)
d={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Official Debian HTTPS InRelease and AMD64 Packages.xz read only in memory <=4MiB compressed/16MiB expanded; hashes and selected apt/libapt-pkg6.0 paragraphs only retained. Compressed index digest compared with InRelease SHA256 row; OpenPGP signature not verified by this script. No package binaries fetched, apt resolver or installation executed.','records':records,'selected_binary_packages':selected,'exact_apt_2_6_2_listed':any(p['Package']=='apt' and p['Version']=='2.6.2' for p in selected),'exact_libapt_2_6_2_listed':any(p['Package']=='libapt-pkg6.0' and p['Version']=='2.6.2' for p in selected),'qualification':'Official index availability supports a candidate-only same-suite update. Dependencies/repository configuration/installability remain for CI apt resolver and actual image verification; index listing is not actual successful install.'}
p=Path('/private/tmp/arc-langflow-transition.l7tcavqh/sources/debian-apt-availability.json');out=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode();assert len(out)<16*1024
with p.open('xb') as f:f.write(out)
print(out.decode())
