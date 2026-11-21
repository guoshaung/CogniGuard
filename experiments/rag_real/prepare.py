from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HOTPOT_REV = "1908d6afbbead072334abe2965f91bd2709910ab"
HOTPOT_FILE = "distractor/validation-00000-of-00001.parquet"
HOTPOT_URL = f"https://huggingface.co/datasets/hotpotqa/hotpot_qa/resolve/{HOTPOT_REV}/{HOTPOT_FILE}"
SCIFACT_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
SCIFACT_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def dump(path: Path, data) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)


def download(url: str, limit: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "CogniGuard-public-retrieval-research/1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        if not response.url.startswith("https://"):
            raise ValueError("HTTPS required")
        blob = response.read(limit + 1)
    if len(blob) > limit:
        raise ValueError("download exceeds size cap")
    return blob


def write_bytes(path: Path, blob: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(blob)


def prepare(cache: Path, scifact_archive: Path | None = None) -> dict:
    if cache.exists():
        return load_lock(cache)
    # Read only fixed public data, never an HF loading script or remote Python code.
    import pyarrow.parquet as pq
    metadata = json.loads(download(f"https://huggingface.co/api/datasets/hotpotqa/hotpot_qa/tree/{HOTPOT_REV}/distractor?recursive=false", 2_000_000))
    entry = next(item for item in metadata if item["path"] == HOTPOT_FILE)
    expected = entry["lfs"]["oid"]
    hotpot = download(HOTPOT_URL, 100_000_000)
    if sha(hotpot) != expected:
        raise ValueError("HotpotQA published LFS SHA256 mismatch")
    rows = pq.read_table(io.BytesIO(hotpot)).to_pylist()
    if len(rows) != 7405:
        raise ValueError("unexpected HotpotQA validation count")
    # Public qrels and answers are retained in the local cache, never injected into retrieval.
    normalised = []
    for row in rows:
        context = row["context"]
        facts = row["supporting_facts"]
        converted = {
            "id": row["id"], "question": row["question"], "answer": row["answer"],
            "type": row["type"], "level": row["level"],
            "context": list(zip(context["title"], context["sentences"])),
            "supporting_facts": list(zip(facts["title"], facts["sent_id"])),
        }
        normalised.append(converted)
    scifact = scifact_archive.read_bytes() if scifact_archive else download(SCIFACT_URL, 25_000_000)
    if hashlib.md5(scifact).hexdigest() != SCIFACT_MD5:
        raise ValueError("SciFact official BEIR MD5 mismatch")
    archive = zipfile.ZipFile(io.BytesIO(scifact))
    names = {"corpus.jsonl": "scifact/corpus.jsonl", "queries.jsonl": "scifact/queries.jsonl", "test.tsv": "scifact/qrels/test.tsv"}
    files = {name: archive.read(source) for name, source in names.items()}
    if sum(bool(line.strip()) for line in files["corpus.jsonl"].split(b"\n")) != 5183:
        raise ValueError("unexpected SciFact corpus size")
    qrels = list(csv.DictReader(io.StringIO(files["test.tsv"].decode()), delimiter="\t"))
    if len({row["query-id"] for row in qrels if int(row["score"]) > 0}) != 300:
        raise ValueError("unexpected SciFact test query count")
    cache.mkdir(parents=True, exist_ok=False)
    write_bytes(cache / "hotpot-validation.parquet", hotpot)
    normalised_blob = json.dumps(normalised, ensure_ascii=False).encode()
    write_bytes(cache / "hotpot-validation.json", normalised_blob)
    write_bytes(cache / "scifact.zip", scifact)
    for name, blob in files.items():
        write_bytes(cache / name, blob)
    lock = {
        "checked_client_date": "2026-10-13", "download_tls_verification": True,
        "hotpotqa": {"url": HOTPOT_URL, "revision": HOTPOT_REV, "rows": 7405, "license": "CC-BY-SA-4.0", "published_parquet_sha256": expected, "normalised_sha256": sha(normalised_blob)},
        "scifact": {"url": SCIFACT_URL, "official_beir_archive_md5": SCIFACT_MD5, "archive_sha256": sha(scifact), "documents": 5183, "test_queries": 300, "transport": "verified-TLS macOS download + SSH transfer" if scifact_archive else "verified-TLS direct download", "license_note": "Upstream claims/evidence CC-BY-4.0; S2ORC abstracts ODC-By-1.0; BEIR HF card additionally states CC-BY-SA-4.0", "upstream_license_url": "https://github.com/allenai/scifact/blob/master/LICENSE.md"},
        "files_sha256": {"hotpot-validation.parquet": sha(hotpot), "hotpot-validation.json": sha(normalised_blob), "scifact.zip": sha(scifact), **{name: sha(blob) for name, blob in files.items()}},
    }
    dump(cache / "source-lock.json", lock)
    return lock


def load_lock(cache: Path) -> dict:
    lock = json.loads((cache / "source-lock.json").read_text(encoding="utf-8"))
    allowed = {"hotpot-validation.parquet", "hotpot-validation.json", "scifact.zip", "corpus.jsonl", "queries.jsonl", "test.tsv"}
    if set(lock["files_sha256"]) != allowed:
        raise ValueError("unexpected source files")
    for name, digest in lock["files_sha256"].items():
        if sha((cache / name).read_bytes()) != digest:
            raise ValueError("source bytes changed")
    return lock


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/rag-real-v1")
    parser.add_argument("--scifact-archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.cache, args.scifact_archive), indent=2))
