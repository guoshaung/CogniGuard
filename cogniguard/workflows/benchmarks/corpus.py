from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from ..experiments import ROOT, sha256, write_new

INJ_REV = "f19c9f2c79a41046eb13c03c51a24c567a8ffa07"
HF_REV = "a10aab8eff1c73165a442d4464dce192bd28b9c5"
JBB_REV = "886acc352a31533ffbcf4ef22c744658688086fc"
HF_PARQUET_SHA = "55bbc5e2be771ee16ed67aed4edb5ecef5f44ac69cea317a67e5405c5c6057a4"
SOURCES = {
    "injecagent": {
        "url": "https://github.com/uiuc-kang-lab/InjecAgent",
        "revision": INJ_REV,
        "license": "MIT",
        "role": "native_indirect_tool_injection",
    },
    "hf_wild": {
        "url": "https://huggingface.co/datasets/TrustAIRLab/in-the-wild-jailbreak-prompts",
        "revision": HF_REV,
        "license": "MIT",
        "config": "jailbreak_2023_12_25",
        "role": "jailbreak_wrappers",
    },
    "jbb_benign": {
        "url": "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors",
        "revision": JBB_REV,
        "license": "MIT",
        "split": "benign",
        "role": "benign_behavior_reference_not_attack_prompts",
    },
}


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized_sha(text):
    return text_sha(re.sub(r"\s+", " ", text).strip().casefold())


def partition(group):
    # Community/pair groups stay together; this is NOT a semantic dedup audit.
    return "heldout" if int(text_sha(group)[:8], 16) % 5 == 0 else "development"


def validate_download_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    allowed = (
        host in {"huggingface.co", "raw.githubusercontent.com"}
        or host.endswith(".huggingface.co")
        or host.endswith(".hf.co")
        or host.endswith(".amazonaws.com")
    )
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or not allowed
    ):
        raise ValueError("Dataset redirect is outside the public HTTPS allowlist")


class PublicDataRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        validate_download_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def cached_download(
    url, path, *, allow_download=False, expected_sha=None, no_proxy=False, limit=32 * 1024 * 1024
):
    path = Path(path)
    if path.exists():
        if expected_sha and sha256(path) != expected_sha:
            raise ValueError("Cached public dataset hash mismatch; not overwriting it")
        return path
    if not allow_download:
        raise FileNotFoundError("Public data missing; explicitly enable --allow-download")
    validate_download_url(url)
    handlers = [PublicDataRedirect()]
    if no_proxy:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers={"User-Agent": "CogniGuard-public-benchmark/1.0"})
    with opener.open(request, timeout=40) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Public dataset exceeds size cap")
    if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("Downloaded public dataset hash mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return path


def wild_records(rows):
    seen, result = set(), []
    for index, row in enumerate(rows):
        text = row.get("prompt")
        if row.get("jailbreak") is not True or not isinstance(text, str) or not text.strip():
            continue
        key = normalized_sha(text)
        if key in seen:
            continue
        seen.add(key)
        community = row.get("community_id")
        if isinstance(community, (int, float)) and math.isfinite(float(community)):
            group = "hf_wild:community:" + str(int(community))
        else:
            group = "hf_wild:exact:" + key
        result.append(
            {
                "case_id": "hf_wild:" + str(index),
                "source": "hf_wild",
                "source_index": index,
                "variant": "jailbreak_2023_12_25",
                "text": text,
                "text_sha256": text_sha(text),
                "normalized_sha256": key,
                "group_id": group,
                "partition": partition(group),
                "category": str(row.get("community_name") or row.get("community") or "unspecified"),
                "source_role": "jailbreak_wrapper",
                "native_score": None,
            }
        )
    return result


def injec_records(rows, kind, setting):
    result = []
    for index, row in enumerate(rows):
        if not all(k in row for k in ("Tool Response", "Attacker Instruction", "User Tool")):
            raise ValueError("InjecAgent official schema mismatch")
        text = row["Tool Response"]
        if not isinstance(text, str):
            raise ValueError("InjecAgent tool response must be text")
        group = f"injecagent:{kind}:{index}"
        result.append(
            {
                "case_id": f"injecagent:{kind}:{setting}:{index}",
                "source": "injecagent_" + kind,
                "source_index": index,
                "variant": setting,
                "text": text,
                "text_sha256": text_sha(text),
                "normalized_sha256": normalized_sha(text),
                "group_id": group,
                "partition": partition(group),
                "category": str(row.get("Attack Type", "unspecified")),
                "source_role": "tool_response",
                "original_user_tool": row["User Tool"],
                "native_score": None,
            }
        )
    return result


def benign_records(rows):
    result = []
    for index, row in enumerate(rows):
        text = row.get("Goal")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("JBB benign schema mismatch")
        group = "jbb_benign:" + str(row.get("Index", index))
        result.append(
            {
                "case_id": group,
                "source": "jbb_benign",
                "source_index": index,
                "variant": "benign",
                "text": text,
                "text_sha256": text_sha(text),
                "normalized_sha256": normalized_sha(text),
                "group_id": group,
                "partition": partition(group),
                "category": row.get("Category", "unspecified"),
                "source_role": "benign_behavior_reference",
                "native_score": None,
            }
        )
    return result


def prepare_corpus(output, *, allow_download=False, no_proxy=False):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Corpus output already exists")
    cache = ROOT / ".cache/cogniguard-benchmarks"
    artifacts, rows, provenance = {}, [], {}
    hf_file = cached_download(
        SOURCES["hf_wild"]["url"]
        + f"/resolve/{HF_REV}/jailbreak_2023_12_25/train-00000-of-00001.parquet?download=true",
        cache / "hf_wild" / HF_REV / "jailbreak_2023_12_25.parquet",
        allow_download=allow_download,
        no_proxy=no_proxy,
        expected_sha=HF_PARQUET_SHA,
    )
    import pyarrow.parquet as pq

    schema = pq.read_schema(hf_file)
    if not {"prompt", "jailbreak"} <= set(schema.names):
        raise ValueError("HF jailbreak schema mismatch")
    columns = [
        k
        for k in ("prompt", "jailbreak", "community_id", "community_name", "community")
        if k in schema.names
    ]
    source_rows = pq.read_table(hf_file, columns=columns).to_pylist()
    hf_rows = wild_records(source_rows)
    rows.extend(hf_rows)
    provenance["hf_wild"] = {
        "raw_rows": len(source_rows),
        "normalized_unique_rows": len(hf_rows),
        "duplicate_rows_removed": len(source_rows) - len(hf_rows),
        "schema_columns": columns,
    }
    artifacts["hf_wild/parquet"] = {"path": str(hf_file), "sha256": sha256(hf_file)}
    readme = cached_download(
        SOURCES["hf_wild"]["url"] + f"/resolve/{HF_REV}/README.md",
        cache / "hf_wild" / HF_REV / "README.md",
        allow_download=allow_download,
        no_proxy=no_proxy,
        limit=128000,
    )
    artifacts["hf_wild/dataset_card"] = {"path": str(readme), "sha256": sha256(readme)}
    existing = ROOT / "experiments/external_data/injecagent" / INJ_REV
    for kind in ("dh", "ds"):
        for setting in ("base", "enhanced"):
            filename = f"test_cases_{kind}_{setting}.json"
            file = existing / "data" / filename
            if not file.exists():
                file = cached_download(
                    f"https://raw.githubusercontent.com/uiuc-kang-lab/InjecAgent/{INJ_REV}/data/{filename}",
                    cache / "injecagent" / INJ_REV / filename,
                    allow_download=allow_download,
                    no_proxy=no_proxy,
                )
            source_rows = json.loads(file.read_text(encoding="utf-8"))
            rows.extend(injec_records(source_rows, kind, setting))
            artifacts["injecagent/" + filename] = {"path": str(file), "sha256": sha256(file)}
            provenance[f"injecagent_{kind}_{setting}"] = {"rows": len(source_rows)}
    license_file = existing / "LICENCE"
    if not license_file.exists():
        license_file = cached_download(
            f"https://raw.githubusercontent.com/uiuc-kang-lab/InjecAgent/{INJ_REV}/LICENCE",
            cache / "injecagent" / INJ_REV / "LICENCE",
            allow_download=allow_download,
            no_proxy=no_proxy,
            limit=128000,
        )
    artifacts["injecagent/license"] = {"path": str(license_file), "sha256": sha256(license_file)}
    jbb = cached_download(
        SOURCES["jbb_benign"]["url"]
        + f"/resolve/{JBB_REV}/data/benign-behaviors.csv?download=true",
        cache / "jbb_benign" / JBB_REV / "benign.csv",
        allow_download=allow_download,
        no_proxy=no_proxy,
        limit=1000000,
    )
    source_rows = list(csv.DictReader(io.StringIO(jbb.read_text(encoding="utf-8-sig"))))
    rows.extend(benign_records(source_rows))
    provenance["jbb_benign"] = {"rows": len(source_rows)}
    artifacts["jbb_benign/csv"] = {"path": str(jbb), "sha256": sha256(jbb)}
    license_file = cached_download(
        SOURCES["jbb_benign"]["url"] + f"/resolve/{JBB_REV}/LICENSE",
        cache / "jbb_benign" / JBB_REV / "LICENSE",
        allow_download=allow_download,
        no_proxy=no_proxy,
        limit=128000,
    )
    artifacts["jbb_benign/license"] = {"path": str(license_file), "sha256": sha256(license_file)}
    output.mkdir(parents=True, exist_ok=False)
    with (output / "cases.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    lock = {
        "schema_version": 1,
        "sources": SOURCES,
        "artifacts": artifacts,
        "cases_sha256": sha256(output / "cases.jsonl"),
        "row_count": len(rows),
        "provenance": provenance,
        "grouping": "InjecAgent base/enhanced paired by kind/index; HF community groups or exact normalized text hash",
        "limitations": [
            "No semantic near-duplicate audit",
            "Two InjecAgent variants are not independent cases",
            "JBB behaviors are not jailbreak wrappers",
            "HF snapshot is historical, not a claim of latest strongest attacks",
        ],
        "dataset_scripts_executed": False,
        "model_weights_downloaded": False,
    }
    write_new(output / "corpus-lock.json", lock)
    return lock


def load_corpus(path):
    path = Path(path)
    lock = json.loads((path / "corpus-lock.json").read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1 or sha256(path / "cases.jsonl") != lock["cases_sha256"]:
        raise ValueError("Frozen corpus integrity mismatch")
    # str.splitlines() also splits U+2028/U+0085 inside valid JSON strings.
    # JSONL records are delimited by actual file newlines, not Unicode text separators.
    with (path / "cases.jsonl").open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if len(rows) != lock["row_count"] or len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("Frozen corpus row/identifier mismatch")
    for row in rows:
        if text_sha(row["text"]) != row["text_sha256"]:
            raise ValueError("Payload integrity mismatch")
    return lock, rows
