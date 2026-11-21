import engine as e
from truth import execute
from pathlib import Path
import json,gzip,sys,time,hashlib
import numpy as np
P=e.P
def read(path):
    if not path.exists():path=Path(str(path)+'.gz')
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf8') as f:return [json.loads(s) for s in f if s.strip()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(split):
    assert split in ['train','dev','test']
    if split!='dev':
        lock=json.loads((P/'final_freeze.json').read_text(encoding='utf8'));assert all(sha(P/p)==h for p,h in lock['sources'].items())
        assert all(sha(e.ROOT/p)==h for p,h in lock['external_dependencies'].items())
    output=P/'results'/split;output.mkdir(parents=True,exist_ok=False)
    tasks=read(P/'data'/split/'tasks.jsonl');truth=read(P/'data'/split/'oracle.jsonl');assert len(tasks)==len(truth)
    n=len(tasks);arms=[(method,k) for k in [2,3,5] for method in e.METHODS]
    features=np.zeros((len(arms),n,e.DIM),dtype=np.float32);labels=np.array([[r[a] for a in ['gender_F','disability_Y']] for r in truth],dtype=np.int8)
    summaries=[];raw=[];start=time.perf_counter();full_equal=0;oracle_success=0
    with gzip.open(output/'raw_rows.jsonl.gz','wt',encoding='utf8') as f:
      for i,(task,oracle) in enumerate(zip(tasks,truth)):
        assert task['request_id']==oracle['request_id'];profile,request=e.begin(task);v=e.values(profile)
        assert v==oracle['source_values'];ref=oracle['reference'];required=set(ref['read_keys']);sens={r.record_id:r.sensitivity for r in profile.profile_records};total=sum(sens.values());fullout=execute(task['type_id'],task['variant'],v,task['params']);assert fullout==ref;oracle_success+=1
        for j,(method,k) in enumerate(arms):
            chosen=e.choose(method,profile,request,k);ids,wire,nt,parsed=e.release(chosen,v,k);features[j,i]=e.view(task,parsed)
            out=execute(task['type_id'],task['variant'],parsed,task['params']);success=out['status']==ref['status'] and out['answer']==ref['answer'];hit=len(required&set(ids));recall=hit/len(required);precision=hit/len(ids) if ids else 0.;f1=2*recall*precision/(recall+precision) if recall+precision else 0.
            row={'case':task['request_id'],'student':task['student_id'],'family':task['family'],'type':task['task_type'],'difficulty':task['difficulty'],'method':method,'K':k,
                 'Recall':recall,'Precision':precision,'F1':f1,'completion':int(success),'answered_success':int(success and ref['status']=='answer'),
                 'reference_answerable':int(ref['status']=='answer'),'correct_clarification':int(success and ref['status']=='clarify'),'fields':len(ids),'tokens':nt,
                 'high_sensitive_selection_ratio':sum(sens[x]>=.7 for x in ids)/len(ids) if ids else 0.,'direct_sensitive_field_count':sum(x in ['gender_F','disability_Y'] for x in ids),
                 'weighted_privacy_exposure':sum(sens[x] for x in ids)/total,'released_sensitivity_mass':sum(sens[x] for x in ids),
                 'budget_feasible_oracle':int(len(required)<=k and len(e.TOKENIZER.encode(e.payload(v,required),add_special_tokens=False))<=96),
                 'selected':ids,'wire':wire,'reference_output':ref['answer'],'actual_output':out['answer'],'outcome_status':out['status']}
            if split=='dev' and method=='MM-FOPD':
                original=e.original.ProfileSelector(e.config(k,method)).select(profile,request);baseline=e.release(original,v,k)[0];full_equal+=set(baseline)==set(ids)
            f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
        if i%200==0:print(split,i,'/',n,'elapsed',round(time.perf_counter()-start,1),flush=True)
    np.savez_compressed(output/'features_LOCAL.npz',**{f'arm{j}':features[j] for j in range(len(arms))},labels=labels,public=features[0,:,:e.PUBN])
    (output/'execution.json').write_text(json.dumps({'status':'COMPLETED','split':split,'tasks':n,'students':len({t['student_id'] for t in tasks}),'arms':arms,'rows':n*len(arms),'seconds':time.perf_counter()-start,'all_candidate_program_correct':oracle_success,'dev_full_equivalent_to_snapshot_after_same_budget':full_equal if split=='dev' else None,'source_hashes':{p.name:sha(p) for p in P.glob('*.py')},'paid_calls':0},indent=2),encoding='utf8')
    print('COMPLETED',split,flush=True)
if __name__=='__main__':run(sys.argv[1])
