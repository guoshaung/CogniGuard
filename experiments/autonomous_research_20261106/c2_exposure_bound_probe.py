"""Counterexample to hard post-release bound using only fictitious text."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from protection.common.schemas import ResourcePolicy, TeacherResource
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.return_policy import produce_controlled_resource

text = 'alpha beta gamma'
out = {'fixture': 'synthetic', 'cases': []}
for cap in (0.0, 0.2):
    policy = ResourcePolicy(allow_quote=True, allow_summary=False, allow_outline=False,
                            allow_variant=False, max_quote_len=20, max_exposure=cap)
    resource = TeacherResource(resource_id='synthetic', chunk_id='synthetic', content=text,
                               knowledge='topic', difficulty='basic', cognitive_level='basic',
                               resource_type='example', copyright_level=0.0, policy=policy)
    ledger = ExposureBudget({})
    candidate = produce_controlled_resource(resource, deepcopy(ledger), {})
    prospective_action = 'refuse' if candidate.exposure_after > cap else 'release'
    actual = produce_controlled_resource(resource, ledger, {})
    assert candidate.mode == actual.mode and candidate.exposure_after == actual.exposure_after
    out['cases'].append({'max_exposure': cap, 'before': actual.exposure_before,
                         'mode': actual.mode, 'after': actual.exposure_after,
                         'complete_fixture_returned': actual.text == text,
                         'after_exceeds_cap': actual.exposure_after > cap,
                         'prospective_same_candidate_action': prospective_action})
paths = ['protection/teacher_resource/src/c2rag/return_policy.py',
         'protection/teacher_resource/src/c2rag/exposure_budget.py']
out['source_sha256'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
print(json.dumps(out, indent=2))
