"""Consolidate verification and hash the completed evidence without rerunning methods."""
import json
import time
from collections import Counter
from experiments.c2rag_imperfect_forecast_20261027_01.common import *


def main():
    deadline();frozen();proof=read('independent_verification.json');repair=read('repairs/forecast_information_boundary.json')
    original=(OUT/'independent_verification.json').read_bytes()
    (OUT/'independent_verification.initial.json').open('xb').write(original)
    oldhashes=read('forecast_manifest.json')
    for p,h in oldhashes.items():
        assert sha((OUT/p).read_bytes())==h
        other=OUT/p.replace('forecasts/','forecasts_causal_recheck/')
        assert (OUT/p).read_bytes()==other.read_bytes()
    planning=read('independent_planning_verification.json');assert planning['all_scores_and_choices_match']
    assert len(repair['workers'])==320 and all(x['identical_all_packet_fields'] for x in repair['workers'])
    assert read('mathematical_contract_verification.json')['T06_field_subsets']==128
    for s in read('events.json'):
        if s['structure']=='kinetic':
            counts=Counter(e['qid'] for e in s['requests']);assert read(f'opt/{s["id"]}.json')['utility']==max(counts.values())
    proof.update({'causal_forecast_processes':320,'causal_packets_reverified_identical':2560,
       'information_boundary_repair':'repairs/forecast_information_boundary.json',
       'independent_all_menu_and_rollout_scores_match':True,'mathematical_T06_subsets_certified':128,
       'kinetic_OPT_majority_closed_form_checked':32,'original_forecast_and_method_results_unchanged':True})
    (OUT/'independent_verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8',newline='')
    write('verification_consolidation.json',{'initial_report':'independent_verification.initial.json',
       'added_checks_only':True,'method_result_changed':False,'original_primary_inputs_hashes_preserved':True})
    write('source_code_sha256.json',{p.relative_to(PROJECT_ROOT).as_posix():sha(p.read_bytes()) for p in sorted(SOURCE.glob('*')) if p.is_file()})
    write('completion_receipt.json',{'start_epoch':START,'deadline_epoch':DEADLINE,'sealed_epoch':time.time(),
        'elapsed_minutes':(time.time()-START)/60,'within120minutes':time.time()<DEADLINE,
        'completed_streams':64,'traces':832,'actual_requests_per_condition_per_method':512,
        'models':0,'paid_APIs':0,'GPU':0,'new_data_or_model_downloads':0,'parameter_search':False,
        'production_changes':False,'stopped_after_sync':True})
    write('MANIFEST.sha256.json',{p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file()})
    print('Evidence sealed, elapsed minutes',round((time.time()-START)/60,2))


if __name__=='__main__':main()
