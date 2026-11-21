"""AST-load only three historical functions and compare a separate oracle."""
import ast
import functools
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path

path = Path(__file__).with_name('r45_source_snapshot.py.txt')
raw = path.read_bytes()
tree = ast.parse(raw.decode('utf-8-sig'))
selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name in {'tau', 'unsafe', 'partition_unsafe'}]
assert [n.name for n in selected] == ['tau', 'unsafe', 'partition_unsafe']
namespace = {'lru_cache': functools.lru_cache}
exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)

def brute(state, k, r):
    full = (1 << r) - 1
    for count in range(min(k, len(state)) + 1):
        for coalition in itertools.combinations(state, count):
            union = 0
            for mask in coalition:
                union |= mask
            if union == full:
                return True
    return False

counts = {'k_le_r': Counter(), 'k_gt_r': Counter(), 'k_gt_r_and_le_n': Counter()}
first = None
for r in range(1, 5):
    for n in range(1, 4):
        for state in itertools.product(range(1 << r), repeat=n):
            for k in range(1, 6):
                expected = brute(state, k, r)
                old = namespace['unsafe'](state, k, r)
                partition = namespace['partition_unsafe'](state, k, r)
                assert partition == expected
                names = ['k_le_r' if k <= r else 'k_gt_r']
                if r < k <= n:
                    names.append('k_gt_r_and_le_n')
                for name in names:
                    c = counts[name]
                    c['cases'] += 1
                    c['mismatch'] += old != expected
                    c['false_unsafe'] += old and not expected
                    c['false_safe'] += not old and expected
                if r < k <= n and old != expected and first is None:
                    first = {'n': n, 'r': r, 'k': k, 'recipient_bitmasks': list(state),
                             'historical_unsafe': old, 'brute_unsafe': expected,
                             'historical_tau': namespace['tau'](state, r)}
print(json.dumps({'source_sha256': hashlib.sha256(raw).hexdigest(),
                  'ranges': {'n': [1, 2, 3], 'r': [1, 2, 3, 4], 'k': [1, 2, 3, 4, 5]},
                  'counts': {k: dict(v) for k, v in counts.items()}, 'first_realizable_witness': first}, indent=2))
