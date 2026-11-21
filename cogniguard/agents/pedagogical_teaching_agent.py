"""Compatibility import; implementation: cogniguard.agents.roles.teaching."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.agents.roles.teaching")
