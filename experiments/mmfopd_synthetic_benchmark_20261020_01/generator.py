"""Wholly synthetic, stochastic learner histories and fresh decision episodes."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
from truth import TYPES,INPUTS,PARAMS,execute
P=Path(__file__).parent
# type,sensitivity: annotations independent of reference program read traces.
FIELDS={
 'mastery_a':('mastery',.40),'mastery_b':('mastery',.40),'mastery_c':('mastery',.40),'prior_mastery':('mastery',.40),
 'recent_score':('mastery',.45),'prior_score':('mastery',.45),'error_a':('error_pattern',.40),'error_b':('error_pattern',.40),'attempts':('behavior_aggregate',.30),
 'preference':('preference',.25),'prerequisite':('mastery',.35),'time_budget':('learning_state',.35),'fatigue':('learning_state',.50),
 'practice_rate':('behavior_aggregate',.35),'activity_recent':('behavior_aggregate',.30),'activity_prior':('behavior_aggregate',.30),'inactive_days':('learning_state',.40),
 'access_rate':('access_context',.55),'deadline':('learning_state',.20),'history_slope':('learning_state',.35),
 'agent_a':('multimodal_summary',.45),'agent_b':('multimodal_summary',.45),'confidence_a':('multimodal_summary',.30),'confidence_b':('multimodal_summary',.30),'behavior_flag':('behavior_aggregate',.40),
 'gender_F':('sensitive',.95),'disability_Y':('sensitive',.95),'device_proxy':('access_context',.55),'schedule_proxy':('behavior_aggregate',.60)}
def seed_for(*parts):return int(hashlib.sha256(':'.join(map(str,parts)).encode()).hexdigest()[:16],16)
def profile(i):
    rng=np.random.default_rng(seed_for(2026102011,i));gender=int(rng.random()<.5);disability=int(rng.random()<.20)
    ability=rng.beta(2,2);n=int(rng.integers(5,41));slope=rng.normal(0,.04)
    hist=[{'day':int(j*7+rng.integers(0,4)),'mastery':float(np.clip(ability+slope*j/4+rng.normal(0,.10),.02,.98)),
           'practice':float(rng.beta(2,2)),'activity':int(rng.poisson(7))} for j in range(n)]
    return {'student_id':f'SYN{i:05d}','split':'train' if i<2500 else ('dev' if i<3000 else 'test'),
      'gender_F':gender,'disability_Y':disability,'ability':float(ability),'slope':float(slope),'preference':int(rng.integers(0,2)),
      'knowledge_mastery':{f'topic{j}':float(rng.beta(2,2)) for j in range(8)},'history':hist}
def dumps(path,rows):
    with path.open('w',encoding='utf8') as f:
        for x in rows:f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
def generate(split):
    if split!='dev':assert (P/'final_freeze.json').exists(),'Freeze before train/test generation'
    out=P/'data'/split;out.mkdir(parents=True,exist_ok=False)
    ids=range(2500,3000) if split=='dev' else (range(2500) if split=='train' else range(3000,5000))
    roster=[profile(i) for i in ids];counts={'dev':1000,'train':5000,'test':10000};seed={'dev':2026102012,'train':2026102013,'test':2026102014}[split]
    rng=np.random.default_rng(seed);assignment=np.tile(np.arange(len(roster)),counts[split]//len(roster));rng.shuffle(assignment)
    public=[];oracles=[];signatures=set()
    for index,personidx in enumerate(assignment):
        person=roster[personidx];rr=np.random.default_rng(seed_for(seed,index));typ=index%8;difficulty=(index//8)%5;variant=(index//40)%4
        topic='topic'+str(int(rr.integers(0,8)));recent=person['history'][-1];prior=person['history'][-2];a=float(np.clip(.5*recent['mastery']+.5*person['knowledge_mastery'][topic]+rr.normal(0,.12),.01,.99))
        values={k:float(rr.beta(2,2)) for k in FIELDS};values.update(mastery_a=a,mastery_b=float(rr.beta(2,2)),mastery_c=float(rr.beta(2,2)),prior_mastery=prior['mastery'],recent_score=round(100*a+rr.normal(0,5),3),prior_score=round(100*prior['mastery'],3),error_a=int(rr.integers(0,12)),error_b=int(rr.integers(0,12)),attempts=int(rr.integers(12,30)),preference=person['preference'],prerequisite=int(rr.random()>.25),time_budget=int(rr.integers(10,100)),deadline=int(rr.integers(1,22)),fatigue=float(rr.beta(2,2)),inactive_days=int(rr.integers(0,16)),activity_recent=int(rr.poisson(recent['activity']+1)),activity_prior=prior['activity'],history_slope=person['slope'],agent_a=float(np.clip(a+rr.normal(0,.13),0,1)),agent_b=float(np.clip(a+rr.normal(0,.15),0,1)),behavior_flag=int(rr.random()<.4),gender_F=person['gender_F'],disability_Y=person['disability_Y'],device_proxy=float(np.clip(.18+.60*person['gender_F']+rr.normal(0,.16),0,1)),schedule_proxy=float(np.clip(.20+.55*person['disability_Y']+rr.normal(0,.18),0,1)),access_rate=float(np.clip(.75-.32*person['disability_Y']+rr.normal(0,.20),0,1)))
        values={k:round(float(v),3) for k,v in values.items()}
        params={'threshold':round(float(rr.uniform(.30,.70)),4),'weight':round(float(rr.uniform(.65,1.25)),4),'budget':int(rr.integers(20,70)),'count':int(rr.integers(3,10)),'days':int(rr.integers(4,14))}
        if difficulty==2:
            missing=INPUTS[typ][variant][int(rr.integers(0,len(INPUTS[typ][variant])))];values[missing]=None
        elif difficulty==3:
            # Force a branch-rich setting without looking at any selector outcome.
            values['prerequisite']=int(rr.random()<.5)
        nnoise=int(rr.integers(2,min(9,len(person['history']))));metadata={**FIELDS,**{f'history_noise_{j}':('learning_state',.25+.05*(j%4)) for j in range(nnoise)}}
        values.update({f'history_noise_{j}':round(float(rr.beta(2,2)),3) for j in range(nnoise)})
        if difficulty==4:
            # Stress proxy distraction, same known correlations; no hidden target rule changes.
            values['device_proxy']=round(float(np.clip(.1+.8*person['gender_F']+rr.normal(0,.10),0,1)),3)
        records=[]
        for k,(record_type,sens) in metadata.items():
            records.append({'record_id':k,'type':record_type,'knowledge':topic if not k.startswith('history_noise') else 'other_topic',
              'value':f'{k}={"NA" if values[k] is None else values[k]}','confidence':round(float(rr.uniform(.65,.99)),3),'sensitivity':sens,'updated_at':f'2026-09-{int(rr.integers(1,29)):02d}'})
        rr.shuffle(records)
        words=TYPES[typ].replace('_',' ')
        if difficulty in [0,2,3]:words+=' using '+', '.join(INPUTS[typ][variant])
        elif difficulty==4:words+=' consider access and schedule context with educational evidence'
        else:words+=' review current learning evidence and choose the next teaching action'
        question=f'{words}. Decision rule variant {variant}; '+', '.join(f'{k}={params[k]}' for k in PARAMS[typ][variant])+'.'
        task={'request_id':f'{split}-{index:05d}','student_id':person['student_id'],'split':split,'type_id':typ,'task_type':TYPES[typ],'variant':variant,'family':f'{TYPES[typ]}:v{variant}','difficulty':['explicit','ambiguous','missing','dependency','sensitive_proxy'][difficulty],'knowledge':topic,'question':question,'params':params,'records':records}
        ref=execute(typ,variant,values,params)
        oracle={'request_id':task['request_id'],'student_id':person['student_id'],'gender_F':person['gender_F'],'disability_Y':person['disability_Y'],'reference':ref,'source_values':values}
        signature=hashlib.sha256(json.dumps({'type':typ,'variant':variant,'values':{k:values[k] for k in INPUTS[typ][variant]},'params':{k:params[k] for k in PARAMS[typ][variant]}},sort_keys=True).encode()).hexdigest();signatures.add(signature)
        public.append(task);oracles.append(oracle)
    dumps(out/'profiles.jsonl',roster);dumps(out/'tasks.jsonl',public);dumps(out/'oracle.jsonl',oracles)
    stats={'split':split,'students':len(roster),'tasks':len(public),'structural_program_families':32,'unique_semantic_episode_fingerprints':len(signatures),'unique_question_strings':len({t['question'] for t in public}),'history_min':min(len(r['history']) for r in roster),'history_max':max(len(r['history']) for r in roster),'candidate_count_range':[min(len(r['records']) for r in public),max(len(r['records']) for r in public)],'protected_positives':{k:sum(r[k] for r in roster) for k in ['gender_F','disability_Y']}}
    (out/'statistics.json').write_text(json.dumps(stats,indent=2),encoding='utf8');print(stats,flush=True)
if __name__=='__main__':generate(sys.argv[1])
