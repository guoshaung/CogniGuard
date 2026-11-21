"""Canonical protection entrypoint: every request executes a LangGraph graph."""
from __future__ import annotations

from core.domain import ProtectionResult
from core.inputs import load_inputs
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline

# Keep the public import path while replacing the sequential implementation.
ProtectionPipeline = LangGraphProtectionPipeline

__all__ = ["ProtectionPipeline", "ProtectionResult", "load_inputs"]
