"""No-retry MiMo JSON mode; validate each node before it can be signed/sent."""
import json
import base64
import time
import urllib.error
import urllib.request

from experiments.cgc_propagation_v2.dataset import ROOT, append_json, now
from .contract import FormatError, validate_wire, validate_public_binding


class NodeContractStopped(RuntimeError):
    pass


class StrictBudget:
    def __init__(self, path, limit, client=None):
        if client is None:
            from experiments.focused.redteam.model import JsonModel
            client = JsonModel(ROOT, max_completion_tokens=1200)
        self.client, self.path, self.limit = client, path, limit
        self.calls, self.records = 0, []
        self.case_id = self.node_id = self.method = self.seed = None

    def call(self, system, payload):
        if self.calls >= self.limit:
            raise NodeContractStopped("budget_exhausted_before_call")
        self.calls += 1
        body = {"model": self.client.model, "messages": [{"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                "temperature": 0, "seed": self.seed, "max_completion_tokens": 1200,
                "thinking": {"type": "disabled"}, "response_format": {"type": "json_object"}}
        record = {"attempt": self.calls, "case_id": self.case_id, "node_id": self.node_id,
                  "method": self.method, "seed": self.seed, "started_at_utc": now(),
                  "request_body": body, "status": "transport_error", "usage": None}
        start = time.perf_counter()
        try:
            request = urllib.request.Request(self.client.base_url + "/chat/completions",
                data=json.dumps(body).encode("utf-8"), headers={"Authorization": "Bearer " + self.client.key,
                                                             "Content-Type": "application/json"})
            with self.client.opener.open(request, timeout=self.client.timeout) as response:
                # Persist exact response bytes (decoded losslessly as UTF-8) before parsing.
                response_bytes = response.read()
                record["raw_http_body_base64"] = base64.b64encode(response_bytes).decode("ascii")
                record["raw_http_body"] = response_bytes.decode("utf-8")
        except urllib.error.HTTPError as exc:
            record["error_code"] = "http_" + str(exc.code)
            self._save(record, start)
            raise NodeContractStopped("transport_error") from None
        except Exception as exc:
            record["error_code"] = type(exc).__name__
            self._save(record, start)
            raise NodeContractStopped("transport_error") from None
        try:
            result = json.loads(record["raw_http_body"])
            record["response"] = result
            record["usage"] = result.get("usage")
            message = result["choices"][0]["message"]
            record["finish_reason"] = result["choices"][0].get("finish_reason")
            record["status"] = "format_error"
            if message.get("refusal"):
                record["status"], record["error_code"] = "refusal", "provider_refusal_without_report"
                raise FormatError("provider_refusal_without_report")
            if record["finish_reason"] != "stop":
                raise FormatError("non_stop_finish_reason")
            outer, inner, category = validate_wire(message.get("content"))
            validate_public_binding(inner, json.loads(payload["task_view"]["question"]))
            record["status"] = category
            usage = result.get("usage") or {}
            if not all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("prompt_tokens", "completion_tokens")):
                record["status"], record["error_code"] = "transport_error", "missing_usage_metadata"
                raise NodeContractStopped("missing_usage_metadata")
        except Exception as exc:
            if record["status"] != "refusal" and record.get("error_code") != "missing_usage_metadata":
                record["status"] = "format_error"
            record.setdefault("error_code", str(exc) if isinstance(exc, FormatError) else type(exc).__name__)
            self._save(record, start)
            raise NodeContractStopped(record["status"]) from None
        self._save(record, start)
        return {"output": outer, "usage": usage}

    def _save(self, record, started):
        record["latency_ms"] = round((time.perf_counter()-started)*1000, 3)
        append_json(self.path, record)
        self.records.append(record)
