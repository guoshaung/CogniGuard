"""Two-turn synthetic graph accounting after optional governance rejection."""
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
def reject_network(*args, **kwargs):
    raise RuntimeError('network prohibited in synthetic two-turn probe')
socket.socket.connect = reject_network
socket.socket.connect_ex = reject_network
socket.create_connection = reject_network

from cogniguard.governance import CapabilityGrant, CapabilityPolicy, LifecycleGuard
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline
from core.access import AccessScope
from protection.common.schemas import ProfileRecord, ResourcePolicy, StudentProfile, TeacherResource

class NoExport:
    def export(self, recorder):
        pass

cfg = {'fopd': {'use_enhanced_fopd': True, 'privacy_budget': 1.0}}
profile = StudentProfile('fictional', profile_records=[
    ProfileRecord('fictional', 'mastery', 'algebra', 0.55, 1.0, 0.3, '2026-01-01')])
question = {'request_id': 'fictional', 'student_id': 'fictional', 'question': 'alpha beta gamma algebra',
            'expected_knowledge': 'algebra', 'need_resource': True}
fixture = 'alpha beta gamma'
out = {'synthetic_only': True, 'network_blocked': True, 'runs': []}
for guarded in (False, True):
    resource = TeacherResource('synthetic', 'synthetic', fixture, 'algebra', 'basic', 'basic', 'example', 0.0,
                               ResourcePolicy(allow_quote=True, allow_summary=False, allow_outline=False,
                                              allow_variant=False, max_quote_len=20, max_exposure=0.2))
    grants = [CapabilityGrant('service', dest, frozenset({'education'})) for dest in ('teaching', 'delivery')]
    guard = LifecycleGuard(CapabilityPolicy(grants)) if guarded else None
    runner = LangGraphProtectionPipeline(cfg, [resource], guard=guard, watermark=None,
                                         generator=None, monitor=NoExport(), retrieval_guard=None)
    turns = []
    for turn in (1, 2):
        before = runner.budget.get('synthetic')
        start_actions = len(guard.audit.records) if guard else 0
        mode = returned_full = None
        try:
            result = runner.run(profile, question, access=AccessScope('fictional'))
            outcome = 'returned'
            mode = result.controlled.mode if result.controlled else None
            returned_full = bool(result.controlled and result.controlled.text == fixture)
        except PermissionError:
            outcome = 'permission_error'
        assert runner.watermark is None
        turns.append({'turn': turn, 'ledger_before': before, 'ledger_after': runner.budget.get('synthetic'),
                      'outcome': outcome, 'mode': mode, 'full_fixture_returned': returned_full,
                      'guard_actions': [r['action'] for r in guard.audit.records[start_actions:]] if guard else []})
    out['runs'].append({'guarded': guarded, 'turns': turns})
print(json.dumps(out, indent=2))
