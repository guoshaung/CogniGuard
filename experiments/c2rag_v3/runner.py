from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .baselines import EXTERNAL_BASELINES, METHODS


SEED = 20260827
DENSE_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
RERANKER_REVISION = "81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc"
GENERATOR_REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _snapshot(root: Path, repo_name: str, revision: str) -> Path:
    return root / "models" / "hf_cache" / f"models--{repo_name.replace('/', '--')}" / "snapshots" / revision


def _model_path(root: Path, repo_name: str, revision: str) -> str | None:
    snapshot = _snapshot(root, repo_name, revision)
    if (snapshot / "model.safetensors").is_file() or (snapshot / "pytorch_model.bin").is_file():
        return str(snapshot)
    return None


def _generator_path(root: Path) -> str | None:
    candidate = root / "models" / "qwen2.5-0.5b-instruct-7ae55760"
    return str(candidate) if (candidate / "model.safetensors").is_file() else None


def _model_manifest(root: Path, config: C2RAGConfig, engine: C2RAGV3) -> dict:
    from .aggregate_results import dependency_manifest, sha256_file
    from .generator import model_file_hash
    dense_snapshot = _snapshot(root, config.dense_model_name, config.dense_model_revision)
    reranker_snapshot = _snapshot(root, config.reranker_model_name, config.reranker_model_revision)
    return {
        "dense": {
            "name": config.dense_model_name,
            "revision": config.dense_model_revision,
            "snapshot_path": config.dense_model_path,
            "weight_sha256": sha256_file(dense_snapshot / "model.safetensors") or sha256_file(dense_snapshot / "pytorch_model.bin"),
            "dimensions": engine.dense.dimensions,
            "device": engine.dense.device,
            "fallback": engine.dense.is_fallback,
            "failure_reason": engine.dense.failure_reason,
        },
        "reranker": {
            "name": config.reranker_model_name,
            "revision": config.reranker_model_revision,
            "snapshot_path": config.reranker_model_path,
            "weight_sha256": sha256_file(reranker_snapshot / "model.safetensors") or sha256_file(reranker_snapshot / "pytorch_model.bin"),
            "device": engine.reranker.device,
            "fallback": engine.reranker.is_fallback,
            "failure_reason": engine.reranker.failure_reason,
        },
        "generator": {**engine.generator.manifest(), "weight_sha256": model_file_hash(config.generator_model_path)},
        "dependencies": dependency_manifest(),
    }


def run(output: Path, limit: int | None = None, rounds: int = 4, offset: int = 0, dataset_root: Path | None = None, generator_backend: str = "qwen", copyright_budget: float = 2.0, fixture_profile: str = "default", attack_family: str | None = None, offline_fallback: bool = False) -> dict:
    from .graph import run_rag_graph
    return run_rag_graph(output, limit, rounds, offset, dataset_root,
                         generator_backend, copyright_budget, fixture_profile,
                         attack_family, offline_fallback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("experiments/c2rag_v3/results/development_pilot_v5"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--dataset-root", type=Path, default=None)
    parser.add_argument("--generator-backend", choices=("qwen", "fallback"), default="qwen")
    parser.add_argument("--copyright-budget", type=float, default=2.0)
    parser.add_argument("--fixture-profile", choices=("default", "paired"), default="default")
    parser.add_argument("--attack-family", default=None)
    parser.add_argument("--offline-fallback", action="store_true", help="Explicitly use fallback retrieval and generation for wiring checks; not a model result")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.limit, args.rounds, args.offset, args.dataset_root, args.generator_backend, args.copyright_budget, args.fixture_profile, args.attack_family, args.offline_fallback), ensure_ascii=False, indent=2, sort_keys=True))
