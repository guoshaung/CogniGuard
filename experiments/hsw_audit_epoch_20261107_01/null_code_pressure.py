"""Unused-code pressure on cached public MPAC decoding; no new scoring calls."""
import json,hashlib
from bootstrap import R,save
from secrets_store import read
D=R/'analysis_round01';freeze=json.loads((D/'NULL_STRESS_FREEZE.json').read_text())
material=read(D/'DETECTOR_KEYS.dpapi');nullkeys=read(R/'private/NULL_DETECTOR_KEYS.dpapi')['null_keys']
assert not set(nullkeys)&(set(material['B2_keys'].values())|set(material['epoch_keys'].values())), 'Null key collided with issued key'
wm=[json.loads(l) for l in (D/'WM_SCORES.jsonl').read_text().splitlines()]
codes=freeze['unused_public_codes'];rows=[]
for q in freeze['queries']:
 matching=[r for r in wm if r['method']=='B3_MPAC32_OFFICIAL_LIST' and r['public_sha256']==q['public_sha256']]
 # Several B0 parents have the same exact bytes; deduplicate identical decoding.
 unique={r['candidate_key_id']:r for r in matching};assert set(unique)=={'MPAC_E1','MPAC_E2'}
 decoded={c['message_code'] for r in unique.values() for c in r['scores']['candidates']}
 for K in [1,8,32,128,512]:
  rows.append({'variant':q['variant'],'null_codes':K,'all_historical_epochs_scanned':2,'matching_unused_codes':len(set(codes[:K])&decoded),
   'actual_resource_count_not_K':True,'empirical_FPR_not_estimated':True})
save(D/'NULL_CODE_PRESSURE.json',{'status':'COMPLETE_CACHED_DECODINGS','new_model_calls':0,'new_detector_calls':0,
 'key_collision_check':'NO_COLLISION_WITH_ANY_ACTUALLY_RETAINED_KEY','independent_background_chapters':1,
 'rows':rows,'not_claimed_512_recipient_generation_or_attribution':True})
print('NULL_CODE_PRESSURE_SAVED_NO_NEW_FORWARD')
