from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from pathlib import Path
from typing import Any

from experiments.baselines.copyright_baselines import build_copyright_external_baselines
from protection.common.schemas import TeacherResource
from protection.common.text_utils import cosine_text, lcs_ratio, read_jsonl, write_json
from protection.student_profile.src.pipeline.run_demo import load_config, load_resources
from protection.teacher_resource.src.c2rag.exposure_budget import ExposureBudget
from protection.teacher_resource.src.c2rag.return_policy import (
    produce_controlled_resource,
    render_controlled_resource,
)


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return "|".join(f"{key}={item}" for key, item in value.items())
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})


def plain_rag_response(resource: TeacherResource, round_idx: int) -> str:
    if round_idx == 0:
        return resource.content[:30]
    if round_idx < 3:
        return resource.content[: min(len(resource.content), 45 + round_idx * 12)]
    return resource.content


def leakage_score(text: str, resource: TeacherResource) -> float:
    return max(cosine_text(text, resource.content), lcs_ratio(text, resource.content))


def _resource_with_policy(resource: TeacherResource, **updates: Any) -> TeacherResource:
    return replace(resource, policy=replace(resource.policy, **updates))


def _guardrail_only_response(
    resource: TeacherResource,
    prompt: str,
    round_idx: int,
    config: dict[str, Any],
) -> tuple[str, str]:
    lower = prompt.lower()
    blocked_intents = (
        "verbatim",
        "full text",
        "original",
        "continue",
        "copy",
        "原文",
        "逐字",
        "完整",
        "继续",
        "不要省略",
        "讲义",
        "所有内容",
    )
    if round_idx >= 2 or any(token in lower for token in blocked_intents):
        return (
            "The protected teaching resource cannot be reconstructed verbatim. "
            "Use a concept-level explanation or a newly generated practice item instead.",
            "refuse",
        )
    text, _ = render_controlled_resource(resource, "summary", config)
    return text, "summary"


def _append_row(
    rows: list[dict[str, Any]],
    *,
    round_idx: int,
    attack: dict[str, Any],
    method: str,
    return_mode: str,
    output: str,
    exposure: float,
    resource: TeacherResource,
    source_trace: dict[str, Any] | None = None,
    baseline_family: str = "",
    baseline_note: str = "",
) -> None:
    trace = source_trace or {}
    rows.append(
        {
            "round": round_idx + 1,
            "attack_id": attack.get("attack_id", f"atk_{round_idx + 1:03d}"),
            "prompt": attack.get("prompt", ""),
            "method": method,
            "return_mode": return_mode,
            "output": output,
            "leakage": leakage_score(output, resource),
            "exposure": exposure,
            "availability": int(return_mode != "refuse"),
            "is_variant": int(return_mode == "variant"),
            "is_quote": int(return_mode == "quote"),
            "is_refusal": int(return_mode == "refuse"),
            "trace_owner": trace.get("trace_owner", ""),
            "trace_scope": trace.get("trace_scope", ""),
            "policy_reason": trace.get("policy_reason", ""),
            "quote_span_hash": trace.get("quote_span_hash", ""),
            "resource_provenance_commitment": trace.get("resource_provenance_commitment", ""),
            "baseline_family": baseline_family,
            "baseline_note": baseline_note,
        }
    )


def _summarize_method(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {
            "avg_leakage": 0.0,
            "max_leakage": 0.0,
            "reconstruction_success_rate": 0.0,
            "avg_exposure": 0.0,
            "availability_rate": 0.0,
            "variant_rate": 0.0,
            "quote_rate": 0.0,
            "refuse_rate": 0.0,
        }
    n = len(rows)
    return {
        "avg_leakage": sum(float(r["leakage"]) for r in rows) / n,
        "max_leakage": max(float(r["leakage"]) for r in rows),
        "reconstruction_success_rate": sum(float(r["leakage"]) >= 0.65 for r in rows) / n,
        "avg_exposure": sum(float(r["exposure"]) for r in rows) / n,
        "availability_rate": sum(int(r["availability"]) for r in rows) / n,
        "variant_rate": sum(int(r["is_variant"]) for r in rows) / n,
        "quote_rate": sum(int(r["is_quote"]) for r in rows) / n,
        "refuse_rate": sum(int(r["is_refusal"]) for r in rows) / n,
    }


def simulate(config_path: str | Path) -> dict[str, Any]:
    config = load_config(config_path)
    project_root = Path(__file__).resolve().parents[2]
    teacher_root = project_root / "protection" / "teacher_resource"
    experiment_root = project_root / "experiments"
    resources = load_resources(teacher_root / "data/teacher_resources.jsonl")
    attacks = read_jsonl(
        experiment_root / "attacks" / "data" / "copyright_attack_cases.jsonl"
    )
    resource = max(resources, key=lambda r: r.copyright_level)
    resource_no_variant = _resource_with_policy(resource, allow_variant=False)
    full_budget = ExposureBudget(config)
    no_variant_budget = ExposureBudget(config)
    rows: list[dict[str, Any]] = []

    for idx, attack in enumerate(attacks):
        plain = plain_rag_response(resource, idx)
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="PlainRAG",
            return_mode="quote",
            output=plain,
            exposure=float(idx + 1),
            resource=resource,
            baseline_family="weak_baseline",
            baseline_note="Unprotected RAG returns increasingly large source excerpts.",
        )

        truncated = resource.content[: resource.policy.max_quote_len]
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="RAG-Truncation",
            return_mode="quote",
            output=truncated,
            exposure=float(len(truncated)) / max(len(resource.content), 1),
            resource=resource,
            baseline_family="weak_baseline",
            baseline_note="Naive fixed-length truncation without cumulative budget.",
        )

        summary_text, _ = render_controlled_resource(resource, "summary", config)
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="RAG-SummaryOnly",
            return_mode="summary",
            output=summary_text,
            exposure=leakage_score(summary_text, resource),
            resource=resource,
            baseline_family="weak_baseline",
            baseline_note="Always returns a summary, without provenance or exposure budgeting.",
        )

        guardrail_text, guardrail_mode = _guardrail_only_response(
            resource,
            str(attack.get("prompt", "")),
            idx,
            config,
        )
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="GuardrailOnly",
            return_mode=guardrail_mode,
            output=guardrail_text,
            exposure=leakage_score(guardrail_text, resource),
            resource=resource,
            baseline_family="weak_baseline",
            baseline_note="Prompt-level refusal/summary guardrail without resource-level budget.",
        )

        for baseline in build_copyright_external_baselines(
            resource=resource,
            attack=attack,
            round_idx=idx,
            candidate_plain_output=plain,
            config=config,
        ):
            _append_row(
                rows,
                round_idx=idx,
                attack=attack,
                method=baseline.method,
                return_mode=baseline.return_mode,
                output=baseline.output,
                exposure=leakage_score(baseline.output, resource),
                resource=resource,
                baseline_family=baseline.baseline_family,
                baseline_note=baseline.baseline_note,
            )

        no_budget = produce_controlled_resource(resource, ExposureBudget(config), config)
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="C2RAG-w/o-Budget",
            return_mode=no_budget.mode,
            output=no_budget.text,
            exposure=no_budget.exposure_after,
            resource=resource,
            source_trace=no_budget.source_trace,
            baseline_family="c2rag_ablation",
            baseline_note="C2-RAG without cumulative exposure memory.",
        )

        no_variant = produce_controlled_resource(resource_no_variant, no_variant_budget, config)
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="C2RAG-w/o-Variant",
            return_mode=no_variant.mode,
            output=no_variant.text,
            exposure=no_variant.exposure_after,
            resource=resource,
            source_trace=no_variant.source_trace,
            baseline_family="c2rag_ablation",
            baseline_note="C2-RAG without protected variant generation.",
        )

        controlled = produce_controlled_resource(resource, full_budget, config)
        _append_row(
            rows,
            round_idx=idx,
            attack=attack,
            method="C2RAG-full",
            return_mode=controlled.mode,
            output=controlled.text,
            exposure=controlled.exposure_after,
            resource=resource,
            source_trace=controlled.source_trace,
            baseline_family="c2rag_full",
            baseline_note="Full C2-RAG with exposure budget, controlled return, variants, and resource provenance.",
        )

    output_root = experiment_root / "results" / "attacks"
    out_csv = output_root / "copyright_reconstruction.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    method_summary = {
        method: _summarize_method([r for r in rows if r["method"] == method])
        for method in sorted({r["method"] for r in rows})
    }
    summary = {
        "methods": method_summary,
        "plain_avg_leakage": method_summary["PlainRAG"]["avg_leakage"],
        "c2rag_avg_leakage": method_summary["C2RAG-full"]["avg_leakage"],
        "c2rag_modes": [r["return_mode"] for r in rows if r["method"] == "C2RAG-full"],
    }
    write_json(output_root / "copyright_reconstruction_summary.json", summary)
    write_json(
        experiment_root / "results" / "ablation" / "c2rag_component_ablation.json",
        {
            "rows": rows,
            "summary": method_summary,
            "ablation_note": (
                "C2RAG-full is compared with no exposure budget, no variant generation, "
                "summary-only, truncation-only, guardrail-only, and PlainRAG baselines."
            ),
        },
    )
    ablation_root = experiment_root / "results" / "ablation"
    baselines_root = experiment_root / "results" / "baselines"
    write_json(
        baselines_root / "copyright_baseline_comparison.json",
        {
            "rows": rows,
            "summary": method_summary,
            "baseline_note": (
                "External copyright baselines include ProtectedMaterialDetector, MemFree-Ngram, "
                "SHIELD-Agent, BloomScrub-Rewrite, and a black-box R-CAD approximation."
            ),
        },
    )
    _write_csv(ablation_root / "c2rag_component_ablation_rows.csv", rows)
    _write_csv(
        ablation_root / "c2rag_component_ablation_summary.csv",
        [{"method": method, **values} for method, values in method_summary.items()],
    )
    _write_csv(baselines_root / "copyright_baseline_comparison_rows.csv", rows)
    _write_csv(
        baselines_root / "copyright_baseline_comparison_summary.csv",
        [{"method": method, **values} for method, values in method_summary.items()],
    )
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default="protection/student_profile/configs/default.yaml",
    )
    args = ap.parse_args()
    print(simulate(args.config))


if __name__ == "__main__":
    main()
