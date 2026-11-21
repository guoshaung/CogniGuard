"""Frozen-rule evidence expansion; does not tune on benchmark outcomes.

CG results measure adapter decisions, not endpoint safety or full governance.
Profile results measure selection, not inferred leakage from rendered text.
Watermark results are a reanalysis of existing attacks, not new generations.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import requests

from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
from cogniguard.runtime.mode import DEFAULT_GUARDRAILS_CONFIG
from experiments.evaluation.run_cg_jailbreakbench import fetch_split
from experiments.evaluation.run_cg_xstest import URL as XSTEST_URL
from experiments.mmfopd_v3.baselines import METHODS
from experiments.mmfopd_v3.runner import _task
from protection.common.schemas import StudentProfile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.student_profile.src.pipeline.run_demo import load_config

ROOT = Path(__file__).resolve().parents[2]


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [max(0, c-h), min(1, c+h)]


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()]


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')


def confusion(rows):
    tp = sum(r['positive'] and r['blocked'] for r in rows)
    fn = sum(r['positive'] and not r['blocked'] for r in rows)
    fp = sum(not r['positive'] and r['blocked'] for r in rows)
    tn = sum(not r['positive'] and not r['blocked'] for r in rows)
    recall = tp/(tp+fn) if tp+fn else None
    fpr = fp/(fp+tn) if fp+tn else None
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, recall=recall, false_block_rate=fpr,
                precision=tp/(tp+fp) if tp+fp else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
                balanced_accuracy=(recall+1-fpr)/2 if recall is not None and fpr is not None else None,
                recall_wilson95=wilson(tp,tp+fn), false_block_wilson95=wilson(fp,fp+tn))


def run_cg(output):
    adapter = NeMoGuardrailsAdapter(str(DEFAULT_GUARDRAILS_CONFIG))
    datasets = {}
    datasets['jbb_behaviors'] = [(r['Index'], r['Goal'], s == 'harmful', r['Category'])
                               for s in ('harmful','benign') for r in fetch_split(s)]
    cache = ROOT/'experiments/external_data/xstest'/ 'd7bb5bd738c1_prompts.csv'
    if not cache.exists():
        resp = requests.get(XSTEST_URL, timeout=45)
        resp.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(resp.content)
    with cache.open(encoding='utf8',newline='') as f:
        datasets['xstest'] = [(r['id'],r['prompt'],r['label']=='unsafe',r['type']) for r in csv.DictReader(f)]
    results = {}
    for name, source in datasets.items():
        rows = []
        for case_id, prompt, positive, category in source:
            started = time.perf_counter()
            decision = adapter.check_user_input(prompt,{})
            rows.append(dict(case_id=case_id,positive=positive,category=category,
                             prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                             blocked=decision['decision']=='block',decision=decision['decision'],
                             policy=decision['matched_policy'],latency_ms=1000*(time.perf_counter()-started)))
        groups = defaultdict(list)
        for r in rows:
            groups[r['category']].append(r)
        results[name] = dict(scope='full public file, frozen adapter only; no LLM judge or governance episode',
                             n=len(rows),metrics=confusion(rows),
                             categories={k:confusion(v) for k,v in groups.items()})
        save(output/f'{name}_rows.json',rows)
    save(output/'cg_full_summary.json',results)
    return results


def run_profiles(output):
    data = ROOT/'experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded'
    profiles = {r['student_id']:StudentProfile.from_dict(r) for r in read_jsonl(data/'profiles.jsonl')}
    questions = read_jsonl(data/'student_questions.jsonl')
    cfg = load_config(ROOT/'protection/student_profile/configs/default.yaml')
    variants = [('default',cfg)]
    for component in ('use_orthogonal','use_task_attention','use_bottleneck'):
        c = copy.deepcopy(cfg)
        c['fopd']['components'][component] = False
        variants.append(('without_'+component,c))
    for k in (2,4,6):
        c = copy.deepcopy(cfg)
        c['fopd']['top_k_profile_records'] = k
        c['fopd']['unit_budget']['max_units'] = k
        variants.append(('unit_limit_'+str(k),c))
    rows=[]
    for q in questions:
        if q.get('split') not in ('dev','test'):
            continue
        task=_task(q)
        profile=profiles[task.student_id]
        experiments=[(name, select(profile,task,cfg)) for name,select in METHODS.items()]
        experiments += [('MM-FOPD/'+name,ProfileSelector(c).select(profile,task)) for name,c in variants if name!='default']
        for name,selected in experiments:
            records=[x.record for x in selected]
            required={(task.knowledge,t) for t in ('mastery','error_pattern','preference')}
            units={(r.knowledge,r.type) for r in records}
            tp=len(units & required)
            p=tp/len(units) if units else 0
            recall=tp/len(required)
            mass=sum(r.sensitivity for r in records)
            total=sum(r.sensitivity for r in profile.profile_records)
            rows.append(dict(method=name,split=q['split'],student_id=task.student_id,request_id=task.request_id,
                             selected_ids=[r.record_id for r in records],selected_count=len(records),
                             selected_high_sensitive_count=sum(r.sensitivity>=.7 for r in records),
                             any_selected_high_sensitive=int(any(r.sensitivity>=.7 for r in records)),
                             weighted_selection_exposure=mass/total if total else 0,
                             recall=recall,corrected_unit_precision=p,
                             corrected_unit_f1=2*p*recall/(p+recall) if p+recall else 0))
    groups=defaultdict(list)
    for r in rows:
        groups[(r['split'],r['method'])].append(r)
    summary=[]
    for (split,method),rs in groups.items():
        k=sum(r['any_selected_high_sensitive'] for r in rs)
        summary.append(dict(split=split,method=method,n=len(rs),students=len({r['student_id'] for r in rs}),
                            high_sensitive_selection_tasks=k,
                            high_sensitive_selection_task_rate=k/len(rs),
                            **{metric:sum(r[metric] for r in rs)/len(rs) for metric in
                               ('selected_count','weighted_selection_exposure','recall','corrected_unit_precision','corrected_unit_f1')}))
    save(output/'profile_rows.json',rows)
    save(output/'profile_summary.json',dict(scope='selection-level fixed three-type gold; not teaching utility or output attribute inference',
         hash_seed=os.getenv('PYTHONHASHSEED'), configurations={k:c for k,c in variants},summary=summary))
    return summary


def watermark_reanalysis(output):
    folder=ROOT/'experiments/results/text_watermark_selective12/run_20260906_221459_352036'
    with (folder/'attack_results.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    groups=defaultdict(list)
    for r in rows:
        groups[r['attack']].append(r)
    result={}
    for attack,rs in groups.items():
        k=sum(r['is_watermarked'].lower()=='true' for r in rs)
        result[attack]=dict(detected=k,n=len(rs),adr=k/len(rs),wilson95=wilson(k,len(rs)))
    save(output/'watermark_attack_summary.json',dict(scope='reanalysis of existing 12 texts; attacks share source samples; not new trials',results=result))
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--skip-cg',action='store_true')
    args=ap.parse_args()
    results={}
    for name,fn in [('profiles',run_profiles),('watermark',watermark_reanalysis),('cg',run_cg)]:
        if name=='cg' and args.skip_cg:
            continue
        try:
            results[name]=fn(args.output)
            print(name+' completed',flush=True)
        except Exception as e:
            results[name]={'error_type':type(e).__name__,'error':str(e)}
            print(name+' failed: '+str(e),flush=True)
    save(args.output/'combined_summary.json',results)


if __name__=='__main__':
    main()
