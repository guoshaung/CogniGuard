"""Repository layout and translation of paths stored before the layout migration."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_DIR = PROJECT_ROOT / "cogniguard"
VISUALIZATION_DIR = PROJECT_ROOT / "visualization"
RUNTIME_DIR = PROJECT_ROOT / "var"
LOGS_DIR = RUNTIME_DIR / "logs"
OUTPUTS_DIR = RUNTIME_DIR / "outputs"
RESULTS_DIR = RUNTIME_DIR / "results"
CACHE_DIR = RUNTIME_DIR / "cache"
ASSETS_DIR = PROJECT_ROOT / "assets"
MODELS_DIR = ASSETS_DIR / "models"
CHECKPOINTS_DIR = ASSETS_DIR / "checkpoints"
EDITGUARD_DIR = PROJECT_ROOT / "third_party" / "editguard"
IMAGE_WATERMARK_DIR = PROJECT_ROOT / "protection" / "supporting" / "image_watermark"
CG_GUARDRAILS_DIR = PROJECT_ROOT / "protection" / "supporting" / "cg_guardrails"
BENCHMARK_DATA_DIR = PROJECT_ROOT / "data" / "benchmarks"

LEGACY_PREFIXES = {
    "frontend": ("visualization",),
    "code": ("third_party", "editguard"),
    "dfg_locguard": ("protection", "supporting", "image_watermark"),
    "logs": ("var", "logs"),
    "outputs": ("var", "outputs"),
    "results": ("var", "results"),
    "models": ("assets", "models"),
    "checkpoints": ("assets", "checkpoints"),
    "datasets": ("data", "benchmarks"),
}


def resolve_project_path(value: str | Path, project_root: str | Path = PROJECT_ROOT) -> Path:
    """Translate an old project-local prefix; leave absolute external paths alone.

    This allows existing reports and image registry records to retain their
    original path strings. It does not create aliases or directories at the root.
    """
    root = Path(project_root).expanduser().resolve()
    path = Path(value).expanduser()
    if path.is_absolute():
        try:
            relative = path.resolve().relative_to(root)
        except ValueError:
            return path
    else:
        relative = path
    if relative.parts:
        if relative.parts[:2] == ("backend", "app"):
            relative = Path("cogniguard", *relative.parts[2:])
        elif relative.parts[:2] == ("dfg_locguard", "api_jobs"):
            relative = Path("var", "outputs", "sce_locguard_api_jobs", *relative.parts[2:])
        elif relative.parts[:3] == ("protection", "image_watermark", "api_jobs"):
            relative = Path("var", "outputs", "sce_locguard_api_jobs", *relative.parts[3:])
        elif relative.parts[:4] == ("protection", "supporting", "image_watermark", "api_jobs"):
            relative = Path("var", "outputs", "sce_locguard_api_jobs", *relative.parts[4:])
        replacement = LEGACY_PREFIXES.get(relative.parts[0])
        if replacement is not None:
            relative = Path(*replacement, *relative.parts[1:])
    return root / relative
