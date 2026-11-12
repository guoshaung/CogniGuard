"""Freeze exact Batch01 insertion implementation adapted only to T5 input/output paths."""
from common_adjusted import *
s=(PREV/'insert_batch1.py').read_text(encoding='utf-8-sig')
s=s.replace('from initialize import *','from common_adjusted import *')
s=s.replace('from common import OLD,R',"from common import OLD,R\nBASE_OUTPUT=O\nO=BASE_OUTPUT/'T5_insertion'\nfor name in ['records','outputs']:(O/name).mkdir(parents=True,exist_ok=True)\ndef sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()")
s=s.replace("dest=O/'prepared_batch1'","dest=BASE_OUTPUT/'T5_prepared'")
s=s.replace("def spent():return 0", "def spent():return 0 # Stage cap remains7200; outer E3 ledger accounts all prior runtime")
# Only the exact path adapter and str/Path admission normalization are changed.
(E/'insert_t5.py').write_text(s,encoding='utf8')
put(E/'T5_INSERTION_ADAPTER_FREEZE.json',dict(parent_sha256=sha(PREV/'insert_batch1.py'),adapted_sha256=sha(E/'insert_t5.py'),changes=['input/output path isolation','sha supports str path'],algorithm_parameters_changed=False,scoring_per_source_seconds=300,scoring_per_source_tokens=250000,scoring_context_max=1024,stage_seconds=7200))
