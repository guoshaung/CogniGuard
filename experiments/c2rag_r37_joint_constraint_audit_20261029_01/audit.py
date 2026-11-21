"""Independent saved-delivery recount and mathematical certificates, not a policy."""
import csv
import hashlib
import io
import itertools
import json
import tarfile
import time
from collections import Counter

from experiments.c2rag_r37_joint_constraint_audit_20261029_01.common import (
    OUT, R32, R35, closure, frozen, write,
)


def groups(n, k=3):
    return [c for size in range(1, min(n, k) + 1) for c in itertools.combinations(range(n), size)]


def csvout(name, rows):
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    write(name, buf.getvalue())


def main():
    start = time.perf_counter()
    frozen()
    write('PROTOCOL_CLARIFICATION.md', '''# 协议文字勘误（审计执行前）

冻结PROTOCOL中“CPU/模型Token/GPU/付费API/训练/新教育数据下载均不发生”的CPU一词为文字错误：本轮显然使用本地CPU做离线只读核验；未运行新的方法性能实验，模型/GPU/付费API/训练/新教育数据下载为0。原协议及其哈希保留，不变更任何数据、评分、算法、门槛或计算上限。本说明不是结果驱动的契约修改。
''')
    data = (R32/'evidence.tar.gz').read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert blob == '0bd48b1815c376bcf5e304dd442aac83e8425d40'
    with tarfile.open(R32/'evidence.tar.gz') as archive:
        def load(path):
            return json.load(archive.extractfile(path))
        assets = {a['id']: a for a in load('inputs/assets.json')}
        sequences = {s['id']: s for s in load('inputs/sequences.json')}
        independent = load('independent_results.json')
        gold = {(r['id'], r['method']): r for r in independent['records']}
        stats = Counter()
        rows = []
        for name in sorted(archive.getnames()):
            if not name.startswith('method_traces/') or not name.endswith('.json'):
                continue
            trace = load(name)
            seq = sequences[trace['id']]
            asset = assets[trace['asset']]
            views = [set() for _ in range(seq['n'])]
            utility = size = unsafe_steps = 0
            for request, step in zip(seq['requests'], trace['steps'], strict=True):
                candidate = asset['questions'][request['qid']]
                reply = step['published_text']
                assert reply in ['', candidate['answer']]
                assert bytes.fromhex(step['published_utf8_hex']).decode('utf8') == reply
                assert step['before_views'] == [sorted(v) for v in views]
                utility += int(bool(reply))
                size += len(reply.encode('utf8'))
                if reply:
                    views[request['recipient']].update(candidate['facts'])
                assert step['after_views'] == [sorted(v) for v in views]
                unsafe = any(asset['target'] in closure(set().union(*(views[i] for i in c)), asset['rules'], asset['public'])
                             for c in groups(seq['n']))
                unsafe_steps += int(unsafe)
                stats['coalition_prefix_checks'] += len(groups(seq['n']))
                stats['steps'] += 1
            scored = gold[(trace['id'], trace['method'])]
            assert utility == trace['utility'] == scored['utility']
            assert size == trace['output_bytes'] == scored['output_bytes']
            assert unsafe_steps == scored['unsafe_steps'] == 0
            assert size <= seq['budget']['output_bytes']
            rows.append({'sequence': trace['id'], 'method': trace['method'], 'utility': utility,
                         'bytes': size, 'unsafe_steps': unsafe_steps, 'source': 'R32_REUSED_SAVED_TRACE'})
        certs = independent['exact_opt_certificates']
        assert len(rows) == 510 and len(certs) == len(sequences) == 102
        for cert in certs:
            qs = [q['qid'] for q in sequences[cert['id']]['requests']]
            assert cert['utility'] == max(Counter(qs).values())
            assert cert['all_schedules_enumerated'] == 2 ** len(qs)
        totals = {m: sum(r['utility'] for r in rows if r['method'] == m) for m in sorted({r['method'] for r in rows})}
        assert totals == {'G':340, 'A1-U':136, 'A1-O':357, 'A2-O':442, 'OPT':442}
        fail = load('method_traces/kinetic-N8-S1__A1-O.json')
        request_types = [q['qid'] for q in sequences['kinetic-N8-S1']['requests']]
        remaining = Counter(request_types[1:])
        current = request_types[0]
        true_loss = max(remaining.values()) - remaining[current]
        first_full = next(t for t in fail['steps'][0]['trials'] if t['full'])
        assert true_loss == 0 and first_full['opportunity_loss'] == '3' and first_full['score'] == '-2'
        write('R32_RAW_REAUDIT.json', {'source_git_blob': blob, 'saved_traces': len(rows),
                                      'totals': totals, **dict(stats), 'majority_certificates_checked': len(certs),
                                      'old_schedules_already_enumerated_not_new_runs': sum(c['all_schedules_enumerated'] for c in certs),
                                      'A1_failure': {'id': fail['id'], 'current_qid': current,
                                                     'future_counts': dict(remaining), 'proxy_loss': 3,
                                                     'true_joint_optimum_loss': true_loss, 'actual_utility': fail['utility']},
                                      'original_failures_retained': load('failure_case_register.json'),
                                      'method_source_not_distributed_in_R32_archive': True,
                                      'no_original_worker_rerun_claimed': True})
        csvout('R32_RECOUNT.csv', rows)

    banks = json.loads((R35/'banks.json').read_text(encoding='utf8'))
    bank = next(b for b in banks if b['id'] == 'L3')
    assert bank['case']['rules'] == [[['a','b'],'TARGET'], [['b','c','d'],'TARGET']]
    # Truth assignments are the semantic reference, not the old Horn risk engine.
    atoms = bank['case']['facts']
    worlds = [set(a for a, bit in zip(atoms, bits) if bit)
              for bits in itertools.product([False, True], repeat=len(atoms))]
    worlds = [w for w in worlds if all(not set(body) <= w or head in w for body, head in bank['case']['rules'])]
    def entails(known):
        compatible = [w for w in worlds if set(known) <= w]
        assert compatible
        return all('TARGET' in w for w in compatible)
    subset_rows = []
    for bits in range(16):
        known = {a for i,a in enumerate('abcd') if bits & (1 << i)}
        unsafe = entails(known)
        assert unsafe == ('TARGET' in closure(known, bank['case']['rules']))
        subset_rows.append({'observed': sorted(known), 'unsafe': unsafe,
                            'countermodel_TARGET_false': sorted(next(w for w in worlds if known <= w and 'TARGET' not in w)) if not unsafe else None})
    write('MINIMAL_JOINT_TRUTH_TABLE.json', subset_rows)
    safe3 = [r['observed'] for r in subset_rows if not r['unsafe'] and len(r['observed']) == 3]
    assert safe3 == [['a','c','d']]
    oracles = {r['leaf']: r for r in json.loads((R35/'oracles.json').read_text(encoding='utf8')) if r['asset']=='L3'}
    opt = {}
    schedules_checked = 0
    for seq in itertools.product(range(4), repeat=4):
        best = -1
        plans = []
        for mask in range(16):
            schedules_checked += 1
            released = {bank['observations'][q] for t,q in enumerate(seq) if mask & (1 << t)}
            if not entails(released):
                u = mask.bit_count()
                if u > best:
                    best, plans = u, [mask]
                elif u == best:
                    plans.append(mask)
        key = 'L3-' + ''.join(map(str, seq))
        assert best == oracles[key]['utility']
        opt[key] = {'value': best, 'plan_masks': plans}
    replays = json.loads((R35/'replays.json').read_text(encoding='utf8'))
    allowed = ['NoGate','Counter4','G-Shared','Simple','A2','B-SAA','MenuRecourse']
    selected = [r for r in replays if r['asset']=='L3' and r['law']=='uniform' and r['method'] in allowed
                and (r['error']=='0' or r['method'] in ['NoGate','Counter4','G-Shared'])]
    recounted = []
    witnesses = []
    views_cache = {}
    for replay in selected:
        views = [set() for _ in range(4)]
        utility = size = 0
        prefix = []
        for step in replay['steps']:
            prefix.append(step)
            reply = step['reply']
            if reply:
                parsed = json.loads(reply)
                assert parsed['asset'] == 'L3'
                expected = bank['queries'][step['query_id']]['answers'][0]
                assert reply == expected['reply']
                views[step['recipient']].update(parsed['positive'])
                utility += 1
            size += len(reply.encode('utf8'))
            assert step['bytes'] == len(reply.encode('utf8'))
            known_key = tuple(tuple(sorted(v)) for v in views)
            if known_key not in views_cache:
                bad = [list(c) for c in groups(3) if entails(set().union(*(views[i] for i in c)))]
                views_cache[known_key] = min(map(len,bad)) if bad else None
            if replay['leaf']=='L3-1230' and replay['method']=='NoGate' and step['step']==2:
                assert views_cache[known_key] == 3
                witnesses.append({'source': 'R35_REUSED_SAVED_TRACE', 'leaf': replay['leaf'],
                                  'prefix_steps': prefix.copy(), 'actual_views': [sorted(v) for v in views],
                                  'k_min': 3, 'proper_pairs_no_entailment': True,
                                  'same_candidate_state_PairExact_would_miss': True,
                                  'fourth_step_warning': 'same r0 later receives a; prefix is not a final three-person-only claim'})
        kmin = views_cache[tuple(tuple(sorted(v)) for v in views)]
        assert utility == replay['correct'] and size == replay['bytes'] and size <= bank['budget_bytes']
        if replay['method'] not in ['NoGate','Counter4']:
            assert kmin is None
        recounted.append({'leaf': replay['leaf'], 'method': replay['method'], 'correct':utility,
                          'refusals':4-utility, 'bytes':size, 'full_recovery':int(kmin is not None),
                          'k_min':kmin, 'offline':opt[replay['leaf']]['value'], 'source':'R35_REUSED_SAVED_TRACE'})
    assert len(selected) == 7*256
    sums = []
    for method in allowed:
        rs = [r for r in recounted if r['method']==method]
        assert len(rs)==256
        sums.append({'method':method,'requests':1024,'streams':256,'independent_assets':1,
                     'correct':sum(r['correct'] for r in rs), 'refusals':sum(r['refusals'] for r in rs),
                     'bytes':sum(r['bytes'] for r in rs),'full_recovery_streams':sum(r['full_recovery'] for r in rs),
                     'offline_correct':sum(r['offline'] for r in rs),'evidence':'R35_RECOUNT_NOT_NEW_EXPERIMENT'})
    csvout('L3_REUSED_PER_STREAM.csv', recounted)
    csvout('L3_REUSED_METHOD_SUMMARY.csv', sums)
    write('THREE_AGENT_WITNESS.json', witnesses)
    sample = [r for r in selected if r['leaf'] == 'L3-1023']
    write('MINIMAL_JOINT_SAVED_PLANS.json', {'contract':bank,'leaf':'L3-1023',
                                           'plans':sample, 'independent_opt':opt['L3-1023'],
                                           'manual_optimum':3,'unique_safe_three_unit_set':['a','c','d'],
                                           'why_no_new_sample':'already contained in R35 complete test_leaves; retrospective mathematical illustration'})
    elapsed = time.perf_counter()-start
    assert elapsed <= 600
    frozen()
    write('VERIFICATION.json', {'status':'PASS','retrospective':True,'elapsed_seconds':elapsed,
                              'R32_saved_traces':510,'R32_saved_steps':stats['steps'],
                              'L3_observation_subsets':16,'L3_complete_flows':256,
                              'L3_independent_plan_checks':schedules_checked,'L3_saved_replays_recounted':len(selected),
                              'new_assets':0,'new_method_runs':0,'new_models':0,'unknown':0,
                              'independent_computation_not_independent_human_review':True})
    print(json.dumps({'R32':totals,'L3':sums,'verify_seconds':elapsed}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        write('FAILURE.json', {'error_type':type(exc).__name__,'message':str(exc),'preserved':True})
        raise
