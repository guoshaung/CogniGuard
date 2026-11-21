"""Report paired, stratified outcomes and export text-free shareable traces."""
import collections
import csv
import hashlib
import json
import random
import statistics

from data_cases import HERE, RUN, SEED, dump, read_json

ARMS = ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
        "drop_high", "drop_low", "drop_random"]
CONTRASTS = ["B0", "B2", "B3", "B5", "B6", "B7", "B8", "drop_high", "drop_low", "drop_random"]


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 6) if values else None


def quality(scores):
    return statistics.fmean(scores) if all(score is not None for score in scores) else None


def cluster_interval(rows):
    by_group = collections.defaultdict(list)
    for group, value in rows:
        by_group[group].append(value)
    groups = sorted(by_group)
    if len(groups) < 2:
        return [None, None]
    rng = random.Random(SEED)
    draws = []
    for _ in range(2000):
        samples = [value for group in rng.choices(groups, k=len(groups)) for value in by_group[group]]
        draws.append(statistics.fmean(samples))
    draws.sort()
    return [round(draws[49], 6), round(draws[1949], 6)]


def sha_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main():
    gold = read_json(RUN / "gold.local.json")
    cases = {c["case"]: c for c in read_json(RUN / "cases.local.json")}
    test = read_lines(RUN / "teaching_test.local.jsonl")
    dev = read_lines(RUN / "teaching_dev.local.jsonl")
    traces = dev + test
    judges = {j["case"]: j for split in ("dev", "test") for j in read_lines(RUN / f"judge_{split}.local.jsonl")}
    assert len({trace["case"] for trace in traces}) == len(traces) == len(cases)
    with (RUN / "teaching_traces.jsonl").open("w", encoding="utf-8") as stream:
        for trace in traces:
            stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
    summary = []
    ablations = []
    pairs = []
    share = []
    scenario = {}
    for source in ("PeerMathDial", "Bridge"):
        for split in ("dev", "test"):
            data = [t for t in traces if (t["source"], t["split"]) == (source, split)]
            if not data:
                continue
            label = source + "/" + split
            scenario[label] = {
                "cases": len(data),
                "requests": sum(bool(t["request"]) for t in data),
                "judge_needs_more_yes": sum(judges[t["case"]]["need"] == "yes" for t in data),
                "judge_current_sufficient": sum(judges[t["case"]]["need"] == "no" for t in data),
                "judge_need_unknown": sum(judges[t["case"]]["need"] == "unknown" for t in data),
                "judge_necessary_multiple_prior_turns": sum(len(judges[t["case"]]["necessary"]) >= 2 for t in data),
                "candidate_semantic_duplicate_cases": sum(t["rows"]["B1"]["near_duplicate_pairs"] > 0 for t in data),
                "direct_pii_flag_cases": sum(t["candidate_pii_flags"] > 0 for t in data),
                "attention_changes_wire_vs_uniform": sum(t["rows"]["B4"]["wire"] != t["rows"]["B6"]["wire"] for t in data),
                "attention_changes_wire_vs_noattention": sum(t["rows"]["B4"]["wire"] != t["rows"]["B5"]["wire"] for t in data),
                "projection_nonzero": sum(any(t["selector"]["B4"]["projected"]) for t in data),
                "b4_bottleneck_empty_before_refill": sum(not t["selector"]["B4"]["bottleneck_out"] for t in data),
                "b4_refill_changed_selection": sum(set(t["selector"]["B4"]["bottleneck_out"]) != set(t["selector"]["B4"]["selected_before_wire"]) for t in data),
                "actual_teacher_calls": sum(t["actual_calls"] for t in data),
                "actual_blind_judge_calls": len(data),
            }
            for arm in ARMS:
                rows = []
                for t in data:
                    row = t["rows"][arm]
                    j = judges[t["case"]]
                    scores = j["scores"].get(arm, [None] * 3)
                    ref = gold[t["case"]]
                    response = row["teacher"]["output"]
                    picked = set(row["indices"])
                    rel = set(j["relevant"])
                    necessary = set(j["necessary"])
                    judge_ok = j["judge"]["status"] == "OK"
                    row_summary = {
                        "case": t["case"], "source": source, "split": split, "method": arm,
                        "n_fragments": len(picked), "history_tokens": row["history_tokens"],
                        "history_chars": row["history_chars"], "result_only_tokens": row.get("result_tokens", 0),
                        "cosine_redundancy": row["redundancy_cosine"], "near_duplicates": row["near_duplicate_pairs"],
                        "exact_duplicate_count": row["duplicate_texts"],
                        "direct_pii_count": row["regex_sensitive_fragments"],
                        "correct": scores[0], "targeted": scores[1], "hint": scores[2], "quality": quality(scores),
                        "teacher_status": row["teacher"]["status"], "judge_status": j["judge"]["status"],
                        "latency_s": row["teacher"]["latency_s"],
                        "prompt_tokens": row["teacher"]["usage"].get("prompt_tokens"),
                        "completion_tokens": row["teacher"]["usage"].get("completion_tokens"),
                        "expert_error_exact": (int(response["error_code"] == ref["error"])
                                               if source == "Bridge" and response and ref["error"] in
                                               {"diagnose","guess","right-idea","imprecise","misinterpret","careless"} else None),
                        "expert_move_exact": (int(response["move_code"] == ref["move"])
                                              if source == "Bridge" and response and ref["move"] in
                                              {"ask_question","explain_concept","provide_strategy","provide_hint",
                                               "provide_similar_problem","simplify_question","affirm_correct_answer",
                                               "encourage_student","provide_correction","provide_example"} else None),
                        "judge_relevant_precision": len(picked & rel) / len(picked) if picked and judge_ok and rel else None,
                        "judge_necessary_recall": len(picked & necessary) / len(necessary) if necessary and judge_ok else None,
                        "judge_unnecessary_fragments": len(picked - necessary) if judge_ok and j["need"] != "unknown" else None,
                        "result_copied_history_fragments": row.get("raw_history_exactly_in_result", 0),
                    }
                    rows.append(row_summary)
                    share.append(row_summary | {
                        "candidate_count": t["candidate_count"], "positions": [
                            cases[t["case"]]["candidates"][i]["position"] for i in row["indices"]],
                        "wire_sha256": sha_text(row["wire"]), "request_sha256": sha_text(t["request"]),
                        "response_sha256": sha_text(row["teacher"].get("response_text", "")),
                        "request_present": bool(t["request"]), "cache_reuse": row["cache_reuse"],
                        "case_task": cases[t["case"]]["task_family"], "deleted_index": row["deletion"],
                        "evaluation_status": "BLINDED_MODEL_RUBRIC",
                    })
                metrics = {key: mean([r[key] for r in rows]) for key in (
                    "n_fragments","history_tokens","history_chars","result_only_tokens","cosine_redundancy",
                    "near_duplicates","exact_duplicate_count","direct_pii_count","correct","targeted","hint","quality",
                    "latency_s","prompt_tokens","completion_tokens","expert_error_exact","expert_move_exact",
                    "judge_relevant_precision","judge_necessary_recall","judge_unnecessary_fragments",
                    "result_copied_history_fragments")}
                summary.append({"source": source, "split": split, "method": arm, "n": len(rows),
                                "scored": sum(r["quality"] is not None for r in rows),
                                "unknown": sum(r["quality"] is None for r in rows),
                                "teacher_failure": sum(r["teacher_status"] != "OK" for r in rows),
                                "judge_failure": sum(r["judge_status"] != "OK" for r in rows),
                                "expert_error_n": sum(r["expert_error_exact"] is not None for r in rows),
                                "expert_move_n": sum(r["expert_move_exact"] is not None for r in rows),
                                "api_usd": 0, **metrics})
            for arm in CONTRASTS:
                values = []
                session_values = []
                matched_values = []
                changes = 0
                for t in data:
                    full = t["rows"]["B4"]
                    other = t["rows"][arm]
                    changed = full["wire"] != other["wire"]
                    changes += changed
                    j = judges[t["case"]]
                    q4 = quality(j["scores"].get("B4", [None] * 3))
                    q_other = quality(j["scores"].get(arm, [None] * 3))
                    delta = q4 - q_other if q4 is not None and q_other is not None else None
                    if delta is not None:
                        values.append((t["group"], delta))
                        session_values.append((t["session"], delta))
                        if (len(full["indices"]) == len(other["indices"])
                                and abs(full["history_tokens"] - other["history_tokens"]) <= 16):
                            matched_values.append((t["group"], delta))
                    fw4 = t["selector"]["B4"]
                    fw_other = t["selector"].get(arm, {})
                    w4 = fw4["weights"]
                    w_other = fw_other.get("weights")
                    order4 = [i for i, _ in w4]
                    order_other = [i for i, _ in w_other] if w_other is not None else None
                    ablations.append({
                        "case": t["case"], "source": source, "split": split, "contrast": arm,
                        "weight_values_changed": w4 != w_other if w_other is not None else None,
                        "shortlist_order_changed": order4 != order_other if order_other is not None else None,
                        "full_attention": json.dumps(w4), "contrast_weights": json.dumps(w_other),
                        "full_projection_nonzero": any(fw4["projected"]),
                        "full_pre_refill": json.dumps(fw4["bottleneck_out"]),
                        "full_before_cap": json.dumps(fw4["selected_before_wire"]),
                        "contrast_before_cap": json.dumps(fw_other.get("selected_before_wire")),
                        "full_indices": json.dumps(full["indices"]), "contrast_indices": json.dumps(other["indices"]),
                        "wire_changed": changed, "full_tokens": full["history_tokens"],
                        "contrast_tokens": other["history_tokens"], "deleted_index": other["deletion"],
                        "quality_full": q4, "quality_contrast": q_other, "delta_full_minus_contrast": delta,
                        "same_teacher_output": full["teacher"]["output"] == other["teacher"]["output"],
                    })
                pairs.append({"source": source, "split": split, "contrast": arm,
                              "n": len(data), "wire_changed": changes, "paired_n": len(values),
                              "mean_delta": mean([d for _, d in values]), "ci95": cluster_interval(values),
                              "session_ci95": cluster_interval(session_values),
                              "matched_fragments_within16_tokens_n": len(matched_values),
                              "matched_mean_delta": mean([d for _, d in matched_values]),
                              "matched_ci95": cluster_interval(matched_values)})
    write_csv(HERE / "results.csv", summary)
    write_csv(HERE / "attention_ablation.csv", ablations)
    with (HERE / "teaching_traces.jsonl").open("w", encoding="utf-8") as stream:
        for row in share:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    assessment = {"scenarios": scenario, "paired": pairs, "source_boundaries": {
        "PeerMathDial": "middle-school real transcript; no expert diagnosis/strategy ground truth",
        "Bridge": "primary-school real text, expert references, no learner identity linkage",
    }}
    main_test = [p for p in pairs if p["source"] == "PeerMathDial" and p["split"] == "test"
                 and p["contrast"] in {"B2", "B3", "B5", "B6"}]
    effect = scenario["PeerMathDial/test"]["attention_changes_wire_vs_uniform"] >= 12
    passed = effect and len(main_test) == 4 and all(p["ci95"][0] is not None and p["ci95"][0] > 0 for p in main_test)
    assessment["gate_a"] = {"wire_mechanism_passed": effect, "utility_passed": passed,
                            "gate_b_triggered": passed}
    dump(HERE / "analysis.json", assessment)
    print(json.dumps(assessment["scenarios"], ensure_ascii=True))


if __name__ == "__main__":
    main()
