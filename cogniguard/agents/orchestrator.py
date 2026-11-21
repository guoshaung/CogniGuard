"""Compatibility import; implementation: cogniguard.agents.research_orchestrator."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.agents.research_orchestrator")
