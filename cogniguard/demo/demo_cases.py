"""Compatibility import; implementation: cogniguard.applications.education.cases."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.applications.education.cases")
