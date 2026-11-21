"""Explicit route registry and callable endpoint strategies.

Route selection is independent of business workflows and the HTTP transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from urllib.parse import parse_qs, urlsplit

if TYPE_CHECKING:
    from .http_server import CogniGuardDashboardAPIHandler


@dataclass(frozen=True, slots=True)
class ApiRequest:
    path: str
    query: dict[str, list[str]]

    @classmethod
    def from_target(cls, target: str) -> ApiRequest:
        parsed = urlsplit(target)
        return cls(parsed.path, parse_qs(parsed.query))

    @property
    def case_index(self) -> int:
        return int(self.query.get("index", ["0"])[0])


class Endpoint(Protocol):
    """Each registered callable handles one HTTP operation."""

    def __call__(self, handler: CogniGuardDashboardAPIHandler, request: ApiRequest, /) -> None: ...


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    path: str
    endpoint: Endpoint
    prefix: bool = False


class Router:
    """Exact matches take priority; prefix routes are longest-first."""

    def __init__(self) -> None:
        self._exact: dict[tuple[str, str], Route] = {}
        self._prefix: list[Route] = []

    def register(self, route: Route) -> None:
        if route.method != route.method.upper() or not route.path.startswith("/api/"):
            raise ValueError(f"Invalid API route: {route.method} {route.path}")
        if not callable(route.endpoint):
            raise TypeError("Route endpoint must be callable")
        if any(
            item.method == route.method and item.path == route.path and item.prefix == route.prefix
            for item in self.routes
        ):
            raise ValueError(f"Duplicate API route: {route.method} {route.path}")
        if route.prefix:
            self._prefix.append(route)
            self._prefix.sort(key=lambda item: len(item.path), reverse=True)
        else:
            self._exact[(route.method, route.path)] = route

    @property
    def routes(self) -> tuple[Route, ...]:
        return tuple(self._exact.values()) + tuple(self._prefix)

    def match(self, method: str, path: str) -> Route | None:
        exact = self._exact.get((method, path))
        if exact is not None:
            return exact
        return next(
            (item for item in self._prefix if item.method == method and path.startswith(item.path)),
            None,
        )

    def allowed_methods(self, path: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    route.method
                    for route in self.routes
                    if path == route.path or (route.prefix and path.startswith(route.path))
                }
            )
        )

    def dispatch(
        self, method: str, handler: CogniGuardDashboardAPIHandler, request: ApiRequest
    ) -> bool:
        route = self.match(method, request.path)
        if route is None:
            return False
        route.endpoint(handler, request)
        return True
