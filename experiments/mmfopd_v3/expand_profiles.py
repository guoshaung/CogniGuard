from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path


TYPES = ("mastery", "error_pattern", "preference", "learning_state", "behavior_aggregate", "multimodal_summary")
DISTRACTOR_KNOWLEDGE = ("number_theory", "statistics", "linear_algebra", "probability_combinatorics", "general_math_reasoning")


def expand(source: Path, target: Path, *, records_per_profile: int = 50, seed: int = 20260906) -> dict[str, int]:
    rng = random.Random(seed)
    target.mkdir(parents=True, exist_ok=True)
    profiles = [json.loads(line) for line in (source / "profiles.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    for profile in profiles:
        p = copy.deepcopy(profile)
        records = list(p.get("profile_records", []))
        original = list(records)
        student_id = str(p["student_id"])
        knowledge = sorted({str(r.get("knowledge", "general_math_reasoning")) for r in original if r.get("knowledge") != "local_identity"})
        if not knowledge:
            knowledge = ["general_math_reasoning"]
        idx = len(records) + 1
        while len(records) < records_per_profile:
            cycle = len(records) - len(original)
            k = knowledge[cycle % len(knowledge)] if cycle % 5 else DISTRACTOR_KNOWLEDGE[cycle % len(DISTRACTOR_KNOWLEDGE)]
            typ = TYPES[cycle % len(TYPES)]
            sensitivity = 0.25 + 0.65 * rng.random()
            value = {
                "mastery": round(0.25 + 0.7 * rng.random(), 2),
                "error_pattern": f"historical variation {cycle % 9}: needs targeted checking",
                "preference": ("worked_example_then_practice", "visual_then_symbolic", "socratic_questions")[cycle % 3],
                "learning_state": f"confusion={(cycle % 3)}; attention={(cycle + 1) % 3}; fatigue={(cycle + 2) % 3}",
                "behavior_aggregate": f"window={(cycle % 6) + 1}d; hint_rate={round(rng.uniform(.05,.6),2)}; revision_rate={round(rng.uniform(.05,.6),2)}",
                "multimodal_summary": f"modality={(cycle % 4)}; consistency={round(rng.uniform(.3,.98),2)}",
            }[typ]
            records.append({
                "record_id": f"{student_id}_hist_{idx:03d}",
                "type": typ,
                "knowledge": k,
                "value": value,
                "confidence": round(0.45 + 0.5 * rng.random(), 2),
                "sensitivity": round(sensitivity, 2),
                "updated_at": f"2025-{(cycle % 12) + 1:02d}-{(cycle % 27) + 1:02d}",
            })
            idx += 1
        p["profile_records"] = records
        p["profile_version"] = "3.0-mmfopd-expanded"
        p["profile_quality"]["q_history"] = round(min(float(p["profile_quality"].get("q_history", .8)), .9), 2)
        out.append(p)
    (target / "profiles.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in out) + "\n", encoding="utf-8")
    for name in ("student_questions.jsonl", "learning_events.jsonl"):
        (target / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
    return {"profiles": len(out), "records_per_profile": records_per_profile, "total_records": sum(len(p["profile_records"]) for p in out)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--records-per-profile", type=int, default=50)
    args = ap.parse_args()
    print(json.dumps(expand(args.source, args.target, records_per_profile=args.records_per_profile), indent=2))


if __name__ == "__main__":
    main()
