"""Independent shadow attacker for MM-FOPD output cards.

This file is an evaluator only. It does not alter MM-FOPD selection or policy.
The attacker sees the released card and predicts whether a sensitive profile
attribute was present, using a frozen keyword/prototype shadow classifier.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from experiments.mmfopd_v3.baselines import METHODS
from protection.common.schemas import StudentProfile
from protection.common.text_utils import read_jsonl
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.pipeline.run_demo import load_config
from experiments.mmfopd_v3.runner import _task

ROOT = Path(__file__).resolve().parents[2]


def sensitive_targets(profile: StudentProfile) -> list[str]:
    return [str(r.value).strip().lower() for r in profile.profile_records if r.sensitivity >= .7 and str(r.value).strip()]


def predict(card: str, targets: list[tuple[str, str, str]]) -> bool:
    c = card.lower()
    cues = {'mastery': ('掌握状态','掌握'), 'error_pattern': ('常见错误','错误'), 'preference': ('推荐策略','策略'), 'learning_state': ('学习状态','状态'), 'behavior_aggregate': ('行为','行为'), 'multimodal_summary': ('模态','模态')}
    for value, knowledge, kind in targets:
        words = [w for w in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", value) if len(w) >= 2]
        if words and sum(w in c for w in words) >= max(1, len(words)//2):
            return True
        # Shadow attacker uses publicly visible task knowledge and the
        # structured card's section cues, but never sees the selection labels.
        if knowledge and knowledge.lower() in c and kind in c:
            return True
        if any(cue in c for cue in cues.get(kind, ())):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=ROOT/'experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded')
    ap.add_argument("--config", type=Path, default=ROOT/'protection/student_profile/configs/default.yaml')
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--split", choices=('dev','test'), default='test')
    args = ap.parse_args()
    cfg=load_config(args.config)
    profiles={r['student_id']:StudentProfile.from_dict(r) for r in read_jsonl(args.data_root/'profiles.jsonl')}
    questions=[r for r in read_jsonl(args.data_root/'student_questions.jsonl') if r.get('split')==args.split]
    rows=[]
    for q in questions:
        task=_task(q); profile=profiles[task.student_id]; targets=sensitive_targets(profile)
        for method, select in METHODS.items():
            selected=select(profile,task,cfg); card,_=build_context_card(profile,task,selected)
            # Balanced per-card attack: one sensitive value is the positive
            # target and one value from another profile is a negative decoy.
            sensitive_records = [r for r in profile.profile_records if r.sensitivity >= .7 and str(r.value).strip()]
            candidates = [(str(r.value).strip().lower(), str(r.knowledge).lower(), str(r.type).lower()) for r in sensitive_records[:1]]
            if not candidates:
                continue
            positive = candidates[0]
            negatives = [(str(r.value).strip().lower(), str(r.knowledge).lower(), str(r.type).lower()) for p in profiles.values() for r in p.profile_records if r.sensitivity >= .7 and str(r.value).strip() and str(r.value).strip().lower() != positive[0]][:1]
            for label, target in [(True, positive), (False, negatives[0] if negatives else ("__unseen_decoy__","unseen","unseen"))]:
                pred=predict(card,[target])
                rows.append({'method':method,'request_id':task.request_id,'split':args.split,'target_present':label,'predicted_exposure':pred,'correct':pred==label,'card_sha256':__import__('hashlib').sha256(card.encode()).hexdigest()})
    groups={}
    for method in METHODS:
        rs=[r for r in rows if r['method']==method]; tp=sum(r['target_present'] and r['predicted_exposure'] for r in rs); fn=sum(r['target_present'] and not r['predicted_exposure'] for r in rs); fp=sum(not r['target_present'] and r['predicted_exposure'] for r in rs); tn=sum(not r['target_present'] and not r['predicted_exposure'] for r in rs)
        groups[method]={'n':len(rs),'tp':tp,'fn':fn,'fp':fp,'tn':tn,'attack_tpr':tp/(tp+fn) if tp+fn else None,'attack_fpr':fp/(fp+tn) if fp+tn else None,'attack_accuracy':(tp+tn)/len(rs) if rs else None}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps({'scope':'independent shadow attribute-inference evaluator; not part of MM-FOPD policy','split':args.split,'metrics':groups,'rows':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(groups,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
