"""供应链清单：登记外部制品及其固定方式（哈希 / 版本 / revision）与许可证。"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import subprocess

from experiments.focused.injecagent.upstream import REVISION as INJECAGENT_REVISION

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Artifact:
    name: str
    kind: str              # hf_model / remote_model / dataset / config / dependency
    license: str
    pin_by: str            # "sha256" / "version" / "revision"
    path: str | None = None        # 可本地哈希的制品（相对 ROOT）
    declared: dict = field(default_factory=dict)   # 对不可哈希制品声明的固定值


def build_inventory() -> list[Artifact]:
    ds = f"experiments/external_data/injecagent/{INJECAGENT_REVISION}"
    return [
        # —— 基座模型：远程 API，按模型名+端点声明固定（不可哈希）——
        Artifact("base_model_mimo", "remote_model", "vendor API（火山/小米 MiMo）", "version",
                 declared={"model": "mimo-v2.5-pro", "endpoint": "MIMO_BASE_URL(.env)"}),
        # —— 外部检测器：HuggingFace 权重，按 repo+revision 固定；license 记录 ——
        Artifact("detector_protectai", "hf_model", "Apache-2.0", "revision",
                 declared={"repo": "protectai/deberta-v3-base-prompt-injection-v2", "revision": "UNPINNED"}),
        Artifact("detector_deepset", "hf_model", "MIT", "revision",
                 declared={"repo": "deepset/deberta-v3-base-injection", "revision": "UNPINNED"}),
        # —— 外部数据集：已固定 commit，并对关键文件做哈希 ——
        Artifact("injecagent_dataset_cases", "dataset", "MIT", "sha256",
                 path=f"{ds}/data/user_cases.jsonl", declared={"revision": INJECAGENT_REVISION}),
        Artifact("injecagent_license", "dataset", "MIT", "sha256", path=f"{ds}/LICENCE"),
        # —— 本地关键配置 ——
        Artifact("config_focused", "config", "project", "sha256", path="configs/focused.yaml"),
        # —— 依赖包：按安装版本固定 ——
        Artifact("dep_numpy", "dependency", "BSD-3", "version", declared={"package": "numpy"}),
        Artifact("dep_torch", "dependency", "BSD-3", "version", declared={"package": "torch"}),
        Artifact("dep_transformers", "dependency", "Apache-2.0", "version", declared={"package": "transformers"}),
        Artifact("dep_sklearn", "dependency", "BSD-3", "version", declared={"package": "scikit-learn"}),
    ]


def file_sha256(rel_path: str) -> str | None:
    p = ROOT / rel_path
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dep_version(package: str) -> str | None:
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version(package)
        except PackageNotFoundError:
            # The graph orchestrator is intentionally lightweight. Heavy model
            # dependencies may live in the isolated, preserved model worker.
            worker = ROOT / ".venv/Scripts/python.exe"
            if package not in {"torch", "transformers", "scikit-learn"} or not worker.is_file():
                return None
            probe = subprocess.run(
                [str(worker), "-B", "-c",
                 "import importlib.metadata as m,sys;print(m.version(sys.argv[1]))", package],
                capture_output=True, text=True, timeout=10, check=False,
            )
            return probe.stdout.strip() if probe.returncode == 0 and probe.stdout.strip() else None
    except Exception:
        return None


def collect_actual(inv: list[Artifact]) -> dict:
    """采集每个制品的当前真实指纹：哈希 / 依赖版本 / 声明值。"""
    actual = {}
    for a in inv:
        if a.pin_by == "sha256" and a.path:
            actual[a.name] = {"sha256": file_sha256(a.path), "missing": file_sha256(a.path) is None}
        elif a.pin_by == "version" and a.declared.get("package"):
            v = dep_version(a.declared["package"])
            actual[a.name] = {"version": v, "missing": v is None}
        elif a.kind == "remote_model":
            actual[a.name] = {"model": a.declared.get("model"), "missing": False}
        elif a.kind == "hf_model":
            actual[a.name] = {"revision": a.declared.get("revision"), "missing": False}
        else:
            actual[a.name] = {"declared": a.declared, "missing": False}
    return actual
