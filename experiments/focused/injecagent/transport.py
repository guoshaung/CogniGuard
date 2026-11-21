"""MiMo 文本适配器：保留官方 ReAct 格式，不强制 JSON 输出。"""
import json
import time
import urllib.error
import urllib.request

from experiments.focused.redteam.model import JsonModel, ModelError


class TextModel(JsonModel):
    def call_text(self, system: str, user: str) -> dict:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        body = {"model": self.model, "messages": messages, "temperature": 0,
                "max_completion_tokens": 2048, "thinking": {"type": "disabled"}}
        request = urllib.request.Request(self.base_url + "/chat/completions",
            data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + self.key,
                                                   "Content-Type": "application/json"})
        started = time.monotonic()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            choice = result["choices"][0]
            output = choice["message"]["content"]
            if not isinstance(output, str) or not output.strip():
                raise ValueError("empty model content")
        except urllib.error.HTTPError as exc:
            raise ModelError(f"HTTP {exc.code}; 服务端错误正文未记录") from None
        except Exception as exc:
            raise ModelError(f"真实模型调用失败：{type(exc).__name__}") from None
        return {"output": output, "messages": messages, "usage": result.get("usage", {}),
                "response_model": result.get("model"), "finish_reason": choice.get("finish_reason"),
                "latency_ms": round((time.monotonic() - started) * 1000, 1)}
