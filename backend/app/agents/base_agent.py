from __future__ import annotations

import json
import inspect
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable


class AgentValidationError(ValueError):
    """Raised when an agent receives data outside its safety boundary."""


class BaseAgent(ABC):
    """Base class for protected tutoring agents.

    Agents receive only a payload body. Transport metadata is created and
    validated by TPCSController so that agents cannot call each other directly.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        role: str,
        allowed_inputs: list[str] | tuple[str, ...],
        forbidden_inputs: list[str] | tuple[str, ...],
        llm_client: Any | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.role = role
        self.allowed_inputs = tuple(allowed_inputs)
        self.forbidden_inputs = tuple(forbidden_inputs)
        self.llm_client = llm_client
        self.event_sink = event_sink
        self.call_log: list[dict[str, Any]] = []

    def validate_input(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise AgentValidationError(f"{self.agent_name} payload must be a dict.")

        missing = [key for key in self.allowed_inputs if key not in payload]
        if missing:
            raise AgentValidationError(
                f"{self.agent_name} missing required inputs: {missing}"
            )

        unexpected = [
            key
            for key in payload
            if key not in self.allowed_inputs and not key.startswith("_")
        ]
        if unexpected:
            raise AgentValidationError(
                f"{self.agent_name} received non-permitted inputs: {unexpected}"
            )

        forbidden = self._find_forbidden_keys(payload)
        if forbidden:
            raise AgentValidationError(
                f"{self.agent_name} received forbidden inputs: {sorted(forbidden)}"
            )

    @abstractmethod
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Generate a protected agent output."""

    def log_agent_call(
        self, input_summary: dict[str, Any] | str, output_summary: dict[str, Any] | str
    ) -> dict[str, Any]:
        meta = getattr(self, "last_call_metadata", None)
        if meta is None:
            meta = {
                "prompt": "Mock System Prompt\n\nPayload:\n" + (input_summary if isinstance(input_summary, str) else json.dumps(input_summary, ensure_ascii=False)),
                "sanitized_prompt": "Mock System Prompt\n\nPayload:\n" + (input_summary if isinstance(input_summary, str) else json.dumps(input_summary, ensure_ascii=False)),
                "raw_response": output_summary if isinstance(output_summary, str) else json.dumps(output_summary, ensure_ascii=False),
                "parsed_output": output_summary if isinstance(output_summary, dict) else {},
                "fallback_or_real_llm": "real_llm" if getattr(self, "c2rag_service", None) is not None else "fallback"
            }
        entry = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "timestamp": utc_now_iso(),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "llm_prompt": meta.get("prompt"),
            "sanitized_prompt": meta.get("sanitized_prompt"),
            "llm_response": meta.get("raw_response"),
            "parsed_output": meta.get("parsed_output"),
            "fallback_or_real_llm": meta.get("fallback_or_real_llm"),
        }
        self.call_log.append(entry)
        self.last_call_metadata = None
        return entry

    def _llm_json_or_fallback(
        self,
        system_prompt: str,
        payload: dict[str, Any],
        fallback: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        call_id = f"{self.agent_id}_{uuid.uuid4().hex[:10]}"
        prompt = (
            f"{system_prompt}\n\n"
            "Return JSON only. Payload:\n"
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )
        self._emit_event(
            {
                "type": "llm_call_started",
                "call_id": call_id,
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "system_prompt": system_prompt,
                "payload": payload,
                "prompt": prompt,
                "timestamp": utc_now_iso(),
            }
        )

        if self.llm_client is None:
            fallback_result = fallback()
            self.last_call_metadata = {
                "prompt": prompt,
                "sanitized_prompt": prompt,
                "raw_response": json.dumps(fallback_result, ensure_ascii=False),
                "parsed_output": fallback_result,
                "fallback_or_real_llm": "fallback"
            }
            self._emit_llm_completed(call_id, fallback_result, "fallback")
            return fallback_result

        try:
            raw = self._call_llm(
                prompt,
                system_prompt,
                payload,
                on_text_delta=lambda delta: self._emit_event(
                    {
                        "type": "llm_response_delta",
                        "call_id": call_id,
                        "agent_id": self.agent_id,
                        "agent_name": self.agent_name,
                        "delta": delta,
                        "timestamp": utc_now_iso(),
                    }
                ),
            )
            parsed = _parse_json_object(raw)
            if isinstance(parsed, dict):
                self.last_call_metadata = {
                    "prompt": prompt,
                    "sanitized_prompt": prompt,
                    "raw_response": raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False),
                    "parsed_output": parsed,
                    "fallback_or_real_llm": "real_llm"
                }
                self._emit_llm_completed(call_id, parsed, "real_llm")
                return parsed
            else:
                fallback_result = fallback()
                self.last_call_metadata = {
                    "prompt": prompt,
                    "sanitized_prompt": prompt,
                    "raw_response": str(raw),
                    "parsed_output": fallback_result,
                    "fallback_or_real_llm": "fallback"
                }
                self._emit_llm_completed(call_id, fallback_result, "fallback")
                return fallback_result
        except Exception as e:
            fallback_result = fallback()
            self.last_call_metadata = {
                "prompt": prompt,
                "sanitized_prompt": prompt,
                "raw_response": f"Error: {e}",
                "parsed_output": fallback_result,
                "fallback_or_real_llm": "fallback"
            }
            self._emit_llm_completed(
                call_id,
                fallback_result,
                "fallback",
                error=str(e),
            )
            return fallback_result

    def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        payload: dict[str, Any],
        on_text_delta: Callable[[str], None] | None = None,
    ) -> str | dict[str, Any]:
        client = self.llm_client

        if hasattr(client, "chat"):
            parameters = inspect.signature(client.chat).parameters
            if "on_text_delta" in parameters:
                return client.chat(
                    system_prompt=system_prompt,
                    payload=payload,
                    on_text_delta=on_text_delta,
                )
            return client.chat(system_prompt=system_prompt, payload=payload)
        if hasattr(client, "generate"):
            return client.generate(prompt)
        if callable(client):
            return client(prompt)

        raise TypeError("Unsupported llm_client interface.")

    def _emit_llm_completed(
        self,
        call_id: str,
        response: dict[str, Any],
        mode: str,
        error: str | None = None,
    ) -> None:
        self._emit_event(
            {
                "type": "llm_call_completed",
                "call_id": call_id,
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "response": response,
                "response_text": json.dumps(response, ensure_ascii=False, indent=2),
                "mode": mode,
                "error": error,
                "timestamp": utc_now_iso(),
            }
        )

    def _emit_event(self, event: dict[str, Any]) -> None:
        if self.event_sink is None:
            return
        try:
            self.event_sink(event)
        except Exception:
            return

    def _find_forbidden_keys(self, value: Any) -> set[str]:
        forbidden = set()
        forbidden_inputs = set(self.forbidden_inputs)

        if isinstance(value, dict):
            for key, nested in value.items():
                if key in forbidden_inputs:
                    forbidden.add(key)
                forbidden.update(self._find_forbidden_keys(nested))
        elif isinstance(value, list):
            for item in value:
                forbidden.update(self._find_forbidden_keys(item))

        return forbidden


COMMON_FORBIDDEN_INPUTS = (
    "raw_multimodal_data",
    "raw_student_data",
    "full_student_profile",
    "long_term_student_profile",
    "raw_teacher_resources",
    "full_teacher_resources",
    "full_original_teacher_resources",
    "direct_profile_update",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def summarize_text(value: Any, max_chars: int = 180) -> str:
    text = str(value or "")
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _parse_json_object(value: str | dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
