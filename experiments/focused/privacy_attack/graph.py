"""LangGraph for synthetic population → per-mechanism shadow attack → aggregate."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context
import numpy as np

from .population import make_population


class PrivacyState(TypedDict, total=False):
    stage: str
    seed_index: int
    mechanism_index: int
    seed_count: int
    mechanism_count: int
    completed: bool


@dataclass
class PrivacyFrame:
    output: Path | None
    population_size: int
    seeds: tuple[int, ...]
    settings: dict[str, Any] = field(default_factory=dict)
    population: Any = None
    current_results: dict[str, dict] = field(default_factory=dict)
    per_seed: list[dict[str, dict]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    output_path: Path | None = None


@dataclass
class PrivacyContext:
    frame: PrivacyFrame


def prepare(state: PrivacyState, runtime: Runtime[PrivacyContext]):
    f = runtime.context.frame
    from .runner import MECHANISMS, config
    if f.population_size < 2 or not f.seeds:
        raise ValueError("Population and seeds must be nonempty")
    f.settings = config()
    return {"stage": "prepare", "seed_index": 0, "mechanism_index": 0,
            "seed_count": len(f.seeds), "mechanism_count": len(MECHANISMS)}


def build_population(state: PrivacyState, runtime: Runtime[PrivacyContext]):
    f = runtime.context.frame
    seed = f.seeds[state["seed_index"]]
    f.population = make_population(n=f.population_size, seed=20261012 + seed)
    f.current_results = {}
    return {"stage": "build_population", "mechanism_index": 0}


def attack_mechanism(state: PrivacyState, runtime: Runtime[PrivacyContext]):
    f = runtime.context.frame
    from .runner import MECHANISMS, attack_once
    mechanism = MECHANISMS[state["mechanism_index"]]
    seed = f.seeds[state["seed_index"]]
    f.current_results[mechanism] = attack_once(f.population, mechanism, f.settings, seed)
    return {"stage": "attack_mechanism", "mechanism_index": state["mechanism_index"] + 1}


def finish_seed(state: PrivacyState, runtime: Runtime[PrivacyContext]):
    f = runtime.context.frame
    f.per_seed.append(f.current_results)
    f.population = None
    return {"stage": "finish_seed", "seed_index": state["seed_index"] + 1}


def aggregate(state: PrivacyState, runtime: Runtime[PrivacyContext]):
    f = runtime.context.frame
    from .runner import MECHANISMS
    agg = {}
    for mechanism in MECHANISMS:
        accuracies = [result[mechanism]["attack_accuracy"] for result in f.per_seed]
        aucs = [result[mechanism]["attack_auc"] for result in f.per_seed]
        bases = [result[mechanism]["base_rate"] for result in f.per_seed]
        exposures = [result[mechanism]["explicit_exposure_rate"] for result in f.per_seed]
        agg[mechanism] = {
            "attack_accuracy_mean": round(float(np.mean(accuracies)), 3),
            "attack_accuracy_std": round(float(np.std(accuracies)), 3),
            "attack_auc_mean": round(float(np.mean(aucs)), 3),
            "base_rate": round(float(np.mean(bases)), 3),
            "explicit_exposure_rate": round(float(np.mean(exposures)), 3),
            "advantage_over_base": round(float(np.mean(accuracies)) - float(np.mean(bases)), 3),
        }
    f.summary = {
        "status": "MM_FOPD_ATTRIBUTE_INFERENCE_ATTACK", "execution_mode": "offline_shadow_model",
        "sensitive_attribute": "family_support (low/high)", "population": f.population_size,
        "seeds": list(f.seeds),
        "attacker": "shadow LogisticRegression on released-text features (train 60% / test 40%)",
        "mechanisms": agg,
        "headline": {
            "explicit_exposure": {m: agg[m]["explicit_exposure_rate"] for m in MECHANISMS},
            "attack_accuracy": {m: agg[m]["attack_accuracy_mean"] for m in MECHANISMS},
            "interpretation": "MM-FOPD 把显式暴露率降到 0，但属性推断准确率仍可高于 base rate（经相关非敏感信号残留）；"
                              "说明‘低高敏感选择率’不等于隐私，需以攻击推断准确率衡量真实隐私。",
        },
        "limitations": [
            "合成群体、相关性由生成器设定；绝对数值依赖该相关强度与噪声，不可外推到真实数据。",
            "攻击者为简单影子逻辑回归 + 规则特征；更强攻击者可能提升推断，故此为下界。",
            "FullProfile 的 ~1.0 来自显式字段，属平凡上界；对比重点是 MM-FOPD 相对 base rate 的残留优势。",
            "需在真实 270 画像数据上复跑，并给出多强度相关下的敏感性分析与置信区间。",
        ],
    }
    return {"stage": "aggregate"}


def persist(state: PrivacyState, runtime: Runtime[PrivacyContext]):
    f = runtime.context.frame
    from .runner import ROOT
    f.output_path = f.output or ROOT / "experiments/results/privacy_attack" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    f.output_path.mkdir(parents=True, exist_ok=False)
    (f.output_path / "summary.json").write_text(json.dumps(f.summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (f.output_path / "per_seed.json").write_text(json.dumps(f.per_seed, ensure_ascii=False, indent=2), encoding="utf-8")
    files = [Path(__file__), Path(__file__).with_name("runner.py"),
             Path(__file__).with_name("population.py"), ROOT / "core/access.py",
             ROOT / "protection/student_profile/src/fopd/context_card.py",
             ROOT / "protection/student_profile/src/fopd/profile_selector.py"]
    (f.output_path / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(), "synthetic_only": True,
        "orchestrator": "langgraph",
        "files_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in files},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"stage": "persist", "completed": True}


def build_privacy_graph():
    builder = StateGraph(PrivacyState, context_schema=PrivacyContext)
    nodes = (("prepare", prepare), ("build_population", build_population),
             ("attack_mechanism", attack_mechanism), ("finish_seed", finish_seed),
             ("aggregate", aggregate), ("persist", persist))
    for name, fn in nodes:
        builder.add_node(name, fn)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "build_population")
    builder.add_edge("build_population", "attack_mechanism")
    builder.add_conditional_edges("attack_mechanism",
                                  lambda s: "next" if s["mechanism_index"] < s["mechanism_count"] else "finish",
                                  {"next": "attack_mechanism", "finish": "finish_seed"})
    builder.add_conditional_edges("finish_seed",
                                  lambda s: "next" if s["seed_index"] < s["seed_count"] else "aggregate",
                                  {"next": "build_population", "aggregate": "aggregate"})
    builder.add_edge("aggregate", "persist")
    builder.add_edge("persist", END)
    return builder.compile(checkpointer=False, name="CogniGuardPrivacyInference")


PRIVACY_GRAPH = build_privacy_graph()


def run_privacy_graph(output=None, n=300, seeds=(1, 2, 3, 4, 5)):
    frame = PrivacyFrame(Path(output) if output else None, n, tuple(seeds))
    with tracing_context(enabled=False):
        state = PRIVACY_GRAPH.invoke({}, context=PrivacyContext(frame),
                                     config={"recursion_limit": 128})
    if not state.get("completed"):
        raise RuntimeError("Privacy inference graph did not complete")
    return frame.output_path, frame.summary
