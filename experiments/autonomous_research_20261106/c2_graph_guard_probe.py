"""Run protected graph on a synthetic capped resource, without HSW or network."""
import hashlib
import json
import os
import socket
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ['COGNIGUARD_LANGSMITH_ENABLED'] = '0'
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
def block_network(*args, **kwargs):
    raise RuntimeError('network prohibited in synthetic graph probe')
socket.socket.connect = block_network
socket.socket.connect_ex = block_network
socket.create_connection = block_network

from cogniguard.governance import CapabilityGrant, CapabilityPolicy, LifecycleGuard
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline
from core.access import AccessScope
from protection.common.schemas import ProfileRecord, ResourcePolicy, StudentProfile, TeacherResource

class NoExport:
    def export(self, recorder):
        pass

def guard_factory():
    grants = [CapabilityGrant('service', dest, frozenset({'education'})) for dest in ('teaching', 'delivery')]
    return LifecycleGuard(CapabilityPolicy(grants))

cfg = {'fopd': {'use_enhanced_fopd': True, 'privacy_budget': 1.0}}
profile = StudentProfile(student_id='fictional', profile_records=[
    ProfileRecord('fictional', 'mastery', 'algebra', 0.55, 1.0, 0.3, '2026-01-01')])
question = {'request_id': 'fictional', 'student_id': 'fictional', 'question': 'alpha beta gamma algebra',
            'expected_knowledge': 'algebra', 'need_resource': True}
fixture = 'alpha beta gamma'
out = {'synthetic_only': True, 'network_blocked': True, 'cases': []}
for cap in (0.0, 0.2):
    for guarded in (False, True):
        policy = ResourcePolicy(allow_quote=True, allow_summary=False, allow_outline=False,
                                allow_variant=False, max_quote_len=20, max_exposure=cap)
        resource = TeacherResource('synthetic', 'synthetic', fixture, 'algebra', 'basic', 'basic',
                                   'example', 0.0, policy)
        guard = guard_factory() if guarded else None
        runner = LangGraphProtectionPipeline(cfg, [resource], guard=guard, watermark=None,
                                             generator=None, monitor=NoExport(), retrieval_guard=None)
        outcome, mode, returned_fixture = None, None, None
        try:
            result = runner.run(profile, question, access=AccessScope('fictional'))
            outcome = 'returned'
            mode = result.controlled.mode if result.controlled else None
            returned_fixture = bool(result.controlled and result.controlled.text == fixture)
        except PermissionError:
            outcome = 'permission_error'
        assert runner.watermark is None
        actions = [r['action'] for r in guard.audit.records] if guard else []
        out['cases'].append({'max_exposure': cap, 'guarded': guarded, 'outcome': outcome,
                             'controlled_mode': mode, 'full_fixture_in_controlled_result': returned_fixture,
                             'ledger_after': runner.budget.get('synthetic'), 'guard_actions': actions})
paths = ['cogniguard/workflows/pipeline.py', 'cogniguard/governance/lifecycle.py',
         'protection/teacher_resource/src/c2rag/return_policy.py']
out['source_sha256'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
print(json.dumps(out, indent=2))
