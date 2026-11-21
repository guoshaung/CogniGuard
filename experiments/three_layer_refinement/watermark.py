"""Paired local-model experiment: KGW context 4 vs 1 with unchanged protection.

Separate new educational sources from the old twelve, freeze calibration
before test generation, and report repair/fallback and clean false positives.
This is an internal context ablation, not a public-corpus benchmark.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARMS = {"Selective-context4": 4, "Selective-context1": 1}


def steps(output, dtype="float16"):
    from protection.audit_trace.src import main as wm
    from experiments.attacks.watermark_attacks import run_all_attacks
    from experiments.rag_real.retrieval import dump, sha

    cfg = wm.load_config(ROOT / "experiments/text_watermark/config.local_qwen05b_selective12.yaml")
    cfg["model"]["dtype"] = dtype
    data = ROOT / "protection/audit_trace/data"
    samples = [x for x in wm.read_jsonl(data / "expanded_edu_dataset.jsonl")
               if x.get("length_tier") == "long"][12:24]
    clean = [x["text"] for x in wm.read_jsonl(data / "expanded_clean_baseline.jsonl") if x.get("text")]
    if len(samples) != 12 or len(clean) < 10:
        raise ValueError("expected twelve new long sources and at least ten clean controls")
    terms_extra = wm._load_terms(data / "protected_terms_math.txt")
    tok = wm._get_tokenizer_for_detect({}, cfg)
    paths = [Path(__file__), ROOT / "protection/audit_trace/src/watermark_rewriter.py",
             ROOT / "protection/audit_trace/src/watermark_logits_processor.py",
             ROOT / "protection/audit_trace/src/watermark_detector.py"]
    hashes = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "protocol-lock.json", {
        "protocol": "selective_context_paired_ablation_v1", "status": "FROZEN_BEFORE_GENERATION",
        "arms": ARMS, "dev_ids": [s["sample_id"] for s in samples[:4]],
        "test_ids": [s["sample_id"] for s in samples[4:]],
        "source_sha256": sha((data / "expanded_edu_dataset.jsonl").read_bytes()),
        "clean_sha256": sha((data / "expanded_clean_baseline.jsonl").read_bytes()),
        "source_code_sha256": hashes, "delta": cfg["watermark"]["delta"],
        "max_rewrite_tokens": cfg["model"]["rewrite_max_new_tokens"],
        "paired_model_dtype": dtype,
        "seed": 20261016, "real_api_calls": 0,
        "threshold_rule": "max(2.85, largest first-half clean z + epsilon), per arm before test",
        "selection_rule": "largest dev ADR; ties retain legacy context4",
        "limitations": ["Small handcrafted educational sources, not real student data.",
                        "Clean controls are authored, not matched model-generated controls.",
                        "summary_like retains first two sentences, not an abstractive model summary.",
                        "Fidelity includes deterministic placeholder repair."],
    })
    def detect(text, window, threshold):
        w = cfg["watermark"]
        return wm.detect_full_text(text, tok, tok.vocab_size, w["gamma"], w["key"], window, threshold)

    mid = len(clean) // 2
    thresholds = {arm: max(2.85, max(detect(t, window, 2.85)["z_score"] for t in clean[:mid]) + 1e-9)
                  for arm, window in ARMS.items()}
    dump(output / "clean-calibration-lock.json", {"thresholds": thresholds, "calibration_count": mid})
    yield "prepare", 24
    records = []
    selected_on_dev = None
    for index, sample in enumerate(samples):
        if index == 4:
            scores = {arm: statistics.mean(a["detected"] for r in records if r["arm"] == arm
                                           for a in r["attacks"]) for arm in ARMS}
            selected_on_dev = max(ARMS, key=lambda arm: (scores[arm], arm == "Selective-context4"))
            dump(output / "dev-selection-lock.json", {"dev_adr": scores, "selected": selected_on_dev,
                                                      "before_test_generation": True})
        for arm, window in ARMS.items():
            config = copy.deepcopy(cfg)
            config["watermark"]["window_size"] = window
            wm.set_seed(20261016 + index)
            terms, formulas, numbers = wm.extract_protected_spans(sample, terms_extra)
            result = wm.rewrite_sample(sample["draft_answer"], terms, formulas, numbers,
                                       config, "full", question=sample.get("question", ""))
            text = result["watermarked_answer"]
            detected = detect(text, window, thresholds[arm])
            attacks = run_all_attacks(text, clean[(index + mid) % len(clean)], 20261016 + index)
            def kept(items):
                expected = [x for x in set(items) if x and x in sample["draft_answer"]]
                return sum(x in text for x in expected) / max(1, len(expected)) if expected else 1.0
            row = {"sample_id": sample["sample_id"], "split": "dev" if index < 4 else "test", "arm": arm,
                   "detection": detected, "term_keep": kept(terms), "formula_keep": kept(formulas),
                   "number_keep": kept(numbers), "repair_count": result["repaired_placeholder_count"],
                   "draft_fallback": result["used_draft_fallback"], "attempts": result["rewrite_attempts_used"],
                   "attacks": [{"attack": name, "detected": detect(attacked, window, thresholds[arm])["is_watermarked"],
                                "token_count": len(tok.encode(attacked, add_special_tokens=False))}
                               for name, attacked in attacks.items()]}
            records.append(row)
            dump(output / f"{index:02d}-context{window}.json", {"metrics": row, "synthetic_released_text": text})
            print(json.dumps({"source_index": index, "split": row["split"], "arm": arm,
                              "detected": detected["is_watermarked"], "repair_count": row["repair_count"]}), flush=True)
            yield "item"
    summaries = []
    for arm, window in ARMS.items():
        rows = [r for r in records if r["arm"] == arm and r["split"] == "test"]
        attacks = [a for r in rows for a in r["attacks"]]
        summaries.append({"arm": arm, "test_sources": len(rows), "threshold": thresholds[arm],
                          "wdr": statistics.mean(r["detection"]["is_watermarked"] for r in rows),
                          "adr": statistics.mean(a["detected"] for a in attacks),
                          "clean_fpr": statistics.mean(detect(t, window, thresholds[arm])["is_watermarked"] for t in clean[mid:]),
                          "clean_test_n": len(clean) - mid,
                          "by_attack": {name: statistics.mean(a["detected"] for a in attacks if a["attack"] == name)
                                        for name in sorted({a["attack"] for a in attacks})},
                          **{k: statistics.mean(r[k] for r in rows) for k in
                             ("term_keep", "formula_keep", "number_keep", "repair_count", "draft_fallback")}})
    if hashes != {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}:
        raise ValueError("watermark implementation changed during experiment")
    final = {"status": "COMPLETED_PAIRED_LOCAL_MODEL_ABLATION", "selected_on_dev": selected_on_dev,
             "methods": summaries, "real_api_calls": 0}
    dump(output / "summary.json", final)
    return final


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--dtype", choices=("float16", "float32"), default="float16")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    if not a.worker:
        env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONHASHSEED="20261016",
                   LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", TOKENIZERS_PARALLELISM="false",
                   OMP_NUM_THREADS="2")
        raise SystemExit(subprocess.run([sys.executable, "-X", "utf8", "-m", __spec__.name,
                                        *sys.argv[1:], "--worker"], cwd=ROOT, env=env).returncode)
    from experiments.rag_real.graph import CONTROL_GRAPH, invoke_batch
    result = invoke_batch(CONTROL_GRAPH, steps(a.output, a.dtype), recursion_limit=100)
    print(json.dumps({"status": result["status"], "output": str(a.output)}))


if __name__ == "__main__":
    main()
