"""Frozen offline request-only inference gate. No network/model calls."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.paths import PROJECT_ROOT, RESULTS_DIR  # noqa: E402

E = Path(__file__).resolve().parent
R = RESULTS_DIR / E.name
ARCHIVE = PROJECT_ROOT / '.cache/oulad-author-v1/anonymisedData.zip'
PAIRS = [('BBB', '2014J'), ('DDD', '2014J'), ('FFF', '2014J')]
SALT = 'mmfopda-gate0-20261113-v1'
TABLES = ['studentInfo', 'studentAssessment', 'assessments', 'studentVle',
          'vle', 'studentRegistration', 'courses']
LABELS = ['disability', 'imd_low20', 'age55plus']


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def read(name, **kwargs):
    with zipfile.ZipFile(ARCHIVE) as z, z.open(name + '.csv') as f:
        return pd.read_csv(f, **kwargs)


def subset(df):
    return df[df[['code_module', 'code_presentation']].apply(tuple, axis=1).isin(PAIRS)]


def student_hash(sid):
    return hashlib.sha256(f'{SALT}:{int(sid)}'.encode()).hexdigest()


def audit():
    R.mkdir(parents=True, exist_ok=True)
    lines = ['# OULAD 字段审计（全发布表，非仅选中队列）', '',
             '来源、许可见 README.md。缺失率为 pandas 默认 NA（含空单元格），不把 0 当缺失。',
             '类型为整列实际可解析类型；整数语义但存在缺失时为 float64。',
             'studentInfo 的三项标签仅在攻击拟合/评价时读取，不传入请求生成函数。',
             '联结键不作为请求内容或攻击特征。其他画像列、最终结果和未来行为禁止用于生成。',
             'courses 为额外的公开日历元数据表，仅用于全学期终点，非画像输入。', '']
    roles = {
        'studentInfo': {'disability': '敏感标签：Y=1', 'imd_band': '敏感标签：0-10%、10-20=1；缺失排除本标签',
                        'age_band': '敏感标签：55<= =1'},
        'studentAssessment': {'date_submitted': '请求：已发生提交；模拟分数可用时间',
                              'score': '请求：模拟已公布分数', 'is_banked': '过滤：不使用结转成绩'},
        'assessments': {'date': '请求：截止日；无截止日不触发', 'assessment_type': '过滤：仅 TMA/CMA',
                        'weight': '禁止使用'},
        'studentVle': {'date': '请求：截至当周已发生点击', 'sum_click': '请求：资源占比'},
        'vle': {'activity_type': '请求：资源类型', 'week_from': '禁止使用', 'week_to': '禁止使用'},
        'studentRegistration': {'date_registration': '资格：截止时已注册',
                                'date_unregistration': '资格：截止时已退课则不发新请求'},
        'courses': {'module_presentation_length': '日历：全学期观察终点'},
    }
    schemas = {}
    for name in TABLES:
        missing, count, kinds = None, 0, {}
        with zipfile.ZipFile(ARCHIVE) as z, z.open(name + '.csv') as f:
            for chunk in pd.read_csv(f, chunksize=400000):
                missing = chunk.isna().sum() if missing is None else missing + chunk.isna().sum()
                count += len(chunk)
                for col in chunk:
                    kinds.setdefault(col, set()).add(str(chunk[col].dtype))
        lines += [f'## {name}.csv — {count:,} 行', '', '| 字段 | 实测类型 | 缺失率 | 用途 |',
                  '|---|---|---:|---|']
        schemas[name] = {'rows': count, 'columns': {}}
        for col in missing.index:
            role = roles.get(name, {}).get(col, '禁止使用')
            if col in ['id_student', 'id_assessment', 'id_site', 'code_module', 'code_presentation']:
                role = '仅内部联结/队列/划分；禁止进入外发和攻击特征'
            typ = '/'.join(sorted(kinds[col]))
            rate = float(missing[col] / count)
            lines.append(f'| {col} | {typ} | {rate:.6%} | {role} |')
            schemas[name]['columns'][col] = {'types': sorted(kinds[col]), 'missing_rate': rate, 'role': role}
        lines.append('')
    source = {'archive': str(ARCHIVE), 'sha256': sha(ARCHIVE), 'tables': schemas}
    dump(E / 'DATA_AUDIT.json', source)
    (E / 'FIELD_TABLE.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'audit_complete': True, 'archive_sha256': source['sha256']}))


def freeze():
    assert (E / 'FIELD_TABLE.md').exists()
    assert not (E / 'FREEZE.json').exists(), 'Already frozen; do not replace.'
    info = subset(read('studentInfo'))
    # Exactly one course enrollment per ID, chosen without looking at any labels.
    info['choice'] = [hashlib.sha256(f'{SALT}:enrol:{s}:{m}:{p}'.encode()).hexdigest()
                      for s, m, p in info[['id_student', 'code_module', 'code_presentation']].itertuples(index=False)]
    info = info.sort_values('choice').drop_duplicates('id_student').sort_values('id_student')
    split = info[['id_student', 'code_module', 'code_presentation']].copy()
    split['student_key'] = split.id_student.map(student_hash)
    split['split'] = split.student_key.map(lambda h: 'train' if int(h, 16) / 2**256 < .6 else 'test')
    split.to_csv(R / 'split_LOCAL.csv', index=False)
    manifest = {'salt': SALT, 'pairs': PAIRS, 'student_rows': len(split),
                'split_counts': split['split'].value_counts().to_dict(),
                'source_sha256': sha(ARCHIVE), 'split_sha256': sha(R / 'split_LOCAL.csv'),
                'files': {p: sha(E / p) for p in ['REQUEST_RULES.md', 'PROTOCOL.md',
                          'FIELD_TABLE.md', 'DATA_AUDIT.json', 'run_gate0.py']},
                'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__}
    dump(E / 'FREEZE.json', manifest)
    print(json.dumps(manifest, ensure_ascii=False))


def check_freeze():
    frozen = json.loads((E / 'FREEZE.json').read_text(encoding='utf-8'))
    assert sha(ARCHIVE) == frozen['source_sha256']
    assert sha(R / 'split_LOCAL.csv') == frozen['split_sha256']
    for name, digest in frozen['files'].items():
        assert sha(E / name) == digest, f'Frozen artifact modified: {name}'


def build_requests():
    """Accept no studentInfo or label columns; serialize request-only receiver views."""
    split = pd.read_csv(R / 'split_LOCAL.csv')
    ids = split.id_student.to_numpy()
    n = len(ids)
    lookup = dict(zip(ids, range(n)))
    courses = read('courses').set_index(['code_module', 'code_presentation'])
    lengths = np.array([courses.loc[(m, p), 'module_presentation_length']
                        for m, p in split[['code_module', 'code_presentation']].itertuples(index=False)])
    reg = subset(read('studentRegistration')).merge(
        split[['id_student', 'code_module', 'code_presentation']],
        on=['id_student', 'code_module', 'code_presentation'])
    reg = reg.set_index('id_student').reindex(ids)
    start = reg.date_registration.to_numpy()
    stop = reg.date_unregistration.to_numpy()
    meta = subset(read('vle'))
    types = sorted(meta.activity_type.unique())
    ti = {t: i for i, t in enumerate(types)}
    maxweek = int(np.ceil(lengths.max() / 7))
    clicks = np.zeros((n, maxweek, len(types)))
    days = np.zeros((n, maxweek))
    # Daily records may span multiple sites: deduplicate active days after joining.
    seen_days = set()
    with zipfile.ZipFile(ARCHIVE) as z, z.open('studentVle.csv') as f:
        for chunk in pd.read_csv(f, chunksize=400000):
            chunk = chunk[chunk.id_student.isin(ids)]
            chunk = chunk.merge(split[['id_student', 'code_module', 'code_presentation']],
                                on=['id_student', 'code_module', 'code_presentation'])
            chunk = chunk.merge(meta[['id_site', 'code_module', 'code_presentation', 'activity_type']],
                                on=['id_site', 'code_module', 'code_presentation'], validate='many_to_one')
            for sid, date, count, typ in chunk[['id_student', 'date', 'sum_click', 'activity_type']].itertuples(index=False):
                i = lookup[sid]
                if 0 <= date < lengths[i] and date >= start[i] and (np.isnan(stop[i]) or date < stop[i]):
                    w = int(date // 7)
                    clicks[i, w, ti[typ]] += count
                    if count > 0:
                        seen_days.add((i, w, date))
    for i, w, _ in seen_days:
        days[i, w] += 1
    ass = read('studentAssessment').merge(read('assessments'), on='id_assessment', validate='many_to_one')
    ass = ass.merge(split[['id_student', 'code_module', 'code_presentation']],
                    on=['id_student', 'code_module', 'code_presentation'])
    ass = ass[(ass.is_banked == 0) & ass.assessment_type.isin(['TMA', 'CMA'])
              & ass.date.notna() & ass.date_submitted.notna()].copy()
    ass['available'] = ass[['date', 'date_submitted']].max(axis=1) + 7
    ass = ass.sort_values(['available', 'id_assessment'])
    groups = {sid: g for sid, g in ass.groupby('id_student')}
    requests = np.zeros((n, maxweek, 3 + len(types)), dtype=np.int32)
    raw = np.zeros((n, maxweek, 9 + len(types)))
    payloads = []
    training = split['split'].eq('train').to_numpy()
    module = split.code_module.to_numpy()
    for w in range(maxweek):
        end = np.minimum(7 * (w + 1) - 1, lengths - 1)
        active = (~np.isnan(start)) & (start <= end) & (np.isnan(stop) | (stop > end)) & (7*w < lengths)
        total = clicks[:, w].sum(axis=1)
        share = np.divide(clicks[:, w], total[:, None], out=np.zeros_like(clicks[:, w]), where=total[:, None] > 0)
        for m, _ in PAIRS:
            reference = training & active & (module == m)
            med = np.median(share[reference], axis=0) if reference.any() else np.zeros(len(types))
            mask = active & (module == m) & (total >= 10)
            requests[mask, w, 3:] = (share[mask] >= med + .20).astype(int)
        for i, sid in enumerate(ids):
            g = groups.get(sid)
            score = np.array([])
            submitted = None
            if g is not None:
                # Filter event dates by registration, independent of future withdrawal.
                valid = (g.date_submitted >= start[i]) & (np.isnan(stop[i]) | (g.date_submitted < stop[i]))
                submitted = g[valid & (g.date_submitted <= end[i])]
                avail = g[valid & (g.available <= end[i]) & g.score.notna()]
                score = avail.score.to_numpy()
            if active[i]:
                requests[i, w, 0] = int(len(score) > 0 and score[-1] < 40)
                requests[i, w, 1] = int(len(score) >= 3 and score[-1] < score[-2] < score[-3])
                if submitted is not None:
                    recent = submitted if w == 0 else submitted[submitted.date_submitted > 7*w-1]
                    requests[i, w, 2] = int((recent.date_submitted > recent.date).sum())
            late = submitted[submitted.date_submitted > submitted.date] if submitted is not None else None
            raw[i, w] = [clicks[i, :w+1].sum(), *clicks[i, :w+1].sum(axis=0),
                         days[i, :w+1].sum(), len(score), score.mean() if len(score) else 0,
                         score[-1] if len(score) else 0, score.min() if len(score) else 0,
                         len(submitted) if submitted is not None else 0,
                         len(late) if late is not None else 0,
                         (late.date_submitted - late.date).sum() if late is not None else 0]
    names = ['tutoring', 'review_session', 'extension'] + ['format_' + t for t in types]
    with (R / 'requests_LOCAL.jsonl').open('w', encoding='utf-8') as f:
        for i in range(n):
            for w in range(maxweek):
                for j, name in enumerate(names):
                    for _ in range(int(requests[i, w, j])):
                        agent = 'tutor' if j < 2 else 'admin' if j == 2 else 'resource'
                        message = {'request': name}
                        assert set(message) == {'request'}
                        f.write(json.dumps({'student_key': split.student_key.iloc[i], 'week': w+1,
                                            'agent': agent, 'message': message}) + '\n')
    np.savez_compressed(R / 'features_LOCAL.npz', requests=requests, raw=raw, lengths=lengths)
    dump(R / 'feature_schema.json', {'request_names': names, 'types': types,
         'students': n, 'total_requests': int(requests.sum()),
         'by_request': dict(zip(names, requests.sum(axis=(0, 1)).astype(int).tolist())),
         'zero_request_students': int((requests.sum(axis=(1, 2)) == 0).sum())})
    # Strong invariance: changing label values cannot affect features: no label table read here.
    return split, requests, raw


def bootstrap_scores(y, prob, weights):
    """Weighted exact AUC with probability ties, paired student resampling."""
    order = np.argsort(prob, kind='stable')
    ys = y[order]
    ps = prob[order]
    starts = np.r_[0, np.flatnonzero(np.diff(ps)) + 1]
    pos = np.add.reduceat(weights[:, order] * ys, starts, axis=1)
    neg = np.add.reduceat(weights[:, order] * (1-ys), starts, axis=1)
    ptotal, ntotal = pos.sum(axis=1), neg.sum(axis=1)
    auc = (pos * (np.cumsum(neg, axis=1) - .5*neg)).sum(axis=1) / (ptotal * ntotal)
    pred = prob >= .5
    ba = .5 * ((weights * (y * pred)).sum(axis=1) / ptotal +
                (weights * ((1-y) * (~pred))).sum(axis=1) / ntotal)
    return auc, ba


def run():
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score, balanced_accuracy_score
    import sklearn

    check_freeze()
    assert not (R / 'metrics.csv').exists(), 'Completed run exists; do not overwrite.'
    split, requests, raw = build_requests()
    print('Request-only messages generated; loading targets only now.', flush=True)
    info = read('studentInfo').merge(split, on=['id_student', 'code_module', 'code_presentation'])
    info = info.set_index('id_student').reindex(split.id_student)
    targets = {
        'disability': info.disability.map({'Y': 1, 'N': 0}).to_numpy(dtype=float),
        'imd_low20': info.imd_band.map(lambda x: np.nan if pd.isna(x) else int(x in ['0-10%', '10-20'])).to_numpy(),
        'age55plus': info.age_band.map({'0-35': 0, '35-55': 0, '55<=': 1}).to_numpy(dtype=float),
    }
    observers = {'tutor': [0, 1], 'admin': [2], 'resource': list(range(3, requests.shape[2]))}
    observers.update({'tutor+admin': [0, 1, 2], 'tutor+resource': [0, 1] + observers['resource'],
                      'admin+resource': [2] + observers['resource'], 'all3': list(range(requests.shape[2]))})
    rows, student_rows, differences, subgroup_rows = [], [], [], []
    rng = np.random.default_rng(20261113)
    counts = {}
    for label, target in targets.items():
        train = split['split'].eq('train').to_numpy() & ~np.isnan(target)
        test = split['split'].eq('test').to_numpy() & ~np.isnan(target)
        yt = target[train].astype(int)
        ye = target[test].astype(int)
        counts[label] = {'train_n': len(yt), 'train_positive': int(yt.sum()),
                         'test_n': len(ye), 'test_positive': int(ye.sum()),
                         'missing': int(np.isnan(target).sum())}
        assert len(np.unique(yt)) == len(np.unique(ye)) == 2, f'Single class: {label}'
        # Fixed resamples shared over horizons, observers and models for this label.
        weights = rng.multinomial(len(ye), np.full(len(ye), 1/len(ye)), size=1000).astype(float)
        valid = ((weights @ ye) > 0) & ((weights @ (1-ye)) > 0)
        weights = weights[valid]
        shuffle_train, shuffle_test = rng.permutation(yt), rng.permutation(ye)
        null_weights = weights.copy()
        null_valid = ((null_weights @ shuffle_test) > 0) & ((null_weights @ (1-shuffle_test)) > 0)
        null_weights = null_weights[null_valid]
        test_split = split.loc[test].reset_index(drop=True)
        for horizon, w in [('4', 4), ('8', 8), ('12', 12), ('full', requests.shape[1])]:
            cumulative = requests[:, :w].sum(axis=1)
            views = {name: cumulative[:, cols] for name, cols in observers.items()}
            views['raw_behavior'] = raw[:, w-1]
            for model in ['LR', 'Tree3']:
                actual = {}
                for observer, features in views.items():
                    transformed = np.log1p(features)
                    scaler = StandardScaler().fit(transformed[train])
                    xt, xe = scaler.transform(transformed[train]), scaler.transform(transformed[test])
                    for control, ytrain, ytest, boot in [('actual', yt, ye, weights),
                                                        ('shuffled', shuffle_train, shuffle_test, null_weights)]:
                        clf = (LogisticRegression(C=1, class_weight='balanced', max_iter=2000,
                                                  solver='lbfgs') if model == 'LR' else
                               DecisionTreeClassifier(max_depth=3, class_weight='balanced', random_state=20261113))
                        clf.fit(xt, ytrain)
                        probability = clf.predict_proba(xe)[:, 1]
                        auc = roc_auc_score(ytest, probability)
                        ba = balanced_accuracy_score(ytest, probability >= .5)
                        aucs, bas = bootstrap_scores(ytest, probability, boot)
                        row = {'label': label, 'observer': observer, 'week': horizon,
                               'model': model, 'control': control, **counts[label],
                               'auc': auc, 'auc_low': np.quantile(aucs, .025), 'auc_high': np.quantile(aucs, .975),
                               'balanced_accuracy': ba, 'ba_low': np.quantile(bas, .025),
                               'ba_high': np.quantile(bas, .975), 'bootstrap_valid': len(boot)}
                        rows.append(row)
                        if control == 'actual':
                            actual[observer] = (auc, aucs)
                            for course in ['BBB', 'DDD', 'FFF']:
                                mask = test_split.code_module.eq(course).to_numpy()
                                if len(np.unique(ytest[mask])) == 2:
                                    subgroup_rows.append({'label': label, 'observer': observer, 'week': horizon,
                                        'model': model, 'course': course, 'n': int(mask.sum()),
                                        'positive': int(ytest[mask].sum()), 'auc': roc_auc_score(ytest[mask], probability[mask])})
                        for j, record in test_split.iterrows():
                            student_rows.append({'student_key': record.student_key, 'split': 'test',
                                'course': record.code_module, 'presentation': record.code_presentation,
                                'label': label, 'week': horizon, 'observer': observer, 'model': model,
                                'control': control, 'sensitive_target': int(ye[j]), 'evaluation_target': int(ytest[j]),
                                'probability': probability[j], 'prediction': int(probability[j] >= .5)})
                singles = ['tutor', 'admin', 'resource']
                best = max(singles, key=lambda x: actual[x][0])
                delta = actual['all3'][0] - actual[best][0]
                paired = actual['all3'][1] - np.maximum.reduce([actual[x][1] for x in singles])
                differences.append({'label': label, 'week': horizon, 'model': model, 'best_single': best,
                    'best_single_auc': actual[best][0], 'all3_auc': actual['all3'][0], 'delta_auc': delta,
                    'delta_low': np.quantile(paired, .025), 'delta_high': np.quantile(paired, .975)})
            print(f'{label} week={horizon} finished', flush=True)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(R / 'metrics.csv', index=False)
    pd.DataFrame(student_rows).to_csv(R / 'per_student.csv', index=False)
    pd.DataFrame(differences).to_csv(R / 'collusion_delta.csv', index=False)
    pd.DataFrame(subgroup_rows).to_csv(R / 'course_diagnostics.csv', index=False)
    dump(R / 'RUN.json', {'counts': counts, 'sklearn': sklearn.__version__,
                          'api_calls': 0, 'gpu_used': False, 'bootstrap': 1000,
                          'feature_sha256': sha(R / 'features_LOCAL.npz'),
                          'request_sha256': sha(R / 'requests_LOCAL.jsonl')})
    print('Completed. Run report phase next.', flush=True)


def report():
    check_freeze()
    m = pd.read_csv(R / 'metrics.csv', dtype={'week': str})
    d = pd.read_csv(R / 'collusion_delta.csv', dtype={'week': str})
    actual = m[m.control == 'actual']
    joined = actual[actual.observer == 'all3'].merge(d, on=['label', 'week', 'model'])
    passing = joined[(joined.auc >= .65) & (joined.auc_low > .55) & (joined.delta_auc >= .03)]
    single = actual[actual.observer.isin(['tutor', 'admin', 'resource'])]
    partial = single[single.auc >= .65]
    decision = 'PASS' if len(passing) else 'PARTIAL' if len(partial) else 'FAIL / STOP'
    # No modification of the gate based on negative controls or diagnostic courses.
    lines = ['# MMFOPD-A Gate 0 结果', '', f'**判定：{decision}**。Gate 1 未执行。', '',
             '真实 OULAD 行为 + 冻结规则模拟请求；无画像字段外发、无模型API、无GPU。',
             '分数采用固定公布时间假设，非实际部署时间证明。所有区间为测试学生1000次bootstrap、固定模型条件区间。', '',
             '## 样本与请求', '', '```json', (R / 'RUN.json').read_text(), '```', '',
             '```json', (R / 'feature_schema.json').read_text(), '```', '',
             '## 主表：真实标签 AUC [95%区间] / 平衡准确率 [95%区间]', '',
             '| 标签 | 观察方 | 周数 | 模型 | AUC [95%] | BA [95%] |', '|---|---|---|---|---|---|']
    for r in actual.itertuples():
        lines.append(f'| {r.label} | {r.observer} | {r.week} | {r.model} | {r.auc:.3f} [{r.auc_low:.3f}, {r.auc_high:.3f}] | {r.balanced_accuracy:.3f} [{r.ba_low:.3f}, {r.ba_high:.3f}] |')
    lines += ['', '## 合谋增量（最佳单方在同标签、周数、模型内选取）', '',
              '| 标签 | 周数 | 模型 | 最佳单方 | 三方 AUC | 差值 [配对95%] |', '|---|---|---|---|---|---|']
    for r in d.itertuples():
        lines.append(f'| {r.label} | {r.week} | {r.model} | {r.best_single} ({r.best_single_auc:.3f}) | {r.all3_auc:.3f} | {r.delta_auc:.3f} [{r.delta_low:.3f}, {r.delta_high:.3f}] |')
    lines += ['', '## 标签置乱下界', '',
              '| 标签 | 观察方 | 周数 | 模型 | AUC [95%] | BA [95%] |', '|---|---|---|---|---|---|']
    for r in m[m.control == 'shuffled'].itertuples():
        lines.append(f'| {r.label} | {r.observer} | {r.week} | {r.model} | {r.auc:.3f} [{r.auc_low:.3f}, {r.auc_high:.3f}] | {r.balanced_accuracy:.3f} [{r.ba_low:.3f}, {r.ba_high:.3f}] |')
    lines += ['', '## 解释边界', '',
              '本结果只检验请求与敏感标签的相关推断，不是自进化投毒、教学效用或新防御算法证据。',
              '三方模型与单方模型均固定；增加信息并不保证有限样本拟合AUC增加。',
              '3标签×4截点×2模型为探索性多重比较；无多重校正，不声称确认性显著发现。',
              '课程分组诊断见 course_diagnostics.csv；课程/学期不作为攻击特征，但请求可能间接携带课程差异。',
              '没有独立跨课程/跨学期复现。请求规则和分数延时假设限制外推；资源基准仅用训练学生。',
              '原始行为对照是信息更丰富的参照，不是浅模型可达到的数学上界。',
              '逐学生 CSV/请求/原始ID与标签仅保存在本机 var，不公开上传。']
    (E / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8')
    for name in ['metrics.csv', 'collusion_delta.csv', 'course_diagnostics.csv', 'RUN.json', 'feature_schema.json']:
        (E / name).write_bytes((R / name).read_bytes())
    outcome = {'decision': decision, 'passing_configurations': passing.to_dict('records'),
               'partial_configurations': partial.to_dict('records'), 'gate1_executed': False}
    dump(E / 'DECISION.json', outcome)
    text = f'# 最终决定：{decision}\n\n'
    if len(passing):
        text += '至少一个冻结配置满足三方AUC、下界与相对最佳单方增量的全部门槛。仅通过可行性闸门，本轮不运行Gate 1。\n'
    elif len(partial):
        text += '存在单接收方AUC≥0.65，但三方合谋没有配置同时满足全部增量闸门。多Agent累积路线不通过；若后续研究，应限于单接收方版本。本轮不设计防御。\n'
    else:
        text += '没有配置满足完整或部分通过条件。停止本方向，MM-FOPD降级为系统组件并保留负面边界结果；不调规则、不换标签、不进入Gate 1。\n'
    text += '\n具体配置和配对差区间见 DECISION.json、collusion_delta.csv；完整主表见 RESULT.md。该门槛为探索性筛选，未做多重比较校正。\n'
    (E / 'final_decision.md').write_text(text, encoding='utf-8')
    dump(E / 'OUTPUT_SHA256.json', {p.name: sha(p) for p in E.iterdir()
                                   if p.is_file() and p.name != 'OUTPUT_SHA256.json'})
    print(json.dumps({'decision': decision, 'passing': len(passing), 'partial': len(partial)}))


if __name__ == '__main__':
    {'audit': audit, 'freeze': freeze, 'run': run, 'report': report}[sys.argv[1]]()
