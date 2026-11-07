"""New missing-edge regression; preserves original v1 tests and actual records."""
import json,tempfile,time
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from lifecycle import Register,canonical
from lifecycle_v2 import StrictRegister
from bootstrap import E,R,save,digest
key=Ed25519PrivateKey.generate();pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
record={'issue_id':'UNIT_I','source_id':'S','issuer_id':'UNIT_ISSUER','recipient_pseudonym':'UNIT_R',
 'content_version':'v1','key_epoch':'E2','parent_issue_id':None,'method':'UNIT_FIXTURE','key_id':'UNIT_ONLY',
 'public_sha256':'0'*64,'issued_at':120,'message_code':'UNIT_CODE'}
tests=[];t=time.perf_counter()
with tempfile.TemporaryDirectory(dir=R/'tmp') as temp:
 for cls in [Register,StrictRegister]:
  reg=cls(Path(temp)/(cls.__name__+'.sqlite3'),pub);reg.add_epoch('E2',100,200,1000);reg.register(record,key.sign(canonical(record)))
  futurevisible=bool(reg.audit_candidates(50));historicalvisible=bool(reg.audit_candidates(150))
  reg.compromise('E2');new={**record,'issue_id':'UNIT_NEW','message_code':'UNIT_NEW_CODE'}
  blocked=False
  try:reg.register(new,key.sign(canonical(new)))
  except ValueError:blocked=True
  retroblocked=False
  try:reg.permission('UNIT_I',50,'REVOKED')
  except ValueError:retroblocked=True
  tests.append({'implementation':cls.__name__,'future_issuance_hidden':not futurevisible,'historical_issuance_visible':historicalvisible,
   'new_issue_under_compromised_epoch_blocked':blocked,'retroactive_before_issue_permission_blocked':retroblocked})
  reg.close()
 assert not tests[0]['future_issuance_hidden'] and not tests[0]['new_issue_under_compromised_epoch_blocked']
 assert all(v for k,v in tests[1].items() if k!='implementation')
 # Actual signed v1 issue records are not changed. Evaluate new clock filter only.
 actual=json.loads((R/'analysis_round01/REGISTER_PUBLIC.json').read_text())['rows']
 visible=[x['record']['issue_id'] for x in actual if x['record']['issued_at']<=150]
 assert len(visible)==len(actual)
save(R/'LIFECYCLE_V2_REGRESSION.json',{'status':'PASS_NEW_OFFLINE_GUARDS','kind':'UNIT_FIXTURE_AND_ACTUAL_RECORD_COMPATIBILITY',
 'new_generated_answers':0,'tests':tests,'actual_records_at150_unchanged':len(visible),'actual_past_scores_rewritten':False,
 'v1_known_gaps_retained':True,'new_adapter_sha256':digest(E/'lifecycle_v2.py'),'wall_seconds':time.perf_counter()-t,
 'not_trusted_external_timestamp_or_production_transaction_security':True})
print(json.dumps({'status':'V2_GUARDS_PASS','actual_at150_unchanged':len(visible)}))
