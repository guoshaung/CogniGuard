"""LangGraph for free-chat safety, generation, output check and presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.observability.graphs import invoke_observed_graph, observed_node
from cogniguard.observability.telemetry import SafeTelemetry


class FreeChatState(TypedDict, total=False):
    stage: str
    stopped: bool
    completed: bool


@dataclass
class FreeChatFrame:
    message: str
    history: list[dict[str, Any]]
    existing_image_count: int
    question: str = ""
    answer: str = ""
    runtime_status: dict[str, Any] = field(default_factory=dict)
    guardrail: dict[str, Any] | None = None
    controlled_summary: dict[str, Any] | None = None
    guardrail_adapter: Any = None
    result: dict[str, Any] | None = None
    recorder: SafeTelemetry = field(default_factory=SafeTelemetry)


@dataclass
class FreeChatContext:
    frame: FreeChatFrame


def validate(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    f.question = str(f.message or "").strip()
    if not f.question:
        raise ValueError("自由提问内容不能为空")
    return {"stage": "validate", "stopped": False}


def check_input(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.conversation import _free_chat_safety_block
    from cogniguard.runtime.mode import get_runtime_status

    blocked = _free_chat_safety_block(f.question)
    f.runtime_status = get_runtime_status()
    if blocked is not None:
        f.answer = blocked["safe_answer"]
        f.guardrail = {
            "decision": "block",
            "rail_type": "deterministic_free_chat_safety",
            "matched_policy": blocked["matched_policy"],
            "reason": blocked["reason"],
        }
        return {"stage": "check_input", "stopped": True}
    return {"stage": "check_input", "stopped": False}


def select_backend(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    if f.runtime_status["agent_call_mode"] != "real_llm":
        from cogniguard.applications.education.conversation import _deterministic_free_chat_answer

        f.answer = _deterministic_free_chat_answer(f.question)
        f.guardrail = {"decision": "allow", "rail_type": "mock_free_chat", "matched_policy": "none"}
        return {"stage": "select_backend", "stopped": True}
    return {"stage": "select_backend", "stopped": False}


def guard_input(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.conversation import (
        _build_guardrail_text,
        _protected_resource_summary,
    )
    from cogniguard.runtime.mode import build_guardrail_adapter

    f.guardrail_adapter = build_guardrail_adapter()
    if f.guardrail_adapter is None:
        return {"stage": "guard_input", "stopped": False}
    check = f.guardrail_adapter.check_user_input(
        _build_guardrail_text(f.question, f.history),
        {"surface": "free_chat", "case_context_enabled": False},
    )
    check["original"] = f.question
    check["backend"] = f.runtime_status["guardrail_backend"]
    check["nemo_runtime_available"] = f.runtime_status["nemo_runtime_available"]
    if check["decision"] == "sanitize":
        f.answer, f.controlled_summary = _protected_resource_summary()
        f.guardrail = check
        return {"stage": "guard_input", "stopped": True}
    if check["decision"] == "block":
        f.answer = (
            "系统中确实存在受版权保护的教师素材、题库和原创课件资源，"
            "但不能直接浏览素材目录、文件或原文。你可以告诉我具体知识点或"
            "学习目标，系统可通过受控流程提供摘要、提示或等价变式。"
        )
        f.guardrail = check
        return {"stage": "guard_input", "stopped": True}
    return {"stage": "guard_input", "stopped": False}


def generate(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.conversation import FREE_CHAT_SYSTEM_PROMPT
    from cogniguard.runtime.mode import build_runtime_llm_client

    compact_history = [
        {"role": str(item.get("role", ""))[:20], "content": str(item.get("content", ""))[:1200]}
        for item in f.history[-8:]
        if item.get("content")
    ]
    result = build_runtime_llm_client().chat(
        FREE_CHAT_SYSTEM_PROMPT,
        {
            "question": f.question,
            "conversation_history": compact_history,
            "case_context_enabled": False,
        },
    )
    f.answer = str(result.get("answer") or "").strip()
    if not f.answer:
        raise RuntimeError("真实模型没有返回有效回答")
    return {"stage": "generate"}


def guard_output(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    if f.guardrail_adapter is not None:
        check = f.guardrail_adapter.check_output(
            f.answer,
            {"surface": "free_chat", "case_context_enabled": False},
        )
        check["backend"] = f.runtime_status["guardrail_backend"]
        check["nemo_runtime_available"] = f.runtime_status["nemo_runtime_available"]
        f.guardrail = check
        if check["decision"] == "block":
            f.answer = "回答内容触发了输出安全策略，已停止展示。"
    return {"stage": "guard_output"}


def finish(state: FreeChatState, runtime: Runtime[FreeChatContext]):
    f = runtime.context.frame
    from cogniguard.applications.education.conversation import (
        _maybe_generate_free_chat_images,
        _messages,
    )

    images = []
    if (
        f.guardrail is None
        or f.guardrail.get("rail_type") == "mock_free_chat"
        or f.guardrail.get("decision") not in {"sanitize", "block"}
    ):
        images = _maybe_generate_free_chat_images(f.question, f.answer, f.existing_image_count)
    result = {
        "success": True,
        "answer": f.answer,
        "guardrail": f.guardrail,
        "runtime_status": f.runtime_status,
        "messages": _messages(
            f.question,
            f.answer,
            guardrail=f.guardrail,
            controlled_summary=f.controlled_summary,
            teaching_images=images,
        ),
    }
    if f.controlled_summary is not None:
        result["controlled_resource_summary"] = f.controlled_summary
    f.result = result
    return {"stage": "finish", "completed": True}


def build_free_chat_graph():
    builder = StateGraph(FreeChatState, context_schema=FreeChatContext)
    for name, fn in (
        ("validate", validate),
        ("check_input", check_input),
        ("select_backend", select_backend),
        ("guard_input", guard_input),
        ("generate", generate),
        ("guard_output", guard_output),
        ("finish", finish),
    ):
        builder.add_node(name, observed_node("free_chat", name, fn))
    builder.add_edge(START, "validate")
    builder.add_edge("validate", "check_input")
    builder.add_conditional_edges(
        "check_input",
        lambda s: "finish" if s["stopped"] else "select_backend",
        {"finish": "finish", "select_backend": "select_backend"},
    )
    builder.add_conditional_edges(
        "select_backend",
        lambda s: "finish" if s["stopped"] else "guard_input",
        {"finish": "finish", "guard_input": "guard_input"},
    )
    builder.add_conditional_edges(
        "guard_input",
        lambda s: "finish" if s["stopped"] else "generate",
        {"finish": "finish", "generate": "generate"},
    )
    builder.add_edge("generate", "guard_output")
    builder.add_edge("guard_output", "finish")
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=False, name="CogniGuardFreeChat")


FREE_CHAT_GRAPH = build_free_chat_graph()


def run_free_chat_graph(
    message: str, history: list[dict[str, Any]] | None, existing_image_count: int, monitor=None
):
    frame = FreeChatFrame(message, history or [], existing_image_count)
    state = invoke_observed_graph(
        FREE_CHAT_GRAPH, {}, context=FreeChatContext(frame), frame=frame, monitor=monitor
    )
    if not state.get("completed") or frame.result is None:
        raise RuntimeError("Free chat graph did not complete")
    return frame.result
