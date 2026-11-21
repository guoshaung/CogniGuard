"""Compatibility module; implementation lives in cogniguard.observability.telemetry."""

import sys

from cogniguard.observability import telemetry as _implementation

sys.modules[__name__] = _implementation
