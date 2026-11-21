"""Supplemental single-function attention removal; never edits frozen main methods.

The historical no-attention fallback also changes score scale and Top8 shortlist.
This separate, explicitly post-design audit replaces only attention weights with
uniform normalized values, retaining its Top8 interface and every other flag.
"""
import engine as e
from evaluate import read
import json,gzip,hashlib,sys
from pathlib import Path
P=e.P
def uniform_attention(self,task,records):
    return [(i,1/len(records)) for i in range(min(self.top_k,len(records)))] if records else []
def run(split):
    lock=P/'strict_attention_supplement_lock.json'
    if not lock.exists():
        lock.write_text(json.dumps({'classification':'SUPPLEMENTAL_MECHANISM_AUDIT_NOT_INITIAL_CONFIRMATORY_BASELINE','reason':'legacy no-attention simultaneously changes normalized score scale and shortlist size; cannot isolate attention','intervention':'only replace compute_attention with uniform1/N normalized scoring and sameTop8; all MM component flags and common gates/caps unchanged','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'primary_final_freeze_unchanged':True,'no_test_resampling_or_parameter_search':True},indent=2),encoding='utf8')
    assert json.loads(lock.read_text())['source_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output=P/'results'/split/'strict_attention_equivalence.json'
    if output.exists():raise RuntimeError('no overwrite')
    ref={}
    with gzip.open(P/'results'/split/'raw_rows.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line)
            if row['method']=='MM-FOPD':ref[(row['case'],row['K'])]=row['wire']
    e.att.TaskAttentionSelector.compute_attention=uniform_attention
    tasks=read(P/'data'/split/'tasks.jsonl');n=0;equal=0
    for row in tasks:
        profile,task=e.begin(row);v=e.values(profile)
        for k in [2,3,5]:
            chosen=e.CachedSelector(e.config(k,'MM-FOPD')).select(profile,task);_,wire,_,_=e.release(chosen,v,k);n+=1;equal+=wire==ref[(row['request_id'],k)]
    result={'split':split,'actual_recomputations':n,'actual_wire_equal_to_full':equal,'all_equal':n==equal,'new_name':'MM-no-attention-strict-uniform','same_caps_gates_TaskSlot_bottleneck_projection':True,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output.write_text(json.dumps(result,indent=2),encoding='utf8')
    if n!=equal:raise RuntimeError('not identical: keep audit and evaluate new features before claiming metrics')
    print(result,flush=True)
if __name__=='__main__':run(sys.argv[1])
