"""Paths and reproducibility metadata for offline field audits."""
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

REPO = Path(__file__).resolve().parents[2]


def raw_dir():
    return Path(os.environ.get("COGNIGUARD_RAW_DIR", REPO.parent / "cogniguard_raw"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(dataset, report, hashes):
    parent = Path(os.environ.get("COGNIGUARD_DATA_DIR", REPO.parent / "cogniguard_data"))
    folder = (parent / "audits" / dataset).resolve()
    if any((p / ".git").exists() for p in (folder, *folder.parents)):
        raise ValueError("audit reports belong outside the checkout")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = {"raw_file_sha256": hashes, "phase": "field_audit", "dataset": dataset}
    for name, obj in (("AUDIT", report), ("MANIFEST", manifest)):
        with NamedTemporaryFile("w", encoding="utf8", dir=folder, delete=False) as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write("\n")
        Path(f.name).replace(folder / (name + ".json"))
    print(folder / "AUDIT.json")
