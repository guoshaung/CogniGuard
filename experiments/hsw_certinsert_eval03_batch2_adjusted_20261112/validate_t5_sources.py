"""Read-only raw generation linkage check, not a knowledge review."""
from common_adjusted import *

def main():
    planned={x['id']:x for x in read(O/'data/T5_QUESTIONS.json')}
    result=read(O/'P3/RESULT.json');seen=set();checks=[]
    for row in result['rows']:
        sid=row['source_id'];assert sid in planned and sid not in seen;seen.add(sid)
        p=O/'P3/outputs'/(row['id']+'.txt')
        if row['status']=='COMPLETED':
            assert sha(p)==row['output_sha256']
            expected=hashlib.sha256(planned[sid]['question'].encode()).hexdigest()
            request=read(O/'P3/records'/(row['id']+'.request.json'))
            prompt=read(O/'P3/EVAL_FREEZE.json')['T3_prompt']
            rendered='<|im_start|>system\nYou are a careful English science textbook editor.<|im_end|>\n<|im_start|>user\n'+prompt+'\n\n'+planned[sid]['question']+'<|im_end|>\n<|im_start|>assistant\n'
            assert request['prompt']==rendered
            assert request['seed']==(int(rank('T5_generation',sid)[:8],16)&0x7fffffff)
            assert all(request[k]==v for k,v in dict(n_predict=1024,temperature=.7,top_p=.9,top_k=40,repeat_penalty=1.).items())
            checks.append(dict(id=row['id'],input_sha256=expected,output_sha256=sha(p),tokens=row['tokens'],stop_type=row.get('stop_type'),PASS=True))
        else:checks.append(dict(id=row['id'],status=row['status'],PASS=None))
    assert result['attempted']==len(seen)
    put(O/'T5_SOURCE_LINKAGE_VALIDATION.json',dict(planned=len(planned),attempted=len(seen),completed=sum(x.get('PASS') is True for x in checks),unique_attempts=True,checks=checks,meaning='Byte hashes and planned question linkage only; not scientific knowledge validation'))
    print('T5 source linkage PASS',len(checks))

if __name__=='__main__':main()
