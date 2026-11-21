import json
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ScoredProfileRecord
from protection.student_profile.src.fopd.context_card import build_context_card,_mastery_phrase
from protection.student_profile.src.fopd.privacy_budget import PrivacyBudgetLedger
records=[ProfileRecord('fictional_low','mastery','concept_alpha',0.42,1.0,0.5),ProfileRecord('fictional_high','mastery','concept_beta',0.84,1.0,0.5)]
profile=StudentProfile('fictional_adult',{},records)
task=Task('synthetic_task','fictional_adult','exercise','concept_alpha','standard',False)
summary_ledger=PrivacyBudgetLedger(maximum=1.0)
raw_ledger=PrivacyBudgetLedger(maximum=1.0)
out=[]
cards=[]
for record in records:
 card,_=build_context_card(profile,task,[ScoredProfileRecord(record,1.0,{})]);cards.append(card)
 assert _mastery_phrase(record.value) in card and str(record.value) not in card
 ev=summary_ledger.measure_and_commit(profile,[record.record_id],card)
 control=raw_ledger.measure_and_commit(profile,[record.record_id],str(record.value))
 out.append({'summary':ev.to_dict(),'raw_control':control.to_dict()})
assert _mastery_phrase(records[0].value)!=_mastery_phrase(records[1].value)
assert all(x['summary']['released_exposure']==0 for x in out)
assert all(x['raw_control']['released_exposure']==0.5 for x in out)
print(json.dumps({'different_mastery_bands':True,'rounds':out},indent=2))
