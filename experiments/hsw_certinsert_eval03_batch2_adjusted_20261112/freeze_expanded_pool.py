from common_adjusted import *
import copy

def main():
 d=O/'data_expanded';d.mkdir(exist_ok=False);pub=copy.deepcopy(read(O/'data/PUBLIC_OUTPUTS.json'));rows=read(O/'T5_insertion/INSERT_T5_all_RESULT.json')['rows']
 for r in rows:
  if r['status']!='PREDICTED_TARGET_REACHED':continue
  root=O/'T5_insertion';tp=root/'outputs'/(r['id']+'.txt');rp=root/'records'/(r['id']+'.json');pub[r['method']].append(dict(id=r['id'],source_id=r['source_id'],dataset='T5',text_path=str(tp),text_sha256=sha(tp),record_path=str(rp),record_sha256=sha(rp)))
 obs={}
 for method,items in pub.items():
  items.sort(key=lambda x:rank('observe|'+method,x['source_id']));assert len({x['source_id'] for x in items})==len(items)
  obs[method]={str(n):dict(status='AVAILABLE' if len(items)>=n else 'NOT_AVAILABLE',available=len(items),ids=[x['id'] for x in items[:n]] if len(items)>=n else []) for n in [10,50,200]}
 put(d/'PUBLIC_OUTPUTS.json',pub);put(d/'OBSERVATIONS.json',obs);put(E/'EXPANDED_POOL_FREEZE.json',dict(public_sha256=sha(d/'PUBLIC_OUTPUTS.json'),observations_sha256=sha(d/'OBSERVATIONS.json'),counts={m:len(v) for m,v in pub.items()},protocol_sha256=sha(E/'EXPANDED_ATTACK_PHASE.md')))
if __name__=='__main__':main()
