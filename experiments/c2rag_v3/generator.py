from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:  # pragma: no cover - the deterministic test fallback remains available
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None

if torch is not None:
    torch.set_num_threads(max(1, min(2, os.cpu_count() or 2)))


_QWEN_CACHE: dict[tuple[str, str, str], tuple[Any, Any]] = {}
_GENERATION_CACHE: dict[tuple[str, str, str, str, str, str], str] = {}


@dataclass(frozen=True)
class GenerationOutput:
    text: str
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cache_hit: bool = False


class TeachingGenerator:
    """Shared generator interface; production pilot uses the local Qwen model."""

    def __init__(
        self,
        backend: str = "fallback",
        model_name: str = "Qwen/Qwen2.5-0.5B-Instruct",
        model_revision: str = "7ae557604adf67be50417f59c2c2f167def9a775",
        model_path: str | None = None,
        device: str = "auto",
        max_new_tokens: int = 96,
        seed: int = 20260827,
    ) -> None:
        self.backend_requested = backend
        self.model_name = model_name
        self.model_revision = model_revision
        self.model_path = model_path
        self.device = self._resolve_device(device)
        self.max_new_tokens = max_new_tokens
        self.seed = seed
        self.calls = 0
        self.tokenizer: Any = None
        self.model: Any = None
        self.is_fallback = True
        self.failure_reason = ""
        if backend in {"auto", "qwen"}:
            try:
                self._load_qwen()
            except Exception as exc:  # noqa: BLE001 - recorded in manifest
                self.failure_reason = f"{type(exc).__name__}: {exc}"
                if backend == "qwen":
                    raise RuntimeError(f"Qwen generator unavailable: {self.failure_reason}") from exc

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        return "cuda" if torch is not None and torch.cuda.is_available() else "cpu"

    def _load_qwen(self) -> None:
        if torch is None or AutoTokenizer is None or AutoModelForCausalLM is None:
            raise RuntimeError("transformers and torch are required")
        source = self.model_path or self.model_name
        cache_key = (source, self.model_revision, self.device)
        if cache_key not in _QWEN_CACHE:
            tokenizer = AutoTokenizer.from_pretrained(source, revision=self.model_revision, local_files_only=bool(self.model_path))
            model = AutoModelForCausalLM.from_pretrained(source, revision=self.model_revision, local_files_only=bool(self.model_path))
            model.to(self.device)
            model.eval()
            _QWEN_CACHE[cache_key] = (tokenizer, model)
        self.tokenizer, self.model = _QWEN_CACHE[cache_key]
        self.is_fallback = False

    def manifest(self) -> dict[str, Any]:
        return {
            "backend_requested": self.backend_requested,
            "model_name": self.model_name,
            "revision": self.model_revision,
            "model_path": self.model_path,
            "device": self.device,
            "max_new_tokens": self.max_new_tokens,
            "seed": self.seed,
            "fallback": self.is_fallback,
            "failure_reason": self.failure_reason,
        }

    def generate(self, query: str, evidence: str, action: str, topic: str) -> GenerationOutput:
        started = time.perf_counter()
        self.calls += 1
        if action == "refuse":
            return GenerationOutput("当前资源不在允许的披露范围内。", 0, 0, 0, (time.perf_counter() - started) * 1000)
        if self.is_fallback:
            text = self._fallback(evidence, action, topic)
            return GenerationOutput(text, 0, 0, len(text.split()), (time.perf_counter() - started) * 1000)
        prompt = (
            "你是数学教学助手。严格依据允许的证据回答用户问题。"
            "不得补写证据中没有的私人信息或受保护原文。"
            f"\n动作={action}\n主题={topic}\n允许证据={evidence}\n用户问题={query}\n"
            "请给出简洁、可教学验证的回答。"
        )
        cache_key = (self.model_path or self.model_name, self.model_revision, query, evidence, action, topic)
        if cache_key in _GENERATION_CACHE:
            text = _GENERATION_CACHE[cache_key]
            return GenerationOutput(text, 0, 0, len(self.tokenizer.encode(text, add_special_tokens=False)), (time.perf_counter() - started) * 1000, True)
        torch.manual_seed(self.seed)
        encoded = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with torch.inference_mode():
            generated = self.model.generate(
                **encoded,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=1.0,
                top_p=1.0,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = generated[0][encoded["input_ids"].shape[1] :]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        if not text:
            text = "无法在当前允许证据范围内生成回答。"
        _GENERATION_CACHE[cache_key] = text
        return GenerationOutput(
            text,
            1,
            int(encoded["input_ids"].shape[1]),
            int(new_tokens.shape[0]),
            (time.perf_counter() - started) * 1000,
        )

    @staticmethod
    def _fallback(evidence: str, action: str, topic: str) -> str:
        if action == "unrestricted_source":
            return evidence
        if action == "controlled_quote":
            return f"引用摘录：{evidence}"
        if action == "minimal_excerpt":
            return f"受控摘录：{evidence}"
        if action == "abstractive_summary":
            return evidence
        if action == "concept_only":
            return evidence
        if action == "minimal_hint":
            return evidence
        if action == "generated_variant":
            return evidence
        return "当前资源不在允许的披露范围内。"


def model_file_hash(model_path: str | None) -> str | None:
    if not model_path:
        return None
    candidate = Path(model_path) / "model.safetensors"
    if not candidate.is_file():
        return None
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
