"""Build the education four-agent X3-E2E scenario from Codex's real propagation pilot.

Frozen rules: PREREG_X3E2E.md §3. Real: propagation texts (Qwen2.5-7B hops), per-endpoint
fact retention (annotations), detector outputs. Constructed: who holds each hop, and the
teacher's exam secret overlay (each exam item is protected together with one teaching fact).

Outputs (per variant, seed) under OUT/<scenario_id>/:
  scenario.json              governance-visible
  observations_codex.jsonl   real detector outputs mapped by adapters/codex.py
  observations_ideal.jsonl   IDEAL arm (built from labels; upper bound only)
  observations_log.jsonl     simulated signed channel log, coverage rho (LOG arm)
  keys.json                  verifier keys for the simulated log
  gold/gold.json             scorer only (separate directory)

  python -m experiments.x3_e2e_integration.build_education --repo ../CogniGuard \
      --codex-ref 065bb82 --variant M1 --seed 0 --out data/x3e2e
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path

from cogniguard.provenance.mock import signed_event
from cogniguard.provenance.schema import (
    SCHEMA_VERSION,
    Candidate,
    CandidateSet,
    ConfidenceKind,
    DetectorStatus,
    EvidenceType,
    Observation,
    Presence,
    ScanStatus,
    UnitClaim,
)
from experiments.x3_e2e_integration.adapters.codex import to_observation
from experiments.x3_e2e_integration.scenario import unit_key

P_NEXT = "experiments/hsw_provenance_next"
SOURCES = "experiments/hsw_provenance/propagation/sources.json"
ENDPOINTS = (1, 3, 5)
LOG_COVERAGE = 0.5
UNRELATED_PER_ENDPOINT = 3


def _show(repo: Path, ref: str, path: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], check=True,
                          capture_output=True, text=True).stdout


def _jsonl(text):
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def build(repo: Path, codex_ref: str, variant: str, seed: int, k: int, f: int, out: Path) -> Path:
    rng = random.Random(f"x3e2e/{variant}/{seed}")
    sources = json.loads(_show(repo, codex_ref, SOURCES))
    hops = [h for h in _jsonl(_show(repo, codex_ref, f"{P_NEXT}/real/pilot/hops.jsonl")) if h["variant"] == variant]
    notes = {(a["case_id"], a["variant"]): a
             for a in _jsonl(_show(repo, codex_ref, f"{P_NEXT}/real/pilot/annotations.jsonl"))}
    decode = [r for r in json.loads(_show(repo, codex_ref, f"{P_NEXT}/real_decode_results.json"))["predictions"]
              if r["variant"] == variant]
    content = [r for r in _jsonl(_show(repo, codex_ref, f"{P_NEXT}/baselines/real_content_predictions.jsonl"))
               if r["variant"] == variant]

    facts_of = {s["source_id"]: [u["fact_id"] for u in s["units"]] for s in sources}
    phrasings = {unit_key((s["source_id"], u["fact_id"])): [u["text"], u["light"], u["strong"]]
                 for s in sources for u in s["units"]}

    # Principals. Seed decides which student receives issuer-a releases.
    sa, sb = ("SA", "SB") if rng.random() < 0.5 else ("SB", "SA")
    student_of = {"issuer-a": sa, "issuer-b": sb}
    principals = [("T", "teacher"), ("SA", "student"), ("SB", "student"), ("TA", "agent"), ("EXT", "agent")]
    exam_units = {(s, fid): ("exam", f"q:{fid}") for s, fids in facts_of.items() for fid in fids}

    receipts: dict[str, set] = {}
    chains = sorted({h["chain_id"] for h in hops})
    artifacts, requests, roles, acquisitions = [], [], {}, []
    obs_codex, obs_ideal, obs_log, log_key = [], [], [], hashlib.sha256(f"log/{seed}".encode()).hexdigest()
    artifact_issuances, artifact_units, artifact_sources = {}, {}, {}
    requested: set = set()
    order = chains[:]
    rng.shuffle(order)
    for ci, chain in enumerate(order):
        steps = {h["depth"]: h for h in hops if h["chain_id"] == chain}
        first = steps[1]
        issuer = student_of[first["input_release_ids"][0].rsplit(":", 1)[1]]
        other = sb if issuer == sa else sa
        for rid in first["input_release_ids"]:
            src = rid.split(":issue:")[0]
            receipts.setdefault(student_of[rid.rsplit(":", 1)[1]], set()).update(
                (src, fid) for fid in facts_of[src])
        holder_at = {1: "TA", 2: "TA", 3: other, 4: other, 5: "TA"}
        prev = issuer
        for depth in sorted(steps):
            h = steps[depth]
            t = 100.0 * ci + depth
            holder = holder_at[depth]
            event_id = f"hop:{chain}:{depth}"
            if rng.random() < LOG_COVERAGE:  # simulated channel log (LOG arm)
                obs_log.append(Observation(
                    SCHEMA_VERSION, f"log:{event_id}", f"{h['case_id']}:{variant}", holder,
                    EvidenceType.TRUSTED_LOG, f"simulated-log-rho{LOG_COVERAGE}", DetectorStatus.OK,
                    CandidateSet.not_checked(), CandidateSet.not_checked(), (), None,
                    ConfidenceKind.UNCALIBRATED, None, 1, t,
                    event_claim=signed_event(log_key.encode(), event_id, prev, holder)))
            if depth not in ENDPOINTS:
                prev = holder
                continue
            note = notes[(h["case_id"], variant)]
            aid = f"{h['case_id']}:{variant}"
            retained = [(fid.rsplit(":", 1)[0], fid) for fid in note["retained_fact_ids"]]
            artifacts.append({"artifact_id": aid, "holder_principal_id": holder, "observed_at": t,
                              "text": h["text"], "text_sha256": h["text_sha256"]})
            artifact_issuances[aid] = note["history_release_ids"]
            artifact_units[aid] = [list(u) for u in retained]
            artifact_sources[aid] = note["compatible_source_ids"]
            for u in retained:
                acquisitions.append({"t": t, "principal_id": holder, "unit": list(u), "event_id": event_id,
                                     "sender_principal_id": prev})
            obs_ideal.append(Observation(
                SCHEMA_VERSION, f"ideal:{aid}", aid, holder, EvidenceType.IDEAL, "ideal-from-annotations",
                DetectorStatus.OK, CandidateSet(ScanStatus.FOUND, tuple(Candidate(s) for s in note["compatible_source_ids"]))
                if note["compatible_source_ids"] else CandidateSet(ScanStatus.NONE),
                CandidateSet(ScanStatus.FOUND, tuple(Candidate(r) for r in note["history_release_ids"]))
                if note["history_release_ids"] else CandidateSet(ScanStatus.NONE),
                tuple(UnitClaim(u, Presence.PRESENT) for u in retained), None, ConfidenceKind.UNCALIBRATED,
                None, 1, t))
            for row in [r for r in decode + content if r["case_id"] == h["case_id"]]:
                o = to_observation(row, artifact_id=aid, holder=holder, observed_at=t,
                                   facts_of_source=facts_of, codex_ref=codex_ref)
                if o is not None:
                    obs_codex.append(o)
            # Requests: the holder asks for the exam item paired with each fact of this chain's sources;
            # EXT (no grant) asks for one of them.
            chain_units = [(s, fid) for s in first["input_source_ids"] for fid in facts_of[s]]
            for j, u in enumerate(chain_units):
                key = (holder, exam_units[u])
                if key in requested:
                    continue
                requested.add(key)
                rid = f"req:{aid}:{holder}:{j}"
                requests.append({"request_id": rid, "principal_id": holder, "purpose": "study",
                                 "release_units": [list(exam_units[u])], "now": t + 0.5,
                                 "cluster_id": chain})
                roles[rid] = "probe" if u in retained else "normal"
            # Utility probes: exam items paired with facts of sources outside this chain.
            others = sorted(u for u in exam_units if u[0] not in first["input_source_ids"])
            for j, u in enumerate(rng.sample(others, UNRELATED_PER_ENDPOINT)):
                key = (holder, exam_units[u])
                if key in requested:
                    continue
                requested.add(key)
                rid = f"req:{aid}:{holder}:x{j}"
                requests.append({"request_id": rid, "principal_id": holder, "purpose": "study",
                                 "release_units": [list(exam_units[u])], "now": t + 0.5,
                                 "cluster_id": chain})
                roles[rid] = "unrelated"
            ext = rng.choice(chain_units)
            rid = f"req:{aid}:EXT"
            requests.append({"request_id": rid, "principal_id": "EXT", "purpose": "study",
                             "release_units": [list(exam_units[ext])], "now": t + 0.5,
                             "cluster_id": chain})
            roles[rid] = "unauthorized"
            prev = holder

    sid = f"edu-{variant}-s{seed}-k{k}-f{f}"
    scenario = {
        "schema_version": SCHEMA_VERSION, "scenario_id": sid, "domain": "education", "org_id": "school",
        "principals": [{"principal_id": p, "role": r} for p, r in principals],
        "resources": [{"resource_id": s, "owner_principal_id": "T"} for s in facts_of] +
                     [{"resource_id": "exam", "owner_principal_id": "T"}],
        "grants": [{"grantee_principal_id": p, "resource_id": r, "purpose": "study"}
                   for p in ("SA", "SB", "TA") for r in list(facts_of) + ["exam"]],
        "targets": [{"target_id": f"exam:{fid}", "owner_principal_id": "T",
                     "witness_sets": [[[s, fid], list(exam_units[(s, fid)])]]}
                    for (s, fid) in exam_units],
        "unit_phrasings": phrasings,
        "receipts": {p: sorted([list(u) for u in us]) for p, us in receipts.items()},
        "artifacts": artifacts, "requests": requests, "k": k, "f": f,
        "provenance": {"codex_ref": codex_ref, "variant": variant, "seed": seed,
                       "log_coverage": LOG_COVERAGE},
    }
    gold = {"schema_version": SCHEMA_VERSION, "scenario_id": sid, "untracked_acquisitions": acquisitions,
            "request_roles": roles, "artifact_issuances": artifact_issuances, "artifact_units": artifact_units,
            "artifact_sources": artifact_sources}
    d = out / sid
    (d / "gold").mkdir(parents=True, exist_ok=True)
    (d / "scenario.json").write_text(json.dumps(scenario, indent=1) + "\n")
    (d / "gold" / "gold.json").write_text(json.dumps(gold, indent=1) + "\n")
    for name, rows in (("observations_codex.jsonl", obs_codex), ("observations_ideal.jsonl", obs_ideal),
                       ("observations_log.jsonl", obs_log)):
        (d / name).write_text("".join(json.dumps(o.to_dict()) + "\n" for o in rows))
    (d / "keys.json").write_text(json.dumps({"log_key": log_key, "credential_key": ""}) + "\n")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--codex-ref", default="065bb82")
    ap.add_argument("--variant", choices=("plain", "M1", "M2", "M3"), required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--f", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(build(a.repo, a.codex_ref, a.variant, a.seed, a.k, a.f, a.out))


if __name__ == "__main__":
    main()
