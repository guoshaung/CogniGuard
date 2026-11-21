"""Compatibility module; implementation lives in cogniguard.observability.graphs."""

import sys

from cogniguard.observability import graphs as _implementation

sys.modules[__name__] = _implementation
