import json,os,re,socket,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
def deny(*args,**kwargs):raise RuntimeError('network prohibited')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
from cogniguard.agents.learning_assessment_agent import LearningAssessmentAgent
questions=[(2,3,7,'equation algebra subtract three divide two isolate answer equals two'),
           (3,-2,7,'equation algebra add two divide three isolate answer equals three'),
           (4,1,13,'equation algebra subtract one divide four isolate answer equals three')]
agent=LearningAssessmentAgent(llm_client=None);rows=[]
for a,b,c,teaching in questions:
 assert (c-b)%a==0
 solution=(c-b)//a; wrong=solution+1
 cases={'short_correct':f'x={solution}', 'short_wrong':f'x={wrong}',
        'long_wrong':f'{teaching}. But I conclude x={wrong}',
        'correct_working':f'{teaching}. Therefore x={solution}',
        'correct_paraphrase':f'I undo the addition or subtraction and then scale down. My result is x={solution}'}
 for kind,response in cases.items():
  match=re.search(r'x\s*=\s*(-?\d+)\s*$',response)
  value=int(match.group(1)) if match else None
  truth=(a*value+b==c) if value is not None else None
  result=agent.generate({'teaching_answer':teaching,'student_response':response,
                         'knowledge_point':'equation algebra','profile_encoding':{}})
  score=result['mastery_score']
  rows.append({'equation':[a,b,c],'kind':kind,'parsed_answer':value,'final_answer_correct':truth,
               'fallback_score':score,'fallback_label':result['assessment_result']})
assert len(rows)==15 and all(r['final_answer_correct'] is not None for r in rows)
summary={}
for threshold in (.45,.75):
 counts={'tp':0,'tn':0,'fp':0,'fn':0}
 for r in rows:
  pred=r['fallback_score']>=threshold; true=r['final_answer_correct']
  counts['tp' if pred and true else 'fp' if pred else 'fn' if true else 'tn']+=1
 summary[str(threshold)]=counts
by_kind={}
for kind in ('short_correct','short_wrong','long_wrong','correct_working','correct_paraphrase'):
 group=[r for r in rows if r['kind']==kind]
 by_kind[kind]={'mean_score':sum(r['fallback_score'] for r in group)/len(group),'scores':[r['fallback_score'] for r in group],
                'final_answer_correct':sum(r['final_answer_correct'] for r in group)}
rank=[]
for a,b,c,_ in questions:
 s=[r for r in rows if r['equation']==[a,b,c]]
 good=next(r['fallback_score'] for r in s if r['kind']=='short_correct')
 bad=next(r['fallback_score'] for r in s if r['kind']=='long_wrong')
 rank.append({'equation':[a,b,c],'wrong_long_above_short_correct':bad>good,'tied':bad==good})
print(json.dumps({'cases':rows,'fixed_threshold_diagnostics':summary,'by_response_type':by_kind,
                  'ranking':rank,'final_answer_baseline_correct':sum(r['final_answer_correct']==(a['a']*r['parsed_answer']+a['b']==a['c']) for r,a in [(r,dict(a=r['equation'][0],b=r['equation'][1],c=r['equation'][2])) for r in rows]),
                  'baseline_scope':'restricted integer x format; final answer only','hash_seed':os.environ.get('PYTHONHASHSEED')},indent=2))
