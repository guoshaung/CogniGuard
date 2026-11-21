"""Compatibility import; implementation: cogniguard.agents.protected_orchestrator."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.agents.protected_orchestrator")
