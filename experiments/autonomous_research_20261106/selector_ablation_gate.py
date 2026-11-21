"""CPU-only paired probe of current selector; no pipeline, model or real profile."""
import hashlib
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from protection.common.schemas import ProfileRecord, StudentProfile, Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector

record = ProfileRecord(record_id='synthetic', type='mastery', knowledge='algebra',
                       value='example', confidence=1.0, sensitivity=0.95,
                       updated_at='2026-01-01')
profile = StudentProfile(student_id='synthetic', profile_records=[record])
task = Task(request_id='synthetic', student_id='synthetic', question='algebra example',
            knowledge='algebra', difficulty='unknown', need_resource=False)
cfg = {'fopd': {'use_enhanced_fopd': True, 'top_k_profile_records': 3,
                'relevance_threshold': 0.15, 'sensitivity_threshold': 0.70,
                'components': {'use_orthogonal': True, 'use_task_attention': True,
                               'use_bottleneck': True},
                'weights': {'rel': 0.5, 'tag': 0.25, 'confidence': 0.15,
                            'recency': 0.10, 'sens_gate': 0.20},
                'bottleneck': {'max_mutual_info_bits': 6.0, 'privacy_lambda': 0.5},
                'unit_budget': {'max_units': 3, 'allowed': ['mastery', 'error_pattern', 'preference']}}}
source = root / 'protection/student_profile/src/fopd/profile_selector.py'
out = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
       'record_sensitivity': record.sensitivity, 'threshold': 0.70, 'arms': {}}
for orthogonal in (True, False):
    c = deepcopy(cfg)
    c['fopd']['components']['use_orthogonal'] = orthogonal
    selected = ProfileSelector(c).select(profile, task)
    out['arms'][str(orthogonal).lower()] = {
        'selected_count': len(selected),
        'synthetic_high_sensitivity_selected': any(x.record.sensitivity > 0.70 for x in selected),
        'serialization_contains_record_value': any('value' in asdict(x.record) for x in selected),
    }
print(json.dumps(out, indent=2))
