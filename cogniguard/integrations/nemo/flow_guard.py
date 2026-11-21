"""Model-free NeMo Colang gates at CogniGuard's trusted boundaries.

Events contain fixed labels only; actual content stays in the local callback.
The gates do not grant permissions or execute an agent or tool.
"""
from __future__ import annotations

import asyncio
import atexit
import os
from threading import RLock, Thread

from .native import NativeNeMoUnavailable

_COLANG = '''
define user cgc check
  "cgc check"
define bot cgc allow
  "ALLOW"
define bot cgc block
  "BLOCK"
define flow cgc boundary
  user cgc check
  $allowed = execute cgc_boundary_check
  if $allowed
    bot cgc allow
  else
    bot cgc block
define subflow cgc retrieval check
  $allowed = execute cgc_retrieval_check
  if not $allowed
    $relevant_chunks = ""
'''

_YAML = r'''models: []
rails:
  config:
    regex_detection:
      retrieval:
        patterns:
          - '(?i)ignore\s+(all\s+)?(previous|prior)\s+(instructions|rules)'
          - '(?i)(reveal|print|show)\s+(the\s+)?(system|developer)\s+prompt'
          - '(忽略|无视).{0,12}(之前|上面|系统).{0,12}(指令|规则|提示)'
          - '(显示|泄露|输出).{0,10}(系统提示词|开发者指令)'
  retrieval:
    flows:
      - cgc retrieval check
'''


class NativeColangGates:
    """A bounded, local Colang engine; fail closed if execution is incomplete."""

    def __init__(self):
        try:
            from nemoguardrails import LLMRails, RailsConfig
            from nemoguardrails.actions import action
            from nemoguardrails.library.regex.actions import detect_regex_pattern

            self._rails = LLMRails(RailsConfig.from_content(colang_content=_COLANG, yaml_content=_YAML))
            self._detect = detect_regex_pattern
            self._pending = None

            @action(is_system_action=True)
            async def cgc_boundary_check():
                if self._pending is None:
                    raise RuntimeError("Missing trusted boundary input")
                return await self._check_text() if self._pending[0] != "retrieval" else True

            @action(is_system_action=True)
            async def cgc_retrieval_check():
                if self._pending is None:
                    raise RuntimeError("Missing trusted retrieval input")
                self._retrieval_seen = True
                allowed = await self._check_text() if self._pending[0] == "retrieval" else True
                self._last_retrieval_allowed = allowed
                return allowed

            self._rails.register_action(cgc_boundary_check)
            self._rails.register_action(cgc_retrieval_check)
            self._lock = RLock()
            self._loop = asyncio.new_event_loop()
            self._thread = Thread(target=self._loop.run_forever, name="cogniguard-colang", daemon=True)
            self._thread.start()
            self._closed = False
            self._failed = False
            atexit.register(self.close)
        except Exception as exc:
            raise NativeNeMoUnavailable("Native Colang gates could not be initialized") from exc

    async def _check_text(self):
        outcome = await self._detect(source="retrieval", text=self._pending[1], config=self._rails.config)
        return not outcome.metadata["is_match"]

    def check(self, stage: str, text: str) -> bool:
        if stage not in {"dialog", "retrieval", "execution"} or not isinstance(text, str):
            raise ValueError("Invalid Colang gate input")
        with self._lock:
            if self._closed or self._failed:
                raise NativeNeMoUnavailable("Native Colang gates are unavailable")
            self._pending = (stage, text)
            self._retrieval_seen = False
            self._last_retrieval_allowed = False
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._rails.generate_events_async([{"type": "UserIntent", "intent": "cgc check"}]),
                    self._loop,
                )
                events = future.result(timeout=30)
                answers = [event.get("text") for event in events if event.get("type") == "BotMessage"]
                finished = [event for event in events if event.get("type") == "InternalSystemActionFinished"]
                for name in ("cgc_boundary_check", "cgc_retrieval_check"):
                    checks = [event for event in finished if event.get("action_name") == name]
                    if len(checks) != 1 or checks[0].get("status") != "success":
                        raise ValueError("Colang action failed or did not run exactly once")
                if answers not in (["ALLOW"], ["BLOCK"]) or not self._retrieval_seen:
                    raise ValueError("Incomplete Colang flow")
                # The retrieval rail transforms the placeholder; its boolean must
                # be retained independently to enforce the actual candidate check.
                if stage == "retrieval":
                    return self._last_retrieval_allowed and answers == ["ALLOW"]
                return answers == ["ALLOW"]
            except Exception as exc:
                # A timed-out action may still be finishing; never reuse the engine.
                self._failed = True
                if "future" in locals():
                    future.cancel()
                raise NativeNeMoUnavailable("Native Colang gate failed") from exc
            finally:
                self._pending = None

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10)
            if not self._thread.is_alive():
                self._loop.close()


def configured_colang_gates():
    mode = os.environ.get("COGNIGUARD_NEMO_COLANG", "off").strip().lower()
    if mode == "off":
        return None
    if mode != "on":
        raise NativeNeMoUnavailable("COGNIGUARD_NEMO_COLANG must be 'on' or 'off'")
    if os.environ.get("COGNIGUARD_NEMO_NATIVE", "off").strip().lower() != "on":
        raise NativeNeMoUnavailable("Colang gates require the native NeMo base guard")
    return NativeColangGates()
