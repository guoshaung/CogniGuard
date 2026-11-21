"""Construct read-only transcript tasks. Gold is stored separately from inputs."""
import collections
import hashlib
import json
import random
import sys
from pathlib import Path

SEED = 20261112
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from core.paths import CACHE_DIR, RESULTS_DIR

CACHE = CACHE_DIR / "mmfopd_text_transfer_20261112"
RUN = RESULTS_DIR / "mmfopd/text_transfer_20261112/run01"
PEER_REV = "e290f0f7ed766ea128f0c8bab33c0fa98801cbb7"
BRIDGE_REV = "a5b1d426ce517e0aeb4b7b2a64e842501c98e38f"

# Public problem figures inspected at the pinned revision. No answer is added.
FIGURES = {
    "ice_cream": "Chart transcription: mint 10%, strawberry 25%, chocolate chip 15%, vanilla 50%.",
    "one_thousand_one_pennies": "Coin figure transcription: penny 1 cent, nickel 5 cents, dime 10 cents, quarter 25 cents.",
    "znorlian": (
        "Transcription of six clue cards. Symbols named A=upward open angle, B=downward triangle, "
        "C=horizontal bowtie, D=vertical hourglass, E=filled square. "
        "A means one. Order does not matter; AC=CA (five). Adding joins symbols: AA=B. "
        "Three spellings of seven: BABB=BCA=CBA. CC=E=BBBB. "
        "Subtraction card: D-B=BEC. The five symbols B,C,D,E,A write every number 1 through 31 "
        "without doubling a symbol. What is the shortest way to write 21?"
    ),
}


def digest(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fragment(role, text, position):
    return {"role": role, "text": text, "position": position}


def peer_cases():
    source = CACHE / "PeerMathDial"
    turns = [json.loads(line) for line in (source / "data/turns.jsonl").read_text(encoding="utf-8").splitlines()]
    questions = {}
    for path in sorted((source / "tasks").glob("*.md")):
        problem = path.read_text(encoding="utf-8").split("## Problem or Modeling Task", 1)[1].split("## Expected Student Work")[0]
        lines = [line for line in problem.strip().splitlines() if not line.lstrip().startswith("![")]
        questions[path.stem] = "\n".join(lines).strip() + "\n" + FIGURES.get(path.stem, "")
    previous = collections.defaultdict(list)
    grouped = collections.defaultdict(list)
    excluded = collections.Counter()
    for row in turns:
        if row["role"] != "student" or not row["speaker_id"].startswith("student_"):
            excluded["not_identified_student_turn"] += 1
            continue
        if row["grade_band"] != "7-8":
            excluded["outside_grade_7_8"] += 1
            continue
        if row["task_id"] == "bakers_cake":
            excluded["cake_diagram_day_not_reliably_bound_to_current_turn"] += 1
            continue
        speaker = row["speaker_id"]
        history = previous[row["session_id"], speaker]
        text = row["text"]
        if len(text.split()) >= 8 and len(history) >= 4:
            case = {
                "case": "P" + digest((row["session_id"], row["turn_id"], speaker)),
                "group": digest(speaker),
                "session": digest(row["session_id"]),
                "source_position": row["turn_id"],
                "source": "PeerMathDial",
                "topic": row["task_name"],
                "task_family": row["task_id"],
                "problem": questions[row["task_id"]],
                "current": text,
                "candidates": history[-32:].copy(),
                "figure_transcribed": row["task_id"] in FIGURES,
                "day": row["day"],
            }
            grouped[speaker].append((case, {"action": row["action_name"]}))
        else:
            excluded["short_current_or_fewer_than_4_own_prior_turns"] += 1
        if len(text.split()) >= 3:
            history.append(fragment("student", text, row["turn_id"]))
    rng = random.Random(SEED)
    speakers = sorted(grouped)
    rng.shuffle(speakers)
    # Partition whole speakers. Round-robin caps avoid one prolific student dominating.
    development, test = speakers[: max(1, len(speakers) // 4)], speakers[max(1, len(speakers) // 4):]

    def draw(groups, count, split):
        queues = []
        for speaker in groups:
            queue = grouped[speaker].copy()
            rng.shuffle(queue)
            queues.append(queue[:8])
        cases = []
        for turn_index in range(8):
            for queue in queues:
                if turn_index < len(queue) and len(cases) < count:
                    case, gold = queue[turn_index]
                    cases.append((case | {"split": split}, gold))
        return cases

    return draw(development, 20, "dev") + draw(test, 60, "test"), {
        "release_turns": len(turns),
        "release_sessions": len({row["session_id"] for row in turns}),
        "eligible_turns": sum(map(len, grouped.values())),
        "eligible_speakers": len(speakers),
        "excluded_turns": dict(excluded),
    }


def bridge_cases():
    result = []
    audit = {}
    groups_used = set()
    rng = random.Random(SEED)
    for upstream_split, split, count in [("validation", "dev", 6), ("test", "test", 18)]:
        rows = read_json(CACHE / f"bridge/dataset/{upstream_split}.json")
        rng.shuffle(rows)
        eligible = 0
        added = 0
        for row in rows:
            history = row["c_h"]
            if len(history) < 4 or history[-1]["user"] != "student" or history[-2]["user"] != "tutor":
                continue
            if not isinstance(history[-1]["text"], str) or not history[-1]["text"].strip():
                continue
            if not row["c_r_"] or not row["e"] or not row["z_what"]:
                continue
            eligible += 1
            group = row["c_id"].split("_", 1)[0]
            if group in groups_used or added >= count:
                continue
            groups_used.add(group)
            added += 1
            case = {
                "case": "B" + digest(row["c_id"]), "group": digest(group), "session": digest(group),
                "source": "Bridge", "split": split, "topic": row["lesson_topic"],
                "task_family": row["lesson_topic"], "source_position": history[-1]["id"],
                "problem": history[-2]["text"], "current": history[-1]["text"],
                "candidates": [fragment(t["user"], t["text"], t["id"]) for t in history[:-2][-32:]
                               if isinstance(t["text"], str) and t["text"].strip()],
                "figure_transcribed": False,
            }
            gold = {"error": row["e"], "move": row["z_what"], "intent": row["z_why"],
                    "reference": [x["text"] for x in row["c_r_"]]}
            result.append((case, gold))
        audit[split] = {"release_examples": len(rows), "eligible": eligible, "selected": added}
    return result, audit


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    peer, peer_audit = peer_cases()
    bridge, bridge_audit = bridge_cases()
    cases = [case for case, _ in peer + bridge]
    groups = collections.defaultdict(set)
    for case in cases:
        groups[case["source"], case["group"]].add(case["split"])
        assert all(f["position"] < case["source_position"] for f in case["candidates"])
        if case["source"] == "PeerMathDial":
            assert all(f["role"] == "student" for f in case["candidates"])
    assert all(len(splits) == 1 for splits in groups.values())
    dump(RUN / "cases.local.json", cases)
    dump(RUN / "gold.local.json", {case["case"]: gold for case, gold in peer + bridge})
    audit = {"peer": peer_audit, "bridge": bridge_audit, "strata": {}}
    for source in ("PeerMathDial", "Bridge"):
        for split in ("dev", "test"):
            subset = [c for c in cases if (c["source"], c["split"]) == (source, split)]
            audit["strata"][source + "/" + split] = {
                "cases": len(subset), "groups": len({c["group"] for c in subset}),
                "sessions": len({c["session"] for c in subset}),
                "task_families": dict(collections.Counter(c["task_family"] for c in subset)),
                "figure_transcribed": sum(c["figure_transcribed"] for c in subset),
            }
    dump(HERE / "sample_manifest.json", audit)
    print(json.dumps(audit, ensure_ascii=True))


if __name__ == "__main__":
    main()
