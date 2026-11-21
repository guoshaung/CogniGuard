"""One navigable experiment inventory over reviewed and historical graph jobs.

Discovery never imports a script. Only reviewed entries receive managed output
arguments; all other entries keep the stricter historical tool policy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cogniguard.observability.telemetry import LangSmithMonitor

from . import tool_jobs
from .experiments import ROOT, run_matrix


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    family: str
    module: str | None
    output_option: str | None
    risk: str
    description: str


SPECS = (
    ExperimentSpec(
        "cgc-science-communication",
        "safety-control",
        "experiments.communication_security.evidence_runner",
        "--output",
        "model",
        "Three paired QASC tasks, real relay/synthesis, final-only vs per-hop source checking",
    ),
    ExperimentSpec(
        "refine-qasc-retrieval",
        "copyright",
        "experiments.three_layer_refinement.qasc_retrieval",
        "--output",
        "model",
        "QASC question-only retrieval over a global curated fact corpus, not official 17M corpus",
    ),
    ExperimentSpec(
        "cgc-communication-offline",
        "safety-control",
        "experiments.communication_security.offline_runner",
        "--output",
        "offline",
        "Five-node communication DAG propagation and boundary fixtures",
    ),
    ExperimentSpec(
        "cgc-communication-real",
        "safety-control",
        "experiments.communication_security.real_runner",
        "--output",
        "model",
        "Two real relay teachers plus synthesis, at most 24 model calls",
    ),
    ExperimentSpec(
        "refine-privacy",
        "privacy",
        "experiments.three_layer_refinement.privacy",
        "--output",
        "offline",
        "Exploratory real-UCI task-slot adaptation with equal field budget",
    ),
    ExperimentSpec(
        "refine-rag-evidence",
        "copyright",
        "experiments.three_layer_refinement.rag",
        "--output",
        "model",
        "Matched real-corpus evidence utility and measured disclosure",
    ),
    ExperimentSpec(
        "refine-rag-model",
        "copyright",
        "experiments.three_layer_refinement.rag_model",
        "--output",
        "model",
        "Bounded real-model pilot of trusted internal transformation and short fact release",
    ),
    ExperimentSpec(
        "refine-watermark",
        "text-watermark",
        "experiments.three_layer_refinement.watermark",
        "--output",
        "model",
        "Paired context-length watermark ablation with frozen clean calibration",
    ),
    ExperimentSpec(
        "teacher-security-offline",
        "safety-control",
        "experiments.teacher_security.offline_runner",
        "--output",
        "offline",
        "New teaching-security suite: independent scoring and frozen dataset",
    ),
    ExperimentSpec(
        "teacher-security-real",
        "safety-control",
        "experiments.teacher_security.real_runner",
        "--output",
        "model",
        "Frozen pilot with ablations and adaptive two-attacker development search",
    ),
    ExperimentSpec(
        "comparison-matrix",
        "cross-module",
        None,
        None,
        "plan_dependent",
        "Versioned baseline/ablation and teacher DAG matrix",
    ),
    ExperimentSpec(
        "mmfopd-uci",
        "privacy",
        "experiments.mmfopd_uci.runner",
        "--output",
        "offline",
        "UCI student-performance equal-budget evaluation",
    ),
    ExperimentSpec(
        "mmfopd-uci-alignment",
        "privacy",
        "experiments.mmfopd_uci.alignment_probe",
        "--output",
        "offline",
        "UCI field-alignment diagnosis",
    ),
    ExperimentSpec(
        "mmfopd-uci-transfer",
        "privacy",
        "experiments.mmfopd_uci.portuguese_transfer_probe",
        "--output",
        "offline",
        "UCI Portuguese-subject transfer stress test",
    ),
    ExperimentSpec(
        "mmfopd-v3",
        "privacy",
        "experiments.mmfopd_v3.runner",
        "--output",
        "offline",
        "MM-FOPD V3 baseline and component study",
    ),
    ExperimentSpec(
        "c2rag-v3",
        "copyright",
        "experiments.c2rag_v3.runner",
        "--output",
        "model",
        "C2-RAG V3 controlled retrieval study",
    ),
    ExperimentSpec(
        "rag-pair-audit",
        "copyright",
        "experiments.rag_real.reranker_pair_audit",
        "--output",
        "offline",
        "Paired real-retrieval ranking audit",
    ),
    ExperimentSpec(
        "rag-control-probe",
        "copyright",
        "experiments.rag_real.control_probe",
        "--output",
        "model",
        "Real-corpus retrieval and control probe",
    ),
    ExperimentSpec(
        "rag-scifact-calibration",
        "copyright",
        "experiments.rag_real.scifact_train_calibration",
        "--output",
        "model",
        "Train-only SciFact fusion calibration and test evaluation",
    ),
    ExperimentSpec(
        "formal-v2",
        "cross-module",
        "experiments.formal_v2.run_formal",
        "--output-root",
        "offline",
        "Formal V2 offline matrix",
    ),
    ExperimentSpec(
        "teacher-pollution-lab",
        "safety-control",
        "experiments.focused.agent_pollution.runner",
        "--output",
        "offline",
        "Synthetic compromised/colluding teacher A/B laboratory",
    ),
    ExperimentSpec(
        "teacher-pollution-real",
        "safety-control",
        "experiments.focused.agent_pollution.real_runner",
        "--output",
        "model",
        "Bounded MiMo pilot on the synthetic compromised-teacher cases",
    ),
)
CATALOG = {spec.name: spec for spec in SPECS}
BY_MODULE = {spec.module: spec for spec in SPECS if spec.module}
FAMILIES = (
    "privacy",
    "copyright",
    "text-watermark",
    "image-watermark",
    "safety-control",
    "datasets",
    "cross-module",
    "operations",
)


def _family(module: str) -> str:
    if module.startswith(
        ("experiments.mmfopd", "protection.student_profile.", "protection.Layer1_fopd_c2rag.")
    ):
        return "privacy"
    if module.startswith(("experiments.c2rag", "experiments.rag_real.")):
        return "copyright"
    if module.startswith(
        (
            "experiments.text_watermark.",
            "experiments.formal_v2_output.",
            "protection.Layer2_hsw_st_minimal.",
            "protection.audit_trace.",
        )
    ):
        return "text-watermark"
    if module.startswith(
        ("protection.supporting.image_watermark.", "third_party.editguard.", "scripts.server.")
    ):
        return "image-watermark"
    if module.startswith(
        (
            "experiments.teacher_security.",
            "experiments.focused.",
            "experiments.attacks.",
            "experiments.evaluation.",
            "experiments.demo_multiagent_system",
            "cogniguard.",
        )
    ):
        return "safety-control"
    if module.startswith(
        (
            "experiments.dataset_builders.",
            "scripts.build_",
            "scripts.download_",
            "scripts.generate_",
        )
    ):
        return "datasets"
    if module.startswith(
        (
            "experiments.formal_v2.",
            "experiments.formal_v2_llm.",
            "experiments.ablation.",
            "experiments.baselines.",
            "experiments.common.",
        )
    ):
        return "cross-module"
    return "operations"


def _tier(spec: ExperimentSpec) -> str:
    if spec.risk == "unavailable_archive":
        return "unavailable"
    return "managed" if spec.name in CATALOG else "compatible"


def _record(spec: ExperimentSpec) -> dict[str, str | None]:
    return {
        **vars(spec),
        "tier": _tier(spec),
        "output_mode": "managed_artifacts"
        if spec.output_option
        else "matrix"
        if spec.module is None
        else "script_defined",
    }


def _all_specs() -> list[ExperimentSpec]:
    specs = [CATALOG["comparison-matrix"]]
    for item in tool_jobs.list_tools():
        module = item["module"]
        reviewed = BY_MODULE.get(module)
        if reviewed is not None:
            if reviewed.risk != item["risk"]:
                raise RuntimeError("Catalog risk disagrees with reviewed tool policy")
            specs.append(reviewed)
        else:
            specs.append(
                ExperimentSpec(
                    module,
                    _family(module),
                    module,
                    None,
                    item["risk"],
                    "First-party CLI; script output and side effects require individual review",
                )
            )
    return specs


def list_experiments(*, family: str | None = None) -> list[dict[str, str | None]]:
    if family is not None and family not in FAMILIES:
        raise ValueError(f"Unknown experiment family: {family}")
    records = [_record(spec) for spec in _all_specs() if family is None or spec.family == family]
    order = {name: index for index, name in enumerate(FAMILIES)}
    rank = {"managed": 0, "compatible": 1, "unavailable": 2}
    return sorted(records, key=lambda row: (order[row["family"]], rank[row["tier"]], row["name"]))


def inventory_summary(records: list[dict[str, str | None]]) -> dict:
    return {
        "schema_version": 1,
        "count": len(records),
        "tiers": {
            tier: sum(row["tier"] == tier for row in records)
            for tier in ("managed", "compatible", "unavailable")
        },
        "families": {
            family: sum(row["family"] == family for row in records)
            for family in FAMILIES
            if any(row["family"] == family for row in records)
        },
    }


def format_inventory(records: list[dict[str, str | None]], *, show_all: bool = False) -> str:
    summary = inventory_summary(records)
    counts = summary["tiers"]
    lines = [
        f"CogniGuard experiments: {summary['count']} entries "
        f"({counts['managed']} managed, {counts['compatible']} compatible, "
        f"{counts['unavailable']} unavailable)"
    ]
    for family, count in summary["families"].items():
        lines.append(f"\n{family} ({count})")
        group = [row for row in records if row["family"] == family]
        for tier in ("managed", "compatible", "unavailable"):
            members = [row for row in group if row["tier"] == tier]
            if not members:
                continue
            lines.append(f"  {tier} ({len(members)})")
            if tier == "managed" or show_all:
                for row in members:
                    lines.append(f"    {row['name']}  [{row['risk']}]")
            else:
                namespaces: dict[str, int] = {}
                for row in members:
                    parts = row["module"].split(".")
                    if parts[:3] == ["protection", "supporting", "image_watermark"]:
                        namespace = ".".join(parts[:4])
                    else:
                        namespace = (
                            parts[0]
                            if parts[0] == "scripts" and parts[1] != "server"
                            else ".".join(parts[:2])
                        )
                    namespaces[namespace] = namespaces.get(namespace, 0) + 1
                for namespace, total in sorted(
                    namespaces.items(), key=lambda item: (-item[1], item[0])
                ):
                    lines.append(f"    {namespace}/  {total}")
                lines.append(f"    Use --all --family {family} for module names")
    return "\n".join(lines)


def resolve_experiment(name: str) -> ExperimentSpec:
    name = tool_jobs.canonical_tool_module(name)
    if name in CATALOG:
        return CATALOG[name]
    if name in BY_MODULE:
        return BY_MODULE[name]
    for item in tool_jobs.list_tools():
        if item["module"] == name:
            return ExperimentSpec(
                name,
                _family(name),
                name,
                None,
                item["risk"],
                "First-party CLI; script output and side effects require individual review",
            )
    raise ValueError(f"Unknown experiment: {name}")


def describe_experiment(name: str) -> dict[str, str | None]:
    return _record(resolve_experiment(name))


def _save_index(output: Path, spec: ExperimentSpec, status: str, manifest: Path) -> dict:
    if not manifest.is_file():
        raise RuntimeError("Graph runner did not create a manifest")
    index = {
        "schema_version": 1,
        "orchestrator": "langgraph",
        "name": spec.name,
        "module": spec.module,
        "family": spec.family,
        "tier": _tier(spec),
        "output_mode": _record(spec)["output_mode"],
        "risk": spec.risk,
        "status": status,
        "manifest": manifest.name,
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with (output / "experiment-index.json").open("x", encoding="utf-8") as stream:
        json.dump(index, stream, ensure_ascii=False, indent=2)
    return index


def run_experiment(
    name: str,
    output: Path,
    *,
    execute: bool = False,
    plan: Path | None = None,
    allow_model_calls: bool = False,
    allow_network: bool = False,
    allow_unreviewed: bool = False,
    allow_default_output: bool = False,
    timeout_seconds: int = 300,
    seed: int = 20261013,
    script_args: tuple[str, ...] = (),
    langsmith: bool = False,
) -> dict:
    """Use one result index and fresh output directory for either graph lane."""
    spec = resolve_experiment(name)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Experiment output already exists: {output}")
    if spec.module is None:
        if script_args:
            raise ValueError("Script arguments do not apply to comparison-matrix")
        summary = run_matrix(
            plan or ROOT / "configs/langgraph-experiments.yaml",
            output,
            execute=execute,
            allow_model_calls=allow_model_calls,
            monitor=LangSmithMonitor(enabled=langsmith),
        )
        status = (
            "FAILED"
            if summary["failed_jobs"]
            else "COMPLETED"
            if execute and any(job["status"] == "completed" for job in summary["jobs"])
            else "PLANNED"
        )
    else:
        if plan is not None:
            raise ValueError("--plan applies only to comparison-matrix")
        if spec.output_option and script_args:
            raise ValueError(
                "Managed experiments fix their arguments; use the historical module through tools for custom options"
            )
        if not output.is_relative_to(tool_jobs.TOOL_RESULTS_ROOT.resolve()):
            raise ValueError(
                "Non-matrix output must be under experiments/results/langgraph_tool_jobs"
            )
        artifact_dir = output / "artifacts"
        forwarded = (spec.output_option, str(artifact_dir)) if spec.output_option else script_args
        summary = tool_jobs.run_tool_job(
            tool_jobs.ToolRequest(
                spec.module,
                tuple(forwarded),
                output,
                execute=execute,
                allow_model_calls=allow_model_calls,
                allow_network=allow_network,
                allow_unreviewed=allow_unreviewed,
                allow_default_output=allow_default_output,
                timeout_seconds=timeout_seconds,
                seed=seed,
            ),
            monitor=LangSmithMonitor(enabled=langsmith),
        )
        status = summary["status"]
    index = _save_index(output, spec, status, output / "manifest.json")
    return {**index, "output": str(output), "details": summary}
