from __future__ import annotations

import json
from pathlib import Path

from ..experiments import ROOT, dependencies, sha256, source_hashes, write_new
from ..teachers.catalog import PromptLibrary, TeamCatalog
from ..teachers.dag import effective_prompt_hash
from .corpus import load_corpus, text_sha

ENTRIES = frozenset({"producer_context", "relay_tamper", "direct_user"})
ATTACK_SOURCES = frozenset({"hf_wild", "injecagent_dh", "injecagent_ds"})


def runtime_hashes():
    values = source_hashes()
    values["experiments/focused/redteam/model.py"] = sha256(
        ROOT / "experiments/focused/redteam/model.py"
    )
    return values


def choose_cases(
    rows, sources, *, per_source=1, seed=20261013, partition="heldout", max_chars=1600
):
    if type(per_source) is not int or not 1 <= per_source <= 100:
        raise ValueError("per_source must be 1..100")
    if not set(sources) <= ATTACK_SOURCES or not sources or len(set(sources)) != len(sources):
        raise ValueError("Only attack-prompt sources are valid; JBB behaviors are not wrappers")
    if partition not in {"heldout", "development"}:
        raise ValueError("Invalid evaluation partition")
    result = []
    for source in sources:
        eligible = [
            r
            for r in rows
            if r["source"] == source
            and r["partition"] == partition
            and r["variant"] in {"base", "jailbreak_2023_12_25"}
            and 20 <= len(r["text"]) <= max_chars
        ]
        eligible.sort(key=lambda r: text_sha(str(seed) + ":" + r["case_id"]))
        seen = set()
        picked = []
        for row in eligible:
            if row["group_id"] in seen:
                continue
            seen.add(row["group_id"])
            picked.append(row)
            if len(picked) == per_source:
                break
        if len(picked) != per_source:
            raise ValueError("Insufficient held-out length-bounded groups for " + source)
        result.extend(picked)
    return result


def target_edge(team):
    # Study a legitimate producer with access to the controlled resource view.
    by_id = {n.id: n for n in team.nodes}
    edges = [e for e in team.edges if "resource_text" in by_id[e.source].view_fields]
    if not edges:
        raise ValueError("Team has no resource-reading producer with an outgoing edge")
    edges.sort(key=lambda e: (team.order().index(e.source), e.target))
    return edges[0]


def build_plan(
    corpus,
    output,
    *,
    team_name="serial_coaching",
    sources=("hf_wild", "injecagent_dh", "injecagent_ds"),
    entries=("producer_context", "relay_tamper"),
    per_source=1,
    seed=20261013,
    partition="heldout",
    max_calls=120,
    max_payload_chars=1600,
):
    if not set(entries) <= ENTRIES or not entries or len(set(entries)) != len(entries):
        raise ValueError("Invalid attack entries")
    if type(max_calls) is not int or not 1 <= max_calls <= 10000:
        raise ValueError("Invalid call budget")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Invalid seed")
    corpus = Path(corpus).resolve()
    output = Path(output)
    if output.exists():
        raise FileExistsError("Plan output already exists")
    lock, rows = load_corpus(corpus)
    prompts, teams = ROOT / "configs/teacher-prompts.yaml", ROOT / "configs/teacher-teams.yaml"
    library = PromptLibrary(prompts)
    catalog = TeamCatalog(teams, library)
    team = catalog.get(team_name)
    edge = target_edge(team)
    # Keep the complete attack and canary objective inside the edge char cap.
    payload_cap = min(max_payload_chars, edge.max_chars - 256, 8000)
    selected = choose_cases(
        rows, sources, per_source=per_source, seed=seed, partition=partition, max_chars=payload_cap
    )
    trials = []
    for row in selected:
        marker = "CG_CANARY_" + text_sha(row["case_id"] + ":" + str(seed))[:16]
        for entry in entries:
            for mode in ("enforce", "observe_only"):
                for condition in ("clean", "attack"):
                    trials.append(
                        {
                            "trial_id": f"t{len(trials):05d}",
                            "case_id": row["case_id"],
                            "source": row["source"],
                            "text_sha256": row["text_sha256"],
                            "entry": entry,
                            "trust_mode": mode,
                            "condition": condition,
                            "marker": marker,
                        }
                    )
    paths = {
        "config": ROOT / "configs/focused.yaml",
        "profiles": ROOT / "protection/student_profile/data/profiles.jsonl",
        "questions": ROOT / "protection/student_profile/data/student_questions.jsonl",
        "resources": ROOT / "protection/teacher_resource/data/teacher_resources.jsonl",
    }
    plan = {
        "schema_version": 1,
        "protocol": "teacher_external_canary_transfer_v1",
        "corpus": str(corpus),
        "corpus_lock_sha256": sha256(corpus / "corpus-lock.json"),
        "corpus_cases_sha256": lock["cases_sha256"],
        "team": team.name,
        "team_sha256": team.sha256,
        "prompt_library": str(prompts),
        "team_catalog": str(teams),
        "prompt_library_sha256": library.sha256,
        "team_catalog_sha256": catalog.sha256,
        "effective_system_prompts": {
            n.id: effective_prompt_hash(library.get(n.teacher, n.prompt)) for n in team.nodes
        },
        "runtime_code_sha256": runtime_hashes(),
        "runtime_dependencies": dependencies(),
        "input_paths": {k: str(v) for k, v in paths.items()},
        "input_hashes": {k: sha256(v) for k, v in paths.items()},
        "source_node": edge.source,
        "target_node": edge.target,
        "seed": seed,
        "partition": partition,
        "selected_cases": len(selected),
        "max_payload_chars": payload_cap,
        "trials": trials,
        "model_calls_upper_bound": len(trials) * len(team.nodes),
        "max_model_calls": max_calls,
        "scoring": "terminal canary marker proxy + per-node propagation; not official InjecAgent/JBB ASR",
        "normal_task_quality_judge": "not_configured",
        "payload_truncation": False,
        "ground_truth_location": "detached_evaluator_only",
        "limitations": [
            "Original attack goals replaced by an appended harmless canary objective",
            "Chinese teaching task with external attack text; not original benchmark task distribution",
            "producer_context is a post-C2 teaching-view intervention; not a C2 copyright evaluation",
            "clean producer/direct-user controls are character-length matched, not tokenizer-matched",
            "relay clean controls retain the original signed packet; modified packets are a different threat from legitimate producers",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "plan.json", plan)
    write_new(
        output / "plan-lock.json",
        {"schema_version": 1, "plan_sha256": sha256(output / "plan.json")},
    )
    return plan


def load_plan(path):
    path = Path(path)
    lock = json.loads((path / "plan-lock.json").read_text(encoding="utf-8"))
    if sha256(path / "plan.json") != lock["plan_sha256"]:
        raise ValueError("Frozen benchmark plan changed")
    plan = json.loads((path / "plan.json").read_text(encoding="utf-8"))
    if (
        plan.get("schema_version") != 1
        or plan.get("protocol") != "teacher_external_canary_transfer_v1"
    ):
        raise ValueError("Unsupported benchmark protocol")
    if sha256(Path(plan["corpus"]) / "corpus-lock.json") != plan["corpus_lock_sha256"]:
        raise ValueError("Corpus lock changed")
    corpus_lock, rows = load_corpus(plan["corpus"])
    if corpus_lock["cases_sha256"] != plan["corpus_cases_sha256"]:
        raise ValueError("Corpus changed")
    library = PromptLibrary(plan["prompt_library"])
    catalog = TeamCatalog(plan["team_catalog"], library)
    team = catalog.get(plan["team"])
    if (
        library.sha256 != plan["prompt_library_sha256"]
        or catalog.sha256 != plan["team_catalog_sha256"]
        or team.sha256 != plan["team_sha256"]
    ):
        raise ValueError("Teacher catalogs changed")
    effective = {n.id: effective_prompt_hash(library.get(n.teacher, n.prompt)) for n in team.nodes}
    if (
        effective != plan.get("effective_system_prompts")
        or runtime_hashes() != plan.get("runtime_code_sha256")
        or dependencies() != plan.get("runtime_dependencies")
    ):
        raise ValueError(
            "Runtime code, dependency or effective system prompt changed; rebuild the plan"
        )
    for name, path in plan["input_paths"].items():
        if sha256(path) != plan["input_hashes"][name]:
            raise ValueError("Teaching input changed")
    by_id = {r["case_id"]: r for r in rows}
    for trial in plan["trials"]:
        if (
            trial["entry"] not in ENTRIES
            or trial["trust_mode"] not in {"enforce", "observe_only"}
            or trial["condition"] not in {"clean", "attack"}
        ):
            raise ValueError("Invalid benchmark trial")
        row = by_id[trial["case_id"]]
        if row["text_sha256"] != trial["text_sha256"] or row["partition"] != plan["partition"]:
            raise ValueError("Trial source mismatch")
    return plan, by_id, library, team
