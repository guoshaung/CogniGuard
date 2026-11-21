"""仅实验使用的真实模型传输；无 mock 回退，不记录密钥或服务端错误正文。"""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


class ModelError(RuntimeError):
    pass


class JsonModel:
    def __init__(self, root: Path, model: str | None = None, no_proxy: bool = False,
                 max_completion_tokens: int = 650):
        # 复用现有配置约定，避免导入旧 backend 的完整 Agent 编排。
        values = {}
        env_path = root / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip('\"').strip("'")
        def setting(name, default=""):
            return os.environ.get(name, values.get(name, default))
        self.key = setting("MIMO_API_KEY").strip()
        if not self.key or self.key.startswith("your_"):
            raise ModelError("MIMO_API_KEY 未配置；不会使用模拟结果替代真实模型。")
        self.base_url = setting("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
        self.model = model or setting("MIMO_MODEL", "mimo-v2.5-pro")
        self.timeout = min(float(setting("MIMO_TIMEOUT_SECONDS", "60")), 60.0)
        # 默认 650 与既有 redteam/injecagent 运行一致；教学注入实验显式调高以避免长回答被截断。
        self.max_completion_tokens = int(max_completion_tokens)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if no_proxy else urllib.request.build_opener()

    def call(self, system: str, payload: dict) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        body = {"model": self.model, "messages": messages, "temperature": 0,
                "max_completion_tokens": self.max_completion_tokens, "thinking": {"type": "disabled"},
                "response_format": {"type": "json_object"}}
        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("not an object")
        except urllib.error.HTTPError as exc:
            raise ModelError(f"HTTP {exc.code}; 服务端错误正文未写入日志") from None
        except Exception as exc:
            raise ModelError(f"模型调用或 JSON 解析失败：{type(exc).__name__}") from None
        return {"output": parsed, "raw_output": raw, "messages": messages,
                "usage": result.get("usage", {}), "response_model": result.get("model"),
                "latency_ms": round((time.monotonic() - started) * 1000, 1)}
