from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ProfileEncodingResult:
    base_embedding: list[float]
    abstract_profile: dict[str, Any]
    subspaces: dict[str, list[float]]
    labels: dict[str, Any]
    textual_cards: dict[str, str]


class ProfileEncodingPipeline:
    """Hybrid profile encoding pipeline with an abstract profile layer."""

    def __init__(self, model_name: str = "microsoft/deberta-v3-large") -> None:
        self.model_name = model_name
        self._backend = self._load_backend(model_name)

    def encode(self, mixed_input: dict[str, Any]) -> ProfileEncodingResult:
        text = mixed_input.get("mixed_text", "")
        labels = mixed_input.get("labels", {})
        base_embedding = self._backend.encode(text)
        abstract_profile = self._build_abstract_profile(base_embedding, labels, mixed_input)
        subspaces = self._split_subspaces(base_embedding)
        textual_cards = self._verbalize(abstract_profile, subspaces, labels)
        return ProfileEncodingResult(
            base_embedding=base_embedding,
            abstract_profile=abstract_profile,
            subspaces=subspaces,
            labels=labels,
            textual_cards=textual_cards,
        )

    def _load_backend(self, model_name: str):
        if os.environ.get("COGNIGUARD_PROFILE_ENCODER_BACKEND", "").strip().lower() in {"fallback", "mock", "hash"}:
            return _FallbackBackend(model_name)
        try:
            from transformers import AutoModel, AutoTokenizer
            import torch
        except Exception:
            return _FallbackBackend(model_name)
        try:
            return _HFBackend(model_name=model_name, AutoModel=AutoModel, AutoTokenizer=AutoTokenizer, torch=torch)
        except Exception:
            return _FallbackBackend(model_name)

    def _build_abstract_profile(
        self,
        base_embedding: list[float],
        labels: dict[str, Any],
        mixed_input: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "profile_id": mixed_input.get("profile_id"),
            "source_types": mixed_input.get("source_types", []),
            "embedding_dim": len(base_embedding),
            "encoding_model": self.model_name,
            "labels": labels,
        }

    def _split_subspaces(self, base_embedding: list[float]) -> dict[str, list[float]]:
        if not base_embedding:
            return {"learning": [], "privacy": [], "teaching": []}
        chunks = _chunk_embedding(base_embedding, 3)
        return {"learning": chunks[0], "privacy": chunks[1], "teaching": chunks[2]}

    def _verbalize(
        self,
        abstract_profile: dict[str, Any],
        subspaces: dict[str, list[float]],
        labels: dict[str, Any],
    ) -> dict[str, str]:
        return {
            "learning_card": _verbalize_learning(labels),
            "privacy_card": _verbalize_privacy(labels),
            "teaching_card": _verbalize_teaching(labels),
            "abstract_card": (
                f"profile={abstract_profile.get('profile_id')} | "
                f"model={abstract_profile.get('encoding_model')} | "
                f"dims={abstract_profile.get('embedding_dim')} | "
                f"subspaces={','.join(subspaces.keys())}"
            ),
        }


class _HFBackend:
    def __init__(self, model_name: str, AutoModel, AutoTokenizer, torch) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.torch = torch
        self.model.eval()

    def encode(self, text: str) -> list[float]:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with self.torch.no_grad():
            outputs = self.model(**inputs)
        hidden = outputs.last_hidden_state.mean(dim=1).squeeze(0)
        return hidden.detach().cpu().float().tolist()


class _FallbackBackend:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def encode(self, text: str) -> list[float]:
        seed = sum(ord(ch) for ch in text) or 1
        return [((seed * (i + 3)) % 997) / 997.0 for i in range(24)]


def _chunk_embedding(values: list[float], parts: int) -> list[list[float]]:
    if parts <= 0:
        return [values]
    size = max(1, len(values) // parts)
    chunks = [values[i * size : (i + 1) * size] for i in range(parts - 1)]
    chunks.append(values[(parts - 1) * size :])
    return [chunk for chunk in chunks if chunk]


def _verbalize_learning(labels: dict[str, Any]) -> str:
    return f"学习画像：掌握度={labels.get('mastery_level', 'unknown')}，错误类型={labels.get('error_type', 'unknown')}，阶段={labels.get('learning_stage', 'unknown')}"


def _verbalize_privacy(labels: dict[str, Any]) -> str:
    return f"隐私画像：敏感级别={labels.get('sensitivity_level', 'unknown')}，可记录范围={labels.get('recordable_scope', 'bounded')}"


def _verbalize_teaching(labels: dict[str, Any]) -> str:
    return f"教学画像：提示深度={labels.get('hint_depth', 'medium')}，教学策略={labels.get('teaching_strategy', 'scaffold_then_variant')}"
