"""One frozen, small, exploratory train/development run; never loads2014J."""
import os
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                  OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
from pathlib import Path
import sys, json, hashlib, time, csv, warnings
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mean_absolute_error, balanced_accuracy_score, roc_auc_score, accuracy_score

P = Path(__file__).parent; ROOT = P.parents[1]
OLD = ROOT / 'experiments/oulad_dynamic_20261019_01'
sys.path[:0] = [str(P), str(OLD), str(ROOT)]
import privacy_core as pc
import selection_engine as e
import design as d
from protection.common.schemas import ProfileRecord, Task
from transformers import AutoTokenizer

def load(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n, v): (P/n).write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
def writecsv(n, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (P/n).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

def estimator(kind):
    if kind == 'LR': return LogisticRegression(C=1, class_weight='balanced', solver='liblinear', max_iter=2000, random_state=20261020)
    return RandomForestClassifier(n_estimators=64, max_depth=6, min_samples_leaf=5,
                                  class_weight='balanced_subsample', random_state=20261020, n_jobs=1)

def fit_attack(xtr, xdv, labels_tr, labels_dv, kind):
    model = make_pipeline(DictVectorizer(), StandardScaler(with_mean=False), estimator(kind))
    model.fit(xtr, labels_tr)
    prob = model.predict_proba(xdv)[:, 1]; pred = model.predict(xdv)
    return {'BA': float(balanced_accuracy_score(labels_dv, pred)),
            'AUC': float(roc_auc_score(labels_dv, prob)),
            'Accuracy': float(accuracy_score(labels_dv, pred))}, prob, pred

def wire(values):
    assert len(values) == 3 and np.isfinite(values).all()
    # Only projected coordinates enter this function, never S or attack predictions.
    return '\n'.join(f'c{i}={v:.3f}' for i, v in enumerate(values))

def parsed_view(row, payload):
    out = e.view(row, [])
    pairs = dict(line.split('=') for line in payload.splitlines())
    assert set(pairs) == {'c0', 'c1', 'c2'}
    out.update({k: float(v) for k, v in pairs.items()})
    return out

def attention_slots(row, intent, wording):
    rec = [ProfileRecord(k, typ, 'oulad', k, 1., cost, '')
           for k, (typ, cost, role, desc) in d.FIELDS.items()]
    assert all(x.sensitivity <= .7 for x in rec)
    task = Task('oulad', '', f'Task purpose {intent}. ' + d.question(intent, wording, row['cutoff']), 'oulad', 'development', False)
    utility, _, _ = e.alg.attention_values(rec, task, d.CFG['temperature'])
    order = sorted(range(len(rec)), key=lambda i: (-float(utility[i]), rec[i].record_id))
    return order[:3], {r.record_id: float(v) for r, v in zip(rec, utility)}

def auc_cluster_interval(labels, pa, pb, students):
    # Conditional on these fitted models; resample students, not repeated snapshots.
    unique = np.unique(students); indices = [np.flatnonzero(students == s) for s in unique]
    rng = np.random.default_rng(20261020); values = []
    for _ in range(500):
        ix = np.concatenate([indices[j] for j in rng.integers(0, len(unique), len(unique))])
        if len(np.unique(labels[ix])) == 2:
            values.append(roc_auc_score(labels[ix], pa[ix]) - roc_auc_score(labels[ix], pb[ix]))
    return np.quantile(values, [.025, .975]).tolist()

def run():
    if (P/'execution_lock.json').exists(): raise RuntimeError('Run is immutable; no overwrite')
    sources = {n: sha(P/n) for n in ['protocol.json', 'privacy_core.py', 'run_dev.py']}
    save('execution_lock.json', {'status': 'FROZEN_BEFORE_FIT', 'sources_sha256': sources,
                                'input_sha256': sha(OLD/'dev_data/snapshots_LOCAL.json'),
                                '2014J_access': False, 'no_search': True})
    started = time.perf_counter()
    rows = load(OLD/'dev_data/snapshots_LOCAL.json')
    train = [r for r in rows if r['split'] == 'train']; dev = [r for r in rows if r['split'] == 'dev']
    assert len(train) == 1337 and len(dev) == 473
    assert set(r['student'] for r in train).isdisjoint({r['student'] for r in dev})
    assert all(r['presentation'] == '2013J' for r in train + dev)
    fields = list(d.FIELDS); attrs = ['gender_F', 'disability_Y']
    strn = np.array([[r[a] for a in attrs] for r in train]); sdv = np.array([[r[a] for a in attrs] for r in dev])
    encoder = pc.ProfileEncoding(fields).fit(train); ztr = encoder.transform(train); zdv = encoder.transform(dev)
    transforms, meta = pc.fit_projections(ztr, strn)
    save('representation.json', encoder.description())
    save('projection_fit.json', meta)
    save('projection_checks.json', pc.verify(ztr, zdv, strn, transforms, meta))
    save('projection_matrices.json', {k: {a: b.tolist() for a, b in v.items()} for k, v in transforms.items()})
    print('Projection fits completed; train-only, official orth parity', meta['official_orth_max_abs_difference'], flush=True)
    attacks = []; internal = []; public = {}; all_predictions = {}; local = {}; summaries = []; templates = {}
    pt = [e.view(r, []) for r in train]; pd = [e.view(r, []) for r in dev]
    for ai, attr in enumerate(attrs):
        for kind in ['LR', 'RF']:
            m, prob, pred = fit_attack(pt, pd, strn[:, ai], sdv[:, ai], kind)
            rec = {'scope': 'public_only', 'method': 'Public', 'intent': 'all', 'wording': 'all',
                   'attribute': attr, 'attacker': kind, 'n': len(dev), **m}
            attacks.append(rec); public[(attr, kind)] = m
            local['PUBLIC|' + attr + '|' + kind] = {'prob': prob.tolist(), 'pred': pred.tolist()}
    for name, t in transforms.items():
        tr = pc.apply_transform(ztr, t); dv = pc.apply_transform(zdv, t)
        for visibility in ['z_only', 'z_plus_public']:
            it = [{**(p if visibility == 'z_plus_public' else {}), **{f'z{j}': float(v) for j, v in enumerate(z)}} for p, z in zip(pt, tr)]
            iv = [{**(p if visibility == 'z_plus_public' else {}), **{f'z{j}': float(v) for j, v in enumerate(z)}} for p, z in zip(pd, dv)]
            for ai, attr in enumerate(attrs):
                for kind in ['LR', 'RF']:
                    m, prob, pred = fit_attack(it, iv, strn[:, ai], sdv[:, ai], kind)
                    internal.append({'scope': visibility, 'method': name, 'attribute': attr, 'attacker': kind, 'n': len(dev), **m})
        print('internal attacks', name, flush=True)
    tokenizer = AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'), local_files_only=True)
    mi = load(OLD/'dev_results/TrainMI_train_only.json')['order'][:3]
    fixed = [fields.index(k) for k in mi]
    assert mi == ['latest_score', 'inactive_days', 'clicks_recent']
    variants = [('Att+Identity', 'Identity', True), ('NoAtt+OPP', 'OPP', False),
                ('Att+OPP', 'OPP', True), ('NoAtt+Identity', 'Identity', False),
                ('Att+INLP3', 'INLP3', True), ('Att+LEACE', 'LEACE', True)]
    allrows = train + dev; rawz = np.concatenate([ztr, zdv]); ytr = np.array([r['target_score'] for r in train]); ydv = np.array([r['target_score'] for r in dev]); observed = np.array([r['target_observed'] for r in dev])
    transformed = {name: pc.apply_transform(rawz, t) for name, t in transforms.items()}
    ids = np.array([r['student'] for r in dev]); internal_changes = {}
    for intent in d.INTENTS:
        for wording in ['explicit', 'ambiguous']:
            slotcache = {}
            for row in allrows:
                if row['cutoff'] not in slotcache:
                    slotcache[row['cutoff']] = attention_slots(row, intent, wording)
                    templates[f'{intent}|{wording}|{row["cutoff"]}'] = {'fields': [fields[i] for i in slotcache[row['cutoff']][0]], 'task_cosine': slotcache[row['cutoff']][1]}
            for method, name, att in variants:
                start = time.perf_counter()
                slots = [slotcache[r['cutoff']][0] if att else fixed for r in allrows]
                wires = [wire(z[s]) for z, s in zip(transformed[name], slots)]
                ntokens = [len(v) for v in tokenizer(wires, add_special_tokens=False)['input_ids']]
                assert max(ntokens) <= 64, ('Frozen precision exceeds token cap', max(ntokens))
                views = [parsed_view(r, p) for r, p in zip(allrows, wires)]
                delivery_ms = 1000 * (time.perf_counter() - start) / len(allrows)
                xtr = views[:len(train)]; xdv = views[len(train):]
                model = make_pipeline(DictVectorizer(), StandardScaler(with_mean=False), Ridge(alpha=10., solver='lsqr')).fit(xtr, ytr)
                pred = np.clip(model.predict(xdv), 0, 100)
                key = method + '|' + intent + '|' + wording
                all_predictions[key] = pred
                ws = wires[len(train):]; ds = slots[len(train):]
                local[key] = {'wire': ws, 'slots': [[fields[i] for i in s] for s in ds], 'prediction': pred.tolist(), 'tokens': ntokens[len(train):], 'attacks': {}}
                for ai, attr in enumerate(attrs):
                    for kind in ['LR', 'RF']:
                        m, prob, ap = fit_attack(xtr, xdv, strn[:, ai], sdv[:, ai], kind)
                        b = public[(attr, kind)]
                        attacks.append({'scope': 'actual_release_plus_public', 'method': method,
                                        'intent': intent, 'wording': wording, 'attribute': attr,
                                        'attacker': kind, 'n': len(dev), **m,
                                        'delta_AUC_vs_public': m['AUC'] - b['AUC'],
                                        'delta_BA_vs_public': m['BA'] - b['BA'],
                                        'nonnegative_observed_AUC_excess': max(0., m['AUC'] - b['AUC'])})
                        local[key]['attacks'][attr + '|' + kind] = {'prob': prob.tolist(), 'pred': ap.tolist()}
                required = set(d.INTENTS[intent]['required'])
                source_recall = [len({fields[i] for i in s} & required)/3 for s in ds]
                missing = [sum(r['values'][fields[i]] is None for i in s)/3 for r, s in zip(dev, ds)]
                identity_wires = [wire(z[s]) for z, s in zip(rawz[len(train):], ds)]
                summary = {'method': method, 'intent': intent, 'wording': wording, 'interface': 'three_numeric_summary',
                           'n_snapshots': len(dev), 'n_students': len(set(ids)), 'MAE': float(mean_absolute_error(ydv, pred)),
                           'observed_grade_MAE': float(mean_absolute_error(ydv[observed], pred[observed])),
                           'observed_grade_n': int(observed.sum()), 'actual_tokens_mean': float(np.mean(ntokens[len(train):])),
                           'actual_tokens_max': max(ntokens[len(train):]), 'scalar_count': 3, 'raw_fact_recall': None,
                           'source_slot_contract_recall': float(np.mean(source_recall)), 'source_slot_missing_fraction': float(np.mean(missing)),
                           'physical_output_missing_fraction': 0., 'payload_change_vs_identity_same_readout': float(np.mean([a != b for a, b in zip(ws, identity_wires)])),
                           'mean_delivery_ms_amortized': delivery_ms, 'direct_sensitive_release_count': 0, 'failures': 0}
                summaries.append(summary)
                print('summary fit', key, 'MAE', round(summary['MAE'], 4), 'Token', round(summary['actual_tokens_mean'], 2), flush=True)
            save('summary_results.json', summaries); save('attack_results.json', attacks); save('internal_attacks.json', internal)
            save('predictions_LOCAL.json', local)
    # Paired projection/attention changes, conditional on fixed fitted models.
    paired = []; gates = []
    for intent in d.INTENTS:
        for wording in ['explicit', 'ambiguous']:
            suffix = '|' + intent + '|' + wording
            full = local['Att+OPP' + suffix]; identity = local['Att+Identity' + suffix]; noatt = local['NoAtt+OPP' + suffix]
            mae_full = next(x['MAE'] for x in summaries if x['method']=='Att+OPP' and x['intent']==intent and x['wording']==wording)
            mae_id = next(x['MAE'] for x in summaries if x['method']=='Att+Identity' and x['intent']==intent and x['wording']==wording)
            for reference in ['Att+Identity', 'NoAtt+OPP', 'NoAtt+Identity', 'Att+INLP3', 'Att+LEACE']:
                other = local[reference + suffix]
                paired.append({'intent': intent, 'wording': wording, 'reference': reference, 'n': len(dev),
                               'payload_changed_rate': float(np.mean([a != b for a, b in zip(full['wire'], other['wire'])])),
                               'readout_slots_changed_rate': float(np.mean([set(a) != set(b) for a, b in zip(full['slots'], other['slots'])])),
                               'prediction_changed_rate': float(np.mean(np.abs(np.array(full['prediction']) - other['prediction']) > 1e-8)),
                               'delta_MAE_Full_minus_reference': float(np.mean(abs(np.array(full['prediction'])-ydv) - abs(np.array(other['prediction'])-ydv)))})
            for ai, attr in enumerate(attrs):
                diffs = {}
                for kind in ['LR', 'RF']:
                    a = np.array(full['attacks'][attr+'|'+kind]['prob']); b = np.array(identity['attacks'][attr+'|'+kind]['prob'])
                    diffs[kind] = float(roc_auc_score(sdv[:,ai], a) - roc_auc_score(sdv[:,ai], b))
                    paired.append({'intent': intent, 'wording': wording, 'reference': 'Att+Identity', 'n': len(dev),
                                   'attribute': attr, 'attacker': kind, 'delta_AUC': diffs[kind],
                                   'student_cluster_bootstrap500_95': auc_cluster_interval(sdv[:,ai], a, b, ids)})
                gates.append({'intent': intent, 'wording': wording, 'attribute': attr,
                              'delta_LR_AUC': diffs['LR'], 'delta_RF_AUC': diffs['RF'],
                              'delta_MAE': mae_full-mae_id,
                              'passed': bool(diffs['LR'] <= -.02 and diffs['RF'] <= .02 and mae_full-mae_id <= 2 and full['wire'] != identity['wire'])})
    save('paired_changes.json', paired); save('readout_templates.json', templates)
    save('phaseC_gate.json', {'classification': 'exploratory_development_screen_only', 'any_passed': any(x['passed'] for x in gates),
                             'cells': gates, 'new_independent_test_run': False, 'no_2014J_access': True,
                             'next_action': 'freeze unchanged candidate and request independent validation' if any(x['passed'] for x in gates) else 'stop; retain negative result; no retuning'})
    save('cohort.json', {'train_students': len({r['student'] for r in train}), 'dev_students': len(set(ids)),
                        'train_snapshots': len(train), 'dev_snapshots': len(dev), 'train_dev_disjoint': True,
                        'protected_counts': {a: {'train_positive_snapshots': int(strn[:, i].sum()), 'dev_positive_snapshots': int(sdv[:, i].sum()),
                            'train_positive_students': len({r['student'] for r in train if r[a]}), 'dev_positive_students': len({r['student'] for r in dev if r[a]})} for i,a in enumerate(attrs)}})
    save('dev_pairing_LOCAL.json', [{'student': r['student'], 'target': r['target_score'], 'gender_F': r['gender_F'], 'disability_Y': r['disability_Y'], 'cutoff': r['cutoff'], 'module': r['module']} for r in dev])
    save('completion.json', {'status': 'COMPLETED_DEV_ONLY', 'summary_cells': len(summaries), 'actual_attack_cells': len(attacks)-4,
                             'internal_attack_cells': len(internal), 'public_attack_cells': 4, 'seconds': time.perf_counter()-started,
                             'sources_sha256': sources, 'test_access': False, 'parameter_search': False, 'LLM_API_calls': 0,
                             'failures': 0, 'all_tokens_le64': all(x['actual_tokens_max']<=64 for x in summaries)})
    print('COMPLETED_DEV_ONLY', flush=True)

if __name__ == '__main__': run()
