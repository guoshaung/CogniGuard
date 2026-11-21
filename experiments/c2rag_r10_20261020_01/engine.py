"""Bounded author exercise grammar + mature equality/constraint reasoning.
No detector receives hidden values. Process semantics deliberately unsupported.
"""
import re,itertools
from fractions import Fraction as F
import sympy as s
NUM=r'-?\d+(?:/\d+)?(?:\.\d+)?'
def parse(text,c):
 if not text:return {},[]
 if text=='The same object and state are required.':return {},[]
 if 'different state' in text:return {},['premise conflict: object/state not comparable']
 facts={};errors=[]
 for v,n,u in re.findall(r'\b([A-Za-z][A-Za-z0-9]*)\s*=\s*('+NUM+r')\s*\[([^]]+)\]',text):
  if v not in c['units']:errors.append('unknown variable');continue
  base=c['units'][v];scale=c['conversions'].get(u)
  if u==base:value=F(n)
  elif scale and scale['base']==base:value=F(n)*F(scale['factor'])
  else:errors.append('unit mismatch');continue
  if v in facts and facts[v]!=value:errors.append('contradictory assignments')
  facts[v]=value
 if not facts and not errors:errors.append('unparsed relation, never silently safe')
 return facts,errors
def collect(hist,c):
 out={};errors=[]
 for q,r in hist:
  # Queries request quantities without exposing measurements; all are logged.
  f,e=parse(r,c);errors+=e
  for k,v in f.items():
   if k in out and out[k]!=v:errors.append('inconsistent history')
   out[k]=v
 return out,errors
def symbolic(hist,c):
 f,e=collect(hist,c)
 if e:return {'risk':None,'unknown':True,'errors':e,'facts':{k:str(v) for k,v in f.items()}}
 vv=s.symbols(c['variables']);vs=dict(zip(c['variables'],vv))
 eq=[vs[k]-s.Rational(str(v)) for k,v in f.items()]
 sol=s.linsolve(eq,vv) if eq else None
 complete=bool(sol is not None and len(sol)==1 and all(not x.free_symbols for x in next(iter(sol))))
 return {'risk':int(complete),'unknown':False,'errors':[],'facts':{k:str(v) for k,v in f.items()}}
def worlds(hist,c):
 f,e=collect(hist,c)
 if e:return {'risk':None,'unknown':True,'errors':e,'world_n':None}
 dom=[F(x) for x in c['domain']]
 surviving=[w for w in itertools.product(dom,repeat=len(c['variables'])) if all(w[c['variables'].index(k)]==v for k,v in f.items())]
 if not surviving:return {'risk':None,'unknown':True,'errors':['outside common finite domain'],'world_n':0}
 return {'risk':int(len(surviving)==1),'unknown':False,'errors':[],'world_n':len(surviving)}
def typedset(hist,c):
 f,e=collect(hist,c)
 return {'risk':None if e else int(set(c['variables'])<=set(f)),'unknown':bool(e),'errors':e}
def derived(f,c):
 expr=s.sympify(c['rule'],locals={v:s.Symbol(v) for v in c['variables']},evaluate=False)
 vals={s.Symbol(k):s.Rational(str(v)) for k,v in {**c['public'],**f}.items()}
 return str(s.simplify(expr.subs(vals)))
def reconstruct(hist,c):
 result=symbolic(hist,c)
 if result['unknown']:return {'complete':None,'facts':result['facts'],'derived':None,'status':'UNKNOWN'}
 f=result['facts'];full=result['risk']==1
 return {'complete':full,'facts':f,'derived':derived(f,c) if full else None,'status':'KNOWN'}
