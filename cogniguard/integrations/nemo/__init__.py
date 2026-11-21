"""Inspectable NeMo/Colang boundary; native execution is deliberately disabled."""

from .colang import ColangExecutionDisabled, ColangInterface

__all__ = ["ColangExecutionDisabled", "ColangInterface"]
