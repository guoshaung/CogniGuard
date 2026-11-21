"""属性推断攻击对比：FullProfile / MM-FOPD 卡片 / RuleSummary / NoProfile。

每种机制产出“释放给对手的文本表征”，对手用影子模型（在群体一半上训练）推断敏感属性 A，
在另一半上评估准确率/AUC。对比并与“显式暴露率”“高敏感选择率”对照，论证选择率不等于隐私。
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from core.access import ProfileReadPolicy
from protection.common.schemas import StudentProfile, Task
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from .population import KNOWLEDGE, make_population

ROOT = Path(__file__).resolve().parents[3]
MECHANISMS = ("FullProfile", "MM-FOPD", "RuleSummary", "NoProfile")


def config():
    return yaml.safe_load((ROOT / "configs/focused.yaml").read_text(encoding="utf-8"))


def _task(sid: str) -> Task:
    return Task(request_id="atk", student_id=sid, question=f"讲解{KNOWLEDGE}的顶点与对称轴",
                knowledge=KNOWLEDGE, difficulty="basic", need_resource=False)


def release(profile: StudentProfile, mechanism: str, settings: dict) -> str:
    """机制产出释放给对手的文本表征。"""
    task = _task(profile.student_id)
    if mechanism == "NoProfile":
        return ""
    if mechanism == "FullProfile":
        parts = [f"family_support={profile.local_only_fields.get('family_support')}"]
        for r in profile.profile_records:
            parts.append(f"{r.type}:{r.knowledge}:{r.value}:sens={r.sensitivity}")
        return " | ".join(parts)
    if mechanism == "RuleSummary":
        # 朴素摘要：保留全部记录（不做敏感度门限），但不含 local_only 显式字段。
        return " | ".join(f"{r.type}:{r.value}" for r in profile.profile_records)
    if mechanism == "MM-FOPD":
        # 真实 MM-FOPD：字段白名单+敏感度门限 → 相关性选择 → 最小卡片。
        filtered = ProfileReadPolicy(settings).filter(profile)
        selected = ProfileSelector(settings).select(filtered, task)
        card, _ = build_context_card(profile, task, selected)
        return card
    raise ValueError(mechanism)


# —— 对手特征器：只从释放文本提取信号（对所有机制统一）——
def featurize(text: str) -> list[int]:
    t = text or ""
    low_phrase = "理解不稳定" in t
    high_phrase = "掌握较稳定" in t
    mid_phrase = "基本掌握" in t
    mastery_val = None
    for tok in t.replace("|", " ").split():
        if tok.startswith("mastery:"):
            try:
                mastery_val = float(tok.split(":")[-1])
            except ValueError:
                pass
        else:
            try:
                v = float(tok)
                if 0.0 <= v <= 1.0:
                    mastery_val = v
            except ValueError:
                pass
    m_low = int(low_phrase or (mastery_val is not None and mastery_val < 0.5))
    m_mid = int(mid_phrase or (mastery_val is not None and 0.5 <= mastery_val < 0.75))
    m_high = int(high_phrase or (mastery_val is not None and mastery_val >= 0.75))
    err_sym = int("对称轴" in t)
    err_sign = int("符号" in t)
    err_formula = int("公式" in t)
    err_boundary = int("边界" in t)
    pref_visual = int("图像" in t or "visual" in t)
    pref_step = int("分步" in t or "stepwise" in t or "concise_stepwise" in t)
    explicit_low = int("family_support=low" in t)
    explicit_high = int("family_support=high" in t)
    return [m_low, m_mid, m_high, err_sym, err_sign, err_formula, err_boundary,
            pref_visual, pref_step, explicit_low, explicit_high]


def _explicit_exposed(text: str) -> bool:
    return "family_support=" in (text or "")


def attack_once(people, mechanism: str, settings: dict, seed: int) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    texts = [release(p, mechanism, settings) for p, _ in people]
    X = np.array([featurize(t) for t in texts], dtype=float)
    y = np.array([1 if a == "high" else 0 for _, a in people])
    explicit_rate = float(np.mean([_explicit_exposed(t) for t in texts]))
    # 影子/目标划分：对手在一半群体上训练推断模型，另一半评估。
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.4, random_state=seed, stratify=y)
    base_rate = float(max(yte.mean(), 1 - yte.mean()))
    if X.sum() == 0 or len(set(ytr)) < 2:
        return {"mechanism": mechanism, "attack_accuracy": base_rate, "attack_auc": 0.5,
                "base_rate": base_rate, "explicit_exposure_rate": explicit_rate, "degenerate": True}
    clf = LogisticRegression(max_iter=1000)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, 1]
    acc = float(accuracy_score(yte, clf.predict(Xte)))
    try:
        auc = float(roc_auc_score(yte, proba))
    except ValueError:
        auc = 0.5
    return {"mechanism": mechanism, "attack_accuracy": acc, "attack_auc": auc,
            "base_rate": base_rate, "explicit_exposure_rate": explicit_rate, "degenerate": False}


def run(output=None, n=300, seeds=(1, 2, 3, 4, 5)):
    from .graph import run_privacy_graph
    return run_privacy_graph(output, n, seeds)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MM-FOPD 属性推断攻击（shadow-profile）")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--n", type=int, default=300)
    args = parser.parse_args()
    out, summary = run(args.output, n=args.n)
    print(json.dumps(summary["headline"], ensure_ascii=False, indent=2))
    print(out)
