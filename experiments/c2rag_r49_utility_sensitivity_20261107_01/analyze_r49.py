"""Read-only aggregation of frozen R49 outputs. No policy execution or tuning."""
import csv
import gzip
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import run_r49 as run

ROOT = Path(__file__).resolve().parent


def text(name, content):
    (ROOT / name).write_text(content.rstrip() + '\n', encoding='utf8')


def fmt(x):
    return f'{x:.4f}'.rstrip('0').rstrip('.')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def main():
    run.assert_freeze()
    streams = run.load('streams.json')
    configs = run.load('configurations.json')
    stream_by_id = {s['id']: s for s in streams}
    cfg_by_id = {c['id']: c for c in configs}
    stream_index = {s['id']: i for i, s in enumerate(streams)}
    assert len(list((ROOT / 'chunks').glob('*.json.gz'))) == 2496, 'Incomplete; no final conclusions'
    rows, losses, divergences = [], [], []
    validations = Counter()
    cpu = 0.
    example_traces = {}
    ref = run.reference_namespace()
    run.write_csv('FORECAST_SEEDS.csv', [dict(stream=s['id'], t=t,
        seed=ref['seed'](s['id'], t, 'R49-CRN'), samples=8, horizon=min(6, 23 - t),
        shared_across='all_configs_all_M2_qualities_all_current_actions')
        for s in streams for t in range(24)])
    for path in sorted((ROOT / 'chunks').glob('*.json.gz')):
        chunk = json.loads(gzip.decompress(path.read_bytes()))
        cpu += chunk['cpu_seconds']
        grouped = defaultdict(dict)
        for tr in chunk['records']:
            s, cfg = stream_by_id[tr['stream']], cfg_by_id[tr['config']]
            assert cfg == chunk['config']
            state, _, _ = run.init(s)
            counts = Counter()
            new_by_type, repeat_by_type = Counter(), Counter()
            latency, utility, simulation, blocked = [], 0, 0, 0
            assert len(tr['steps']) == 24
            for step, event in zip(tr['steps'], s['events']):
                who, q = event
                action, bits = step['action'], step['bits']
                assert [step['recipient'], step['query']] == event
                assert bits == {'full': 1 << q, 'alternative': 1 << ((q + 1) % s['r']),
                                'degraded': 0, 'refuse': 0}[action]
                before = state[who]
                assert before == step['state_before']
                new = (bits & ~before).bit_count()
                repeat = bool(bits and not new)
                w = {'full': 80, 'alternative': cfg['alt'], 'degraded': cfg['degraded'], 'refuse': 0}[action]
                expected = w * cfg['repeat'] // 80 if repeat else w
                assert step['u80'] == expected and new == step['new_atoms']
                assert repeat == step['repeat_release']
                state[who] |= bits
                assert state[who] == step['state_after']
                assert step['signature_after'] == sum(1 << m for m in set(state) if m)
                assert not step['actual_unsafe']
                validations['request_action_state_reward_safety_record_checks'] += 1
                utility += expected
                counts[action] += 1
                new_by_type[action] += new
                repeat_by_type[action] += repeat
                latency.append(step['decision_ns'] / 1e6)
                blocked += step['protected_candidates_blocked']
                simulation += step['simulated_steps']
            req_rep = (24 - len(set(map(tuple, s['events'])))) / 24
            rep_group = '<=0.25' if req_rep <= .25 else '(0.25,0.5]' if req_rep <= .5 else '>0.5'
            row = dict(config=cfg['id'], alternative=cfg['alt'] / 80,
                degraded_weight=cfg['degraded'] / 80, repeat_coefficient=cfg['repeat'] / 80,
                stream=s['id'], method=tr['method'], N=s['n'], k=s['k'], r=s['r'],
                r_minus_k=s['r'] - s['k'], family=s['family'], init=s['init'], seed=s['seed'],
                request_repeat_rate=req_rep, request_repeat_group=rep_group,
                utility=utility / 80, new_atoms=sum(new_by_type.values()),
                new_full=new_by_type['full'], new_alternative=new_by_type['alternative'],
                repeat_full=repeat_by_type['full'], repeat_alternative=repeat_by_type['alternative'],
                full=counts['full'], alternative_count=counts['alternative'],
                degraded=counts['degraded'], refuse=counts['refuse'],
                alternative_exact_request_match=0, alternative_semantic_relevance='UNSUPPORTED',
                safety_violations=0, protected_candidates_blocked=blocked,
                endogenous_conflict_density=blocked / 48,
                decision_ms=sum(latency), mean_decision_ms=float(np.mean(latency)),
                p95_decision_ms=float(np.quantile(latency, .95)), simulated_steps=simulation)
            rows.append(row)
            grouped[s['id']][tr['method']] = (row, tr)
        for sid, methods in grouped.items():
            base, base_trace = methods['M1']
            for method in run.METHODS[1:]:
                row, tr = methods[method]
                delta = round(row['utility'] - base['utility'], 8)
                for b, a in zip(base_trace['steps'], tr['steps']):
                    if b['action'] != a['action']:
                        div = dict(config=row['config'], stream=sid, method=method,
                                   first_difference_t=a['t'], utility_delta=delta,
                                   M1=b, M2=a)
                        divergences.append(div)
                        break
                if delta < -1e-8:
                    losses.append(dict(config=row['config'], stream=sid, method=method,
                        M1_utility=base['utility'], M2_utility=row['utility'], delta=delta,
                        new_atoms_delta=row['new_atoms'] - base['new_atoms'], family=row['family']))
                if row['config'] in ('a64_d20_r80', 'a64_d20_r00', 'a80_d00_r00'):
                    example_traces[row['config'], sid, method] = (base_trace, tr)
    assert len(rows) == 52 * 384 * 4
    run.write_csv('REDECISION_RESULTS.csv', rows)
    run.write_csv('FAILURE_CASES.csv', losses)
    with (ROOT / 'DECISION_DIVERGENCES.jsonl').open('w', encoding='utf8') as f:
        for row in divergences:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    run.dump('OUTPUT_VERIFICATION.json', dict(status='PASS', **validations, rows=len(rows),
             chunks=2496, independent_partition_checks_per_actual_step=3,
             original_set_cover_checks_per_actual_step=1,
             execution_cpu_seconds_in_chunks=cpu, frozen_inputs_unchanged=True))

    strata = defaultdict(list)
    for i, s in enumerate(streams):
        strata[s['n'], s['k'], s['r'], s['family'], s['init']].append(i)
    assert len(strata) == 48 and all(len(g) == 8 for g in strata.values())
    rng = np.random.default_rng(4902026)
    indices = np.concatenate([np.array(g)[rng.integers(0, 8, (5000, 8))]
                              for g in strata.values()], axis=1)
    boot_counts = np.zeros((5000, 384), dtype=np.int16)
    for t in range(384):
        np.add.at(boot_counts, (np.arange(5000), indices[:, t]), 1)
    run.dump('BOOTSTRAP_MANIFEST.json', dict(seed=4902026, replicates=5000, n=384,
        strata=48, per_stratum=8, index_sha256=run.sha(indices.astype('<i8').tobytes()),
        CI='paired stratified percentile; descriptive, no multiplicity adjustment'))
    fixed_rows = list(csv.DictReader((ROOT / 'FIXED_TRACE_RESCORING.csv').open(encoding='utf-8-sig')))
    fixed = [{**x, 'utility': float(x['utility']), 'new_atoms': int(x['new_atoms'])} for x in fixed_rows]
    summary, paired, subgroups = [], [], []
    for experiment, records in [('A_fixed', fixed), ('B_redecision', rows)]:
        by = defaultdict(dict)
        for row in records:
            by[row['config'], row['method']][row['stream']] = row
        for cfg in configs:
            for method in run.METHODS:
                rec = by[cfg['id'], method]
                assert len(rec) == 384
                summary.append(dict(experiment=experiment, config=cfg['id'], method=method,
                    utility=round(sum(r['utility'] for r in rec.values()), 8),
                    new_atoms=sum(r['new_atoms'] for r in rec.values()),
                    alternative=cfg['alt'] / 80, degraded=cfg['degraded'] / 80,
                    repeat=cfg['repeat'] / 80,
                    safety_violations=sum(int(r.get('safety_violations', 0)) for r in rec.values()),
                    protected_candidates_blocked=sum(r.get('protected_candidates_blocked', 0) for r in rec.values()),
                    decision_ms=sum(r.get('decision_ms', 0) for r in rec.values())))
            base = by[cfg['id'], 'M1']
            matrix = []
            for method in run.METHODS[1:]:
                rec = by[cfg['id'], method]
                matrix.append(np.array([rec[s['id']]['utility'] - base[s['id']]['utility'] for s in streams]))
            draws = boot_counts @ np.array(matrix).T / 384
            for j, method in enumerate(run.METHODS[1:]):
                delta = matrix[j]
                rec = by[cfg['id'], method]
                low, high = np.quantile(draws[:, j], [.025, .975])
                row = dict(experiment=experiment, config=cfg['id'], method=method, n=384,
                    delta_total=round(float(delta.sum()), 8), delta_mean=float(delta.mean()),
                    M1_total=round(sum(x['utility'] for x in base.values()), 8),
                    method_total=round(sum(x['utility'] for x in rec.values()), 8),
                    wins=int(np.sum(delta > 1e-8)), ties=int(np.sum(abs(delta) <= 1e-8)),
                    losses=int(np.sum(delta < -1e-8)), CI_mean_low=float(low), CI_mean_high=float(high),
                    CI_total_low=float(low * 384), CI_total_high=float(high * 384),
                    new_atoms_delta=sum(rec[s['id']]['new_atoms'] - base[s['id']]['new_atoms'] for s in streams))
                paired.append(row)
                if experiment == 'B_redecision':
                    for dimension in ('family', 'N', 'k', 'r', 'r_minus_k', 'init', 'request_repeat_group'):
                        groups = defaultdict(list)
                        for i, s in enumerate(streams):
                            value = rec[s['id']][dimension]
                            groups[str(value)].append(i)
                        for value, positions in groups.items():
                            d = delta[positions]
                            subgroups.append(dict(config=cfg['id'], method=method,
                                dimension=dimension, value=value, n=len(positions),
                                delta_total=round(float(d.sum()), 8), delta_mean=float(d.mean()),
                                wins=int(np.sum(d > 1e-8)), ties=int(np.sum(abs(d) <= 1e-8)),
                                losses=int(np.sum(d < -1e-8)),
                                new_atoms_delta=sum(rec[streams[i]['id']]['new_atoms'] -
                                                    base[streams[i]['id']]['new_atoms'] for i in positions)))
    run.write_csv('CONFIGURATION_SUMMARY.csv', summary)
    run.write_csv('PAIRED_STATISTICS.csv', paired)
    run.write_csv('SUBGROUP_RESULTS.csv', subgroups)
    by_actual = {(r['config'], r['stream'], r['method']): r for r in rows}
    conflict_rows = []
    for cfg in configs:
        for s in streams:
            b = by_actual[cfg['id'], s['id'], 'M1']
            for method in run.METHODS[1:]:
                r = by_actual[cfg['id'], s['id'], method]
                conflict_rows.append(dict(config=cfg['id'], stream=s['id'], method=method,
                    N=s['n'], k=s['k'], r=s['r'], r_minus_k=s['r'] - s['k'],
                    M1_endogenous_conflict_density=b['endogenous_conflict_density'],
                    method_endogenous_conflict_density=r['endogenous_conflict_density'],
                    utility_delta=round(r['utility'] - b['utility'], 8)))
    run.write_csv('CONFLICT_DIAGNOSTICS.csv', conflict_rows)
    # Quality and predictor effect use the same redecision data, no reward-dependent training.
    quality = list(csv.DictReader((ROOT / 'PREDICTION_QUALITY.csv').open(encoding='utf-8-sig')))
    qrows = []
    for family in ('uniform', 'burst'):
        for q in ('none', 'trained', 'ideal'):
            subset = [x for x in quality if x['family'] == family and x['quality'] == q]
            qrows.append(dict(family=family, quality=q, n=len(subset),
                mean_joint_nll=sum(float(x['mean_joint_nll']) for x in subset) / len(subset),
                mean_brier_sum=sum(float(x['mean_marginal_brier_sum']) for x in subset) / len(subset)))
    run.write_csv('PREDICTION_QUALITY_SUMMARY.csv', qrows)
    ref_by = {(r['experiment'], r['config'], r['method']): r for r in paired}
    su = {(r['experiment'], r['config'], r['method']): r for r in summary}
    btrained = [r for r in paired if r['experiment'] == 'B_redecision' and r['method'] == 'M2-trained']
    selected = [('原权重、重复满额', 'a64_d20_r80'), ('原权重、重复零分', 'a64_d20_r00'),
                ('纯新增覆盖', 'a80_d00_r00')]
    highlighted = []
    for label, cid in selected:
        r = ref_by['B_redecision', cid, 'M2-trained']
        a = ref_by['A_fixed', cid, 'M2-trained']
        highlighted.append(dict(label=label, config=cid, **{k: v for k, v in r.items() if k not in ('config',)}))
    stable = all(r['delta_total'] >= -1e-8 for r in btrained)
    stability_checks = []
    for cid in ('a64_d20_r80', 'a80_d00_r00'):
        r = ref_by['B_redecision', cid, 'M2-trained']
        families = [x for x in subgroups if x['config'] == cid and x['method'] == 'M2-trained' and x['dimension'] == 'family']
        stability_checks.append(r['CI_mean_low'] > 0 and all(x['delta_total'] > 0 for x in families))
    stable &= all(stability_checks)
    meaningful = all(ref_by['B_redecision', cid, 'M2-trained']['delta_total'] /
                     ref_by['B_redecision', cid, 'M2-trained']['M1_total'] >= .01
                     for cid in ('a64_d20_r80', 'a80_d00_r00'))
    # Do not run EducationQ automatically even if this exploratory gate passes.
    # Actual task relevance has not been measured, so EducationQ admission is not automatic.
    teaching_relevance_verified = False
    decision = 'PROCEED' if stable and meaningful and teaching_relevance_verified else 'ANALYZE'
    run.dump('decision.json', dict(decision=decision, scope='R49 complete; no automatic follow-up',
        stable_advantage_gate=bool(stable), at_least_one_percent_gate=bool(meaningful),
        teaching_relevance_verified=False, independent_human_truth=False,
        configurations=52, streams=384, method_stream_runs=79872, model_calls=0,
        prior_R45_trained_delta=19.9,
        trained_positive_configs=sum(r['delta_total'] > 1e-8 for r in btrained),
        trained_zero_configs=sum(abs(r['delta_total']) <= 1e-8 for r in btrained),
        trained_negative_configs=sum(r['delta_total'] < -1e-8 for r in btrained),
        highlighted=highlighted,
        next_action='只审查一个可核验的学生回答相关性/新增覆盖代理是否有教学效度；不启动EducationQ或新算法'))

    main_table = table(['配置', 'M1', 'M2-trained', '总差', '均差95%CI', '胜/平/负', '新增覆盖差'],
        [[h['label'], fmt(h['M1_total']), fmt(h['method_total']), fmt(h['delta_total']),
          f"[{fmt(h['CI_mean_low'])},{fmt(h['CI_mean_high'])}]",
          f"{h['wins']}/{h['ties']}/{h['losses']}", h['new_atoms_delta']] for h in highlighted])
    all_table = table(['Alt', 'Degraded', 'rho', 'M1', 'M2-none差', 'M2-trained差', 'M2-oracle差', 'trained均差95%CI', '胜/平/负'],
        [[fmt(c['alt'] / 80), fmt(c['degraded'] / 80), fmt(c['repeat'] / 80),
          fmt(ref_by['B_redecision', c['id'], 'M2-trained']['M1_total']),
          *[fmt(ref_by['B_redecision', c['id'], m]['delta_total']) for m in run.METHODS[1:]],
          f"[{fmt(ref_by['B_redecision', c['id'], 'M2-trained']['CI_mean_low'])},{fmt(ref_by['B_redecision', c['id'], 'M2-trained']['CI_mean_high'])}]",
          '/'.join(str(ref_by['B_redecision', c['id'], 'M2-trained'][x]) for x in ('wins', 'ties', 'losses'))] for c in configs])
    text('PAIRED_STATISTICS.md', '# R49 配对统计（EXPLORATORY / SYNTHETIC）\n\n' + main_table +
        '\n\n384条冻结合成流是配对单位；不是9216条独立教学测量。48格内分层配对bootstrap，5000次，'
        'seed4902026，所有比较同一重采样。区间为均差，乘384才是总差区间。'
        '区间不包含训练或预测抽样重复，不作52项多重校正，不作真实学生总体推断。\n\n' + all_table +
        '\n\n完整逐配置、逐流和分层结果见 PAIRED_STATISTICS.csv、REDECISION_RESULTS.csv、SUBGROUP_RESULTS.csv。')
    a_table = table(['配置', '固定动作M1', '固定动作M2-trained', '固定动作总差', '重新决策总差'],
        [[label, fmt(ref_by['A_fixed', cid, 'M2-trained']['M1_total']),
          fmt(ref_by['A_fixed', cid, 'M2-trained']['method_total']),
          fmt(ref_by['A_fixed', cid, 'M2-trained']['delta_total']),
          fmt(ref_by['B_redecision', cid, 'M2-trained']['delta_total'])] for label, cid in selected])
    findings = (
        '## 数值结论与归因\n\n'
        '1. **部分支持旧奖励掩盖新增覆盖收益，但不能宣布旧奖励在教学上“不合理”。** '
        '保持Alternative=.8、Degraded=.25，只将rho从1降为0，trained优势从+10/8428.55'
        '（0.1186%）增为+29.10/6475.35（0.4494%），不是数量级的实用突破。'
        '纯新增覆盖则由5809增为5945，+136（2.3412%），总差95%CI=[99,173]，'
        '70胜/293平/21负。是合成覆盖信号，不是真实学习收益。\n\n'
        '2. **不能把大增益单独归因于重复折减。** 只把Alternative提高到1，'
        '保留Degraded=.25、rho=1，trained就已有+99（M1=8625.75）；'
        'Alternative=1、Degraded=0、rho=1也有+132，纯覆盖rho=0时为+136。'
        'Full与Alternative同分时，M1固定Full优先，M2可以在即时收益相同的正确性“假定”菜单'
        '之间考虑未来兼容性。这是平局/菜单机制与代理目标的作用，尚未验证两种回答真的教学等效。\n\n'
        '3. **总体排名未翻转，但优势幅度和局部表现敏感。** trained对M1的52/52配置总差均正，'
        '32/52的描述性配对区间下界>0，20/52不能排除均差为零。原评分下区间包含0，'
        '所以不满足预登记稳定/明显优势门槛；不能把门槛未通过说成“所有配置无收益”。'
        '原评分N=60组总差−1.85、r−k=2组−4.10；纯覆盖重复率>0.5组−2（0胜/37平/1负），'
        '均保留。纯覆盖的+136主要来自uniform +125，burst仅+11；'
        '并非高重复率越高就必然越受益。\n\n'
        '4. **不全是训练预测器的收益。** 纯覆盖M1/none/trained/oracle为'
        '5809/5920/5945/5944；无训练的uniform rollout已贡献+111，trained再增+25，'
        '不能将全部+136归给训练预测。burst中none为−9、trained +11、oracle +15，'
        '说明需求模型在该子组确有作用。burst联合NLL为4.5618/3.0799/3.0236'
        '（none/trained/oracle），uniform训练模型却略逊先验（4.5995对4.5618）。'
        '预测质量不与单次效用单调对应；oracle没有全面消除损失。H=6、S=8未扫描，'
        '不能进一步声称主要瓶颈已确定为有限前瞻或预测误差。\n\n'
        '5. **暂不进入完整EducationQ算法验证。** 值得先验证当前Full/Alternative菜单'
        '是否真的与同一学生任务相关且效用可比；本轮没有这类证据。只有新增覆盖被验证'
        '具有任务效度，才有理由把2.34%的合成信号带入模拟学生实验。'
        '这保留了正面信号，也不把改评分包装成算法创新。\n\n'
        '所有结果为本次冻结共同随机数下的条件比较。R49原评分trained=8438.55，'
        '不是历史8448.45的重现；后者已逐项核对无误。差别源于冻结前已登记的跨预测条件CRN统一，'
        '不能归因于奖励或据此改写R45。\n\n'
    )
    oldcov = [su['A_fixed', 'a64_d20_r80', m]['new_atoms'] for m in run.METHODS]
    text('UTILITY_SENSITIVITY.md', '# R49 奖励敏感性\n\n' + a_table + '\n\n' + findings +
        f'\n\n历史固定动作的新接收者—原子覆盖（M1/none/trained/oracle）：{oldcov}。'
        f'重新决策trained：{sum(x["delta_total"] > 1e-8 for x in btrained)}配置总差正、'
        f'{sum(abs(x["delta_total"]) <= 1e-8 for x in btrained)}平、'
        f'{sum(x["delta_total"] < -1e-8 for x in btrained)}负；均差CI下界>0的配置'
        f'{sum(x["CI_mean_low"] > 0 for x in btrained)}/52。\n\n'
        'A固定动作只回答旧输出如何被新规则评价，不能代表策略已适配。B对全部52配置重新决策，'
        '包括未来贪心也使用新奖励；预测器只拟合请求而不拟合奖励，保持原有权重。'
        'Full/Alternative对同一接收者已知原子才折减；Degraded无语义表示，继续按规定给分。'
        '所有Alternative都不是本轮请求的原子，教学相关性UNSUPPORTED；因此变化不是实测学习收益。\n\n'
        'R45不同quality使用不同预测种子；R49跨方法/配置共享uniform随机数。'
        '同权重M1完全复现，M2数值变动同时受到抽样协议改变，不得把全部变动归因于奖励。'
        'A与B不得直接作算法改进百分比。预测器的质量参见PREDICTION_QUALITY_SUMMARY.csv。\n\n'
        '有限前瞻6、样本8未改变。oracle是分布已知，不是未来已知；oracle损失或持平说明预测质量'
        '不是自动胜出的充分条件。当前实验不能严格分解有限前瞻、贪心continuation与Monte Carlo误差。'
        '这些不能通过一项奖励敏感性结果直接归结为新算法贡献。\n\n完整52配置：\n\n' + all_table)
    failure_lines = ['# R49 失败与反例', '',
        '所有负差流保存在FAILURE_CASES.csv，未剔除；所有首次动作分歧见DECISION_DIVERGENCES.jsonl。',
        '下面按预登记三个重点配置展示最差流，不更改数据或策略。', '']
    for label, cid in selected:
        for method in run.METHODS[1:]:
            subset = sorted([r for r in losses if r['config'] == cid and r['method'] == method], key=lambda x: (x['delta'], x['stream']))
            failure_lines.append(f'## {label} / {method}')
            if not subset:
                failure_lines.append('没有负差流；不因此声称全部资产有效。')
            for loss in subset[:2]:
                d = next(x for x in divergences if x['config'] == cid and x['method'] == method and x['stream'] == loss['stream'])
                failure_lines.append(f'- {loss["stream"]}：M1={loss["M1_utility"]}，M2={loss["M2_utility"]}，差={loss["delta"]}；'
                    f'首个不同决定第{d["first_difference_t"] + 1}轮：M1={d["M1"]["action"]}'
                    f'({d["M1"]["u80"] / 80})，M2={d["M2"]["action"]}({d["M2"]["u80"] / 80})；'
                    f'新增覆盖差={loss["new_atoms_delta"]}。并不能只凭此区分预测错误和有限rollout。')
            failure_lines.append('')
    failure_lines += ['## 未解决的实验漏洞', '',
        '- 循环替代原子没有实际问题相关性真值；不同接收者没有掌握度、先修关系或真实学习效果。',
        '- 384流来自同一合成结构的参数格，不是384个独立教材资产；区间不可推广到教育场景。',
        '- 仅一次冻结CRN，没有重抽预测样本、训练集或改变前瞻长度，无法因果归因全部性能差。',
        '- Degraded内容没有原子表示，零重复系数仍可给提醒累计分；纯覆盖配置排除此分值。',
        '- 纯覆盖组重复率>0.5的38流总差−2（0胜/37平/1负）；不能只展示uniform中的125点增益。',
        '- 原评分N=60的128流总差−1.85；r−k=2的192流总差−4.10。参数子组也非处处占优。',
        '- R45只有一条全原子AND恢复关系，没有独立操纵冲突图密度；CONFLICT_DIAGNOSTICS.csv是内生安全拒绝比例，不能冒充不同依赖结构的泛化。',
        '- 均差区间未作多重比较校正；效用平局沿用Full优先，可能在零奖励下消耗安全空间。',
        '- 本地准备时一次终端输出因GBK不能打印数学符号退出；没有方法运行或数据变动，之后UTF-8输出。']
    text('FAILURE_CASES.md', '\n'.join(failure_lines))
    q_table = table(['流', '预测器', '均联合NLL', '边际Brier之和'],
                    [[q['family'], q['quality'], fmt(q['mean_joint_nll']), fmt(q['mean_brier_sum'])] for q in qrows])
    costs = table(['配置', '方法', '决策墙钟总秒（不含独立核验）', '新增覆盖'],
        [[label, m, fmt(su['B_redecision', cid, m]['decision_ms'] / 1000), su['B_redecision', cid, m]['new_atoms']]
         for label, cid in selected for m in run.METHODS])
    text('FINAL_DECISION.md', '# R49 最终决策：' + decision + '\n\n'
        'EXPLORATORY / SYNTHETIC；52配置×384流×4方法，79,872次方法—流、1,916,928个实际决策。'
        '不是新教材实验，不是学习收益测量。\n\n' + main_table + '\n\n' + findings +
        '## 1. R45是否被不合理评分低估？\n\n'
        'R45确实把重复披露计满分、给未经教学相关性验证的Alternative赋0.8；这使原始教学解释不足。'
        '本次证据支持其压低了覆盖目标下的相对收益，但重复奖励不是唯一原因，回答等价赋分和平局菜单同样关键。'
        '覆盖代理改变了优化目标，不能叫修复真实学习真值。\n\n'
        '## 2. M2是否稳定胜过贪心？\n\n'
        f'trained稳定门槛={bool(stable)}，两个关键配置至少1%门槛={bool(meaningful)}。'
        f'52配置总差正/平/负={sum(r["delta_total"] > 1e-8 for r in btrained)}/'
        f'{sum(abs(r["delta_total"]) <= 1e-8 for r in btrained)}/'
        f'{sum(r["delta_total"] < -1e-8 for r in btrained)}。'
        '均值优势、胜率与实质教学意义分别解释，不能只展示有利配置。\n\n'
        '## 3. 是否进入EducationQ？\n\n'
        '目前不建议直接投入完整EducationQ算法验证，也不自动启动。Alternative对当前请求的教学相关性仍未验证；EducationQ不能为合成赋分背书。'
        '唯一下一步先人工审查一个有明确正确答案的任务中，候选替代是否满足任务与复习/新增覆盖的区分；'
        '这只是代理指标效度问题，不继续A1/A2/B调参。\n\n'
        '## 预测信息及归因限制\n\n' + q_table + '\n\n'
        'no-prediction仍为uniform抽样rollout；oracle是生成分布信息，不是未来真值。'
        '相同CRN、相同安全输入、相同8×6模拟上限；当前与未来奖励均重新适配。'
        '没有H/S或独立样本重复，不能断言主要原因必为有限前瞻或预测误差。\n\n'
        '## 成本与安全\n\n' + costs +
        f'\n\n原子chunk累计CPU={cpu:.3f}秒；实际所有方法决定总时延及模拟步数见REDECISION_RESULTS.csv。'
        '0次安全违规；所有实际Full/Alternative候选经独立holder-partition检查，实际状态再经原R45 tau检查。'
        '总主执行CPU（含checkpoint/压缩等）为EXECUTION_STATE.json中的379.27秒，'
        '与只统计chunk内运行的348.67秒口径不同，不能混称。'
        '没有模型/API/GPU、训练、下载或历史写入。输出为抽象原子，不存在可报告的真实生成Token/学习正确率。\n\n'
        '## 证据位置\n\n'
        'R49_PROTOCOL.md、freeze.json、SOURCE_VERIFICATION.json、VERIFICATION.json、'
        'HISTORICAL_RECONCILIATION.json、chunks/*.json.gz、OUTPUT_VERIFICATION.json、'
        'FIXED_TRACE_RESCORING.csv、REDECISION_RESULTS.csv、PAIRED_STATISTICS.csv、SUBGROUP_RESULTS.csv。'
        '无未获授权的自动提交或推送。')
    text('CHECKPOINT.md', '# R49 恢复检查点\n\n主实验已完成，全部52配置与2496原子chunk齐备。'
         '读取FINAL_DECISION.md与decision.json；不重跑。复核命令为analyze_r49.py，仅读取已有轨迹。'
         '下一步不是自动科研队列，等待用户决策。')
    # Final integrity manifest excludes itself; includes all raw chunk bytes and frozen source.
    hashes = {str(p.relative_to(ROOT)): run.sha(p.read_bytes()) for p in ROOT.rglob('*')
              if p.is_file() and '__pycache__' not in str(p) and p.name != 'EVIDENCE_MANIFEST.json'}
    run.dump('EVIDENCE_MANIFEST.json', dict(created_unix=time.time(), sha256=hashes))
    print(json.dumps(run.load('decision.json'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
