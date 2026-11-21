"""C²-RAG development experiment graph with per-method/session/round nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


class RagState(TypedDict, total=False):
    stage: str
    method_index: int
    method_count: int
    session_index: int
    session_count: int
    round_index: int
    round_count: int
    completed: bool


@dataclass
class RagFrame:
    output: Path
    limit: int | None
    rounds: int
    offset: int
    dataset_root: Path | None
    generator_backend: str
    copyright_budget: float
    fixture_profile: str
    attack_family: str | None
    offline_fallback: bool
    repo: Path | None = None
    split_root: Path | None = None
    fixture_root: Path | None = None
    sessions: list[Any] = field(default_factory=list)
    config: Any = None
    engine: Any = None
    first_engine: Any = None
    current_session: Any = None
    raw_rows: list[dict] = field(default_factory=list)
    snapshots: dict[str, dict] = field(default_factory=dict)
    report: dict = field(default_factory=dict)


@dataclass
class RagContext:
    frame: RagFrame


def build_fixture(state: RagState, runtime: Runtime[RagContext]):
    f = runtime.context.frame
    from .dataset import (build_isolated_development_fixture,
                          build_paired_copyright_fixture, load_isolated_dev_sessions)
    from .baselines import METHODS
    f.repo = Path(__file__).resolve().parents[2]
    f.split_root = f.dataset_root or f.repo / "experiments/datasets/cogniguard_math_suite/mixed_math_suite/splits/dev"
    f.output.mkdir(parents=True, exist_ok=False)
    f.fixture_root = f.output / "runtime_fixture"
    if f.fixture_profile == "paired":
        build_paired_copyright_fixture(f.split_root, f.fixture_root, rounds=f.rounds)
    else:
        build_isolated_development_fixture(f.split_root, f.fixture_root, rounds=f.rounds)
    f.sessions = load_isolated_dev_sessions(f.split_root, f.fixture_root, rounds=f.rounds)
    if f.attack_family:
        f.sessions = [session for session in f.sessions
                      if session.case.attack_family in {f.attack_family, f"clean_for_{f.attack_family}"}]
    f.sessions = f.sessions[f.offset: f.offset + f.limit if f.limit is not None else None]
    if not f.sessions:
        raise RuntimeError("No development sessions loaded")
    return {"stage": "build_fixture", "method_index": 0,
            "method_count": len(METHODS), "session_count": len(f.sessions)}


def configure_models(state: RagState, runtime: Runtime[RagContext]):
    f = runtime.context.frame
    from .core import C2RAGConfig
    from .runner import (_model_path, _generator_path, DENSE_REVISION,
                         RERANKER_REVISION, GENERATOR_REVISION, SEED)
    dense = None if f.offline_fallback else _model_path(
        f.repo, "sentence-transformers/all-MiniLM-L6-v2", DENSE_REVISION)
    reranker = None if f.offline_fallback else _model_path(
        f.repo, "cross-encoder/ms-marco-TinyBERT-L-2-v2", RERANKER_REVISION)
    generator = None if f.offline_fallback else _generator_path(f.repo)
    backend = "fallback" if f.offline_fallback else f.generator_backend
    if backend == "qwen" and generator is None:
        raise RuntimeError("Locked local Qwen model unavailable; no silent fallback")
    f.config = C2RAGConfig(
        retrieval_backend="neural" if dense else "fallback", dense_model_path=dense,
        reranker_backend="neural" if reranker else "fallback", reranker_model_path=reranker,
        model_device="auto", generator_backend=backend,
        generator_model_path=generator, generator_model_revision=GENERATOR_REVISION,
        generator_max_new_tokens=128, generator_seed=SEED,
        total_copyright_budget=f.copyright_budget,
    )
    return {"stage": "configure_models"}


def start_method(state: RagState, runtime: Runtime[RagContext]):
    f = runtime.context.frame
    from .baselines import METHODS
    from .core import C2RAGV3
    method = list(METHODS)[state["method_index"]]
    resources = [session.resource for session in f.sessions]
    f.engine = C2RAGV3(resources, f.config)
    if f.first_engine is None:
        f.first_engine = f.engine
    f.snapshots[method] = {
        **f.engine.mechanism_snapshot(method), "retrieval": f.engine.retrieval_manifest(),
    }
    return {"stage": "start_method", "session_index": 0}


def start_session(state: RagState, runtime: Runtime[RagContext]):
    f = runtime.context.frame
    f.current_session = f.sessions[state["session_index"]]
    session = f.current_session
    principal = session.principal_id or f"principal:{session.case.case_id}"
    f.engine.reset_session(session.case.session_id, principal)
    return {"stage": "start_session", "round_index": 0,
            "round_count": len(session.public_queries)}


def execute_round(state: RagState, runtime: Runtime[RagContext]):
    f = runtime.context.frame
    from .baselines import METHODS
    from .runner import SEED
    method = list(METHODS)[state["method_index"]]
    session = f.current_session
    principal = session.principal_id or f"principal:{session.case.case_id}"
    round_id = state["round_index"] + 1
    query = session.public_queries[state["round_index"]]
    result = f.engine.run_round(
        session_id=session.case.session_id, round_id=round_id,
        identity=principal, query=query, role="teacher", purpose="security_evaluation",
        method=method,
        target_resource_id=session.case.target_resource_id or session.resource.document_id,
        principal_id=principal, cross_session_linked=bool(session.link_group),
    )
    row = result.to_dict()
    row.update({
        "case_id": session.case.case_id, "seed": SEED, "split": "development",
        "hidden_label_access": False, "principal_id": principal,
        "link_group": session.link_group,
        "target_resource_id": session.case.target_resource_id or session.resource.document_id,
        "mechanism_snapshot": f.snapshots[method],
    })
    f.raw_rows.append(row)
    return {"stage": "execute_round", "round_index": round_id}


def next_session(state: RagState, runtime: Runtime[RagContext]):
    return {"stage": "next_session", "session_index": state["session_index"] + 1}


def next_method(state: RagState, runtime: Runtime[RagContext]):
    return {"stage": "next_method", "method_index": state["method_index"] + 1}


def finalize(state: RagState, runtime: Runtime[RagContext]):
    f = runtime.context.frame
    from .aggregate_results import aggregate, dependency_manifest
    from .baselines import EXTERNAL_BASELINES, METHODS
    from .runner import _model_manifest, SEED, write_jsonl
    write_jsonl(f.output / "raw_results.jsonl", f.raw_rows)
    (f.output / "mechanism_snapshots.json").write_text(
        json.dumps(f.snapshots, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = _model_manifest(f.repo, f.config, f.first_engine)
    (f.output / "model_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (f.output / "dependency_versions.json").write_text(
        json.dumps(dependency_manifest(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (f.output / "external_baseline_manifest.json").write_text(
        json.dumps(EXTERNAL_BASELINES, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    freeze = {
        "experiment": "c2rag_security_suite_v3_development_verification",
        "status": "DEVELOPMENT_ONLY_NOT_FORMAL", "orchestrator": "langgraph",
        "split": "development", "test_split_used": False,
        "sessions": len(f.sessions), "rounds_per_session": f.rounds,
        "round_records": len(f.raw_rows), "methods": list(METHODS), "seed": SEED,
        "fixture": "runtime_fixture/public_sessions.jsonl",
        "hidden_evaluator_fixture": "runtime_fixture/hidden_cases.jsonl",
        "hidden_labels_to_runtime": False,
        "config": f.config.__dict__, "models": manifest,
        "external_baselines": EXTERNAL_BASELINES,
        "source_dataset_sha256": hashlib.sha256(
            (f.split_root / "evaluation/data/episodes.jsonl").read_bytes()).hexdigest(),
        "formal_test_authorized": False,
        "generator": manifest.get("generator", {}),
        "evaluator": {"hidden_labels_runtime_access": False,
                      "semantic_thresholds_locked": True},
        "offline_fallback": f.offline_fallback,
    }
    (f.output / "freeze_manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    f.report = aggregate(f.output, f.split_root, f.fixture_root,
                         f.output / "development_pilot_report.md", f.output / "RUN_READINESS.md")
    (f.output / "run_manifest.json").write_text(
        json.dumps({**freeze, **f.report}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    return {"stage": "finalize", "completed": True}


def build_rag_graph():
    builder = StateGraph(RagState, context_schema=RagContext)
    nodes = (("build_fixture", build_fixture), ("configure_models", configure_models),
             ("start_method", start_method), ("start_session", start_session),
             ("execute_round", execute_round), ("next_session", next_session),
             ("next_method", next_method), ("finalize", finalize))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, "build_fixture")
    builder.add_edge("build_fixture", "configure_models")
    builder.add_edge("configure_models", "start_method")
    builder.add_edge("start_method", "start_session")
    builder.add_edge("start_session", "execute_round")
    builder.add_conditional_edges("execute_round",
                                  lambda s: "again" if s["round_index"] < s["round_count"] else "session_done",
                                  {"again": "execute_round", "session_done": "next_session"})
    builder.add_conditional_edges("next_session",
                                  lambda s: "again" if s["session_index"] < s["session_count"] else "method_done",
                                  {"again": "start_session", "method_done": "next_method"})
    builder.add_conditional_edges("next_method",
                                  lambda s: "again" if s["method_index"] < s["method_count"] else "done",
                                  {"again": "start_method", "done": "finalize"})
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=False, name="CogniGuardC2RAGDevelopment")


RAG_GRAPH = build_rag_graph()


def run_rag_graph(output: Path, limit=None, rounds=4, offset=0, dataset_root=None,
                  generator_backend="qwen", copyright_budget=2.0, fixture_profile="default",
                  attack_family=None, offline_fallback=False):
    if not offline_fallback:
        from cogniguard.workflows.model_site import enable_existing_model_environment
        enable_existing_model_environment()
    frame = RagFrame(output, limit, rounds, offset, dataset_root, generator_backend,
                     copyright_budget, fixture_profile, attack_family, offline_fallback)
    with tracing_context(enabled=False):
        state = RAG_GRAPH.invoke({}, context=RagContext(frame),
                                 config={"recursion_limit": 50000})
    if not state.get("completed"):
        raise RuntimeError("C2-RAG development graph did not complete")
    return frame.report
