"""C²-RAG V3 exports, loaded lazily after the model environment is selected."""
from __future__ import annotations

from importlib import import_module


__all__ = ["C2RAGV3", "C2RAGConfig", "C2RAGResult", "ResourceDocument"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module(".core", __name__), name)
