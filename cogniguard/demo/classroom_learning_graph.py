"""Compatibility import; implementation: cogniguard.workflows.education.classroom_learning."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.workflows.education.classroom_learning")
