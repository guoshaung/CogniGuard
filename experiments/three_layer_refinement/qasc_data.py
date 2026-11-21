"""Pinned author-maintained QASC Parquet; never execute a dataset script.

The old data.allenai.org host may be unavailable. This adapter locks the
author's HF snapshot and its published LFS digests. Test is unlabeled; use
train for calibration and validation for a frozen internal held-out partition.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REV = "a34ba204eb9a33b919c10cc08f4f1c8dae5ec070"
BASE = "https://huggingface.co/datasets/allenai/qasc"


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def download(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "CogniGuard-public-dataset-research/1"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            if not response.url.startswith("https://"):
                raise ValueError("HTTPS required")
            blob = response.read(limit + 1)
    except urllib.error.URLError:
        # Windows' platform TLS stack can handle a CDN handshake which the
        # bundled Python OpenSSL rejects. Verification remains on; the exact
        # published LFS SHA256 is still checked before any source is accepted.
        curl = shutil.which("curl.exe")
        if curl is None:
            raise
        (ROOT / ".tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="qasc-tls-", dir=ROOT / ".tmp") as directory:
            destination = Path(directory) / "download.bin"
            result = subprocess.run([curl, "--fail", "--silent", "--show-error", "--location",
                                     "--max-time", "45", "--max-filesize", str(limit),
                                     "--proto", "=https", "--proto-redir", "=https",
                                     "--output", str(destination), url], capture_output=True, timeout=55)
            if result.returncode:
                raise RuntimeError("verified TLS download failed; no insecure fallback used") from None
            blob = destination.read_bytes()
    if len(blob) > limit:
        raise ValueError("download size cap exceeded")
    return blob


def prepare(cache):
    if cache.exists():
        return load(cache)[0]
    from cogniguard.workflows.model_site import enable_existing_model_environment
    enable_existing_model_environment()
    import pyarrow.parquet as pq
    metadata = json.loads(download(f"https://huggingface.co/api/datasets/allenai/qasc/tree/{REV}/data?recursive=false", 2_000_000))
    files, rows = {}, {}
    for split, expected_n in (("train", 8134), ("validation", 926)):
        name = f"{split}-00000-of-00001.parquet"
        path = "data/" + name
        entry = next(item for item in metadata if item["path"] == path)
        published = entry["lfs"]["oid"]
        blob = download(f"{BASE}/resolve/{REV}/{path}", 20_000_000)
        if sha(blob) != published:
            raise ValueError("QASC published LFS digest mismatch")
        records = pq.read_table(io.BytesIO(blob)).to_pylist()
        if len(records) != expected_n:
            raise ValueError("QASC split count mismatch")
        for row in records:
            choices = row["choices"]
            if isinstance(choices, dict):
                choices = list(zip(choices["label"], choices["text"]))
            else:
                choices = [(c["label"], c["text"]) for c in choices]
            row["choices"] = choices
            if len(choices) != 8 or row["answerKey"] not in dict(choices) or not row["fact1"] or not row["fact2"]:
                raise ValueError("QASC row contract mismatch")
        files[name] = blob
        files[f"{split}.json"] = json.dumps(records, ensure_ascii=False).encode()
        rows[split] = len(records)
    cache.mkdir(parents=True, exist_ok=False)
    for name, blob in files.items():
        with (cache / name).open("xb") as stream:
            stream.write(blob)
    lock = {"dataset": "QASC", "revision": REV, "source": BASE, "rows": rows,
            "license_note": "Author repository releases data under CC BY; source license must be preserved.",
            "files_sha256": {name: sha(blob) for name, blob in files.items()},
            "official_full_corpus_evaluation": False}
    with (cache / "source-lock.json").open("x", encoding="utf-8") as stream:
        json.dump(lock, stream, indent=2)
    return lock


def load(cache):
    lock = json.loads((cache / "source-lock.json").read_text(encoding="utf-8"))
    expected = {"train.json", "validation.json", "train-00000-of-00001.parquet", "validation-00000-of-00001.parquet"}
    if lock["revision"] != REV or set(lock["files_sha256"]) != expected:
        raise ValueError("unexpected QASC source lock")
    for name, digest in lock["files_sha256"].items():
        if sha((cache / name).read_bytes()) != digest:
            raise ValueError("QASC source bytes changed")
    return lock, {split: json.loads((cache / f"{split}.json").read_text(encoding="utf-8"))
                  for split in ("train", "validation")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/qasc-real-v1")
    args = parser.parse_args()
    print(json.dumps(prepare(args.cache), indent=2))
