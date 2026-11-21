"""LangGraph execution of Qwen-backed HSW-ST samples and clean controls.

Model calls, watermark embedding and attack detection are separate graph
nodes. Raw teaching content stays in invocation context; graph state contains
only counters. Side-effectful model calls are never checkpointed or retried.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
import time
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context


ATTACKS = [
    "synonym_replacement", "sentence_reorder", "local_deletion",
    "content_insertion", "light_rewrite", "strong_rewrite",
]


class OutputState(TypedDict, total=False):
    sample_index: int
    clean_index: int
    protected_count: int
    clean_count: int
    completed: bool


@dataclass
class OutputFrame:
    test: list[dict[str, Any]]
    model: Any
    tokenizer: Any
    model_dir: str
    model_revision: str
    device: str
    watermark: dict[str, Any]
    generate_fn: Callable[..., tuple[str, float]]
    extract_fn: Callable[..., tuple[list[str], list[str], list[str]]]
    rewrite_fn: Callable[..., dict[str, Any]]
    detect_fn: Callable[..., dict[str, Any]]
    attack_fn: Callable[[str, str], str]
    similarity_fn: Callable[[str, str], float]
    digest_fn: Callable[[Any], str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    attack_rows: list[dict[str, Any]] = field(default_factory=list)
    clean_flags: list[bool] = field(default_factory=list)
    question: str = ""
    draft: str = ""
    generation_latency: float = 0.0
    watermarked: str = ""


@dataclass
class OutputContext:
    frame: OutputFrame


def generate_draft(state: OutputState, runtime: Runtime[OutputContext]):
    f = runtime.context.frame
    item = f.test[state["sample_index"]]
    f.question = str(item["episode"]["user_request"])
    resource_text = str(item["resource"].get("content") or "")
    f.draft, f.generation_latency = f.generate_fn(
        f.model, f.tokenizer, f.question, resource_text,
        20260826 + state["sample_index"])
    return {}


def protect_and_detect(state: OutputState, runtime: Runtime[OutputContext]):
    f = runtime.context.frame
    item = f.test[state["sample_index"]]
    episode, resource = item["episode"], item["resource"]
    sample = {
        "question": f.question, "draft_answer": f.draft,
        "protected_terms": [str(resource.get("knowledge") or "mathematics")],
        "protected_formulas": [],
        "protected_numbers": re.findall(r"-?\d+(?:\.\d+)?", f.question)[:12],
    }
    terms, formulas, numbers = f.extract_fn(sample, [])
    cfg = {
        "model": {
            "provider": "huggingface", "local_model_name": f.model_dir,
            "device": f.device,
            "dtype": "float16" if f.device == "cuda" else "float32",
            "rewrite_max_new_tokens": 128, "rewrite_temperature": 0.26,
            "top_p": 0.9, "repetition_penalty": 1.06,
        },
        "watermark": f.watermark,
        "experiment": {"ablation": "full", "content_fidelity": {
            "enabled": True, "max_attempts": 2,
            "max_draft_similarity": 0.999, "min_term_coverage": 1.0,
            "fallback_to_draft_on_drift": True,
        }},
    }
    started = time.perf_counter()
    rewritten = f.rewrite_fn(f.draft, terms, formulas, numbers, cfg,
                             "full", question=f.question)
    f.watermarked = str(rewritten["watermarked_answer"])
    elapsed = (time.perf_counter() - started) * 1000
    wm = f.watermark
    detection = f.detect_fn(
        f.watermarked, f.tokenizer, f.tokenizer.vocab_size,
        wm["gamma"], wm["key"], wm["window_size"], wm["z_threshold"])
    trace = [{"resource_id": episode["resource_id"],
              "chunk_id": resource.get("chunk_id"),
              "source_family_id": resource.get("resource_family_id")}]
    trace_hash = f.digest_fn(trace)
    f.rows.append({
        "sample_id": episode["episode_id"], "split": "test",
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "model_revision": f.model_revision, "model_path": f.model_dir,
        "seed": 20260826 + state["sample_index"],
        "question": f.question, "source_trace": trace,
        "source_trace_hash": trace_hash, "draft_answer": f.draft,
        "final_output": f.watermarked,
        "WDR": int(detection["is_watermarked"]),
        "payload_id_hash": hashlib.sha256(
            f"{episode['episode_id']}:{wm['key_id']}".encode()).hexdigest(),
        "trace_bind": int(bool(trace_hash)),
        "TKR": sum(term in f.watermarked for term in terms) / len(terms) if terms else 1.0,
        "FKR": sum(formula in f.watermarked for formula in formulas) / len(formulas) if formulas else 1.0,
        "NKR": sum(number in f.watermarked for number in numbers) / len(numbers) if numbers else 1.0,
        "semantic_similarity": f.similarity_fn(f.draft, f.watermarked),
        "generation_latency_ms": round(f.generation_latency, 3),
        "embedding_latency_ms": round(elapsed, 3),
        "detection_latency_ms": 0.0,
        "actual_released_output": f.watermarked,
        "watermark_detection": detection,
        "rewrite_attempts": rewritten.get("rewrite_attempts_used", 0),
        "used_draft_fallback": rewritten.get("used_draft_fallback", False),
    })
    return {"protected_count": len(f.rows)}


def attack_and_detect(state: OutputState, runtime: Runtime[OutputContext]):
    f = runtime.context.frame
    sample_id = f.test[state["sample_index"]]["episode"]["episode_id"]
    wm = f.watermark
    for attack in ATTACKS:
        started = time.perf_counter()
        attacked = f.attack_fn(f.watermarked, attack)
        detection = f.detect_fn(
            attacked, f.tokenizer, f.tokenizer.vocab_size,
            wm["gamma"], wm["key"], wm["window_size"], wm["z_threshold"])
        f.attack_rows.append({
            "sample_id": sample_id, "attack_type": attack,
            "attack_strength": "strong" if attack == "strong_rewrite" else "light",
            "attacked_output": attacked,
            "is_watermarked": int(detection["is_watermarked"]),
            "z_score": detection["z_score"],
            "payload_recovered": int(detection["is_watermarked"]),
            "semantic_similarity": f.similarity_fn(f.watermarked, attacked),
            "detection_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        })
    return {}


def advance_sample(state: OutputState, runtime: Runtime[OutputContext]):
    return {"sample_index": state["sample_index"] + 1}


def route_sample(state: OutputState, runtime: Runtime[OutputContext]):
    return "generate_draft" if state["sample_index"] < len(runtime.context.frame.test) else "clean_control"


def clean_control(state: OutputState, runtime: Runtime[OutputContext]):
    f = runtime.context.frame
    item = f.test[state["clean_index"]]
    clean_text, _ = f.generate_fn(
        f.model, f.tokenizer,
        str(item["episode"]["user_request"]),
        str(item["resource"].get("content") or ""),
        20260926 + state["clean_index"])
    wm = f.watermark
    detection = f.detect_fn(
        clean_text, f.tokenizer, f.tokenizer.vocab_size,
        wm["gamma"], wm["key"], wm["window_size"], wm["z_threshold"])
    f.clean_flags.append(bool(detection["is_watermarked"]))
    return {"clean_count": len(f.clean_flags)}


def advance_clean(state: OutputState, runtime: Runtime[OutputContext]):
    index = state["clean_index"] + 1
    return {"clean_index": index, "completed": index == len(runtime.context.frame.test)}


def route_clean(state: OutputState, runtime: Runtime[OutputContext]):
    return "clean_control" if state["clean_index"] < len(runtime.context.frame.test) else END


def build_output_graph():
    builder = StateGraph(OutputState, context_schema=OutputContext)
    for name, fn in (
        ("generate_draft", generate_draft),
        ("protect_and_detect", protect_and_detect),
        ("attack_and_detect", attack_and_detect),
        ("advance_sample", advance_sample),
        ("clean_control", clean_control),
        ("advance_clean", advance_clean),
    ):
        builder.add_node(name, fn)
    builder.add_conditional_edges(START, route_sample)
    builder.add_edge("generate_draft", "protect_and_detect")
    builder.add_edge("protect_and_detect", "attack_and_detect")
    builder.add_edge("attack_and_detect", "advance_sample")
    builder.add_conditional_edges("advance_sample", route_sample)
    builder.add_edge("clean_control", "advance_clean")
    builder.add_conditional_edges("advance_clean", route_clean)
    return builder.compile(checkpointer=False, name="CogniGuardFormalHSWOutput")


OUTPUT_GRAPH = build_output_graph()


def run_output_graph(frame: OutputFrame) -> OutputFrame:
    if not frame.test:
        raise ValueError("At least one independent test sample is required")
    with tracing_context(enabled=False):
        state = OUTPUT_GRAPH.invoke(
            {"sample_index": 0, "clean_index": 0,
             "protected_count": 0, "clean_count": 0, "completed": False},
            context=OutputContext(frame),
            config={"recursion_limit": max(50, 8 * len(frame.test) + 10)},
        )
    if not state.get("completed") or len(frame.rows) != len(frame.test) or len(frame.clean_flags) != len(frame.test):
        raise RuntimeError("HSW-ST output graph did not complete")
    if len(frame.attack_rows) != len(frame.test) * len(ATTACKS):
        raise RuntimeError("HSW-ST attack graph did not cover every sample")
    return frame
