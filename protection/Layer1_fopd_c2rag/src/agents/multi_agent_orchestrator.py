from __future__ import annotations

from typing import Any

from protection.fopd_c2rag_mvp.src.common.schemas import Task
from protection.fopd_c2rag_mvp.src.llm.ollama_client import OllamaClient, extract_json_object
from protection.fopd_c2rag_mvp.src.pipeline.ag2_simulator import build_ag2_request, compose_final_answer


def _compact_lines(text: str, limit: int = 900) -> str:
    text = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    return text[:limit]


class MultiAgentOrchestrator:
    """LLM-backed agents around deterministic FOPD/C2-RAG/HSW-ST algorithms."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.client = OllamaClient(config)
        self.enabled = self.client.is_enabled()

    def agent1_task_model(self, raw_question: dict[str, Any], task: Task) -> dict[str, Any]:
        fallback = {
            "agent": "AG1 learner_task_agent",
            "llm_used": False,
            "task_intent": "解析学生问题，确认知识点、难度和是否需要资源。",
            "knowledge": task.knowledge,
            "difficulty": task.difficulty,
            "need_resource": task.need_resource,
            "algorithm_link": "AG1 -> FOPD: 只把任务字段交给 FOPD，完整学生画像仍留在本地。",
        }
        if not self.enabled:
            return fallback
        prompt = f"""
你是 AG1 学生任务建模代理。请只输出 JSON，不要输出解释。
目标：读取学生问题，提取教学任务，不读取完整学生隐私画像。
学生问题：{raw_question.get("question", "")}
候选知识点：{task.knowledge}
候选难度：{task.difficulty}
是否需要资源：{task.need_resource}
JSON 字段：
{{"task_intent":"一句话", "knowledge":"...", "difficulty":"basic/medium/hard", "need_resource":true/false, "privacy_boundary":"一句话"}}
"""
        result = self.client.generate(prompt, num_predict=180, temperature=0.1)
        data = extract_json_object(result.text)
        if not data:
            fallback["llm_error"] = result.error or result.text[:160]
            return fallback
        return {
            **fallback,
            "llm_used": True,
            "task_intent": str(data.get("task_intent") or fallback["task_intent"]),
            "knowledge": str(data.get("knowledge") or task.knowledge),
            "difficulty": str(data.get("difficulty") or task.difficulty),
            "need_resource": bool(data.get("need_resource", task.need_resource)),
            "privacy_boundary": str(data.get("privacy_boundary") or "不接触 local_only_fields。"),
        }

    def agent2_resource_request(self, task: Task, context_card: str) -> tuple[dict[str, Any], dict[str, Any]]:
        fallback_request = build_ag2_request(task, context_card)
        fallback_log = {
            "agent": "AG2 tutor_planner_agent",
            "llm_used": False,
            "algorithm_link": "AG2 <- FOPD context_card; AG2 -> C2-RAG resource request。",
            "plan": "基于最小画像卡片生成资源请求。",
        }
        if not self.enabled or not task.need_resource:
            return fallback_request, fallback_log
        prompt = f"""
你是 AG2 教学调度代理。请只输出 JSON，不要输出解释。
你只能使用 FOPD 给出的最小上下文卡片，不得推测学校、家庭、身份等隐私。
学生问题：{task.question}
FOPD 最小上下文卡片：
{context_card}
请生成 C2-RAG 资源请求 JSON：
{{"knowledge":"...", "resource_type":"question_bank/teaching_note", "difficulty":"...", "teaching_goal":"一句话", "privacy_guard":"一句话"}}
"""
        result = self.client.generate(prompt, num_predict=220, temperature=0.2)
        data = extract_json_object(result.text)
        if not data:
            fallback_log["llm_error"] = result.error or result.text[:160]
            return fallback_request, fallback_log
        request = {
            **fallback_request,
            "knowledge": str(data.get("knowledge") or task.knowledge),
            "resource_type": str(data.get("resource_type") or fallback_request["resource_type"]),
            "difficulty": str(data.get("difficulty") or task.difficulty),
            "teaching_goal": str(data.get("teaching_goal") or fallback_request["teaching_goal"]),
            "privacy_guard": str(data.get("privacy_guard") or "只使用最小上下文卡片。"),
        }
        log = {
            **fallback_log,
            "llm_used": True,
            "plan": request["teaching_goal"],
            "privacy_guard": request["privacy_guard"],
        }
        return request, log

    def agent2_final_answer(
        self,
        task: Task,
        context_card: str,
        controlled_resource: Any,
    ) -> tuple[str, dict[str, Any]]:
        fallback = compose_final_answer(task, context_card, controlled_resource)
        log = {
            "agent": "AG2 tutor_answer_agent",
            "llm_used": False,
            "algorithm_link": "AG2 只能融合 C2-RAG 已允许返回的 controlled_resource。",
            "answer_strategy": "规则合成最终回答。",
        }
        if not self.enabled:
            return fallback, log
        mode = controlled_resource.mode if controlled_resource else "none"
        resource_text = controlled_resource.text if controlled_resource else ""
        prompt = f"""
你是 AG2 教学回答代理。请给出简洁中文教学回答。
硬性约束：
1. 只使用下面的 C2-RAG 受控资源，不得补出教师资源原文。
2. 如果 return_mode 是 variant/refuse/outline/summary，不要声称引用了原文。
3. 回答要适合初中学生，步骤清楚。
学生问题：{task.question}
FOPD 最小上下文卡片：
{context_card}
C2-RAG return_mode：{mode}
C2-RAG 受控资源：
{resource_text}
"""
        result = self.client.generate(prompt, num_predict=360, temperature=0.25)
        if not result.ok or not result.text:
            log["llm_error"] = result.error
            return fallback, log
        log["llm_used"] = True
        log["answer_strategy"] = "本地 Ollama 生成，但输入受 FOPD 和 C2-RAG 双重约束。"
        return result.text.strip(), log

    def agent3_policy_explain(
        self,
        return_mode: str,
        retrieved_chunks: list[str],
        source_trace: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = {
            "agent": "AG3 copyright_resource_agent",
            "llm_used": False,
            "algorithm_link": "AG3 = C2-RAG policy: retrieval + exposure budget + return mode。",
            "policy_decision": f"返回模式为 {return_mode}，命中资源 {retrieved_chunks}。",
        }
        if not self.enabled:
            return fallback
        prompt = f"""
你是 AG3 版权资源代理。请只输出 JSON。
根据 C2-RAG 的算法结果，用一句话解释为什么采用该返回模式。不要复述资源原文。
return_mode: {return_mode}
retrieved_chunks: {retrieved_chunks}
source_trace: {source_trace}
JSON 字段：{{"policy_decision":"一句话", "risk_control":"一句话"}}
"""
        result = self.client.generate(prompt, num_predict=160, temperature=0.1)
        data = extract_json_object(result.text)
        if not data:
            fallback["llm_error"] = result.error or result.text[:160]
            return fallback
        return {
            **fallback,
            "llm_used": True,
            "policy_decision": str(data.get("policy_decision") or fallback["policy_decision"]),
            "risk_control": str(data.get("risk_control") or "不返回高版权原文。"),
        }

    def agent4_trace_explain(
        self,
        watermark_id: str,
        trace_binding_id: str,
        source_trace_log: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = {
            "agent": "AG4 watermark_trace_agent",
            "llm_used": False,
            "algorithm_link": "AG4 -> HSW-ST: 绑定 watermark_id、source_trace_log、trace_binding_id。",
            "trace_summary": f"watermark_id={watermark_id}, trace_binding_id={trace_binding_id}",
        }
        if not self.enabled:
            return fallback
        prompt = f"""
你是 AG4 水印与溯源代理。请只输出 JSON。
根据以下日志说明 HSW-ST 与 C2-RAG 如何绑定，不要编造检测结果。
watermark_id: {watermark_id}
trace_binding_id: {trace_binding_id}
source_trace_log: {source_trace_log}
JSON 字段：{{"trace_summary":"一句话", "watermark_boundary":"一句话"}}
"""
        result = self.client.generate(prompt, num_predict=180, temperature=0.1)
        data = extract_json_object(result.text)
        if not data:
            fallback["llm_error"] = result.error or result.text[:160]
            return fallback
        return {
            **fallback,
            "llm_used": True,
            "trace_summary": str(data.get("trace_summary") or fallback["trace_summary"]),
            "watermark_boundary": str(data.get("watermark_boundary") or "当前仅绑定日志，真实水印检测由 HSW-ST 执行。"),
        }

    def algorithm_links(self) -> dict[str, str]:
        return {
            "FOPD": "AG1 解析任务边界，FOPD 选择最少画像记录并生成 context_card，AG2 只看 context_card。",
            "C2-RAG": "AG2 发出资源请求，AG3/C2-RAG 根据版权等级、曝光预算和返回策略输出 controlled_resource。",
            "HSW-ST": "AG4 绑定 answer_id/watermark_id/source_trace_log，后续 HSW-ST 对 final_answer 加水印并复用同一 trace_binding_id。",
        }
