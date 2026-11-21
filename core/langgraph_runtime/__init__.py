"""Compatibility package; implementations live in cogniguard.workflows."""
from importlib import import_module as _import_module


def __getattr__(name):
    return getattr(_import_module("cogniguard.workflows"), name)

__all__ = ["LangGraphProtectionPipeline"]
