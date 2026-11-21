"""Compatibility import; implementation: cogniguard.agents.roles.learner."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.agents.roles.learner")
