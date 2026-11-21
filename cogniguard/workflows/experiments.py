"""Versioned experiment plans and subprocess-isolated LangGraph job execution."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import yaml
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from cogniguard.observability.telemetry import LangSmithMonitor, SafeTelemetry
from core.paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
VARIANTS = frozenset(
    {
        "graph_default",
        "enhanced_full",
        "enhanced_without_orthogonal",
        "enhanced_without_attention",
        "enhanced_without_bottleneck",
    }
)
FOCUSED = frozenset(
    {
        "redteam",
        "injecagent",
        "teaching",
        "multiagent",
        "cgce2e",
        "privacyattack",
        "factuality",
        "supplychain",
        "promptleak",
        "toolgov",
        "memorypoison",
    }
)
MODEL_ADAPTERS = FOCUSED - {"cgce2e", "privacyattack", "supplychain"}


def write_new(path: Path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dependencies():
    result = {}
    for name in (
        "langgraph",
        "langsmith",
        "langchain-core",
        "PyYAML",
        "pydantic",
        "pytest",
        "pyarrow",
    ):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not_installed"
    return result


def source_hashes():
    files = list((ROOT / "core").rglob("*.py"))
    for folder in (
        "cogniguard/workflows",
        "cogniguard/observability",
        "protection/common",
        "protection/student_profile/src",
        "protection/teacher_resource/src",
    ):
        files.extend((ROOT / folder).rglob("*.py"))
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(files)}


def variant_config(config, variant):
    if variant not in VARIANTS:
        raise ValueError("Unknown pipeline variant")
    result = deepcopy(config)
    if variant.startswith("enhanced_"):
        fopd = result.setdefault("fopd", {})
        fopd["use_enhanced_fopd"] = True
        fopd["components"] = {
            "use_orthogonal": True,
            "use_task_attention": True,
            "use_bottleneck": True,
        }
        key = {
            "enhanced_without_orthogonal": "use_orthogonal",
            "enhanced_without_attention": "use_task_attention",
            "enhanced_without_bottleneck": "use_bottleneck",
        }.get(variant)
        if key:
            fopd["components"][key] = False
    # The hard AccessScope / ProfileReadPolicy gate is never ablated.
    return result


def canonical_result(value):
    """Only the legacy C2 trace wall-clock timestamp is non-semantic."""
    result = deepcopy(value)
    if isinstance(result.get("source_trace"), dict):
        result["source_trace"].pop("timestamp", None)
    return result


@dataclass(frozen=True)
class Job:
    index: int
    adapter: str
    variant: str
    seed: int
    dry_run: bool
    config: str
    profiles: str
    questions: str
    resources: str
    workers: int = 2
    limit: int | None = None
    team: str | None = None
    trust_mode: str = "enforce"
    teacher_prompts: str | None = None
    teacher_teams: str | None = None
    expected_prompt_sha256: str | None = None
    expected_team_catalog_sha256: str | None = None

    def validate(self):
        if self.adapter not in FOCUSED | {"pipeline", "teacher_dag"}:
            raise ValueError("Unregistered adapter")
        if self.adapter == "pipeline" and self.variant not in VARIANTS:
            raise ValueError("Unregistered pipeline variant")
        if self.adapter in FOCUSED and self.variant != "focused_graph":
            raise ValueError("Focused jobs use the focused_graph variant")
        if self.adapter == "teacher_dag":
            from .teachers.catalog import PromptLibrary, TeamCatalog

            if self.variant != "teacher_dag" or self.trust_mode not in {"enforce", "observe_only"}:
                raise ValueError("Invalid teacher DAG variant/trust mode")
            if not self.teacher_prompts or not self.teacher_teams:
                raise ValueError("Teacher catalogs are required")
            library = PromptLibrary(self.teacher_prompts)
            catalog = TeamCatalog(self.teacher_teams, library)
            catalog.get(self.team)
            if self.expected_prompt_sha256 and library.sha256 != self.expected_prompt_sha256:
                raise ValueError("Prompt library changed after plan freeze")
            if (
                self.expected_team_catalog_sha256
                and catalog.sha256 != self.expected_team_catalog_sha256
            ):
                raise ValueError("Team catalog changed after plan freeze")
        if (
            not isinstance(self.seed, int)
            or isinstance(self.seed, bool)
            or not 0 <= self.seed < 2**32
        ):
            raise ValueError("Seed must be an unsigned 32-bit integer")
        if (
            type(self.dry_run) is not bool
            or type(self.workers) is not int
            or not 1 <= self.workers <= 4
        ):
            raise ValueError("Invalid dry_run or workers")
        if self.limit is not None and (type(self.limit) is not int or not 1 <= self.limit <= 10):
            raise ValueError("limit must be 1..10")

    def to_dict(self):
        from dataclasses import asdict

        return asdict(self)


def load_plan(path: Path) -> list[Job]:
    plan = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if (
        not isinstance(plan, dict)
        or set(plan) != {"schema_version", "jobs"}
        or plan["schema_version"] != 1
    ):
        raise ValueError("Expected schema_version: 1 and jobs only")
    if not isinstance(plan["jobs"], list) or not plan["jobs"]:
        raise ValueError("Plan must contain jobs")
    allowed = {
        "adapter",
        "variants",
        "seeds",
        "dry_run",
        "config",
        "profiles",
        "questions",
        "resources",
        "workers",
        "limit",
        "teams",
        "trust_modes",
        "teacher_prompts",
        "teacher_teams",
    }
    defaults = {
        "config": "configs/focused.yaml",
        "profiles": "protection/student_profile/data/profiles.jsonl",
        "questions": "protection/student_profile/data/student_questions.jsonl",
        "resources": "protection/teacher_resource/data/teacher_resources.jsonl",
    }
    jobs = []
    for item in plan["jobs"]:
        if not isinstance(item, dict) or set(item) - allowed:
            raise ValueError("Unknown plan fields; runtime plans cannot contain labels/oracle data")
        adapter = item.get("adapter", "pipeline")
        variants = item.get(
            "variants",
            ["graph_default"]
            if adapter == "pipeline"
            else ["teacher_dag"]
            if adapter == "teacher_dag"
            else ["focused_graph"],
        )
        seeds = item.get("seeds", [20261013])
        if (
            not isinstance(variants, list)
            or not variants
            or not isinstance(seeds, list)
            or not seeds
        ):
            raise ValueError("variants/seeds must be nonempty lists")
        if adapter != "teacher_dag" and set(item) & {
            "teams",
            "trust_modes",
            "teacher_prompts",
            "teacher_teams",
        }:
            raise ValueError("Teacher fields are only valid for the teacher_dag adapter")
        teams = item.get("teams", ["committee"]) if adapter == "teacher_dag" else [None]
        modes = item.get("trust_modes", ["enforce"]) if adapter == "teacher_dag" else ["enforce"]
        if not isinstance(teams, list) or not teams or not isinstance(modes, list) or not modes:
            raise ValueError("teams/trust_modes must be nonempty lists")
        for variant in variants:
            for seed in seeds:
                for team in teams:
                    for mode in modes:
                        paths = {
                            k: str((ROOT / item.get(k, v)).resolve()) for k, v in defaults.items()
                        }
                        job = Job(
                            len(jobs),
                            adapter,
                            variant,
                            seed,
                            item.get("dry_run", True),
                            **paths,
                            workers=item.get("workers", 2),
                            limit=item.get("limit"),
                            team=team,
                            trust_mode=mode,
                            teacher_prompts=str(
                                (
                                    ROOT
                                    / item.get("teacher_prompts", "configs/teacher-prompts.yaml")
                                ).resolve()
                            )
                            if adapter == "teacher_dag"
                            else None,
                            teacher_teams=str(
                                (
                                    ROOT / item.get("teacher_teams", "configs/teacher-teams.yaml")
                                ).resolve()
                            )
                            if adapter == "teacher_dag"
                            else None,
                            expected_prompt_sha256=sha256(
                                ROOT / item.get("teacher_prompts", "configs/teacher-prompts.yaml")
                            )
                            if adapter == "teacher_dag"
                            else None,
                            expected_team_catalog_sha256=sha256(
                                ROOT / item.get("teacher_teams", "configs/teacher-teams.yaml")
                            )
                            if adapter == "teacher_dag"
                            else None,
                        )
                        job.validate()
                        jobs.append(job)
    return jobs


def isolated_env(seed):
    env = dict(os.environ)
    env.update(
        PYTHONHASHSEED=str(seed),
        PYTHONIOENCODING="utf-8",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    return env


class AdapterExecutionError(RuntimeError):
    pass


class JobState(TypedDict, total=False):
    job_index: int
    completed: bool
    planned: bool
    artifact_count: int


@dataclass
class JobContext:
    job: Job
    directory: Path
    recorder: SafeTelemetry
    execute: bool
    allow_model_calls: bool


def validate_plan(state: JobState, runtime: Runtime[JobContext]):
    c = runtime.context
    with c.recorder.span("validate_plan") as metrics:
        c.job.validate()
        if (
            c.execute
            and c.job.adapter in MODEL_ADAPTERS
            and not c.job.dry_run
            and not c.allow_model_calls
        ):
            raise PermissionError("Real-model experiments require --allow-model-calls")
        if c.job.adapter in {"pipeline", "teacher_dag"}:
            for name in ("config", "profiles", "questions", "resources"):
                if not Path(getattr(c.job, name)).is_file():
                    raise FileNotFoundError("Missing experiment input: " + name)
        metrics["dry_run"] = not c.execute or c.job.dry_run
    return {"job_index": c.job.index}


def execute_adapter(state: JobState, runtime: Runtime[JobContext]):
    c = runtime.context
    with c.recorder.span("execute_adapter") as metrics:
        if not c.execute or (c.job.adapter in {"pipeline", "teacher_dag"} and c.job.dry_run):
            metrics["dry_run"] = True
            return {"planned": True, "completed": False}
        child = c.directory / "artifacts"
        if c.job.adapter in {"pipeline", "teacher_dag"}:
            command = [
                sys.executable,
                "-m",
                "cogniguard.workflows",
                "_worker",
                "--output",
                str(child),
            ]
            request = json.dumps(c.job.to_dict())
        else:
            command = [sys.executable, "-m", "cogniguard", c.job.adapter, "--output", str(child)]
            if c.job.adapter in MODEL_ADAPTERS:
                command.extend(["--workers", str(c.job.workers)])
                if c.job.dry_run:
                    command.append("--dry-run")
                elif c.allow_model_calls:
                    command.append("--allow-model-calls")
                if c.job.limit is not None and c.job.adapter in {
                    "teaching",
                    "multiagent",
                    "redteam",
                }:
                    command.extend(["--limit", str(c.job.limit)])
                if c.job.adapter == "injecagent":
                    command.extend(["--seed", str(c.job.seed)])
                    if c.job.limit is not None:
                        command.extend(["--per-kind", str(c.job.limit)])
            request = None
        process = subprocess.run(
            command,
            cwd=ROOT,
            input=request,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            env=isolated_env(c.job.seed),
        )
        # Raw child stdout/stderr may include model payloads or transport headers.
        # They are neither published as spans nor copied into new manifests.
        if process.returncode:
            raise AdapterExecutionError(
                "Adapter failed; inspect its own local artifacts. Exit=" + str(process.returncode)
            )
        metrics["succeeded"] = 1
        return {"planned": c.job.adapter in FOCUSED and c.job.dry_run, "completed": True}


def collect_artifacts(state: JobState, runtime: Runtime[JobContext]):
    c = runtime.context
    with c.recorder.span("collect_artifacts") as metrics:
        folder = c.directory / "artifacts"
        files = sorted(p for p in folder.rglob("*") if p.is_file()) if folder.exists() else []
        hashes = {p.relative_to(c.directory).as_posix(): sha256(p) for p in files}
        write_new(c.directory / "artifact-hashes.json", hashes)
        metrics["artifact_count"] = len(files)
    return {"artifact_count": len(files)}


def build_experiment_graph():
    builder = StateGraph(JobState, context_schema=JobContext)
    for name in ("validate_plan", "execute_adapter", "collect_artifacts"):
        builder.add_node(name, globals()[name])
    builder.add_edge(START, "validate_plan")
    builder.add_edge("validate_plan", "execute_adapter")
    builder.add_edge("execute_adapter", "collect_artifacts")
    builder.add_edge("collect_artifacts", END)
    return builder.compile(checkpointer=False, name="CogniGuardExperiment")


def run_matrix(plan, output, *, execute=False, allow_model_calls=False, monitor=None):
    jobs = load_plan(Path(plan))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    monitor = monitor or LangSmithMonitor()
    graph = build_experiment_graph()
    write_new(
        output / "manifest.json",
        {
            "schema_version": 1,
            "orchestrator": "langgraph",
            "plan_sha256": sha256(plan),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dependencies": dependencies(),
            "source_sha256": source_hashes(),
            "jobs": [j.to_dict() for j in jobs],
            "execute": execute,
            "allow_model_calls": allow_model_calls,
            "checkpointing": False,
            "seed_scope": "Pipeline: Python hash + random RNG. Explicit focused runs retain their own RNG protocol.",
            "note": "Focused runners execute in the LangGraph environment; per-scenario graph migration is tracked separately.",
        },
    )
    results = []
    for job in jobs:
        directory = output / f"job-{job.index:03d}-{job.adapter}-{job.variant}-seed{job.seed}"
        directory.mkdir()
        recorder = SafeTelemetry()
        context = JobContext(job, directory, recorder, execute, allow_model_calls)
        failure_class = None
        try:
            with tracing_context(enabled=False):
                state = graph.invoke({"job_index": job.index}, context=context)
            status = "planned" if state.get("planned") else "completed"
        except Exception as exc:
            status = "failed"
            failure_class = type(exc).__name__
        finally:
            write_new(directory / "node-trace.json", recorder.to_dict())
            monitor.export(recorder)
        results.append(
            {
                "job_index": job.index,
                "adapter": job.adapter,
                "variant": job.variant,
                "seed": job.seed,
                "status": status,
                "directory": directory.name,
                "team": job.team,
                "trust_mode": job.trust_mode,
                "failure_class": failure_class,
            }
        )
    summary = {
        "status": "REFACTOR_VALIDATION_ONLY",
        "jobs": results,
        "failed_jobs": sum(r["status"] == "failed" for r in results),
        "langsmith": monitor.last_status,
        "limitation": "Engineering orchestration validation; no pooled ASR or new algorithm claim.",
    }
    write_new(output / "summary.json", summary)
    return summary


def pipeline_worker(job: Job, output: Path):
    """Runs in a fresh interpreter, so Python hash-based features are repeatable."""
    import random

    random.seed(job.seed)
    from core.access import AccessScope
    from core.inputs import load_inputs
    from protection.common.metrics import summarize_metric_rows
    from protection.student_profile.src.fopd.fopd_metrics import compute_fopd_metrics
    from protection.teacher_resource.src.c2rag.c2rag_metrics import compute_c2rag_metrics

    from .pipeline import LangGraphProtectionPipeline

    job.validate()
    if os.environ.get("PYTHONHASHSEED") != str(job.seed):
        raise ValueError("Worker must be spawned with PYTHONHASHSEED fixed before Python starts")
    config, profiles, questions, resources = load_inputs(
        job.config, job.profiles, job.questions, job.resources
    )
    if not questions:
        raise ValueError("Evaluation input is empty")
    config = variant_config(config, job.variant)
    output.mkdir(parents=True, exist_ok=False)
    inputs = {k: sha256(getattr(job, k)) for k in ("config", "profiles", "questions", "resources")}
    write_new(
        output / "manifest.json",
        {
            "inputs": inputs,
            "seed": job.seed,
            "pythonhashseed": os.environ["PYTHONHASHSEED"],
            "variant": job.variant,
            "effective_config": config,
            "dependencies": dependencies(),
            "budget_scope": "per_question",
            "engine": "langgraph",
        },
    )
    rows, traces = [], []
    for question in questions:
        profile = profiles[question["student_id"]]
        pipeline = LangGraphProtectionPipeline(config, resources)
        result = pipeline.run(profile, question, access=AccessScope(profile.student_id))
        metrics = compute_fopd_metrics(profile, result.task, result.context_card, result.selected)
        metrics.update(compute_c2rag_metrics(result.controlled, result.answer, resources))
        rows.append({"result": result.to_dict(), "metrics": metrics})
        traces.append(pipeline.last_trace)
    write_new(output / "rows.json", rows)
    write_new(output / "node-traces.json", traces)
    write_new(
        output / "summary.json",
        {
            "status": "OFFLINE_SMOKE_ONLY",
            "variant": job.variant,
            "budget_scope": "per_question",
            "governance_enabled": False,
            "watermark_enabled": False,
            **summarize_metric_rows([r["metrics"] for r in rows]),
        },
    )
