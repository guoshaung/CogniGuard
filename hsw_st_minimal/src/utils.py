"""通用工具：路径、随机种子、JSONL、时间戳与 ID。"""

from __future__ import annotations

import json
import os
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_path(p: str | Path, root: Path | None = None) -> Path:
    root = root or project_root()
    path = Path(p)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def resolve_model_device_dtype(cfg: dict) -> None:
    """将 model.device / model.dtype 的 auto 解析为实际 cuda/cpu 与 float16/float32。"""
    mm = cfg.get("model")
    if not isinstance(mm, dict):
        return
    dev = str(mm.get("device", "auto")).strip().lower()
    if dev in ("auto", ""):
        try:
            import torch

            mm["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            mm["device"] = "cpu"
    else:
        mm["device"] = dev

    dtype = str(mm.get("dtype", "auto")).strip().lower()
    if dtype in ("auto", ""):
        mm["dtype"] = "float16" if mm["device"] == "cuda" else "float32"
    else:
        mm["dtype"] = dtype
    if mm["device"] == "cpu" and mm["dtype"] in ("float16", "fp16", "bfloat16", "bf16"):
        mm["dtype"] = "float32"


def set_seed(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_watermark_id() -> str:
    return f"wm_{uuid.uuid4().hex[:12]}"


def new_answer_id(sample_id: str) -> str:
    return f"ans_{sample_id}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def expand_env_in_str(s: str) -> str:
    return os.path.expandvars(s)


def load_yaml_with_env_substitution(path: Path) -> dict[str, Any]:
    import yaml

    text = path.read_text(encoding="utf-8")
    # ${VAR} 形式
    pattern = re.compile(r"\$\{([^}]+)\}")

    def repl(m: re.Match[str]) -> str:
        key = m.group(1).strip()
        return os.environ.get(key, "")

    text = pattern.sub(repl, text)
    return yaml.safe_load(text) or {}
