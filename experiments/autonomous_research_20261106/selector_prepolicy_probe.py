"""Compare real profile prefilter vs direct selector on fictional records."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from core.access import ProfileReadPolicy
from protection.common.schemas import ProfileRecord, StudentProfile, Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector

cfg = {'access': {'max_profile_sensitivity': 0.70},
       'fopd': {'use_enhanced_fopd': True, 'top_k_profile_records': 3,
                'relevance_threshold': 0.15, 'sensitivity_threshold': 0.70,
                'components': {'use_orthogonal': False, 'use_task_attention': True,
                               'use_bottleneck': True},
                'bottleneck': {'max_mutual_info_bits': 6.0, 'privacy_lambda': 0.5},
                'unit_budget': {'max_units': 3, 'allowed': ['mastery', 'error_pattern', 'preference']}}}
task = Task(request_id='synthetic', student_id='synthetic', question='algebra',
            knowledge='algebra', difficulty='unknown', need_resource=False)
out = {'sensitivity_limit': 0.70, 'orthogonal': False, 'cases': []}
for sensitivity in (0.65, 0.95):
    record = ProfileRecord(record_id='synthetic', type='mastery', knowledge='algebra',
                           value=0.55, confidence=1.0, sensitivity=sensitivity,
                           updated_at='2026-01-01')
    profile = StudentProfile(student_id='synthetic', profile_records=[record])
    for prefilter in (False, True):
        source = ProfileReadPolicy(cfg).filter(profile) if prefilter else profile
        selected = ProfileSelector(cfg).select(source, task)
        out['cases'].append({'sensitivity': sensitivity, 'prefilter': prefilter,
                             'input_records': len(source.profile_records),
                             'selected_records': len(selected)})
out['policy_sha256'] = hashlib.sha256((root / 'core/access.py').read_bytes()).hexdigest()
out['selector_sha256'] = hashlib.sha256((root / 'protection/student_profile/src/fopd/profile_selector.py').read_bytes()).hexdigest()
print(json.dumps(out, indent=2))
