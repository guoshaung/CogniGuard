"""Keep failed pre-evaluation attempt; fix cross-subject token-cache identity."""
from pathlib import Path
import json,hashlib
P=Path(__file__).parent
source=(P/'run_mm.py').read_text(encoding='utf8')
target=source.replace("O=P/'mm'","O=P/'mm_v2'").replace("key=(p.student_id,tuple(ids));tc=counter_cache.get(key)","key=(p.student_id,t.knowledge,tuple(sorted((k,str(row[k])) for k in ids)));tc=counter_cache.get(key)")
assert target!=source
if (P/'run_mm_v2.py').exists():raise RuntimeError('refuse overwrite')
(P/'run_mm_v2.py').write_text(target,encoding='utf8')
(P/'mm/failure.json').write_text(json.dumps({'status':'FAILED_DURING_FIRST_DEV_CONFIGURATION','reason':'Math and Portuguese reuse uci-math-N IDs. Token counter cache keyed only by student ID and fields incorrectly reused across subjects. Exact serialization assertion caught mismatch.','new_tests_evaluated':0,'old_test_predictions_evaluated':0,'repair':'v2 key includes subject knowledge and canonical eligible field values; original attempt and source retained','original_driver_sha256':hashlib.sha256(source.encode()).hexdigest()},indent=2),encoding='utf8')
