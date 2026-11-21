"""Research HTTP service: python -m cogniguard.api [port].

HTTP transport: cogniguard.api.http_server
Active routes: cogniguard.api.routes
"""

from __future__ import annotations

import sys

from cogniguard.api.http_server import CogniGuardDashboardAPIHandler, start_server

__all__ = ["CogniGuardDashboardAPIHandler", "start_server"]


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port)
