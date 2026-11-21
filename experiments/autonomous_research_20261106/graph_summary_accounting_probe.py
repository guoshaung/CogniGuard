import json, os, socket, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
os.environ.update(COGNIGUARD_LANGSMITH_ENABLED='0',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
def deny(*args,**kwargs): raise RuntimeError('network prohibited')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
from core.access import AccessScope
from cogniguard.runtime.protection_context import ProtectionContext,protection_scope
from cogniguard.runtime.sessions import SessionStore
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline
from protection.common.schemas import ProfileRecord,StudentProfile
class NoExport:
 def export(self,recorder): pass
base=root/'experiments/autonomous_research_20261106/temp'
folder=Path(tempfile.mkdtemp(prefix='profile-graph-',dir=base))
result={}
for arm in ('raw_exact','derived_band','no_disclosure'):
 raw='visual_support' if arm=='raw_exact' else 'visual_cards'
 profile=StudentProfile('fictional_adult',{},[
  ProfileRecord('preference','preference','algebra',raw,1.0,0.5,'2026-01-01'),
  ProfileRecord('other','mastery','other_subject',0.42,1.0,0.5,'2026-01-01')])
 cfg={'access':{'max_profile_sensitivity':0.0 if arm=='no_disclosure' else 0.7},
      'fopd':{'use_enhanced_fopd':False,'top_k_profile_records':1,'relevance_threshold':0.0,
              'sensitivity_threshold':0.7,'privacy_budget':1.0}}
 received=[]
 def generator(data):
  received.append({'category': 'visual_support' in data.context_card,'raw_present':raw in data.context_card})
  return 'fictional local teaching response'
 runner=LangGraphProtectionPipeline(cfg,[],watermark=None,generator=generator,monitor=NoExport())
 store=SessionStore(folder/(arm+'.sqlite3'),limits={'requests':10,'privacy':10,'copyright':10})
 session=store.get_or_create(); rounds=[]
 for i in range(2):
  q={'request_id':'case-'+str(i),'student_id':'fictional_adult','question':'algebra',
     'expected_knowledge':'algebra','need_resource':False}
  with session.request('request-'+str(i),fingerprint=arm+str(i)) as request:
   with session.transaction() as state:
    frame=ProtectionContext(session,'request-'+str(i),'education',state)
    with protection_scope(frame):
     output=runner.run(profile,q,access=AccessScope('fictional_adult')).to_dict()
   request.complete({'completed':True})
  evidence=output['privacy_evidence']; observation=received[-1]
  rounds.append({'selected_ids':output['selected_record_ids'],
                 'selection_cost':evidence['selection_cost'],'released_exposure':evidence['released_exposure'],
                 'memory_remaining':evidence['budget_after'],'session_privacy':session.budget('privacy'),
                 'category_received':observation['category'],'raw_present_at_receiver':observation['raw_present'],
                 'category_in_result':'visual_support' in output['context_card'],
                 'watermark_enabled':runner.last_state.get('watermark_enabled'),
                 'privacy_stage_before':runner.last_state.get('privacy_before'),
                 'privacy_stage_after':runner.last_state.get('privacy_after')})
 result[arm]=rounds
assert all(x['category_received'] and x['raw_present_at_receiver'] and x['released_exposure']==.5 for x in result['raw_exact'])
assert all(x['category_received'] and not x['raw_present_at_receiver'] and x['released_exposure']==0 for x in result['derived_band'])
assert all(not x['category_received'] and x['selected_ids']==[] and x['released_exposure']==0 for x in result['no_disclosure'])
assert all(x['watermark_enabled'] is False for arm in result.values() for x in arm)
print(json.dumps({'synthetic_only':True,'network_blocked':True,'receiver':'local generator fixture','gateway_invoked':False,'results':result},indent=2))
