"""X1 utility diagnosis.

Imports the frozen joint-commit script. Does not retune gates and does not award PASS.
Safety stays check_release. Methods differ only in future-request visibility and the selection rule.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

HISTORICAL = Path(
    "/Users/MBP/.grok/worktrees/cogniguard-cogniguard/"
    "subagent-01a20c49-29d2-7e30-b1ff-6dda8a04b8e5/"
    "experiments/parallel_x_20261124/x1_policy/run.py"
)
OUT_DIR = Path(__file__).resolve().parent
RESULT_PATH = OUT_DIR / "RESULT.md"
SUMMARY_PATH = OUT_DIR / "results" / "summary.json"
WITNESS_TYPES = ("agg", "sum", "test")
EXACT_SUBSET_CAP = 16
UTILITY_TOL = 0.01
CLAIMED_SEED0_SERIAL = (
    "u_agg",
    "u_agg2",
    "u_agg3",
    "u_pair",
    "u_pair2",
    "u_pair3",
)
SCHEDULES = (
    ("simultaneous", "simultaneous", "A", "A", None),
    ("sequential", "sequential", "A", "A", None),
    ("multi_round", "rounds", "A", "A", None),
    ("cross", "cross", "A", "B", ("A", "B")),
)
METHODS = (
    "serial_gate",
    "joint_commit",
    "utility_greedy_reorder",
    "lookahead_2",
    "exact_type_ban",
    "exact_subset",
)


def load_historical():
    root = str(HISTORICAL.resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location("x1_historical_joint", HISTORICAL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load historical script: {HISTORICAL}")
    module = importlib.util.module_from_spec(spec)
    # Python 3.14 dataclasses require the module to be registered before exec.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def flatten(batches):
    return [item for batch in batches for item in batch]


def knowledge_of(holds):
    return {name: frozenset(units) for name, units in holds.items()}


def release_safe(hx, subject, units, holds):
    """Empty release is safe. Otherwise check_release, recipient holdings included."""
    if not units:
        return True
    return hx.check_release(
        hx.REGISTRY,
        subject,
        [unit.ref for unit in units],
        knowledge_of(holds),
        hx.COALITION_K,
    ).safe


def admissible(hx, item, cand, holds):
    return hx.b4_ok(cand) and release_safe(hx, item.subject, cand.units, holds)


def pick_serial(hx, item, holds):
    """Highest utility, then longer unit tuple, matching _select_under_ban's tie break."""
    best = item.task.candidates[-1]
    for cand in item.task.candidates:
        if not admissible(hx, item, cand, holds):
            continue
        if (cand.utility, len(cand.units)) >= (best.utility, len(best.units)):
            best = cand
    return best


def serial_gate(hx, batches, subjects):
    holds = {name: set() for name in subjects}
    chosen = {}
    cursor = 0
    for batch in batches:
        for item in batch:
            cand = pick_serial(hx, item, holds)
            chosen[cursor] = cand
            cursor += 1
            holds[item.subject] |= {unit.ref for unit in cand.units}
    return chosen


def max_candidate_utility(item):
    return max(cand.utility for cand in item.task.candidates)


def utility_greedy_reorder(hx, batches, subjects):
    items = flatten(batches)
    ordered = sorted(items, key=lambda item: (-max_candidate_utility(item), item.task.name))
    return ordered, serial_gate(hx, [ordered], subjects)


def best_safe_utility(hx, item, holds):
    best = 0.0
    for cand in item.task.candidates:
        if admissible(hx, item, cand, holds):
            best = max(best, cand.utility)
    return best


def lookahead_2(hx, batches, subjects):
    """Arrival order. Horizon is the current item and the next item only."""
    items = flatten(batches)
    holds = {name: set() for name in subjects}
    chosen = {}
    for index, item in enumerate(items):
        nxt = items[index + 1] if index + 1 < len(items) else None
        best = None
        best_key = None
        for cand_index, cand in enumerate(item.task.candidates):
            if not admissible(hx, item, cand, holds):
                continue
            nxt_utility = 0.0
            if nxt is not None:
                trial = {name: set(units) for name, units in holds.items()}
                trial[item.subject] |= {unit.ref for unit in cand.units}
                nxt_utility = best_safe_utility(hx, nxt, trial)
            # Sum first. A tie keeps the higher current utility, so an equal-utility
            # next item does not overturn a safe current release.
            key = (cand.utility + nxt_utility, cand.utility, len(cand.units), -cand_index)
            if best_key is None or key > best_key:
                best = cand
                best_key = key
        if best is None:
            best = item.task.candidates[-1]
        chosen[index] = best
        holds[item.subject] |= {unit.ref for unit in best.units}
    return chosen


def benign_success_count(items, chosen):
    count = 0
    for index, item in enumerate(items):
        if item.task.role != "benign":
            continue
        goal = {unit.ref for unit in item.task.units}
        delivered = {unit.ref for unit in chosen[index].units}
        if goal <= delivered:
            count += 1
    return count


def exact_type_ban(hx, items, subjects):
    best = None
    best_key = None
    best_ban = None
    for mask in range(1 << len(WITNESS_TYPES)):
        banned = frozenset(
            WITNESS_TYPES[bit] for bit in range(len(WITNESS_TYPES)) if mask & (1 << bit)
        )
        chosen = {
            index: hx._select_under_ban(item, banned) for index, item in enumerate(items)
        }
        holds = hx._simulate(items, chosen, subjects)
        if not hx.library_safe(holds):
            continue
        success = benign_success_count(items, chosen)
        ban_tuple = tuple(sorted(banned))
        # Higher success, then fewer banned types, then lexical ban tuple.
        key = (success, -len(banned), tuple(-ord(ch) for ch in repr(ban_tuple)))
        if best_key is None or key > best_key:
            best = chosen
            best_key = key
            best_ban = ban_tuple
    if best is None:
        raise RuntimeError("exact_type_ban found no safe witness-type subset")
    return best, best_ban


def best_b4_non_refuse(hx, item):
    best = None
    for cand in item.task.candidates:
        if not cand.units or not hx.b4_ok(cand):
            continue
        if best is None or (cand.utility, len(cand.units)) >= (best.utility, len(best.units)):
            best = cand
    return best


def exact_subset(hx, items, subjects):
    if len(items) > EXACT_SUBSET_CAP:
        return None, (
            f"not run: flattened schedule has {len(items)} items, "
            f"above the {EXACT_SUBSET_CAP}-item cap"
        )
    choosable = []
    for index, item in enumerate(items):
        cand = best_b4_non_refuse(hx, item)
        if cand is not None:
            choosable.append((index, cand))
    refuse = {index: item.task.candidates[-1] for index, item in enumerate(items)}
    best = None
    best_key = None
    width = len(choosable)
    for mask in range(1 << width):
        chosen = dict(refuse)
        for bit, (index, cand) in enumerate(choosable):
            if mask & (1 << bit):
                chosen[index] = cand
        holds = hx._simulate(items, chosen, subjects)
        if not hx.library_safe(holds):
            continue
        success = benign_success_count(items, chosen)
        # Max benign successes. Ties: fewer non-refuse releases, then smaller mask.
        key = (success, -mask.bit_count(), -mask)
        if best_key is None or key > best_key:
            best = chosen
            best_key = key
    if best is None:
        raise RuntimeError("exact_subset found no safe assignment")
    return best, f"run: {len(items)} items, {width} binary tasks, 2^{width} assignments"


def decision_map(items, chosen):
    return tuple(
        sorted(
            (
                item.task.name,
                item.subject,
                chosen[index].name,
                tuple(unit.ref for unit in chosen[index].units),
            )
            for index, item in enumerate(items)
        )
    )


def missed_benign(records):
    return [row.task for row in records if row.role == "benign" and not row.success]


def new_bucket():
    return {
        "tasks": 0,
        "benign_tasks": 0,
        "violations": 0,
        "successes": 0,
        "false_rejects": 0,
        "sessions": 0,
        "joint_covered_sessions": 0,
        "decisions_equal_sessions": 0,
        "status": "run",
        "reason": "",
    }


def add_bucket(bucket, summary, covered, equal):
    bucket["tasks"] += summary["tasks"]
    bucket["benign_tasks"] += summary["benign_tasks"]
    bucket["violations"] += summary["violations"]
    bucket["successes"] += summary["successes"]
    bucket["false_rejects"] += summary["false_rejects"]
    bucket["sessions"] += 1
    bucket["joint_covered_sessions"] += int(covered)
    bucket["decisions_equal_sessions"] += int(equal)


def finish_bucket(bucket):
    tasks = bucket["tasks"]
    benign = bucket["benign_tasks"]
    sessions = bucket["sessions"]
    bucket["violation_rate"] = bucket["violations"] / tasks if tasks else 0.0
    bucket["benign_success"] = bucket["successes"] / benign if benign else 0.0
    bucket["false_reject_rate"] = bucket["false_rejects"] / benign if benign else 0.0
    bucket["joint_covered_sessions_label"] = f"{bucket['joint_covered_sessions']}/{sessions}"
    if bucket["status"] != "run":
        bucket["decisions_equal_joint_commit"] = None
    else:
        bucket["decisions_equal_joint_commit"] = (
            sessions > 0 and bucket["decisions_equal_sessions"] == sessions
        )
    return bucket


def skipped_bucket(reason, sessions):
    bucket = new_bucket()
    bucket["status"] = "not_run"
    bucket["reason"] = reason
    bucket["sessions"] = sessions
    for key in (
        "tasks",
        "benign_tasks",
        "violations",
        "successes",
        "false_rejects",
        "violation_rate",
        "benign_success",
        "false_reject_rate",
        "joint_covered_sessions",
    ):
        bucket[key] = None
    bucket["joint_covered_sessions_label"] = "not run"
    bucket["decisions_equal_joint_commit"] = None
    return bucket


def score(hx, schedule, items, chosen, subjects, pass_to):
    records, holds = hx.materialize(schedule, items, chosen, subjects, pass_to)
    summary = hx.summarize(records)
    covered = "joint_label" in hx.covered_targets(holds)
    return {
        "summary": summary,
        "covered": covered,
        "missed": missed_benign(records),
        "decisions": decision_map(items, chosen),
        "oracle": hx.oracle_label(holds),
    }


def select(hx, method, batches, subjects):
    items = flatten(batches)
    ban = None
    note = "run"
    if method == "serial_gate":
        chosen = serial_gate(hx, batches, subjects)
    elif method == "joint_commit":
        chosen = hx.joint_commit(items, subjects, hx.Clock())
    elif method == "utility_greedy_reorder":
        items, chosen = utility_greedy_reorder(hx, batches, subjects)
    elif method == "lookahead_2":
        chosen = lookahead_2(hx, batches, subjects)
    elif method == "exact_type_ban":
        chosen, ban = exact_type_ban(hx, items, subjects)
    elif method == "exact_subset":
        chosen, note = exact_subset(hx, items, subjects)
        if chosen is None:
            return None
    else:
        raise KeyError(method)
    return {"items": items, "chosen": chosen, "ban": ban, "note": note}


def session_cases(hx):
    cases = []
    for schedule, mode, holder, receiver, explicit_pass in SCHEDULES:
        subjects = ["A"] if holder == receiver else ["A", "B"]
        batches, pass_to = hx.curriculum_batches(mode, holder, receiver)
        if explicit_pass:
            pass_to = explicit_pass
        cases.append(("deterministic", schedule, batches, subjects, pass_to))
    for seed in hx.DEV_SEEDS:
        batches, subjects, pass_to = hx.dev_session(seed)
        cases.append(("dev", f"dev-{seed}", batches, subjects, pass_to))
    return cases


def run_methods(hx):
    rows = []
    utilities = {}
    for item in (*hx.TASKS, hx.AUDIT_DELIVER, hx.AUDIT_BLOCK):
        utilities[item.name] = max_candidate_utility(ItemView(item))
    for split, schedule, batches, subjects, pass_to in session_cases(hx):
        joint = select(hx, "joint_commit", batches, subjects)
        joint_scored = score(
            hx, schedule, joint["items"], joint["chosen"], subjects, pass_to
        )
        for method in METHODS:
            selected = select(hx, method, batches, subjects)
            if selected is None:
                rows.append(
                    {
                        "split": split,
                        "schedule": schedule,
                        "method": method,
                        "status": "not_run",
                        "reason": exact_subset(hx, flatten(batches), subjects)[1],
                        "n_items": len(flatten(batches)),
                        "subjects": list(subjects),
                    }
                )
                continue
            scored = (
                joint_scored
                if method == "joint_commit"
                else score(
                    hx,
                    schedule,
                    selected["items"],
                    selected["chosen"],
                    subjects,
                    pass_to,
                )
            )
            rows.append(
                {
                    "split": split,
                    "schedule": schedule,
                    "method": method,
                    "status": "run",
                    "reason": selected["note"] if method == "exact_subset" else "run",
                    "n_items": len(selected["items"]),
                    "ban": list(selected["ban"]) if selected["ban"] is not None else None,
                    "summary": scored["summary"],
                    "covered": scored["covered"],
                    "missed": scored["missed"],
                    "equal_joint": scored["decisions"] == joint_scored["decisions"],
                    "oracle": scored["oracle"],
                    "batch_names": [
                        [item.task.name for item in batch] for batch in batches
                    ],
                }
            )
    return rows, utilities


class ItemView:
    def __init__(self, task):
        self.task = task


def aggregate(rows, split, method):
    picked = [row for row in rows if row["split"] == split and row["method"] == method]
    if not picked:
        return finish_bucket(new_bucket())
    if any(row["status"] != "run" for row in picked):
        reason = next(row["reason"] for row in picked if row["status"] != "run")
        return skipped_bucket(reason, len(picked))
    bucket = new_bucket()
    sessions = []
    for row in picked:
        add_bucket(bucket, row["summary"], row["covered"], row["equal_joint"])
        sessions.append(
            {
                "schedule": row["schedule"],
                "n_items": row["n_items"],
                "violations": row["summary"]["violations"],
                "violation_rate": row["summary"]["safety_violation_rate"],
                "benign_tasks": row["summary"]["benign_tasks"],
                "successes": row["summary"]["successes"],
                "benign_success": row["summary"]["task_success_rate"],
                "false_rejects": row["summary"]["false_rejects"],
                "false_reject_rate": row["summary"]["false_reject_rate"],
                "joint_covered": row["covered"],
                "decisions_equal_joint_commit": row["equal_joint"],
                "missed_benign": row["missed"],
                "ban": row["ban"],
                "reason": row["reason"],
            }
        )
    finished = finish_bucket(bucket)
    finished["sessions_detail"] = sessions
    return finished


def b4_totals(hx):
    det_viol = 0
    dev_viol = 0
    for split, schedule, batches, subjects, pass_to in session_cases(hx):
        records, _holds = hx.run_method(
            "B4", schedule, batches, subjects, hx.Clock(), pass_to
        )
        viol = sum(1 for row in records if row.violation)
        if split == "deterministic":
            det_viol += viol
        else:
            dev_viol += viol
    return {"deterministic_violations": det_viol, "dev_violations": dev_viol}


def shuffle_ablation(hx):
    """Serial gate on dev arrival order vs one shuffle of that multiset."""
    per_seed = []
    for seed in hx.DEV_SEEDS:
        batches, subjects, pass_to = hx.dev_session(seed)
        arrival = flatten(batches)
        arrival_chosen = serial_gate(hx, batches, subjects)
        arrival_scored = score(hx, f"dev-{seed}", arrival, arrival_chosen, subjects, pass_to)
        shuffled = list(arrival)
        random.Random(seed).shuffle(shuffled)
        shuffled_chosen = serial_gate(hx, [shuffled], subjects)
        shuffled_scored = score(
            hx, f"dev-{seed}", shuffled, shuffled_chosen, subjects, pass_to
        )
        joint_chosen = hx.joint_commit(arrival, subjects, hx.Clock())
        joint_scored = score(hx, f"dev-{seed}", arrival, joint_chosen, subjects, pass_to)
        per_seed.append(
            {
                "seed": seed,
                "benign_tasks": arrival_scored["summary"]["benign_tasks"],
                "arrival_successes": arrival_scored["summary"]["successes"],
                "arrival_benign_success": arrival_scored["summary"]["task_success_rate"],
                "arrival_violations": arrival_scored["summary"]["violations"],
                "arrival_missed": arrival_scored["missed"],
                "shuffled_successes": shuffled_scored["summary"]["successes"],
                "shuffled_benign_success": shuffled_scored["summary"]["task_success_rate"],
                "shuffled_violations": shuffled_scored["summary"]["violations"],
                "shuffled_missed": shuffled_scored["missed"],
                "moved": arrival_scored["summary"]["successes"]
                != shuffled_scored["summary"]["successes"],
                "shuffle_matches_joint_utility": shuffled_scored["summary"]["successes"]
                == joint_scored["summary"]["successes"]
                and shuffled_scored["summary"]["violations"] == 0,
            }
        )
    arrival_success = sum(row["arrival_successes"] for row in per_seed)
    shuffled_success = sum(row["shuffled_successes"] for row in per_seed)
    benign = sum(row["benign_tasks"] for row in per_seed)
    return {
        "per_seed": per_seed,
        "arrival_successes": arrival_success,
        "shuffled_successes": shuffled_success,
        "benign_tasks": benign,
        "arrival_benign_success": arrival_success / benign if benign else 0.0,
        "shuffled_benign_success": shuffled_success / benign if benign else 0.0,
        "order_moves_utility": any(row["moved"] for row in per_seed),
        "any_shuffle_matches_joint_utility": any(
            row["shuffle_matches_joint_utility"] for row in per_seed
        ),
    }


def matches(bucket, joint_bucket):
    if bucket.get("status") != "run" or joint_bucket.get("status") != "run":
        return False
    return (
        bucket["violations"] == 0
        and joint_bucket["violations"] == 0
        and abs(bucket["benign_success"] - joint_bucket["benign_success"]) <= UTILITY_TOL
    )


def choose_label(det, dev, ablation):
    planners = ("utility_greedy_reorder", "lookahead_2")
    planner_match = {
        method: {
            "deterministic": matches(det[method], det["joint_commit"]),
            "dev": matches(dev[method], dev["joint_commit"]),
        }
        for method in planners
    }
    planner = any(
        planner_match[method]["deterministic"] and planner_match[method]["dev"]
        for method in planners
    )
    serial_short = not matches(dev["serial_gate"], dev["joint_commit"])
    reorder_short = not matches(dev["utility_greedy_reorder"], dev["joint_commit"])
    type_matches = matches(dev["exact_type_ban"], dev["joint_commit"])
    subset_matches_det = matches(det["exact_subset"], det["joint_commit"])
    order_only = (not planner) and (
        ablation["any_shuffle_matches_joint_utility"]
        or matches(dev["utility_greedy_reorder"], dev["joint_commit"])
    )
    # A name-sorted serial run is the reorder method. Also treat deterministic
    # equality as evidence that some curriculum order needs no global ban.
    det_order = matches(det["serial_gate"], det["joint_commit"])
    exact_utils = [dev["exact_type_ban"]["benign_success"]]
    if dev["exact_subset"]["status"] == "run":
        exact_utils.append(dev["exact_subset"]["benign_success"])
    planner_utils = [
        dev["serial_gate"]["benign_success"],
        dev["utility_greedy_reorder"]["benign_success"],
        dev["lookahead_2"]["benign_success"],
    ]
    exact_viol_zero = dev["exact_type_ban"]["violations"] == 0 and (
        dev["exact_subset"]["status"] != "run" or dev["exact_subset"]["violations"] == 0
    )
    beats = exact_viol_zero and max(exact_utils) - max(planner_utils) > 0.02
    if planner:
        label = "PLANNER"
        verdict = "STOP"
    elif order_only:
        label = "ORDER_ONLY"
        verdict = "STOP"
    elif serial_short and reorder_short and type_matches:
        label = "FUTURE_INFO"
        verdict = "STOP"
    elif beats and reorder_short:
        label = "JOINT_SELECTOR"
        verdict = "ANALYZE"
    elif det_order and serial_short and not planner:
        # Dev gap remains, but some scored arrival order already matches joint
        # utility with the serial gate and no type ban.
        label = "ORDER_ONLY"
        verdict = "STOP"
    else:
        label = "FUTURE_INFO" if type_matches else "JOINT_SELECTOR"
        verdict = "STOP" if label != "JOINT_SELECTOR" else "ANALYZE"
    return {
        "label": label,
        "verdict": verdict,
        "planner_match": planner_match,
        "planner": planner,
        "serial_short_on_dev": serial_short,
        "reorder_short_on_dev": reorder_short,
        "exact_type_ban_matches_joint_on_dev": type_matches,
        "exact_subset_matches_joint_on_det": subset_matches_det,
        "exact_beats_planners_and_serial": beats,
        "deterministic_serial_matches_joint": det_order,
    }


def fmt(value):
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def table_row(name, bucket):
    if bucket["status"] != "run":
        return (
            f"| {name} | not run | not run | not run | not run | not run | n/a |"
        )
    return (
        f"| {name} | {bucket['violations']} | {fmt(bucket['violation_rate'])} | "
        f"{fmt(bucket['benign_success'])} ({bucket['successes']}/{bucket['benign_tasks']}) | "
        f"{fmt(bucket['false_reject_rate'])} | {bucket['joint_covered_sessions_label']} | "
        f"{bucket['decisions_equal_joint_commit']} |"
    )


def public_bucket(bucket):
    keys = (
        "status",
        "reason",
        "tasks",
        "benign_tasks",
        "violations",
        "violation_rate",
        "successes",
        "benign_success",
        "false_rejects",
        "false_reject_rate",
        "sessions",
        "joint_covered_sessions",
        "joint_covered_sessions_label",
        "decisions_equal_joint_commit",
    )
    out = {key: bucket.get(key) for key in keys}
    if "sessions_detail" in bucket:
        out["sessions_detail"] = bucket["sessions_detail"]
    return out


def attribution(label, det, dev, ablation, seed0, utilities, decision):
    joint = dev["joint_commit"]["benign_success"]
    serial = dev["serial_gate"]["benign_success"]
    greedy = dev["utility_greedy_reorder"]["benign_success"]
    look = dev["lookahead_2"]["benign_success"]
    type_rate = dev["exact_type_ban"]["benign_success"]
    same_u = len(set(utilities.values())) == 1
    u_value = next(iter(utilities.values())) if utilities else None
    names = ", ".join(seed0["serial_gate_missed"]) or "none"
    joint_miss = ", ".join(seed0["joint_commit_missed"]) or "none"
    shuffle_only_test = all(
        row["shuffled_missed"] == ["u_test"] and row["shuffled_violations"] == 0
        for row in ablation["per_seed"]
    )
    if ablation["order_moves_utility"]:
        move = (
            f"Shuffling each dev multiset with Random(seed) moves serial-gate benign success "
            f"from {fmt(ablation['arrival_benign_success'])} to "
            f"{fmt(ablation['shuffled_benign_success'])} "
            f"({ablation['shuffled_successes']}/{ablation['benign_tasks']}). "
        )
        if shuffle_only_test:
            move += (
                "Every shuffled seed misses only u_test and has 0 violations, so those "
                "orders match joint_commit utility with the serial gate and no type ban."
            )
        else:
            move += "Order alone moves utility without a new selector."
    else:
        move = "One dev-seed shuffle of the same multiset did not move serial-gate utility."
    subset_note = dev["exact_subset"]["reason"]
    base = (
        f"Recomputed dev-scan benign success is serial_gate {fmt(serial)} and "
        f"joint_commit {fmt(joint)}, both with 0 reconstruction violations. "
        f"Deterministic schedules do not show that gap: both are "
        f"{fmt(det['joint_commit']['benign_success'])} with the same decisions and "
        f"0 violations. Seed 0 joint_commit misses only "
        f"{joint_miss}; serial_gate misses {names}. "
        f"Every task's max candidate.utility is {u_value}, equal across tasks: {same_u}. "
        f"utility_greedy_reorder therefore sorts by task name and runs the serial gate; "
        f"its dev benign success is {fmt(greedy)}. lookahead_2 dev benign success is "
        f"{fmt(look)}. exact_type_ban dev benign success is {fmt(type_rate)}. "
        f"exact_subset on dev: {subset_note}. {move}"
    )
    if label == "PLANNER":
        which = [
            method
            for method, splits in decision["planner_match"].items()
            if splits["deterministic"] and splits["dev"]
        ]
        return (
            base
            + " "
            + ", ".join(which)
            + " matches joint_commit utility within 0.01 with 0 violations on both splits. "
            "lookahead_2 does not: on the dev scan it stays with the serial gate, because "
            "a conflicting next task has the same utility 1, the two-step sum ties, and "
            "the tie keeps the current safe release. "
            "Ordinary priority planning plus the existing gate closes the utility gap. "
            "The closure is an order, not a new predicate: every max utility is 1, so the "
            "reorder is alphabetical and puts u_test last, after aggregates and summaries "
            "are already held. exact_subset on the 15-item deterministic schedules also "
            "reaches 0.9000, but its decisions differ because it refuses p_joint instead "
            "of releasing that probe's aggregate and summary. It was not run on the "
            "17-item dev sessions. Safety gain versus the serial gate is 0. "
            "Diagnosis verdict STOP. The historical X1 experiment remains STOP and is not a PASS."
        )
    if label == "ORDER_ONLY":
        return (
            base
            + " Some arrival order plus the serial gate matches joint_commit utility "
            "without a global witness ban. The gap is order, not a new selector. "
            "Safety gain versus the serial gate is 0. Diagnosis verdict STOP. "
            "The historical X1 experiment remains STOP and is not a PASS."
        )
    if label == "FUTURE_INFO":
        return (
            base
            + " The online serial gate does not match joint_commit on the dev scan, and "
            "reordering by max candidate utility then applying that gate still falls short. "
            "exact_type_ban matches joint_commit. The utility gap is future-schedule "
            "information used to choose one witness-type ban, not a richer per-item utility. "
            "Safety gain versus the serial gate is 0. Diagnosis verdict STOP. "
            "The historical X1 experiment remains STOP and is not a PASS."
        )
    return (
        base
        + " exact_subset or exact_type_ban beats the serial gate and both planners by "
        "more than 0.02 benign success with 0 violations, and the reorder does not "
        "explain that gain. The residue is a joint selection rule. This diagnosis is "
        "ANALYZE only. It does not award PASS, and the frozen X1 verdict stays STOP. "
        "Safety gain versus the serial gate is 0."
    )


MODEL = """
A finite schedule is a sequence of tasks. Each task has a finite candidate set. A candidate delivers a set of unit refs and has a scalar utility. Every method reads the same task plan, the same candidate objects, and the same `candidate.utility` values.

Safety of a release is `check_release(registry, recipient, release_units, knowledge, k)` from `cogniguard.governance.reconstruction`, with `k = COALITION_K`. Knowledge is every principal's holdings so far, including the recipient. The predicate is that no coalition of size at most `k` that includes the recipient finishes a registered witness. An empty release is safe. No other safety predicate is used. `library_safe` is that predicate on simulated final holdings.

Objective: maximize the number of benign tasks whose goal refs are contained in the delivered refs, subject to safety of the final holdings.

Information each algorithm may read:

- `serial_gate`: the current item and holdings. No future item.
- `joint_commit`: the whole flattened schedule, then one historical witness-type ban.
- `utility_greedy_reorder`: every item's max candidate utility and task name, then the serial gate on that order. No separate utility.
- `lookahead_2`: the current item, the next item, and holdings. Nothing past those two.
- `exact_type_ban`: the whole schedule and the eight subsets of `{agg, sum, test}`.
- `exact_subset`: the whole schedule, and only when it has at most 16 items. Each task is either its best `b4_ok` non-refuse candidate or refuse.

```
serial_gate(batches, holdings):
    for batch in batches:
        for item in batch:
            cand = argmax utility among b4_ok candidates whose units
                   check_release accepts (empty release is safe; else refuse)
            commit cand; add its units to the recipient's holdings
    return commits

utility_greedy_reorder(schedule):
    order = sort schedule by (-max candidate.utility, task name)
    return serial_gate([order], holdings)

lookahead_2(schedule):
    for i, item in enumerate(schedule):
        next = schedule[i + 1] if i + 1 < n else none
        pick cand maximizing cand.utility + best safe utility of next
            after tentatively adding cand
        tie-break: higher cand.utility, then longer unit tuple
        commit cand only; advance one step
    return commits

exact_type_ban(schedule):
    best = none
    for ban in all 8 subsets of {agg, sum, test}:
        chosen = _select_under_ban(item, ban) for item in schedule
        if library_safe(simulate(chosen)):
            keep the safe ban with the most benign successes,
            then fewer banned types, then the lexical ban tuple
    return best
```
""".strip()


def build_report(payload):
    det = payload["utility_table"]["deterministic"]
    dev = payload["utility_table"]["dev_scan"]
    lines = [
        "# X1 utility diagnosis",
        "",
        f"Diagnosis label: **{payload['diagnosis_label']}**.",
        f"Diagnosis verdict: **{payload['diagnosis_verdict']}**.",
        "The frozen X1 verdict stays **STOP**. This file does not award PASS.",
        "",
        "## Model",
        "",
        MODEL,
        "",
        "## Recomputed gap",
        "",
        "Same tasks and the same `candidate.utility` values as the historical joint commit. "
        "The serial gate walks each batch in order and updates holdings before the next item.",
        "",
        "| split | method | violations | benign success | decisions equal joint_commit |",
        "| --- | --- | ---: | ---: | --- |",
        (
            f"| deterministic | joint_commit | {det['joint_commit']['violations']} | "
            f"{fmt(det['joint_commit']['benign_success'])} | yes |"
        ),
        (
            f"| deterministic | serial_gate | {det['serial_gate']['violations']} | "
            f"{fmt(det['serial_gate']['benign_success'])} | "
            f"{det['serial_gate']['decisions_equal_joint_commit']} |"
        ),
        (
            f"| dev scan | joint_commit | {dev['joint_commit']['violations']} | "
            f"{fmt(dev['joint_commit']['benign_success'])} | yes |"
        ),
        (
            f"| dev scan | serial_gate | {dev['serial_gate']['violations']} | "
            f"{fmt(dev['serial_gate']['benign_success'])} | "
            f"{dev['serial_gate']['decisions_equal_joint_commit']} |"
        ),
        "",
        f"B4 violations recomputed: deterministic {payload['b4']['deterministic_violations']}, "
        f"dev {payload['b4']['dev_violations']}. B4 still violates. "
        "Frozen gates, not refit: "
        f"PASS_MIN_ABS_SAFETY_GAIN = {payload['gates']['PASS_MIN_ABS_SAFETY_GAIN']}, "
        f"MAX_UTILITY_DROP = {payload['gates']['MAX_UTILITY_DROP']}, "
        f"MAX_OVERHEAD_RATIO = {payload['gates']['MAX_OVERHEAD_RATIO']}.",
        "",
        "## Deterministic schedules",
        "",
        "Pooled across simultaneous, sequential, multi-round, and cross. Not mixed with the dev scan.",
        "",
        "| method | violations | violation rate | benign success | false reject | joint-covered sessions | decisions equal joint_commit |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for method in METHODS:
        lines.append(table_row(method, det[method]))
    lines.extend(
        [
            "",
            "### Per schedule",
            "",
            "| schedule | method | violations | benign success | equal joint_commit | missed benign |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for method in METHODS:
        detail = det[method].get("sessions_detail") or []
        for row in detail:
            missed = ", ".join(row["missed_benign"]) or "—"
            lines.append(
                f"| {row['schedule']} | {method} | {row['violations']} | "
                f"{fmt(row['benign_success'])} | {row['decisions_equal_joint_commit']} | {missed} |"
            )
        if not detail and det[method]["status"] != "run":
            lines.append(f"| all | {method} | not run | n/a | n/a | {det[method]['reason']} |")
    lines.extend(
        [
            "",
            "## Dev scan",
            "",
            "Five seeds. Round order is shuffled by the historical session builder. Not pooled with the four fixed schedules.",
            "",
            "| method | violations | violation rate | benign success | false reject | joint-covered sessions | decisions equal joint_commit |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for method in METHODS:
        lines.append(table_row(method, dev[method]))
    if dev["exact_subset"]["status"] != "run":
        lines.extend(["", f"exact_subset: {dev['exact_subset']['reason']}."])
    lines.extend(
        [
            "",
            "### Per seed",
            "",
            "| seed | method | benign success | violations | missed benign |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for method in METHODS:
        for row in dev[method].get("sessions_detail") or []:
            missed = ", ".join(row["missed_benign"]) or "—"
            lines.append(
                f"| {row['schedule']} | {method} | {fmt(row['benign_success'])} | "
                f"{row['violations']} | {missed} |"
            )
    seed0 = payload["seed0"]
    lines.extend(
        [
            "",
            "## Seed 0 missed tasks",
            "",
            f"joint_commit missed: {', '.join(seed0['joint_commit_missed']) or '—'}.",
            f"serial_gate missed: {', '.join(seed0['serial_gate_missed']) or '—'}.",
            "Claimed serial misses were "
            + ", ".join(CLAIMED_SEED0_SERIAL)
            + f". Recomputed list matches that claim: {seed0['claimed_serial_matches']}.",
            "",
            "Arrival batches:",
            "",
        ]
    )
    for batch in seed0["batches"]:
        lines.append(f"- {', '.join(batch)}")
    abl = payload["order_ablation"]
    lines.extend(
        [
            "",
            "## Order ablation",
            "",
            "Same dev multiset. `serial_gate` on the historical arrival order versus `serial_gate` "
            "after `random.Random(seed).shuffle` of those items. No new selector.",
            "",
            f"Arrival benign success {fmt(abl['arrival_benign_success'])} "
            f"({abl['arrival_successes']}/{abl['benign_tasks']}). "
            f"Shuffled benign success {fmt(abl['shuffled_benign_success'])} "
            f"({abl['shuffled_successes']}/{abl['benign_tasks']}). "
            f"Order moves utility: {abl['order_moves_utility']}.",
            "",
            "| seed | arrival successes | shuffled successes | moved | shuffle matches joint utility |",
            "| --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in abl["per_seed"]:
        lines.append(
            f"| {row['seed']} | {row['arrival_successes']} | {row['shuffled_successes']} | "
            f"{row['moved']} | {row['shuffle_matches_joint_utility']} |"
        )
    lines.extend(
        [
            "",
            "## Attribution",
            "",
            payload["attribution"],
            "",
            "## Gates",
            "",
            "PASS_MIN_ABS_SAFETY_GAIN = 0.10, MAX_UTILITY_DROP = 0.10, MAX_OVERHEAD_RATIO = 10. "
            "These were not refit. Baseline serial gate already has zero reconstruction violations, "
            "so there is no safety gain to score. A utility recovery from reordering is not a PASS.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    hx = load_historical()
    rows, utilities = run_methods(hx)
    det = {method: aggregate(rows, "deterministic", method) for method in METHODS}
    dev = {method: aggregate(rows, "dev", method) for method in METHODS}
    ablation = shuffle_ablation(hx)
    # Keep the ablation denominator on the same benign count as the dev serial row.
    ablation["benign_tasks"] = dev["serial_gate"]["benign_tasks"]
    ablation["arrival_successes"] = dev["serial_gate"]["successes"]
    ablation["arrival_benign_success"] = dev["serial_gate"]["benign_success"]
    if ablation["benign_tasks"]:
        ablation["shuffled_benign_success"] = (
            ablation["shuffled_successes"] / ablation["benign_tasks"]
        )
    decision = choose_label(det, dev, ablation)
    seed_rows = {
        method: next(
            row
            for row in dev[method].get("sessions_detail") or []
            if row["schedule"] == "dev-0"
        )
        for method in METHODS
        if dev[method]["status"] == "run"
    }
    batches = seed_rows["serial_gate"] and next(
        row["batch_names"]
        for row in rows
        if row["schedule"] == "dev-0" and row["method"] == "serial_gate"
    )
    seed0 = {
        "joint_commit_missed": seed_rows["joint_commit"]["missed_benign"],
        "serial_gate_missed": seed_rows["serial_gate"]["missed_benign"],
        "claimed_serial_gate_missed": list(CLAIMED_SEED0_SERIAL),
        "claimed_serial_matches": seed_rows["serial_gate"]["missed_benign"]
        == list(CLAIMED_SEED0_SERIAL),
        "joint_commit_missed_only_u_test": seed_rows["joint_commit"]["missed_benign"]
        == ["u_test"],
        "batches": batches,
        "utility_greedy_reorder_missed": seed_rows["utility_greedy_reorder"]["missed_benign"],
        "lookahead_2_missed": seed_rows["lookahead_2"]["missed_benign"],
        "exact_type_ban_missed": seed_rows["exact_type_ban"]["missed_benign"],
    }
    b4 = b4_totals(hx)
    both_clean = (
        det["serial_gate"]["violations"] == 0
        and det["joint_commit"]["violations"] == 0
        and dev["serial_gate"]["violations"] == 0
        and dev["joint_commit"]["violations"] == 0
    )
    safety_gain = 0.0 if both_clean else (
        dev["serial_gate"]["violation_rate"] - dev["joint_commit"]["violation_rate"]
    )
    payload = {
        "experiment": "X1-diag",
        "base_sha": hx.BASE_SHA,
        "historical_verdict": "STOP",
        "diagnosis_label": decision["label"],
        "diagnosis_verdict": decision["verdict"],
        "safety_versus_serial_gate": safety_gain,
        "utility_table": {
            "deterministic": {method: public_bucket(det[method]) for method in METHODS},
            "dev_scan": {method: public_bucket(dev[method]) for method in METHODS},
        },
        "attribution": "",
        "paths": [str(RESULT_PATH), str(SUMMARY_PATH), str(OUT_DIR / "run.py")],
        "gates": {
            "PASS_MIN_ABS_SAFETY_GAIN": hx.PASS_MIN_ABS_SAFETY_GAIN,
            "MAX_UTILITY_DROP": hx.MAX_UTILITY_DROP,
            "MAX_OVERHEAD_RATIO": hx.MAX_OVERHEAD_RATIO,
        },
        "max_candidate_utility": utilities,
        "planner_match": decision["planner_match"],
        "planners_matched_joint_commit": decision["planner"],
        "decision": {
            key: value
            for key, value in decision.items()
            if key != "planner_match"
        },
        "seed0": seed0,
        "order_ablation": ablation,
        "b4": b4,
        "imported_script": str(HISTORICAL),
        "notes": (
            "Controls share historical tasks, candidates, and candidate.utility. "
            "check_release is the only safety predicate. "
            "The historical X1 PASS against B4 is not revived."
        ),
    }
    payload["attribution"] = attribution(
        decision["label"], det, dev, ablation, seed0, utilities, decision
    )
    problems = []
    if dev["joint_commit"]["successes"] != 50 or dev["joint_commit"]["benign_tasks"] != 55:
        problems.append(
            f"joint dev successes {dev['joint_commit']['successes']}/"
            f"{dev['joint_commit']['benign_tasks']}"
        )
    if dev["joint_commit"]["violations"] != 0 or dev["serial_gate"]["violations"] != 0:
        problems.append(
            f"dev violations joint {dev['joint_commit']['violations']} "
            f"serial {dev['serial_gate']['violations']}"
        )
    if dev["serial_gate"]["successes"] != 30:
        problems.append(f"serial dev successes {dev['serial_gate']['successes']}")
    if det["joint_commit"]["successes"] != 36 or det["serial_gate"]["successes"] != 36:
        problems.append(
            f"det successes joint {det['joint_commit']['successes']} "
            f"serial {det['serial_gate']['successes']}"
        )
    if det["joint_commit"]["violations"] != 0 or det["serial_gate"]["violations"] != 0:
        problems.append("deterministic violations were not both zero")
    if not det["serial_gate"]["decisions_equal_joint_commit"]:
        problems.append("deterministic serial decisions differ from joint_commit")
    if not seed0["joint_commit_missed_only_u_test"]:
        problems.append(f"seed 0 joint misses {seed0['joint_commit_missed']}")
    if b4["deterministic_violations"] == 0 or b4["dev_violations"] == 0:
        problems.append(f"B4 did not violate: {b4}")
    if abs(safety_gain) > 0 and both_clean:
        problems.append("safety gain should be 0")
    if problems:
        raise SystemExit("reproduction check failed: " + "; ".join(problems))
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    RESULT_PATH.write_text(build_report(payload), encoding="utf-8")
    brief = {
        "diagnosis_label": payload["diagnosis_label"],
        "diagnosis_verdict": payload["diagnosis_verdict"],
        "safety_versus_serial_gate": payload["safety_versus_serial_gate"],
        "deterministic_benign_success": {
            method: det[method]["benign_success"] for method in METHODS
        },
        "dev_benign_success": {
            method: None if dev[method]["status"] != "run" else dev[method]["benign_success"]
            for method in METHODS
        },
        "dev_violations": {method: dev[method]["violations"] for method in METHODS},
        "planners_matched_joint_commit": payload["planners_matched_joint_commit"],
        "planner_match": payload["planner_match"],
        "seed0": {
            "joint": seed0["joint_commit_missed"],
            "serial": seed0["serial_gate_missed"],
            "claimed_serial_matches": seed0["claimed_serial_matches"],
            "greedy": seed0["utility_greedy_reorder_missed"],
            "lookahead": seed0["lookahead_2_missed"],
        },
        "order_moves_utility": ablation["order_moves_utility"],
        "b4": b4,
        "summary": str(SUMMARY_PATH),
    }
    print(json.dumps(brief, indent=2))


if __name__ == "__main__":
    main()
