"""Compatibility import; implementation: cogniguard.workflows.education.conversation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.workflows.education.conversation")
