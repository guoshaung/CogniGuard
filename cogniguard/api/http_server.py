"""Research visualization HTTP transport: CORS, JSON, NDJSON, and static files."""

from __future__ import annotations

import json
import mimetypes
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote

from cogniguard.runtime.protection_context import transport_scope
from cogniguard.runtime.sessions import (
    BudgetExceeded,
    InvalidSessionToken,
    RequestConflict,
    SessionBusy,
    SessionError,
)

from .dependencies import PROJECT_ROOT
from .routes import create_router
from .routing import ApiRequest


class CogniGuardDashboardAPIHandler(BaseHTTPRequestHandler):
    """Dispatch API requests and serve the research visualization for GETs."""

    router = create_router()

    @staticmethod
    def _public_payload(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: CogniGuardDashboardAPIHandler._public_payload(item)
                for key, item in value.items()
                if key not in {"session_token", "traceback"}
            }
        if isinstance(value, (list, tuple)):
            return [CogniGuardDashboardAPIHandler._public_payload(item) for item in value]
        return value

    def _capture_session_token(self, token: str) -> None:
        if not isinstance(token, str) or not token or any(c in token for c in "\r\n"):
            raise InvalidSessionToken("Invalid session credential")
        self._response_session_token = token

    def _session_cookie_header(self) -> None:
        token = getattr(self, "_response_session_token", None)
        if token:
            cookie = SimpleCookie()
            cookie["cgc_session"] = token
            cookie["cgc_session"]["httponly"] = True
            cookie["cgc_session"]["samesite"] = "Lax"
            cookie["cgc_session"]["path"] = "/api"
            self.send_header("Set-Cookie", cookie["cgc_session"].OutputString())
        demo_token = getattr(self, "_demo_identity_cookie", None)
        if demo_token is not None:
            cookie = SimpleCookie()
            cookie["cgc_demo_identity"] = demo_token
            cookie["cgc_demo_identity"]["httponly"] = True
            cookie["cgc_demo_identity"]["samesite"] = "Strict"
            cookie["cgc_demo_identity"]["path"] = "/api/demo-identity"
            cookie["cgc_demo_identity"]["max-age"] = 3600 if demo_token else 0
            self.send_header("Set-Cookie", cookie["cgc_demo_identity"].OutputString())

    def _request_session_token(self) -> str | None:
        cookie_token = None
        raw_cookie = self.headers.get("Cookie", "")
        if raw_cookie:
            try:
                cookie = SimpleCookie()
                cookie.load(raw_cookie)
            except CookieError as exc:
                raise InvalidSessionToken("Malformed session cookie") from exc
            if "cgc_session" in cookie:
                cookie_token = cookie["cgc_session"].value
                if not cookie_token:
                    raise InvalidSessionToken("Empty session credential")
            elif "cgc_session" in raw_cookie:
                raise InvalidSessionToken("Malformed session cookie")
        authorization = self.headers.get("Authorization")
        if authorization is not None:
            scheme, _, bearer = authorization.partition(" ")
            if scheme.casefold() != "bearer" or not bearer.strip() or len(bearer.split()) != 1:
                raise InvalidSessionToken("Malformed bearer credential")
            if cookie_token is not None and cookie_token != bearer.strip():
                raise InvalidSessionToken("Conflicting session credentials")
            return bearer.strip()
        return cookie_token

    def _discard_unread_body(self) -> None:
        # Early credential rejection precedes route JSON parsing. Drain a small
        # already-sent body so Windows does not reset the response connection.
        if getattr(self, "_request_body_read", False):
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return
        if not 0 < length <= 65536:
            return
        previous = self.connection.gettimeout()
        try:
            self.connection.settimeout(2)
            self.rfile.read(length)
        except OSError:
            pass
        finally:
            self.connection.settimeout(previous)

    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Authorization, Idempotency-Key"
        )

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, payload: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._set_cors_headers()
        self._session_cookie_header()
        self.end_headers()
        self.wfile.write(
            json.dumps(self._public_payload(payload), ensure_ascii=False).encode("utf-8")
        )

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length < 0:
            raise ValueError("Content-Length must be non-negative")
        body = self.rfile.read(length)
        self._request_body_read = True
        payload = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def _send_ndjson_event(self, payload: Any) -> None:
        self.wfile.write(
            json.dumps(self._public_payload(payload), ensure_ascii=False).encode("utf-8") + b"\n"
        )
        self.wfile.flush()

    def _prepare_stream_response(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self._set_cors_headers()
        self._session_cookie_header()
        self.end_headers()
        self.close_connection = True

    def _send_api_payload(self, builder: Any, *args: Any, **kwargs: Any) -> None:
        if builder is None:
            raise RuntimeError("dashboard data adapter is not importable")
        self._send_json(builder(*args, **kwargs))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        self._response_session_token = None
        self._demo_identity_cookie = None
        self._request_body_read = False
        try:
            with transport_scope(
                self._request_session_token(),
                self.headers.get("Idempotency-Key"),
                self._capture_session_token,
            ):
                request = ApiRequest.from_target(self.path)
                if self.router.dispatch(method, self, request):
                    return
                allowed = self.router.allowed_methods(request.path)
                if allowed:
                    self.send_response(405)
                    self.send_header("Allow", ", ".join((*allowed, "OPTIONS")))
                    self.send_header("Content-Type", "application/json")
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(b'{"error": "Method not allowed"}')
                elif method == "GET" and not request.path.startswith("/api/"):
                    self._serve_static(request.path)
                else:
                    self._send_json(
                        {"error": "API route not found", "path": request.path}, status=404
                    )
        except InvalidSessionToken:
            self._discard_unread_body()
            self._send_json(
                {"error": "Session credential is invalid", "code": "invalid_session"}, status=401
            )
        except BudgetExceeded:
            self._send_json(
                {"error": "Session budget exhausted", "code": "budget_exceeded"}, status=429
            )
        except (RequestConflict, SessionBusy):
            self._send_json(
                {"error": "Request conflicts with session state", "code": "request_conflict"},
                status=409,
            )
        except SessionError:
            self._send_json(
                {"error": "Session request could not proceed", "code": "session_error"}, status=409
            )
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except (BrokenPipeError, ConnectionResetError):
            return
        except PermissionError:
            self._send_json({"error": "Request is not permitted"}, status=403)
        except Exception:
            self._send_json({"error": "Request processing failed"}, status=500)

    def _serve_static(self, path: str) -> None:
        relative = unquote(path).lstrip("/") or "index.html"
        roots = (PROJECT_ROOT / "visualization/dist", PROJECT_ROOT / "visualization")
        candidates = [(root / relative).resolve() for root in roots]
        if any(
            not candidate.is_relative_to(root.resolve())
            for candidate, root in zip(candidates, roots)
        ):
            self._send_json({"error": "File not found"}, status=404)
            return
        file_path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if file_path is None:
            file_path = next(
                (root / "index.html" for root in roots if (root / "index.html").is_file()), None
            )
        if file_path is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")
            return
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(file_path.read_bytes())


def start_server(port: int = 8000) -> None:
    from cogniguard.runtime.mode import _load_env_file

    _load_env_file()
    httpd = ThreadingHTTPServer(("", port), CogniGuardDashboardAPIHandler)
    print(f"CogniGuard Academic Demo Server running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CogniGuard Server.")
    finally:
        httpd.server_close()
