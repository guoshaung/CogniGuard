"""外部开源注入检测器基线封装（对比用，不是 CogniGuard 的一部分）。

把业界常用的注入分类器作为“检测式防御”基线：对不可信输入打分，命中即拦截。
与 CogniGuard 的结构性最小化/访问控制形成对比：检测器是概率性的，有漏检与误伤。

实测标签：protectai/deberta-v3-base-prompt-injection-v2 -> SAFE / INJECTION；
deepset/deberta-v3-base-injection -> LEGIT / INJECTION。统一以 label 含 "INJECT" 判为 unsafe。
分类器推理很快且非线程安全，故在并发模型调用前一次性串行预计算，不在工作线程里调用。
"""
from __future__ import annotations

import threading

REGISTRY = {
    "protectai": "protectai/deberta-v3-base-prompt-injection-v2",
    "deepset": "deepset/deberta-v3-base-injection",
}

_LOCK = threading.Lock()
_CACHE: dict[str, object] = {}


def get_detector(name: str):
    if name not in REGISTRY:
        raise KeyError(f"未知检测器 {name!r}；可选 {sorted(REGISTRY)}")
    with _LOCK:
        if name not in _CACHE:
            import torch
            from transformers import pipeline
            device = 0 if torch.cuda.is_available() else -1
            _CACHE[name] = pipeline("text-classification", model=REGISTRY[name],
                                    device=device, truncation=True, max_length=512)
        return _CACHE[name]


def classify(name: str, text: str) -> dict:
    """返回 {detector, model_id, label, score, unsafe}。unsafe=True 表示被判为注入。"""
    clf = get_detector(name)
    result = clf(text[:4000])[0]
    label = str(result["label"])
    return {"detector": name, "model_id": REGISTRY[name], "label": label,
            "score": float(result["score"]), "unsafe": "INJECT" in label.upper()}
