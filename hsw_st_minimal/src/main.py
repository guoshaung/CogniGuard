"""HSW-ST 最低实现版：数据生成、语义保护、KGW 改写、检测、攻击与指标导出。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 保证可从项目根目录执行: python src/main.py
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from attacks import run_all_attacks
from data_builder import ensure_data_files
from evaluator import aggregate_and_write_csv, final_summary_stats
from semantic_protector import extract_protected_spans
from source_tracer import build_source_trace_log, build_unified_trace_log, build_watermark_log
from utils import (
    load_yaml_with_env_substitution,
    new_answer_id,
    new_watermark_id,
    project_root,
    read_jsonl,
    resolve_model_device_dtype,
    resolve_path,
    set_seed,
    write_jsonl,
)
from watermark_detector import detect_by_windows, detect_full_text
from watermark_rewriter import rewrite_sample


def load_config(config_path: Path) -> dict:
    return load_yaml_with_env_substitution(config_path)


def _load_terms(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _get_tokenizer_for_detect(rw: dict, cfg: dict):
    tok = rw.get("tokenizer")
    if tok is not None:
        return tok
    from transformers import AutoTokenizer

    name = (cfg.get("model") or {}).get("local_model_name", "Qwen/Qwen2.5-3B-Instruct")
    return AutoTokenizer.from_pretrained(name, trust_remote_code=True)


def run_pipeline(cfg: dict, mode: str) -> None:
    root = project_root()
    mm_before = str((cfg.get("model") or {}).get("device", "auto")).strip().lower()
    resolve_model_device_dtype(cfg)
    mm = cfg.get("model") or {}
    print(f"[HSW-ST] model.device={mm.get('device')} dtype={mm.get('dtype')}")
    try:
        import torch

        if mm.get("device") == "cuda":
            print(f"[HSW-ST] GPU: {torch.cuda.get_device_name(0)}")
        elif mm_before in ("auto", "") and not torch.cuda.is_available():
            print(
                "[HSW-ST] 提示：当前为 CPU。若本机有 NVIDIA 显卡，请安装 CUDA 版 PyTorch，"
                "config 里保持 device: auto 或改为 cuda。"
            )
    except ImportError:
        pass

    set_seed(int((cfg.get("experiment") or {}).get("random_seed", 42)))

    exp = cfg.get("experiment") or {}
    ablation = str(exp.get("ablation", "full"))
    run_attacks = bool(exp.get("run_attacks", True))
    use_emb = bool(exp.get("use_sentence_embedding", False))

    data_cfg = cfg.get("data") or {}
    wm_cfg = cfg.get("watermark") or {}
    paths_cfg = cfg.get("paths") or {}
    base_out = resolve_path(paths_cfg.get("output_dir", "outputs"), root)
    base_out.mkdir(parents=True, exist_ok=True)
    nest = bool(paths_cfg.get("output_run_subdir", True))
    if nest:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        out_dir = base_out / f"run_{stamp}"
        try:
            out_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            out_dir = base_out / f"run_{stamp}_{uuid.uuid4().hex[:8]}"
            out_dir.mkdir(parents=True, exist_ok=False)
        print(f"[HSW-ST] output_base={base_out}")
        print(f"[HSW-ST] output_run={out_dir}")
    else:
        out_dir = base_out
        print(f"[HSW-ST] output_dir={out_dir}")

    ensure_data_files(cfg)

    ds_path = resolve_path(data_cfg.get("dataset_path") or "data/sample_edu_dataset.jsonl", root)
    clean_path = resolve_path(data_cfg.get("clean_baseline_path") or "data/clean_baseline.jsonl", root)
    terms_path = resolve_path(data_cfg.get("terms_path", "data/protected_terms_math.txt"), root)
    extra_terms = _load_terms(terms_path)

    samples = read_jsonl(ds_path)
    limit = 8 if mode == "demo" else len(samples)
    samples = samples[:limit]

    clean_baselines = [r["text"] for r in read_jsonl(clean_path) if r.get("text")]

    wm_answers: list[dict] = []
    wm_logs: list[dict] = []
    st_logs: list[dict] = []
    unified_logs: list[dict] = []
    attack_rows: list[dict] = []
    summary_rows: list[dict] = []

    watermarked_flags: list[bool] = []
    z_list: list[float] = []
    ph_pass: list[bool] = []
    trace_ok: list[bool] = []
    tkr_l: list[float] = []
    fkr_l: list[float] = []
    nkr_l: list[float] = []
    attack_detected: list[bool] = []

    emb_model = None
    if use_emb:
        try:
            from sentence_transformers import SentenceTransformer

            emb_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception:
            emb_model = None

    for idx, sample in enumerate(samples):
        sid = sample["sample_id"]
        answer_id = new_answer_id(sid)
        wmid = new_watermark_id()

        terms, formulas, numbers = extract_protected_spans(sample, extra_terms)
        rw = rewrite_sample(
            sample.get("draft_answer") or "",
            terms,
            formulas,
            numbers,
            cfg,
            ablation,
            question=str(sample.get("question") or ""),
        )
        y_wm = rw["watermarked_answer"]
        tok = _get_tokenizer_for_detect(rw, cfg)

        d_full = detect_full_text(
            y_wm,
            tok,
            tok.vocab_size,
            float(wm_cfg.get("gamma", 0.25)),
            str(wm_cfg.get("key", "demo_secret_key")),
            int(wm_cfg.get("window_size", 4)),
            float(wm_cfg.get("z_threshold", 4.0)),
        )
        d_loc = detect_by_windows(
            y_wm,
            tok,
            tok.vocab_size,
            float(wm_cfg.get("gamma", 0.25)),
            str(wm_cfg.get("key", "demo_secret_key")),
            int(wm_cfg.get("window_size", 4)),
            int(wm_cfg.get("local_window_tokens", 80)),
            int(wm_cfg.get("local_window_stride", 20)),
        )

        model_name = (cfg.get("model") or {}).get("openai_model") if (cfg.get("model") or {}).get(
            "provider"
        ) == "openai" else (cfg.get("model") or {}).get("local_model_name", "")

        log_delta = float(wm_cfg.get("delta", 2.0)) if rw.get("use_kgw") else 0.0
        wm_log = build_watermark_log(
            answer_id,
            sid,
            wmid,
            {**wm_cfg, "delta": log_delta},
            float(d_full["z_score"]),
            str(model_name),
        )
        st_log = build_source_trace_log(answer_id, sid, sample.get("source_trace") or [], watermark_id=wmid)
        unified_log = build_unified_trace_log(wm_log, st_log, y_wm)

        wm_answers.append(
            {
                "answer_id": answer_id,
                "sample_id": sid,
                "watermark_id": wmid,
                "question": sample.get("question"),
                "draft_answer": sample.get("draft_answer"),
                "watermarked_answer": y_wm,
                "z_score": d_full["z_score"],
                "max_z_window": d_loc["max_z"],
                "ablation": ablation,
                "failed_placeholder_check": rw.get("failed_placeholder_check", False),
                "fidelity_violations": rw.get("fidelity_violations", []),
                "used_draft_fallback": rw.get("used_draft_fallback", False),
                "rewrite_attempts_used": rw.get("rewrite_attempts_used", 0),
            }
        )
        wm_logs.append(wm_log)
        st_logs.append(st_log)
        unified_logs.append(unified_log)

        # 保持率
        def rate_kept(xs: list[str]) -> float:
            if not xs:
                return 1.0
            return sum(1 for x in xs if x and x in y_wm) / len(xs)

        tkr = rate_kept(terms)
        fkr = rate_kept(formulas)
        nkr = rate_kept(numbers)
        tkr_l.append(tkr)
        fkr_l.append(fkr)
        nkr_l.append(nkr)

        ph_ok = not rw.get("failed_placeholder_check", False)
        ph_pass.append(1.0 if ph_ok else 0.0)
        tr_ok = bool(wm_log.get("answer_id") == st_log.get("answer_id"))
        trace_ok.append(1.0 if tr_ok else 0.0)

        watermarked_flags.append(bool(d_full["is_watermarked"]))
        z_list.append(float(d_full["z_score"]))

        ssr = ""
        if emb_model is not None:
            try:
                a = emb_model.encode(sample.get("draft_answer") or "", normalize_embeddings=True)
                b = emb_model.encode(y_wm, normalize_embeddings=True)
                import numpy as np

                ssr = float(np.dot(a, b))
            except Exception:
                ssr = ""

        row = {
            "sample_id": sid,
            "answer_id": answer_id,
            "ablation": ablation,
            "WDR_single": 1.0 if d_full["is_watermarked"] else 0.0,
            "TKR": tkr,
            "FKR": fkr,
            "NKR": nkr,
            "PlaceholderPass": 1.0 if ph_ok else 0.0,
            "AvgZ": float(d_full["z_score"]),
            "TraceBindRate": 1.0 if tr_ok else 0.0,
            "SSR": ssr,
        }
        summary_rows.append(row)

        if run_attacks:
            clean_snip = clean_baselines[idx % len(clean_baselines)] if clean_baselines else "干净对照文本。"
            atk_map = run_all_attacks(y_wm, clean_snip, seed=42 + idx)
            for aname, atext in atk_map.items():
                dd = detect_full_text(
                    atext,
                    tok,
                    tok.vocab_size,
                    float(wm_cfg.get("gamma", 0.25)),
                    str(wm_cfg.get("key", "demo_secret_key")),
                    int(wm_cfg.get("window_size", 4)),
                    float(wm_cfg.get("z_threshold", 4.0)),
                )
                attack_detected.append(bool(dd["is_watermarked"]))
                attack_rows.append(
                    {
                        "sample_id": sid,
                        "attack": aname,
                        "z_score": dd["z_score"],
                        "is_watermarked": dd["is_watermarked"],
                    }
                )

    # FPR：干净基线
    clean_flags: list[bool] = []
    tok_fpr = _get_tokenizer_for_detect({"tokenizer": None}, cfg)
    for ct in clean_baselines[: max(5, min(len(clean_baselines), 20))]:
        dd = detect_full_text(
            ct,
            tok_fpr,
            tok_fpr.vocab_size,
            float(wm_cfg.get("gamma", 0.25)),
            str(wm_cfg.get("key", "demo_secret_key")),
            int(wm_cfg.get("window_size", 4)),
            float(wm_cfg.get("z_threshold", 4.0)),
        )
        clean_flags.append(bool(dd["is_watermarked"]))

    agg = final_summary_stats(
        watermarked_flags,
        clean_flags,
        attack_detected,
        z_list,
        ph_pass,
        trace_ok,
        tkr_l,
        fkr_l,
        nkr_l,
    )

    write_jsonl(out_dir / "watermarked_answers.jsonl", wm_answers)
    write_jsonl(out_dir / "watermark_logs.jsonl", wm_logs)
    write_jsonl(out_dir / "source_trace_logs.jsonl", st_logs)
    write_jsonl(out_dir / "unified_trace_logs.jsonl", unified_logs)

    aggregate_and_write_csv(
        summary_rows,
        attack_rows,
        out_dir / "metrics_per_sample.csv",
        out_dir / "attack_results.csv",
    )
    agg_out = {**agg, "row_type": "aggregate"}
    with (out_dir / "metrics_summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg_out.keys()))
        w.writeheader()
        w.writerow(agg_out)

    print(json.dumps(agg, ensure_ascii=False, indent=2))
    print(f"完成。输出目录: {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, default="configs/config.yaml")
    ap.add_argument("--mode", type=str, default="experiment", choices=["demo", "experiment"])
    args = ap.parse_args()
    root = project_root()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = (root / cfg_path).resolve()
    cfg = load_config(cfg_path)
    run_pipeline(cfg, args.mode)


if __name__ == "__main__":
    main()
