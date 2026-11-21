"""Bounded acquisition from the authors' paper-cited public CC-BY4 archive."""
from pathlib import Path
import json,urllib.request,hashlib,zipfile,shutil,time
P=Path(__file__).parent;ROOT=P.parents[1];CACHE=ROOT/'.cache/oulad-author-v1';CACHE.mkdir(parents=True,exist_ok=True)
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')
if (P/'acquisition.json').exists():raise RuntimeError('do not overwrite')
url='https://api.figshare.com/v2/articles/5081998';meta=json.load(urllib.request.urlopen(url,timeout=40));save('author_metadata.json',meta)
f=meta['files'][0];assert meta['doi']=='10.6084/m9.figshare.5081998.v1' and meta['license']['name']=='CC BY 4.0';assert f['size']==46750706 and f['size']<64*1024**2
save('acquisition_protocol.json',{'status':'FROZEN_BOUNDED_PUBLIC_DATA_ACQUISITION','metadata':url,'source_doi':meta['doi'],'license':meta['license'],'file':f,'maximum_network_bytes':64*1024**2,'maximum_uncompressed_bytes':1024**3,'disk_free_before':shutil.disk_usage(ROOT).free,'purpose':'OULAD small development evaluation only; no models, paid API, reidentification or raw-student publication','references':['https://doi.org/10.1038/sdata.2017.171','https://research.stem.open.ac.uk/ouanalyse/dataset/'],'source_scope':'authors exact version1 paper-cited dataset, not a third-party repackaging'})
dest=CACHE/f['name'];downloaded=0;start=time.perf_counter()
if not dest.exists():
 temp=CACHE/'anonymisedData.partial'
 if temp.exists():raise RuntimeError('partial download exists; inspect rather than overwrite')
 with urllib.request.urlopen(f['download_url'],timeout=45) as response,temp.open('xb') as out:
  declared=response.headers.get('Content-Length');assert declared is None or int(declared)<=64*1024**2
  while True:
   block=response.read(1024**2)
   if not block:break
   downloaded+=len(block)
   if downloaded>64*1024**2:raise RuntimeError('bounded transfer exceeded')
   out.write(block)
 assert downloaded==f['size'];temp.rename(dest)
blob=dest.read_bytes();assert len(blob)==f['size'] and hashlib.md5(blob).hexdigest()==f['computed_md5']
with zipfile.ZipFile(dest) as z:
 entries=[{'name':x.filename,'bytes':x.file_size,'compressed':x.compress_size,'CRC':x.CRC} for x in z.infolist()];assert sum(x['bytes'] for x in entries)<1024**3
 # Only small relational tables are extracted; studentVle remains compressed and streamed.
 for entry in z.infolist():
  name=Path(entry.filename).name
  if name in ['assessments.csv','courses.csv','studentAssessment.csv','studentInfo.csv','studentRegistration.csv','vle.csv']:
   assert entry.file_size<32*1024**2;target=CACHE/name
   if not target.exists():
    with target.open('xb') as out:out.write(z.read(entry))
save('acquisition.json',{'status':'AVAILABLE_VERIFIED','archive_sha256':hashlib.sha256(blob).hexdigest(),'archive_md5':hashlib.md5(blob).hexdigest(),'author_md5':f['computed_md5'],'network_bytes_this_run':downloaded,'elapsed_seconds':time.perf_counter()-start,'archive_bytes':len(blob),'entries':entries,'raw_location_LOCAL':str(CACHE),'raw_data_sync':False})
print(json.dumps({'status':'AVAILABLE_VERIFIED','network_bytes':downloaded,'entries':entries},indent=2))
