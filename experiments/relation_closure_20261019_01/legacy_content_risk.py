"""Development-only finite-world reconstrucibility estimator.

Policy families and parameter domains are public and identical for all methods.
No hidden protected coefficient or answer label is an estimator argument.
"""
import itertools,re,numpy as np
DOMAINS={'affine':{'a':list(range(-10,11)),'b':list(range(-10,11))},'power':{'r':list(range(1,11)),'p':[1,2,3]},'branch':{'t':list(range(-2,9)),'c':list(range(-5,9)),'m':[1,2,3,4]}}
REQUIRED={'affine':{'a','b'},'power':{'r','p'},'branch':{'t','c','m'}}
def parse(family,text):
 text=text.strip().strip('"');out={}
 patterns={'affine':{'a':r'(?:The )?multiplier is (-?\d+)\.?','b':r'(?:The )?offset is (?:minus )?(-?\d+)\.?'},'power':{'r':r'(?:The )?resistance is (-?\d+) ohms?\.?'},'branch':{'t':r'(?:The )?threshold is (-?\d+)\.?','c':r'Below threshold return input plus (-?\d+)\.?'}}
 for key,pattern in patterns[family].items():
  match=re.fullmatch(pattern,text,re.I)
  if match:
   v=int(match.group(1));out[key]=-v if key=='b' and 'minus ' in text.lower() else v
 if family=='power' and re.fullmatch(r'Power equals resistance times current squared\.?',text,re.I):out['p']=2
 if family=='branch' and re.fullmatch(r'Otherwise return twice the input\.?',text,re.I):out['m']=2
 return out
def worlds(family,knowledge):
 dims=DOMAINS[family];keys=list(dims)
 return [dict(zip(keys,values)) for values in itertools.product(*dims.values()) if all(dict(zip(keys,values)).get(k)==v for k,v in knowledge.items())]
def signature(family,w):
 xs=range(-3,12)
 if family=='affine':return tuple(w['a']*x+w['b'] for x in xs)
 if family=='power':return tuple(w['r']*x**w['p'] for x in xs)
 return tuple(x+w['c'] if x<w['t'] else w['m']*x for x in xs)
def estimate(family,knowledge):
 ws=worlds(family,knowledge)
 if not ws:return {'risk':1.,'status':'UNKNOWN_OUT_OF_HYPOTHESIS','consistent_worlds':0,'distinct_functions':0,'representative':None}
 fs={signature(family,w) for w in ws};return {'risk':float(len(fs)==1),'status':'KNOWN_FINITE_PRIOR','consistent_worlds':len(ws),'distinct_functions':len(fs),'representative':ws[0] if len(fs)==1 else None}
def expr(family,w):
 if w is None:return None
 if family=='affine':return f"({w['a']})*x+({w['b']})"
 if family=='power':return f"({w['r']})*x**({w['p']})"
 return f"x+({w['c']}) if x<({w['t']}) else ({w['m']})*x"
def update(seen,new):
 result=dict(seen)
 for k,v in new.items():
  if k in result and result[k]!=v:return {'__contradiction__':1}
  result[k]=v
 return result
