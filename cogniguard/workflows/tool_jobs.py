"""LangGraph scheduling for first-party one-off research and data tools.

Tool internals remain ordinary Python. Only an explicit, allowlisted CLI job
can execute them; default invocation materializes a plan without running code.
Raw tool output stays in local diagnostic files and never enters graph state or
LangSmith telemetry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from cogniguard.observability.telemetry import LangSmithMonitor, SafeTelemetry
from core.paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
TOOL_RESULTS_ROOT = ROOT / "experiments" / "results" / "langgraph_tool_jobs"
TOOL_TREES = tuple(
    ROOT / name
    for name in (
        "experiments",
        "protection",
        "scripts",
        "cogniguard",
        "third_party/editguard",
        "deploy",
    )
)
DENIED_PARTS = {
    "external_data",
    "tests",
    "test",
    "__pycache__",
    "archive",
    "results",
    "data",
    "models",
    "artifacts",
    "logs",
    ".cache",
    ".git",
    ".venv",
    ".venv-langgraph",
    "node_modules",
}
MAIN_GUARD = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]")
MODULE_NAME = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*\Z")
SECRET_OPTION = re.compile(
    r"^--(?:[a-z0-9_-]*[-_])?(?:api[-_]?key|access[-_]?token|auth[-_]?token|"
    r"refresh[-_]?token|hf[-_]?token|token|password|passphrase|secret|"
    r"credential|private[-_]?key)(?:=|$)",
    re.I,
)
OUTPUT_OPTIONS = (
    "--output",
    "--output-root",
    "--output-dir",
    "--output-folder",
    "--output_root",
    "--output_dir",
    "--results-root",
    "--results-dir",
    "--results_summary_dir",
    "--out",
    "--out-dir",
    "--out_dir",
)

OFFLINE_TOOLS = frozenset(
    {
        "experiments.teacher_security.offline_runner",
        "experiments.communication_security.offline_runner",
        "experiments.common.plot_joint_sampling",
        "experiments.common.plot_joint_synergy",
        "experiments.c2rag_v3.aggregate_attacks",
        "experiments.c2rag_v3.aggregate_pairs",
        "experiments.c2rag_v3.finalize_development_table",
        "experiments.c2rag_v3.package_v5",
        "experiments.c2rag_v3.reevaluate_cumulative",
        "experiments.evaluation.eval_fopd",
        "experiments.evaluation.eval_c2rag",
        "experiments.evaluation.eval_unified",
        "experiments.evaluation.eval_joint_synergy",
        "experiments.evaluation.eval_joint_synergy_sampling",
        "experiments.evaluation.eval_cross_layer_synergy",
        "experiments.evaluation.eval_feedback_loops",
        "experiments.evaluation.cg_v3_replay",
        "experiments.formal_v2.run_formal",
        "experiments.formal_v2.run_preflight",
        "experiments.mmfopd_v3.runner",
        "experiments.mmfopd_v3.expand_profiles",
        "experiments.mmfopd_uci.runner",
        "experiments.mmfopd_uci.alignment_probe",
        "experiments.mmfopd_uci.portuguese_transfer_probe",
        "experiments.three_layer_refinement.privacy",
        "experiments.three_layer_refinement.round_summary",
        "experiments.focused.agent_pollution.runner",
        "experiments.rag_real.reranker_pair_audit",
        "experiments.text_watermark.reanalysis_source_anchor",
        "experiments.text_watermark.source_anchor_specificity_audit",
    }
)
MODEL_TOOLS = frozenset(
    {
        "experiments.teacher_security.real_runner",
        "experiments.communication_security.runner",
        "experiments.communication_security.real_runner",
        "experiments.communication_security.evidence_runner",
        "experiments.c2rag_v3.runner",
        "experiments.formal_v2_llm.run_llm_in_loop",
        "experiments.formal_v2_output.run_output_protection",
        "experiments.rag_real.retrieval",
        "experiments.rag_real.control_probe",
        "experiments.rag_real.alignment_probe",
        "experiments.rag_real.scifact_train_calibration",
        "experiments.three_layer_refinement.rag",
        "experiments.three_layer_refinement.rag_model",
        "experiments.three_layer_refinement.rag_replay",
        "experiments.three_layer_refinement.qasc_retrieval",
        "experiments.three_layer_refinement.watermark",
        "protection.audit_trace.src.main",
        "protection.Layer2_hsw_st_minimal.src.main",
    }
)
NETWORK_TOOLS = frozenset(
    {
        "experiments.three_layer_refinement.qasc_data",
        "experiments.rag_real.prepare",
        "experiments.c2rag_v3.run_open_retrieval_pilot",
        "experiments.c2rag_v3.run_local_open_retrieval_pilot",
        "experiments.dataset_builders.build_math_datasets",
    }
)
UNAVAILABLE_ARCHIVE_PREFIXES = ("protection.Layer1_fopd_c2rag.",)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_tool_module(module: str) -> str:
    """Resolve historical CLI names without recreating old root packages."""
    for old, new in (
        ("backend.app.", "cogniguard."),
        ("dfg_locguard.", "protection.supporting.image_watermark."),
        ("protection.image_watermark.", "protection.supporting.image_watermark."),
        ("protection.cg_guardrails.", "protection.supporting.cg_guardrails."),
        ("code.", "third_party.editguard."),
    ):
        if module.startswith(old):
            return new + module[len(old) :]
    return module


def _public_module(relative: Path) -> str:
    """Keep historical Layer module names after the files moved under legacy/layers."""
    parts = relative.with_suffix("").parts
    if parts[:3] == ("protection", "legacy", "layers"):
        parts = ("protection",) + parts[3:]
    return ".".join(parts)


def _module_file(module: str) -> Path:
    direct = ROOT.joinpath(*module.split(".")).with_suffix(".py")
    if direct.is_file():
        return direct
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "protection" and parts[1].startswith("Layer"):
        legacy = ROOT.joinpath("protection", "legacy", "layers", *parts[1:]).with_suffix(".py")
        if legacy.is_file():
            return legacy
    return direct


def _source_file(module: str) -> Path:
    module = canonical_tool_module(module)
    if module in {
        "scripts.run_tests",
        "cogniguard.cli",
        "cogniguard.__main__",
        "cogniguard.api.__main__",
        "cogniguard.workflows.__main__",
    }:
        raise ValueError("Repository entrypoints are not research tools")
    if not MODULE_NAME.fullmatch(module) or not module.startswith(
        (
            "experiments.",
            "protection.",
            "scripts.",
            "cogniguard.",
            "third_party.editguard.",
            "protection.supporting.image_watermark.",
            "deploy.",
        )
    ):
        raise ValueError("Tool name must be a first-party dotted Python module")
    path = _module_file(module)
    if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Unknown first-party tool")
    relative = path.relative_to(ROOT)
    if any(part.lower() in DENIED_PARTS for part in relative.parts[:-1]) or path.name.startswith(
        "test_"
    ):
        raise ValueError("Vendored, test and artifact scripts are not scheduled")
    if not MAIN_GUARD.search(path.read_text(encoding="utf-8", errors="replace")):
        raise ValueError("Module has no direct CLI entrypoint")
    return path


def _risk(module: str) -> str:
    module = canonical_tool_module(module)
    if module.startswith(UNAVAILABLE_ARCHIVE_PREFIXES):
        return "unavailable_archive"
    if module in OFFLINE_TOOLS:
        return "offline"
    if module in MODEL_TOOLS or module.startswith("experiments.focused."):
        return "model"
    if module in NETWORK_TOOLS:
        return "network"
    return "unreviewed"


def list_tools() -> list[dict[str, str]]:
    """Read source names only; discovering tools never imports or runs them."""
    items = []
    for tree in TOOL_TREES:
        if not tree.is_dir():
            continue
        for directory, child_dirs, filenames in os.walk(tree):
            child_dirs[:] = [name for name in child_dirs if name.lower() not in DENIED_PARTS]
            for filename in filenames:
                if (
                    not filename.endswith(".py")
                    or filename == "__init__.py"
                    or filename.startswith("test_")
                ):
                    continue
                path = Path(directory) / filename
                relative = path.relative_to(ROOT)
                module = _public_module(relative)
                try:
                    _source_file(module)
                except ValueError:
                    continue
                items.append({"module": module, "risk": _risk(module)})
    return sorted(items, key=lambda item: item["module"])


@dataclass(frozen=True)
class ToolRequest:
    module: str
    args: tuple[str, ...]
    output: Path
    execute: bool = False
    allow_model_calls: bool = False
    allow_network: bool = False
    allow_unreviewed: bool = False
    allow_default_output: bool = False
    timeout_seconds: int = 300
    seed: int = 20261013

    def __post_init__(self):
        object.__setattr__(self, "module", canonical_tool_module(self.module))


class ToolState(TypedDict, total=False):
    stage: str
    planned: bool
    completed: bool
    exit_code: int
    timed_out: bool


@dataclass
class ToolFrame:
    request: ToolRequest
    recorder: SafeTelemetry
    source: Path | None = None
    risk: str = ""
    output: Path | None = None
    owned_output: bool = False
    command: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    frame: ToolFrame


def validate(state: ToolState, runtime: Runtime[ToolContext]):
    f = runtime.context.frame
    with f.recorder.span("tool_validate") as metrics:
        request = f.request
        f.source = _source_file(request.module)
        f.risk = _risk(request.module)
        f.output = Path(request.output).resolve()
        if (
            not f.output.is_relative_to(TOOL_RESULTS_ROOT.resolve())
            or f.output == TOOL_RESULTS_ROOT.resolve()
        ):
            raise ValueError(
                "Tool output must be a fresh directory under experiments/results/langgraph_tool_jobs"
            )
        if f.output.exists():
            raise FileExistsError(f"Tool output already exists: {f.output}")
        if not 1 <= request.timeout_seconds <= 3600:
            raise ValueError("timeout_seconds must be 1..3600")
        if not 0 <= request.seed < 2**32:
            raise ValueError("seed must be an unsigned 32-bit integer")
        if any(SECRET_OPTION.match(arg) for arg in request.args):
            raise ValueError(
                "Pass secrets via the existing local credential store, never CLI arguments"
            )
        output_override = any(
            arg == option or arg.startswith(option + "=")
            for arg in request.args
            for option in OUTPUT_OPTIONS
        )
        help_only = any(arg in {"--help", "-h", "--version"} for arg in request.args)
        if request.execute:
            if f.risk == "unavailable_archive":
                raise PermissionError(
                    "Archived Layer1 entry lacks its original fopd_c2rag_mvp package "
                    "and config/data; use the active student_profile graph path"
                )
            if not (output_override or help_only or request.allow_default_output):
                raise PermissionError(
                    "Specify the script's own output flag after --, or explicitly allow its default output"
                )
            if f.risk == "model" and not request.allow_model_calls:
                raise PermissionError("Model tool requires --allow-model-calls")
            if f.risk == "network" and not request.allow_network:
                raise PermissionError("Network tool requires --allow-network")
            if f.risk == "unreviewed" and not (
                request.allow_unreviewed and request.allow_model_calls and request.allow_network
            ):
                raise PermissionError("Unreviewed tool requires all three explicit risk flags")
        metrics.update(
            validated=1,
            risk_code={
                "offline": 0,
                "model": 1,
                "network": 2,
                "unreviewed": 3,
                "unavailable_archive": 4,
            }[f.risk],
        )
    return {"stage": "validate"}


def freeze(state: ToolState, runtime: Runtime[ToolContext]):
    f = runtime.context.frame
    with f.recorder.span("tool_freeze") as metrics:
        f.output.parent.mkdir(parents=True, exist_ok=True)
        f.output.mkdir(exist_ok=False)
        f.owned_output = True
        execution_kind = (
            "script" if f.request.module.startswith("third_party.editguard.") else "module"
        )
        f.command = (
            [sys.executable, "-B", str(f.source)]
            if execution_kind == "script"
            else [sys.executable, "-B", "-m", f.request.module]
        ) + list(f.request.args)
        f.result = {
            "status": "PLANNED" if not f.request.execute else "RUNNING",
            "orchestrator": "langgraph",
            "module": f.request.module,
            "execution_kind": execution_kind,
            "risk": f.risk,
            "source_sha256": _sha(f.source),
            "args_sha256": hashlib.sha256(json.dumps(f.request.args).encode()).hexdigest(),
            "arg_count": len(f.request.args),
            "seed": f.request.seed,
            "timeout_seconds": f.request.timeout_seconds,
            "execute": f.request.execute,
            "script_output_override_present": any(
                arg == option or arg.startswith(option + "=")
                for arg in f.request.args
                for option in OUTPUT_OPTIONS
            ),
            "allow_default_output": f.request.allow_default_output,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_outputs_local_only": True,
        }
        (f.output / "manifest.json").write_text(
            json.dumps(f.result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metrics.update(source_bytes=f.source.stat().st_size)
    return {"stage": "freeze"}


def execute(state: ToolState, runtime: Runtime[ToolContext]):
    f = runtime.context.frame
    if not f.request.execute:
        return {"stage": "execute", "planned": True, "completed": False}
    with f.recorder.span("tool_execute") as metrics:
        env = dict(os.environ)
        env.update(
            PYTHONHASHSEED=str(f.request.seed),
            PYTHONIOENCODING="utf-8",
            LANGSMITH_TRACING="false",
            LANGCHAIN_TRACING_V2="false",
        )
        with (
            (f.output / "stdout.txt").open("wb") as stdout,
            (f.output / "stderr.txt").open("wb") as stderr,
        ):
            try:
                result = subprocess.run(
                    f.command,
                    cwd=ROOT,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=f.request.timeout_seconds,
                    check=False,
                )
                exit_code, timed_out = result.returncode, False
            except subprocess.TimeoutExpired:
                exit_code, timed_out = 124, True
        f.result.update(
            status="TIMED_OUT" if timed_out else "COMPLETED" if exit_code == 0 else "FAILED",
            exit_code=exit_code,
            timed_out=timed_out,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        metrics.update(exit_code=exit_code, timed_out=int(timed_out))
    return {"stage": "execute", "completed": True, "exit_code": exit_code, "timed_out": timed_out}


def collect(state: ToolState, runtime: Runtime[ToolContext]):
    f = runtime.context.frame
    with f.recorder.span("tool_collect") as metrics:
        logs = {}
        for name in ("stdout.txt", "stderr.txt"):
            path = f.output / name
            if path.exists():
                logs[name] = {"bytes": path.stat().st_size, "sha256": _sha(path)}
        f.result["local_logs"] = logs
        (f.output / "manifest.json").write_text(
            json.dumps(f.result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metrics.update(log_count=len(logs))
    return {"stage": "collect"}


def build_tool_graph():
    builder = StateGraph(ToolState, context_schema=ToolContext)
    for name, fn in (
        ("validate", validate),
        ("freeze", freeze),
        ("execute", execute),
        ("collect", collect),
    ):
        builder.add_node(name, fn)
    builder.add_edge(START, "validate")
    builder.add_edge("validate", "freeze")
    builder.add_edge("freeze", "execute")
    builder.add_edge("execute", "collect")
    builder.add_edge("collect", END)
    return builder.compile(checkpointer=False, name="CogniGuardToolJobs")


TOOL_GRAPH = build_tool_graph()


def run_tool_job(request: ToolRequest, monitor: LangSmithMonitor | None = None) -> dict[str, Any]:
    monitor = monitor or LangSmithMonitor()
    recorder = SafeTelemetry()
    frame = ToolFrame(request, recorder)
    try:
        with tracing_context(enabled=False):
            TOOL_GRAPH.invoke({}, context=ToolContext(frame))
    finally:
        if frame.owned_output and frame.output is not None and frame.output.exists():
            (frame.output / "node-trace.json").write_text(
                json.dumps(recorder.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        monitor.export(recorder)
    return {**frame.result, "output": str(frame.output), "langsmith": monitor.last_status}
