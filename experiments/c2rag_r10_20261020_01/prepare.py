"""R10 source capture and author contracts. No method results are read here."""
from pathlib import Path
import json,hashlib,re,html,urllib.request,concurrent.futures,sys,datetime,shutil
sys.stdout.reconfigure(encoding='utf8')
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def dump(n,x):
 p=P/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(i,cat,book,page,family,phrase,rule,values,units,public=None):
 return dict(id=i,category=cat,book=book,page=page,family=family,source_phrase=phrase,rule=rule,
             values=values,units=units,public=public or {},supported=cat!='process',
             previously_r9_asset=False,annotation='single AI author development annotation; EXPLORATORY',
             problem_origin='author-created numerical exercise grounded in source law; NOT source worked-example numbers',
             target='complete bound instance: both private input quantities with units/premise AND derived conclusion',
             policy='simulated application authorization, not an actual restriction on public textbook use')
A=[]
def add(*args,**kw):A.append(asset(*args,**kw))
B='college-physics-2e'
add('kinetic','formula',B,'7-2-kinetic-energy-and-the-work-energy-theorem','mechanics-energy','kinetic energy','m*v**2/2',{'m':'6','v':'4'},{'m':'kg','v':'m/s'})
add('gravity','formula',B,'7-3-gravitational-potential-energy','mechanics-potential','gravitational potential energy','m*g*h',{'m':'3','h':'5'},{'m':'kg','h':'m'},{'g':'49/5'})
add('momentum','formula',B,'8-1-linear-momentum-and-force','mechanics-momentum','momentum','m*v',{'m':'7','v':'3'},{'m':'kg','v':'m/s'})
add('hooke','formula',B,'16-1-hookes-law-stress-and-strain-revisited','elasticity','spring constant','k*x',{'k':'80','x':'1/4'},{'k':'N/m','x':'m'})
add('wave','formula',B,'16-9-waves','waves','wavelength','f*l',{'f':'12','l':'3/2'},{'f':'Hz','l':'m'})
add('capacitor','formula',B,'19-5-capacitors-and-dielectrics','electrostatics','capacitance','C*V',{'C':'1/1000','V':'9'},{'C':'F','V':'V'})
add('density','units',B,'11-2-density','fluids-density','density','m/V',{'m':'5','V':'1/500'},{'m':'kg','V':'m3'})
add('molarity','units','chemistry-2e','3-3-molarity','solution-concentration','molarity','n/V',{'n':'3/10','V':'3/2'},{'n':'mol','V':'L'})
add('ideal-gas','units',B,'13-3-the-ideal-gas-law','gas-equation','ideal gas law','n*R*T/V',{'n':'2','V':'1/20'},{'n':'mol','V':'m3'},{'R':'8314/1000','T':'300'})
add('heat','units',B,'14-2-temperature-change-and-heat-capacity','calorimetry','specific heat','m*c*dT',{'m':'2','dT':'15'},{'m':'kg','dT':'K'},{'c':'4200'})
add('pressure','units',B,'11-3-pressure','fluids-pressure','pressure','F/A',{'F':'120','A':'3/10'},{'F':'N','A':'m2'})
add('electric-power','units',B,'20-4-electric-power-and-energy','electric-power','electric power','V*I',{'V':'12','I':'5/2'},{'V':'V','I':'A'})
C='college-algebra-2e'
add('discriminant','condition',C,'2-5-quadratic-equations','quadratic-roots','discriminant','b**2-4*c>0',{'b':'5','c':'4'},{'b':'1','c':'1'})
add('log-domain','condition',C,'6-3-logarithmic-functions','logarithmic-domain','domain','x-h>0',{'x':'7','h':'3'},{'x':'1','h':'1'})
add('root-domain','condition',C,'3-2-domain-and-range','radical-domain','square root','r-x**2>=0',{'r':'25','x':'3'},{'r':'1','x':'1'})
add('triangle','condition','prealgebra-2e','9-5-solve-geometry-applications-triangles-and-the-pythagorean-theorem','triangle-feasibility','triangle','a+b>c',{'a':'4','b':'5'},{'a':'m','b':'m'},{'c':'7'})
add('geometric-series','condition',C,'9-3-geometric-sequences','geometric-convergence','geometric series','abs(u/v)<1',{'u':'2','v':'5'},{'u':'1','v':'1'})
add('internal-reflection','condition',B,'25-4-total-internal-reflection','optics-critical-angle','critical angle','theta>critical',{'theta':'60','critical':'42'},{'theta':'degree','critical':'degree'})
D='biology-2e'
for args in [
 ('enzyme-process','6-5-enzymes','enzyme-catalysis','activation energy'),
 ('respiration-process','7-2-glycolysis','glycolysis','pyruvate'),
 ('photosynthesis-process','8-2-the-light-dependent-reactions-of-photosynthesis','photosynthetic-electron-transfer','electron'),
 ('neuron-process','35-2-how-neurons-communicate','neural-transmission','action potential'),
 ('kidney-process','41-2-the-kidneys-and-osmoregulatory-organs','renal-osmoregulation','filtration'),
 ('feedback-process','33-3-homeostasis','homeostatic-feedback','negative feedback')]:
 i,page,family,phrase=args
 add(i,'process',D,page,family,phrase,None,{},{});A[-1]['problem_origin']='original source process paragraph; no invented causal ground truth';A[-1]['target']='complete scoped process explanation; UNSUPPORTED without a validated causal/temporal contract'

def capture(job):
 key,url=job
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 educational research audit'})
  with urllib.request.urlopen(req,timeout=45) as r:b=r.read();status=r.status;final=r.url
  t=b.decode('utf8');paras=[]
  for m in re.finditer(r'<p\b[^>]*>.*?</p>',t,re.S):
   raw=m.group();loc=re.search(r'id="([^"]+)"',raw)
   raw=re.sub(r'<annotation-xml\b.*?</annotation-xml>','',raw,flags=re.S)
   txt=' '.join(html.unescape(re.sub('<[^>]+>','',raw)).split())
   if txt:paras.append({'id':loc.group(1) if loc else None,'text':txt})
  (P/'local_sources'/f'{key}.html').write_bytes(b)
  return key,dict(url=url,final_url=final,status=status,sha256=sha(b),bytes=len(b),paragraphs=paras,
                  license_links=sorted(set(re.findall(r'https?://creativecommons.org/licenses/[^"<>\s]+',t))))
 except Exception as e:return key,dict(url=url,status='CAPTURE_FAILED',error=str(e))

def main():
 assert not (P/'assets.json').exists(),'no replacing frozen candidate assets'
 (P/'local_sources').mkdir(exist_ok=True)
 jobs={a['book']+'/'+a['page']:'https://openstax.org/books/'+a['book']+'/pages/'+a['page'] for a in A}
 jobs.update({b+'/license':'https://openstax.org/books/'+b+'/pages/preface' for b in sorted({a['book'] for a in A})})
 # Stable keys stored without slash, exact URLs remain in capture registry.
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  captures=dict(pool.map(capture,[(k.replace('/','__'),u) for k,u in jobs.items()]))
 dump('source_capture_private.json',captures)
 for a in A:
  rec=captures[a['book']+'__'+a['page']];lic=captures[a['book']+'__license']
  hits=[p for p in rec.get('paragraphs',[]) if a['source_phrase'].lower() in p['text'].lower()]
  a['url']=rec['url'];a['source_hash']=rec.get('sha256');a['source_locator']=hits[0]['id'] if hits else None
  a['source_excerpt']=hits[0]['text'] if hits else None
  a['license_links']=lic.get('license_links',[])
  a['source_verified']=bool(hits and a['license_links'])
  a['eligible']=a['supported'] and a['source_verified']
  a['group_document']=a['book'];a['group_source_section']=a['page']
  if a['id']=='electric-power':a['seen_source_r9']=True
  else:a['seen_source_r9']=False
  if a['id']=='internal-reflection':a['premise']='light travels from optically denser to optically rarer medium; critical angle given'
  elif a['id']=='triangle':a['premise']='positive lengths; c is the longest side'
  elif a['id']=='discriminant':a['premise']='real quadratic with leading coefficient 1; conclusion is two distinct real roots'
  elif a['id']=='geometric-series':a['premise']='infinite geometric series with ratio u/v; v nonzero'
  else:a['premise']='same named object/state; textbook model assumptions hold; variables are positive where denominators require'
 dump('assets.json',A)
 dump('source_registry.json',{k:{kk:vv for kk,vv in v.items() if kk!='paragraphs'} for k,v in captures.items()})
 audit={}
 base=ROOT/'.tmp/c2rag-review-sync-20261019'
 for rel in ['CG/reviews/2026-10-19-c2rag-algorithm-review-01/report.md','CG/experiments/2026-10-19-c2rag-relation-closure-01/c2rag_relation_closure_results.md','CG/experiments/2026-10-19-c2rag-r9-real-text-01/c2rag_r9_real_text_report.md']:
  b=(base/rel).read_bytes();audit[rel]={'sha256':sha(b),'bytes':len(b),'read':True}
 dump('prior_evidence_audit.json',audit)
 print(json.dumps([{'id':a['id'],'source_verified':a['source_verified'],'supported':a['supported'],'excerpt':(a['source_excerpt'] or '')[:140]} for a in A],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
