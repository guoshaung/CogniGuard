"""Synthetic protected vs research graphs; no HSW, model, or network."""
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

def reject_network(*args, **kwargs):
    raise RuntimeError('network prohibited in synthetic boundary probe')
socket.socket.connect = reject_network
socket.socket.connect_ex = reject_network
socket.create_connection = reject_network

from core.access import AccessScope
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline
from cogniguard.workflows.education.research import run_research_flow
from protection.common.schemas import ProfileRecord, StudentProfile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector

class NoExport:
    def export(self, recorder):
        pass

class ResearchOwner:
    def __init__(self, cfg):
        self.enable_fopd = True
        self.enable_c2rag = False
        self.enable_audit = False
        self.profile_selector = ProfileSelector(cfg)
    def _extract_knowledge(self, query):
        return 'algebra'

def config(orthogonal):
    return {'access': {'max_profile_sensitivity': 0.70},
            'fopd': {'use_enhanced_fopd': True, 'top_k_profile_records': 3,
                     'relevance_threshold': 0.15, 'sensitivity_threshold': 0.70,
                     'components': {'use_orthogonal': orthogonal, 'use_task_attention': True,
                                    'use_bottleneck': True},
                     'bottleneck': {'max_mutual_info_bits': 6.0, 'privacy_lambda': 0.5},
                     'unit_budget': {'max_units': 3, 'allowed': ['mastery', 'error_pattern', 'preference']}}}

def profile(sensitivity):
    return StudentProfile(student_id='fictional', profile_records=[
        ProfileRecord(record_id='fixture', type='mastery', knowledge='algebra', value=0.55,
                      confidence=1.0, sensitivity=sensitivity, updated_at='2026-01-01')])

question = {'request_id': 'fictional', 'student_id': 'fictional', 'question': 'algebra',
            'expected_knowledge': 'algebra', 'need_resource': False}
results = []
for sensitivity in (0.65, 0.95):
    for orthogonal in (True, False):
        cfg = config(orthogonal)
        p = LangGraphProtectionPipeline(cfg, [], watermark=None, generator=None, guard=None, monitor=NoExport())
        protected = p.run(profile(sensitivity), question, access=AccessScope('fictional'))
        assert p.watermark is None and p.last_state.get('watermark_enabled') is False
        public = protected.to_dict()
        results.append({'path': 'protected_graph', 'sensitivity': sensitivity, 'orthogonal': orthogonal,
                        'selected_count': len(public['selected_record_ids']),
                        'high_sensitive_selected': any(x.record.sensitivity > .70 for x in protected.selected),
                        'raw_record_values_in_result_schema': 'fopd_context' in public,
                        'watermark_enabled': p.last_state['watermark_enabled']})
        research = run_research_flow(ResearchOwner(cfg), 'algebra', profile(sensitivity), [], 'practice')
        selected = research['fopd_context']
        results.append({'path': 'research_graph_standin', 'sensitivity': sensitivity, 'orthogonal': orthogonal,
                        'selected_count': len(selected),
                        'high_sensitive_selected': any(x['record']['sensitivity'] > .70 for x in selected),
                        'raw_record_values_in_result_schema': any('value' in x['record'] for x in selected),
                        'watermark_enabled': False})

wrong = LangGraphProtectionPipeline(config(False), [], watermark=None, generator=None, guard=None, monitor=NoExport())
try:
    wrong.run(profile(.65), question, access=AccessScope('different-fictional-subject'))
except PermissionError:
    subject_mismatch = 'permission_error'
else:
    subject_mismatch = 'unexpected_return'
paths = ['core/access.py', 'cogniguard/workflows/pipeline.py',
         'cogniguard/workflows/education/research.py', 'protection/student_profile/src/fopd/profile_selector.py']
hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
print(json.dumps({'synthetic_only': True, 'network_blocked': True, 'audit_enabled': False,
                  'cases': results, 'protected_wrong_subject': subject_mismatch,
                  'source_sha256': hashes}, indent=2))
