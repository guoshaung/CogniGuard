"""Bounded R49 replay. Immutable R45 inputs; integer rewards; resumable chunks."""
import argparse
import ast
import base64
import csv
import gzip
import hashlib
import io
import itertools
import json
import random
import tarfile
import time
from bisect import bisect
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
METHODS = ('M1', 'M2-no-prediction', 'M2-trained', 'M2-oracle')
QUALITIES = ('none', 'none', 'trained', 'ideal')
NAMES = ('full', 'alternative', 'degraded', 'refuse')
ARCHIVE_SHA = '3ae21311572ba6e42771d700a3c24c6baa716868323edee270e5723d835b8acc'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, obj):
    path = ROOT / path
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    tmp.replace(path)


def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf8'))


def write_csv(name, rows):
    if not rows:
        return
    with (ROOT / name).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def reference_namespace():
    # Load only pure, inspected original functions, not its prepare/execute or imports.
    tree = ast.parse((ROOT / 'inputs/r45_run.py.txt').read_text(encoding='utf8'))
    names = {'tau', 'partition_unsafe', 'child', 'unsafe', 'initial', 'actions',
             'options', 'greedy', 'probs', 'seed'}
    selected = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in names]
    ns = {'lru_cache': lru_cache, 'hashlib': hashlib, 'json': json}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<frozen_R45_pure_functions>', 'exec'), ns)
    return ns


def assert_freeze():
    for name, expected in load('freeze.json')['sha256'].items():
        assert sha((ROOT / name).read_bytes()) == expected, f'Frozen mismatch: {name}'


def configs():
    return [dict(id=f'a{a:02d}_d{d:02d}_r{rep:02d}', alt=a, degraded=d, repeat=rep)
            for a in (0, 20, 40, 64, 80) for d in (0, 8, 20) if a >= d
            for rep in (0, 20, 40, 80)]


def prepare():
    assert not (ROOT / 'freeze.json').exists(), 'Already frozen'
    blob = base64.b64decode((PROJECT / 'var/tmp/r45_evidence_audit_20261107.b64').read_text())
    assert sha(blob) == ARCHIVE_SHA
    (ROOT / 'inputs').mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
        get = lambda n: tar.extractfile(n).read()
        old_freeze = json.loads(get('freeze.json'))
        for n, h in old_freeze['sha256'].items():
            assert sha(get(n)) == h, n
        manifest = json.loads(get('MANIFEST.json'))
        for n in ('raw_traces.jsonl', 'per_stream.csv', 'run.py'):
            assert sha(get(n)) == manifest['sha256'][n], n
        names = ('frozen_streams.json', 'predictors.json', 'raw_traces.jsonl', 'config.json',
                 'RESULT.md', 'PROTOCOL.md', 'per_stream.csv', 'freeze.json', 'MANIFEST.json')
        for n in names:
            (ROOT / 'inputs' / n).write_bytes(get(n))
        (ROOT / 'inputs/r45_run.py.txt').write_bytes(get('run.py'))
    streams = [s for s in load('inputs/frozen_streams.json') if s['r'] > s['k']]
    assert len(streams) == 384 and sum(map(lambda s: len(s['events']), streams)) == 9216
    dump('streams.json', streams)
    dump('configurations.json', configs())
    dump('SOURCE_VERIFICATION.json', dict(commit='fd93c708527009d76eae162338f16dae38d512f1',
        archive_sha256=ARCHIVE_SHA, frozen_input_checks=len(old_freeze['sha256']),
        main_streams=384, requests_per_method=9216, excluded_degenerate=32,
        access='local cached byte-identical archive, no regeneration',
        source_snapshot_sha256=sha((ROOT / 'inputs/r45_run.py.txt').read_bytes())))
    files = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    dump('freeze.json', dict(frozen_at=time.time(), before_R49_results=True,
        sha256={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files}))
    print('FROZEN', len(configs()), 'configurations; 384 original streams', flush=True)


@lru_cache(maxsize=200000)
def bad_signature(sig, k, r):
    """Exact <=k set cover over present recipient masks; identities not reassigned."""
    full = (1 << r) - 1
    masks = [m for m in range(1, full + 1) if sig & (1 << m)]
    union = 0
    for m in masks:
        union |= m
    if union != full:
        return False
    if full in masks:
        return True
    for a, b in itertools.combinations(masks, 2):
        if a | b == full:
            return k >= 2
    if k >= 3:
        return any(a | b | c == full for a, b, c in itertools.combinations(masks, 3))
    return False


def init(s):
    state = [(1 << i) if s['init'] == 'spread' and i < s['r'] else 0 for i in range(s['n'])]
    counts = [0] * (1 << s['r'])
    for m in state:
        counts[m] += 1
    sig = sum(1 << m for m, c in enumerate(counts) if c and m)
    return state, counts, sig


def next_sig(sig, counts, old, new):
    if old == new:
        return sig
    if old and counts[old] == 1:
        sig &= ~(1 << old)
    return sig | (1 << new)


def candidates(state, counts, sig, who, q, k, r, cfg):
    old = state[who]
    out = []
    for action, bits, weight in ((0, 1 << q, 80), (1, 1 << ((q + 1) % r), cfg['alt']),
                                  (2, 0, cfg['degraded']), (3, 0, 0)):
        new = old | bits
        ns = next_sig(sig, counts, old, new)
        if not bad_signature(ns, k, r):
            reward = weight * cfg['repeat'] // 80 if bits and old == new else weight
            out.append((action, bits, reward, new, ns))
    return out


def commit(state, counts, who, new):
    old = state[who]
    if old != new:
        counts[old] -= 1
        counts[new] += 1
        state[who] = new


def inverse_cdf(probs):
    total = sum(probs)
    c = []
    sofar = 0.
    for p in probs:
        sofar += p / total
        c.append(sofar)
    c[-1] = 1.
    return c


def frozen_forecasts(streams):
    ref = reference_namespace()
    predictors = load('inputs/predictors.json')
    forecasts = {}
    quality_stats = []
    for s in streams:
        model = predictors[f"{s['n']}-{s['k']}-{s['r']}-{s['family']}"]['model']
        n, r = s['n'], s['r']
        for quality in ('none', 'trained', 'ideal'):
            if quality == 'trained':
                rp = model['recipients']
                qp = model['markov']
            elif quality == 'none':
                rp, base = ref['probs'](n, r, 'uniform')
                qp = [base] * r
            else:
                rp = ref['probs'](n, r, s['family'])[0]
                qp = [ref['probs'](n, r, s['family'], last)[1] for last in range(r)]
            rcdf, qcdf = inverse_cdf(rp), [inverse_cdf(p) for p in qp]
            nll = 0.
            brier = 0.
            import math
            for t, (who, q) in enumerate(s['events']):
                rng = random.Random(ref['seed'](s['id'], t, 'R49-CRN'))
                samples = []
                for _ in range(8):
                    last = q
                    sample = []
                    for __ in range(min(6, 23 - t)):
                        rec = bisect(rcdf, rng.random())
                        qt = bisect(qcdf[last], rng.random())
                        sample.append((rec, qt))
                        last = qt
                    samples.append(sample)
                forecasts[s['id'], t, quality] = samples
                if t:
                    last = s['events'][t - 1][1]
                    nll -= math.log(rp[who] * qp[last][q])
                    brier += sum((p - (i == who)) ** 2 for i, p in enumerate(rp))
                    brier += sum((p - (i == q)) ** 2 for i, p in enumerate(qp[last]))
            quality_stats.append(dict(stream=s['id'], quality=quality, family=s['family'],
                                      transitions=23, mean_joint_nll=nll / 23,
                                      mean_marginal_brier_sum=brier / 23))
    return forecasts, quality_stats


def select(state, counts, sig, who, q, s, cfg, method, samples):
    opts = candidates(state, counts, sig, who, q, s['k'], s['r'], cfg)
    if method == 'M1':
        return max(opts, key=lambda x: x[2]), 0
    values = {}
    steps = 0
    for action in opts:
        _, _, reward, new, ns = action
        if new in values:
            continue
        total = 0
        for future in samples:
            st, ct = state.copy(), counts.copy()
            commit(st, ct, who, new)
            ss = ns
            for rec, qt in future:
                nxt = max(candidates(st, ct, ss, rec, qt, s['k'], s['r'], cfg), key=lambda x: x[2])
                total += nxt[2]
                commit(st, ct, rec, nxt[3])
                ss = nxt[4]
                steps += 1
        values[new] = total
    return max(opts, key=lambda a: (8 * a[2] + values[a[3]], a[2])), steps


def run_stream(s, cfg, method, forecasts, ref):
    state, counts, sig = init(s)
    trace = []
    simulated = 0
    quality = QUALITIES[METHODS.index(method)]
    for t, (who, q) in enumerate(s['events']):
        before = state[who]
        samples = None if method == 'M1' else forecasts[s['id'], t, quality]
        begin = time.perf_counter_ns()
        chosen, simulated_steps = select(state, counts, sig, who, q, s, cfg, method, samples)
        latency = time.perf_counter_ns() - begin
        action, bits, u, new, ns = chosen
        # Independently check every actual protected candidate, not only accepted actions.
        blocked = 0
        for b in (1 << q, 1 << ((q + 1) % s['r'])):
            test = list(state)
            test[who] |= b
            optimized = bad_signature(next_sig(sig, counts, before, before | b), s['k'], s['r'])
            independent = ref['partition_unsafe'](test, s['k'], s['r'])
            assert optimized == independent
            blocked += independent
        commit(state, counts, who, new)
        sig = ns
        bad = ref['partition_unsafe'](state, s['k'], s['r'])
        assert bad == ref['unsafe'](tuple(state), s['k'], s['r'])
        simulated += simulated_steps
        trace.append(dict(t=t, recipient=who, query=q, action=NAMES[action], bits=bits,
                          u80=u, new_atoms=(new ^ before).bit_count(),
                          repeat_release=bool(bits and before == new), state_before=before,
                          state_after=new, signature_after=sig, actual_unsafe=bad,
                          protected_candidates_blocked=blocked, decision_ns=latency,
                          request_match=bool(bits == 1 << q), simulated_steps=simulated_steps))
    return dict(stream=s['id'], config=cfg['id'], method=method, steps=trace,
                simulated_steps=simulated)


def fixed_rescore():
    streams = {s['id']: s for s in load('streams.json')}
    traces = [json.loads(line) for line in (ROOT / 'inputs/raw_traces.jsonl').read_text().splitlines()]
    selected = [t for t in traces if t['summary']['stream'] in streams and
                (t['summary']['method'], t['summary']['quality']) in
                [('M1', 'none'), ('M2', 'none'), ('M2', 'trained'), ('M2', 'ideal')]]
    totals, mismatches, rows = Counter(), [], []
    for tr in selected:
        sm = tr['summary']
        s = streams[sm['stream']]
        method = 'M1' if sm['method'] == 'M1' else {'none': 'M2-no-prediction',
                  'trained': 'M2-trained', 'ideal': 'M2-oracle'}[sm['quality']]
        state, _, _ = init(s)
        by_type, repeats, new = Counter(), Counter(), Counter()
        actual = Decimal(0)
        for step, request in zip(tr['steps'], s['events']):
            assert [step['recipient'], step['query']] == request
            who, bits, action = step['recipient'], step['bits'], step['action']
            actual += Decimal(str(step['u']))
            by_type[action] += 1
            repeats[action] += bool(bits and (state[who] | bits) == state[who])
            new[action] += (bits & ~state[who]).bit_count()
            state[who] |= bits
        assert len(tr['steps']) == 24
        if actual != Decimal(str(sm['utility'])):
            mismatches.append(s['id'])
        totals[method] += actual
        for cfg in configs():
            weighted = 0
            for name, w in [('full', 80), ('alternative', cfg['alt']), ('degraded', cfg['degraded'])]:
                weighted += w * (by_type[name] - repeats[name])
                weighted += w * cfg['repeat'] * repeats[name] // 80
            rows.append(dict(config=cfg['id'], stream=s['id'], method=method,
                utility=weighted / 80, new_atoms=sum(new.values()),
                new_full=new['full'], new_alternative=new['alternative'],
                repeat_full=repeats['full'], repeat_alternative=repeats['alternative'],
                full=by_type['full'], alternative=by_type['alternative'],
                degraded=by_type['degraded'], refuse=by_type['refuse'],
                alternative_exact_request_match=0, alternative_semantic_relevance='UNSUPPORTED'))
    assert not mismatches
    assert totals['M1'] == Decimal('8428.55') and totals['M2-trained'] == Decimal('8448.45')
    write_csv('FIXED_TRACE_RESCORING.csv', rows)
    dump('HISTORICAL_RECONCILIATION.json', dict(totals={k: str(v) for k, v in totals.items()},
        mismatches=mismatches, main_streams=384, requests=9216,
        trace_method_pairs=len(selected)))


def verify():
    assert_freeze()
    ref = reference_namespace()
    rng = random.Random(4902)
    cases = [(list(s), k, 3) for s in itertools.product(range(8), repeat=3) for k in (2, 3)]
    cases += [([rng.randrange(1 << r) for _ in range(n)], k, r)
              for r in (3, 4, 5) for n in (4, 8, 30, 60) for k in (2, 3) for _ in range(40)]
    checks = 0
    for state, k, r in cases:
        sig = sum(1 << m for m in set(state) if m)
        assert bad_signature(sig, k, r) == ref['unsafe'](tuple(state), k, r)
        assert bad_signature(sig, k, r) == ref['partition_unsafe'](state, k, r)
        checks += 1
    cfg = {'alt': 64, 'degraded': 20, 'repeat': 80}
    old = {t['summary']['stream']: t for t in
           map(json.loads, (ROOT / 'inputs/raw_traces.jsonl').read_text().splitlines())
           if t['summary']['method'] == 'M1' and not t['summary']['degenerate']}
    steps = 0
    for s in load('streams.json'):
        state, counts, sig = init(s)
        for t, (who, q) in enumerate(s['events']):
            a = max(candidates(state, counts, sig, who, q, s['k'], s['r'], cfg), key=lambda x: x[2])
            b = old[s['id']]['steps'][t]
            assert (NAMES[a[0]], a[1], a[2] / 80) == (b['action'], b['bits'], b['u'])
            commit(state, counts, who, a[3])
            sig = a[4]
            steps += 1
    # Explicit marginal-reward and context tests; both initial and delivered knowledge count.
    cfg0 = {'alt': 80, 'degraded': 0, 'repeat': 0}
    s = dict(n=8, r=3, k=2, init='spread')
    st, ct, sig = init(s)
    assert candidates(st, ct, sig, 0, 0, 2, 3, cfg0)[0][2] == 0
    assert next(a for a in candidates(st, ct, sig, 6, 0, 2, 3, cfg0) if a[0] == 0)[2] == 80
    fixed_rescore()
    dump('VERIFICATION.json', dict(status='PASS', independent_state_checks=checks,
        R45_M1_step_checks=steps, utility_unit=80, configurations=len(configs()),
        no_method_results_used_to_tune=True))
    print('VERIFIED', checks, 'states;', steps, 'legacy M1 steps; historical scores reconciled', flush=True)


def execute():
    assert_freeze()
    assert load('VERIFICATION.json')['status'] == 'PASS'
    streams = load('streams.json')
    forecasts, quality_stats = frozen_forecasts(streams)
    write_csv('PREDICTION_QUALITY.csv', quality_stats)
    (ROOT / 'chunks').mkdir(exist_ok=True)
    ref = reference_namespace()
    start = time.process_time()
    prior = sum(json.loads(gzip.decompress(p.read_bytes()))['cpu_seconds'] for p in (ROOT / 'chunks').glob('*.json.gz'))
    for cfg in configs():
        for chunk in range(48):
            path = ROOT / 'chunks' / f"{cfg['id']}_{chunk:02d}.json.gz"
            if path.exists():
                continue
            if prior + time.process_time() - start >= 7200:
                dump('EXECUTION_STATE.json', dict(status='PARTIAL_CPU_BUDGET', cpu_seconds=prior + time.process_time() - start))
                return
            begin = time.process_time()
            rows = []
            for s in streams[chunk * 8:(chunk + 1) * 8]:
                for method in METHODS:
                    rows.append(run_stream(s, cfg, method, forecasts, ref))
            obj = dict(config=cfg, chunk=chunk, records=rows, cpu_seconds=time.process_time() - begin)
            raw = gzip.compress(json.dumps(obj, separators=(',', ':')).encode(), mtime=0)
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(raw)
            tmp.replace(path)
            dump('EXECUTION_STATE.json', dict(status='RUNNING', latest=path.name,
                completed_chunks=len(list((ROOT / 'chunks').glob('*.json.gz'))), total_chunks=2496,
                cpu_seconds=prior + time.process_time() - start,
                next_action='Run execute again; existing atomic chunks are skipped'))
            ref['tau'].cache_clear()
        print(cfg['id'], 'COMPLETE; CPU', round(prior + time.process_time() - start, 2), flush=True)
    dump('EXECUTION_STATE.json', dict(status='COMPLETE', chunks=2496,
        method_stream_runs=52 * 384 * 4, requests=52 * 384 * 4 * 24,
        cpu_seconds=prior + time.process_time() - start, APIs=0, model_calls=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'verify', 'execute'))
    args = parser.parse_args()
    globals()[args.command]()
