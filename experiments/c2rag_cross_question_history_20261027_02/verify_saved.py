"""Read-only preservation and exhaustive-result consistency check."""
from experiments.c2rag_cross_question_history_20261027_02.common import OUT,OLD,PROJECT_ROOT,read,sha,verify_freeze
import json


def main():
    verify_freeze()
    manifest=read('MANIFEST.sha256.json')
    for path,h in manifest.items():assert sha((OUT/path).read_bytes())==h,path
    oldmanifest=json.loads((OLD/'MANIFEST.sha256.json').read_text(encoding='utf8'))
    for path,h in oldmanifest.items():assert sha((OLD/path).read_bytes())==h,path
    rows=read('replay.json');assert len(rows)==48
    assert len({x['global_case_sha256'] for x in rows})==1
    independent=read('independent_verification.json');assert independent['all_claims_verified']
    for mode in ['fixed','all']:
        a=read(f'opt_{mode}_primary.json');b=read(f'opt_{mode}_independent.json')
        assert a['completed'] and b['completed']
        assert a['safe_codes']==b['safe_codes'] and a['optimal_plans']==b['optimal_plans']
        assert a['checked']==a['planned']==(65536 if mode=='fixed' else 98304)
        assert a['cpu_seconds']<=a['budget_seconds'] and b['cpu_seconds']<=b['budget_seconds']
    print(json.dumps({'artifact_hashes_verified':len(manifest),'old_artifacts_unchanged':len(oldmanifest),
                      'same_global_case_all_groups':True,'full_fixed_and_all_enumeration_verified':True,
                      'independent_checks_verified':True},ensure_ascii=False))


if __name__=='__main__':main()
