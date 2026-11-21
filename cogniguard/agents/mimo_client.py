"""Compatibility import; implementation: cogniguard.providers.mimo."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.providers.mimo")
