"""Compatibility package; implementations live in cogniguard.workflows.benchmarks."""
from importlib import import_module as _import_module


def __getattr__(name):
    return getattr(_import_module("cogniguard.workflows.benchmarks"), name)
