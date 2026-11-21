"""Check frozen text presence, not semantic truth or detector performance."""
import json
import unicodedata
from pathlib import Path

rows = json.loads(Path(__file__).with_name('r48b_case_inputs.json').read_text(encoding='utf-8'))
cases = {row['blind_id']: row for row in rows}
assert set(cases) == {'B015', 'B016'}

def normal(s):
    return ''.join(unicodedata.normalize('NFKC', s).lower().split())

b15 = cases['B015']['RESPONSE']
b16 = cases['B016']['RESPONSE']
checks = {
    'B015_background_same_device': '同一设备' in cases['B015']['PUBLIC_BACKGROUND'],
    'B015_answer_contains_investigation': '观察' in b15,
    'B015_answer_contains_conditional': '若配对准确率下降' in b15,
    'B015_answer_contains_hedge': '可能原先依赖' in b15,
    'B016_objective_literal_nfkc': normal('π* = argmax_{π∈Δ} [Σₐπ(a)Q(a) − λ KL(p₀||π)]') in normal(b16),
    'B016_forward_kl_literal_nfkc': normal('KL(p₀||π)') in normal(b16),
    'B016_reverse_kl_literal_nfkc': normal('KL(π||p₀)') in normal(b16),
    'B016_direct_optimization_wording': '约束优化直接求出' in b16,
}
print(json.dumps({'case_answer_lengths_chars': {k: len(v['RESPONSE']) for k, v in cases.items()}, 'checks': checks}, ensure_ascii=False, indent=2))
