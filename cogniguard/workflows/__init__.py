"""LangGraph workflow composition; importing this package does not compile a graph."""

__all__ = ["LangGraphProtectionPipeline"]


def __getattr__(name):
    if name == "LangGraphProtectionPipeline":
        from .pipeline import LangGraphProtectionPipeline

        return LangGraphProtectionPipeline
    raise AttributeError(name)
