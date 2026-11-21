"""独立评估共享核心，不导入演示服务。"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from core.pipeline import ProtectionPipeline, load_inputs
from core.access import AccessScope
from protection.common.metrics import summarize_metric_rows
from protection.common.text_utils import write_json, write_jsonl
from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
from protection.teacher_resource.src.c2rag.c2rag_metrics import compute_c2rag_metrics

ROOT = Path(__file__).resolve().parents[2]


def evaluate(config_path, profiles_path, questions_path, resources_path, output=None):
    config, profiles, questions, resources = load_inputs(config_path, profiles_path, questions_path, resources_path)
    if not questions:
        raise ValueError("评估数据为空")
    output = Path(output) if output else ROOT / "experiments" / "results" / "focused" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for question in questions:
        profile = profiles[question["student_id"]]
        # 每题独立预算，避免不同学生和题目共享状态。
        result = ProtectionPipeline(config, resources).run(profile, question, access=AccessScope(profile.student_id))
        metrics = compute_fopd_metrics(profile, result.task, result.context_card, result.selected)
        metrics.update(compute_c2rag_metrics(result.controlled, result.answer, resources))
        rows.append({**result.to_dict(), "metrics": metrics})
    write_jsonl(output / "rows.jsonl", rows)
    write_json(output / "summary.json", {
        "status": "SMOKE_ONLY", "execution_mode": "offline_rule_based", "budget_scope": "per_question",
        "limitation": "单方法离线诊断，无基线或显著性检验，不支持论文优越性结论。",
        **summarize_metric_rows([row["metrics"] for row in rows]),
    })
    inputs = {name: {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
              for name, path in zip(("config", "profiles", "questions", "resources"),
                                    (config_path, profiles_path, questions_path, resources_path))}
    write_json(output / "manifest.json", {"inputs": inputs, "created_at": datetime.now(timezone.utc).isoformat()})
    return output
