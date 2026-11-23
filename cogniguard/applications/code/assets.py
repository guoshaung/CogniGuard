"""Split one Python file into release units. Signatures are not units."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodeUnit:
    resource_id: str
    unit_id: str
    kind: str
    source: str


@dataclass(frozen=True)
class FunctionSummary:
    """Signature and docstring. This text is not a disclosed unit."""

    unit_id: str
    signature: str
    docstring: str

    @property
    def text(self) -> str:
        if self.docstring:
            return f"{self.signature}\n{self.docstring}"
        return self.signature


@dataclass(frozen=True)
class CodeAssets:
    resource_id: str
    units: tuple[CodeUnit, ...]
    summaries: tuple[FunctionSummary, ...]

    def unit(self, unit_id: str) -> CodeUnit:
        for item in self.units:
            if item.unit_id == unit_id:
                return item
        raise KeyError(unit_id)

    def summary(self, unit_id: str) -> FunctionSummary:
        for item in self.summaries:
            if item.unit_id == unit_id:
                return item
        raise KeyError(unit_id)


def load_python_assets(source: str, resource_id: str) -> CodeAssets:
    """Each top-level function, class, and constant is one unit."""
    tree = ast.parse(source)
    units: list[CodeUnit] = []
    summaries: list[FunctionSummary] = []
    seen: set[str] = set()
    for node in tree.body:
        extracted = _extract(source, resource_id, node)
        if extracted is None:
            continue
        found, summary = extracted
        for unit in found:
            if unit.unit_id in seen:
                raise ValueError(unit.unit_id)
            seen.add(unit.unit_id)
            units.append(unit)
        if summary is not None:
            summaries.append(summary)
    return CodeAssets(resource_id, tuple(units), tuple(summaries))


def load_python_file(path: str | Path, resource_id: str) -> CodeAssets:
    return load_python_assets(Path(path).read_text(encoding="utf-8"), resource_id)


def _extract(source: str, resource_id: str, node: ast.AST):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        unit = CodeUnit(resource_id, node.name, "function", _segment(source, node))
        summary = FunctionSummary(node.name, _signature(node), ast.get_docstring(node) or "")
        return (unit,), summary
    if isinstance(node, ast.ClassDef):
        unit = CodeUnit(resource_id, node.name, "class", _segment(source, node))
        return (unit,), None
    if isinstance(node, ast.Assign):
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if not names:
            return None
        text = _segment(source, node)
        return tuple(CodeUnit(resource_id, name, "constant", text) for name in names), None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        unit = CodeUnit(resource_id, node.target.id, "constant", _segment(source, node))
        return (unit,), None
    return None


def _segment(source: str, node: ast.AST) -> str:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if start is None or end is None:
        raise ValueError("node has no source span")
    decorators = getattr(node, "decorator_list", ())
    if decorators:
        start = min(start, decorators[0].lineno)
    return "\n".join(source.splitlines()[start - 1 : end])


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = "" if node.returns is None else f" -> {ast.unparse(node.returns)}"
    return f"{prefix} {node.name}({_format_arguments(node.args)}){returns}"


def _format_arguments(args: ast.arguments) -> str:
    parts: list[str] = []
    positional = [*args.posonlyargs, *args.args]
    default_start = len(positional) - len(args.defaults)
    for index, arg in enumerate(positional):
        if index == len(args.posonlyargs) and args.posonlyargs:
            parts.append("/")
        parts.append(_format_arg(arg, args.defaults[index - default_start] if index >= default_start else None))
    if args.vararg is not None:
        parts.append(_format_star(args.vararg, "*"))
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parts.append(_format_arg(arg, default))
    if args.kwarg is not None:
        parts.append(_format_star(args.kwarg, "**"))
    return ", ".join(parts)


def _format_arg(arg: ast.arg, default: ast.expr | None) -> str:
    text = arg.arg if arg.annotation is None else f"{arg.arg}: {ast.unparse(arg.annotation)}"
    if default is not None:
        text += f" = {ast.unparse(default)}"
    return text


def _format_star(arg: ast.arg, marker: str) -> str:
    text = f"{marker}{arg.arg}"
    if arg.annotation is not None:
        text += f": {ast.unparse(arg.annotation)}"
    return text
