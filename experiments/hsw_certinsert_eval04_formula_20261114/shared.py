"""Frozen R inputs and reusable EVAL-03 components."""

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIMARY = ROOT.parents[1] / "CogniGuard"
OUT = ROOT / "var/results/hsw-st/certinsert_eval04_formula_20261114"
STAGE = ROOT / "var/results/hsw-st/certinsert_eval04_20261113/stage0"
OLD = ROOT / "var/results/hsw-st/english_replication_20261110_01/e1_guarded"
HISTORY = ROOT / "var/results/hsw-st/certinsert_eval03_lite_20261112/run01"
VOCAB = OLD / "protocol_v4/revision09/VOCABULARY.json"
FREQ = ROOT / "var/results/hsw-st/certinsert_eval_20261111_02/run01/DOMAIN_FREQUENCIES.json"
BRIDGE = ROOT / "var/results/hsw-st/insertion_feasibility_20261109_01/run05/v2/score_bridge.dll"
MODEL = PRIMARY / "assets/models/qwen2.5-3b-instruct-q4_k_m.gguf"
KATEX = PRIMARY / "visualization/node_modules/katex/dist/katex.js"
NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
SEED = "EVAL04-F-20261114"
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", CUDA_VISIBLE_DEVICES="-1")

for name in ("hsw_certinsert_eval_20261111_02", "hsw_certinsert_eval_20261111_01",
             "hsw_english_replication_20261110_01", "hsw_insertion_feasibility_20261109_01"):
    sys.path.insert(0, str(ROOT / "experiments" / name))
sys.path.insert(0, str(OUT / "deps"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, obj):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def rank(label, ident):
    return sha(f"{SEED}|{label}|{ident}".encode())


def sources():
    corpus = read(STAGE / "R_CORPUS.json")
    assert len(corpus) == 4461 and len({r["id"] for r in corpus}) == len(corpus)
    generated = sorted((r for r in corpus if r["kind"] == "generated"),
                       key=lambda r: rank("embed", r["id"]))
    calib = [r for r in corpus if r["split"] == "calib"]
    assert len(generated) == 300 and len(calib) == 893
    return generated, calib


def verify():
    frozen = read(HERE / "F_FREEZE.json")
    assert digest(HERE / "F_PREREG.md") == frozen["prereg_sha256"]
    for base, section in ((ROOT, "inputs_sha256"), (PRIMARY, "primary_sha256")):
        for path, expected in frozen[section].items():
            assert digest(base / path) == expected, path
    return frozen


def keys():
    lock = read(HERE / "F_FREEZE.json")["keys"]
    sentence = (OLD / "development_round01/restricted/key.bin").read_bytes()
    raw = (OUT / "keys.bin").read_bytes()
    formula = [raw[i:i+32] for i in range(0,len(raw),32)]
    assert len(raw) == 32032 and sha(sentence) == lock["sentence_sha256"]
    assert sha(formula[0]) == lock["formula_dev_sha256"]
    assert list(map(sha,formula[1:])) == lock["calibration_sha256"]
    return sentence, formula[0], formula[1:]
