"""Frozen scores on all unmarked T5 sources; no threshold selection."""
from common_adjusted import *
sys.path.insert(0,str(W/'experiments/hsw_english_replication_20261110_01'))
from e1_v4r3_core import exact,pb_tail

def main():
    plans=[x for x in read(O/'T5_prepared/PLANS.json') if x['method']=='RC']
    lists={tuple(x['selected']) for x in plans};assert len(lists)==1
    ws=list(next(iter(lists)));freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities'];rows=[]
    for x in read(O/'T5_SOURCES.json'):
        old=read(O/'T5_evaluation/records'/('T5__'+x['id']+'__Fingerprint.json'))
        pv=pb_tail([freq[w] for w in ws],sum(exact(x['text'],w) for w in ws))
        rows.append(dict(source_id=x['id'],text_sha256=x['text_sha256'],CertInsert_p=old.get('p'),RC_p=pv))
    counts={m:dict(k=sum(x[m+'_p']<.01 for x in rows if x[m+'_p'] is not None),n=sum(x[m+'_p'] is not None for x in rows)) for m in ['CertInsert','RC']}
    put(O/'T5_UNMARKED_CONTROLS.json',dict(counts=counts,rows=rows,threshold=.01,threshold_unchanged=True,purpose='Diagnostic unmarked generated sources, separate from500 textbook backgrounds',posthoc_reporting_not_calibration=True));print(counts)

if __name__=='__main__':main()
