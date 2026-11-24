"""X3-E2E entry: gold isolation, mock refusal, replay/online parity. Mock data only."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cogniguard.provenance import contract as C
from cogniguard.provenance.mock import MockDetector, Planted, observation
from cogniguard.provenance.schema import SCHEMA_VERSION, EvidenceType, GoldLeakError
from experiments.x3_e2e_integration import run as R
from experiments.x3_e2e_integration import score as SC

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _scenario(tmp: Path) -> Path:
    _, _, receipts, texts = C.fixture()
    sc = {
        "schema_version": SCHEMA_VERSION, "scenario_id": "mock-edu", "domain": "mock", "org_id": "school",
        "principals": [{"principal_id": p, "role": "student"} for p in "ABC"] + [{"principal_id": "T", "role": "teacher"}],
        "resources": [{"resource_id": "exam", "owner_principal_id": "T"}],
        "grants": [{"grantee_principal_id": p, "resource_id": "exam", "purpose": "study"} for p in "AB"],
        "targets": [{"target_id": "exam", "owner_principal_id": "T", "witness_sets": [[list(C.U1), list(C.U2)]]}],
        "unit_phrasings": {f"{u[0]}|{u[1]}": list(v) for u, v in texts.items()},
        "receipts": {p: [list(u) for u in us] for p, us in receipts.items()},
        "artifacts": [{"artifact_id": "art-b", "holder_principal_id": "B", "observed_at": 1.0,
                       "text": "the exam covers fraction multiplication"}],
        "requests": [{"request_id": "q1", "principal_id": "B", "purpose": "study", "release_units": [list(C.U2)], "now": 2.0},
                     {"request_id": "q2", "principal_id": "C", "purpose": "study", "release_units": [list(C.U3)], "now": 2.0}],
        "k": 1, "f": 0,
    }
    p = tmp / "scenario.json"
    p.write_text(json.dumps(sc))
    return p


def _obs(tmp: Path, rows) -> Path:
    p = tmp / "obs.jsonl"
    p.write_text("".join(json.dumps(o.to_dict()) + "\n" for o in rows))
    return p


def test_runner_has_no_gold_parameter_and_refuses_gold_paths(tmp_path):
    import inspect
    assert "gold" not in inspect.signature(R.run).parameters
    sc = _scenario(tmp_path)
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    with pytest.raises(R.RefusedInput):
        R.run(sc, [gold_dir / "x.jsonl"], None, "R0_receipts", "static")


def test_governance_modules_never_read_gold():
    governance = [*(REPO / "cogniguard" / "provenance").glob("*.py"), HERE / "run.py", HERE / "arms.py",
                  HERE / "scenario.py"]
    for path in governance:
        src = path.read_text()
        assert "score" not in {m.split(".")[-1] for m in src.split() if m.startswith("experiments.")}, path
        assert "load_gold" not in src and "gold.json" not in src, path


def test_gold_fields_rejected_everywhere(tmp_path):
    sc = json.loads(_scenario(tmp_path).read_text())
    sc["requests"][0]["true_role"] = "probe"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(sc))
    with pytest.raises(GoldLeakError):
        R.run(bad, [], None, "R0_receipts", "static")


def test_formal_refuses_mock(tmp_path):
    sc = _scenario(tmp_path)
    o = _obs(tmp_path, [observation("m1", "art-b", "B", units=(C.U1,))])
    with pytest.raises(R.RefusedInput):
        R.run(sc, [o], None, "MOCK", "dyn_knowledge", formal=True)
    with pytest.raises(R.RefusedInput):
        R.run(sc, [o], None, "F_STRONG", "dyn_knowledge", formal=True)


def test_mock_replay_equals_online_and_scores(tmp_path):
    sc = _scenario(tmp_path)
    planted = {"art-b": Planted(units=(C.U1,))}
    obs = MockDetector(planted).detect(R.load_scenario(sc).artifacts[0])
    o = _obs(tmp_path, obs)
    replay, m1 = R.run(sc, [o], None, "MOCK", "dyn_knowledge")
    online, m2 = R.run(sc, [], None, "MOCK", "dyn_knowledge", detector=MockDetector(planted))
    assert [d["allowed"] for d in replay] == [d["allowed"] for d in online] == [False, False]
    assert m1["mock"] and not m1["formal"]
    static, _ = R.run(sc, [o], None, "MOCK", "static")
    assert [d["allowed"] for d in static] == [True, False]   # receipts only: B looks clean
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "decisions.jsonl").write_text("".join(json.dumps(d) + "\n" for d in static))
    (run_dir / "manifest.json").write_text(json.dumps(m1 | {"mode": "static"}))
    gold = {"schema_version": SCHEMA_VERSION, "scenario_id": "mock-edu",
            "untracked_acquisitions": [{"t": 1.0, "principal_id": "B", "unit": list(C.U1)}],
            "request_roles": {"q1": "probe", "q2": "unauthorized"}}
    (tmp_path / "g.json").write_text(json.dumps(gold))
    res = SC.score(run_dir, sc, tmp_path / "g.json")
    assert res["harmful"] == 1 and res["unauthorized_success"] == 0


def test_ideal_only_in_ideal_arm(tmp_path):
    sc = _scenario(tmp_path)
    o = _obs(tmp_path, [observation("i1", "art-b", "B", evidence_type=EvidenceType.IDEAL, units=(C.U1,),
                                         method_version="ideal-test")])
    real, _ = R.run(sc, [o], None, "CONTENT_ALL_WM", "dyn_knowledge", formal=True)
    ideal, man = R.run(sc, [o], None, "IDEAL", "dyn_knowledge", formal=True)
    assert real[0]["allowed"] and not ideal[0]["allowed"]
    assert man["upper_bound"] is True


def _has_codex_ref() -> bool:
    return subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", "065bb82"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _has_codex_ref(), reason="Codex commit 065bb82 not in this clone")
def test_builder_is_deterministic(tmp_path):
    from experiments.x3_e2e_integration.build_education import build
    a = build(REPO, "065bb82", "M1", 99, 1, 0, tmp_path / "a")
    b = build(REPO, "065bb82", "M1", 99, 1, 0, tmp_path / "b")
    for name in ("scenario.json", "observations_codex.jsonl", "gold/gold.json"):
        assert (a / name).read_text() == (b / name).read_text()
    assert "gold" not in (a / "observations_codex.jsonl").read_text()
