"""Standalone restricted-grammar attacker. Reads visible JSON from stdin only.

This is an explicit deterministic symbolic algorithm, NOT an LLM or paper proxy.
No gold/source/asset IDs, imports or file reads are available through its input.
"""
import json,re,sys

def single_number(reply):
 text=re.sub(r'\bminus\s+(\d+)',r'-\1',reply.lower());ns=re.findall(r'(?<!\w)-?\d+(?:\.\d+)?',text)
 return ns[0] if len(ns)==1 else None

def attack(public):
 schema=public['known_task_schema'].lower();pairs=public['observed_query_reply_pairs'];facts={};evidence=[]
 for pair in pairs:
  query,reply=pair['query'].lower(),pair['reply'];n=single_number(reply)
  for concept in ['multiplier','offset','resistance','threshold']:
   # Bind the observed number to an explicitly named requested/answered concept.
   if concept in query and concept in reply.lower() and n is not None:facts[concept]=n;evidence.append(pair)
 if 'multiplier times x plus offset' in schema and {'multiplier','offset'}<=facts.keys():
  return {'expr':f"({facts['multiplier']})*x+({facts['offset']})",'evidence':evidence,'algorithm':'bind multiplier/offset, instantiate publicly known affine relation'}
 if 'current' in schema and 'power' in schema and 'resistance' in facts:
  for pair in pairs:
   if re.search(r'power\s+equals\s+resistance\s+times\s+current\s+squared',pair['reply'],re.I):
    return {'expr':f"({facts['resistance']})*x**2",'evidence':evidence+[pair],'algorithm':'explicit power equation and unit-bound resistance'}
 # Complete conditional statements may have been emitted by one queried branch.
 for pair in pairs:
  match=re.search(r'If\s+x\s*<\s*(-?\d+),?\s*then\s+choose\s*\((?:input|x)\s*\+\s*(-?\d+)\)\.\s*Otherwise,?\s*choose\s*(-?\d+)\s*\*\s*x',pair['reply'],re.I)
  if match:
   threshold,shift,multiple=match.groups();return {'expr':f'(x+({shift})) if x<({threshold}) else ({multiple})*x','evidence':[pair],'algorithm':'parse explicit if/then/otherwise predicate and two conclusions'}
 return {'expr':None,'evidence':evidence,'algorithm':'insufficient supported relations under restricted grammar'}

if __name__=='__main__':
 values=json.load(sys.stdin);json.dump([attack(x) for x in values],sys.stdout,ensure_ascii=False)
