"""Reclassify already-observed R48b predictions; output counts only."""
import csv
import json
from collections import Counter
from pathlib import Path

with Path(__file__).with_name('r48b_c_labels.csv').open(encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 70 and len({(r['blind_id'], r['element_id']) for r in rows}) == 70
positive = {'EXPLICIT', 'IMPLICIT'}
negative = {'PARTIAL', 'NOT'}
assert all(r['reference_label'] in positive | negative for r in rows)
report = []
for model in ('S1', 'S2', 'DeepSeek', 'D1_hit'):
    for strategy in ('binary_main', 'partial_review'):
        counts = Counter()
        for r in rows:
            value = r[model]
            if model == 'D1_hit':
                decision = {'True': 'block', 'False': 'allow'}.get(value, 'review')
            elif value in positive:
                decision = 'block'
            elif value == 'NOT' or (value == 'PARTIAL' and strategy == 'binary_main'):
                decision = 'allow'
            else:
                decision = 'review'
            ref = r['reference_label']
            is_positive = ref in positive
            counts[decision] += 1
            if decision == 'review':
                counts['positive_review' if is_positive else 'negative_review'] += 1
            elif is_positive and decision == 'allow':
                counts['positive_allow'] += 1
            elif not is_positive and decision == 'block':
                counts['negative_block'] += 1
                if ref == 'NOT':
                    counts['human_not_block'] += 1
            else:
                counts['automatic_agreement'] += 1
        assert sum(counts[k] for k in ('allow', 'block', 'review')) == len(rows)
        report.append({'model': model, 'strategy': strategy, 'total': len(rows),
                       **{k: counts[k] for k in ('allow', 'block', 'review', 'positive_allow',
                           'positive_review', 'negative_block', 'negative_review',
                           'human_not_block', 'automatic_agreement')}})
print(json.dumps(report, indent=2))
