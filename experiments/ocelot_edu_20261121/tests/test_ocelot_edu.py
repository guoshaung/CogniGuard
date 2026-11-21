"""Local checks for the OCELOT-Edu harness. These tests do not call a paid API."""

from __future__ import annotations

import json
import unittest

from experiments.ocelot_edu_20261121.ocelot_edu.assets import (
    SCAFFOLD,
    all_units,
    marker_index,
)
from experiments.ocelot_edu_20261121.ocelot_edu.constants import B_STAR, EPSILON_R
from experiments.ocelot_edu_20261121.ocelot_edu.defenders import static_labels
from experiments.ocelot_edu_20261121.ocelot_edu.llm import extract_json
from experiments.ocelot_edu_20261121.ocelot_edu.run_experiment import (
    attack_views,
    decide,
    evaluate,
    fan_out_attacks,
    identity_labels,
    labels_from_model,
    local_arms,
    nemo_adapter,
    prompt_messages,
)
from experiments.ocelot_edu_20261121.ocelot_edu.score import (
    bootstrap_ci,
    verdict_gt_zero,
    verdict_recall,
)
from experiments.ocelot_edu_20261121.ocelot_edu.stimuli import build_streams, coalitions
from experiments.ocelot_edu_20261121.ocelot_edu.verifier import (
    Atom,
    Ledger,
    authorize,
    charge,
    verify_stored_chain,
)


def _echo_attacks(releases, coals):
    ix = {(r["arm"], r["turn_id"]): r["released"] for r in releases}
    arms = sorted({r["arm"] for r in releases})
    attacks = []
    for coal in coals:
        for arm in arms:
            view = "\n".join(ix[(arm, tid)] for tid in coal["turn_ids"])
            attacks.append(
                {
                    "coalition_id": coal["coalition_id"],
                    "arm": arm,
                    "pack_id": coal["pack_id"],
                    "k": coal["k"],
                    "purpose": coal["purpose"],
                    "members": coal["members"],
                    "reconstruction": view,
                }
            )
    return attacks


class AssetsAndStreamsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.turns = build_streams()
        cls.coals = coalitions(cls.turns)
        cls.by_student = {}
        for turn in cls.turns:
            cls.by_student.setdefault(turn["student_id"], []).append(turn)

    def test_inventory(self):
        units = all_units()
        self.assertEqual(len(units), 45)
        self.assertEqual(len({u.pack_id for u in units}), 5)
        markers = [f.marker for u in units for f in u.fragments]
        self.assertEqual(len(markers), len(set(markers)))
        self.assertEqual(len(marker_index()), len(markers))

    def test_every_student_has_a_short_trajectory(self):
        packs = {t["pack_id"] for t in self.turns}
        self.assertEqual(len(packs), 5)
        for pack in packs:
            students = {t["student_id"] for t in self.turns if t["pack_id"] == pack}
            self.assertEqual(len(students), 20)
        for sid, turns in self.by_student.items():
            self.assertGreaterEqual(len(turns), 8, sid)
            self.assertLessEqual(len(turns), 12, sid)

    def test_candidate_contains_only_the_assigned_secret(self):
        known = set(marker_index())
        for turn in self.turns:
            found = {m for m in known if m in turn["candidate"]}
            if turn["marker"] is None:
                self.assertEqual(found, set(), turn["turn_id"])
            else:
                self.assertEqual(found, {turn["marker"]}, turn["turn_id"])
            self.assertIn(SCAFFOLD, turn["candidate"])
            self.assertNotIn(turn["marker"] or "讲义步", turn["question"]) if turn["role"] == "normal" else self.assertIn(
                turn["marker"], turn["question"]
            )

    def test_g1_views_exclude_collector_turns(self):
        turn_ix = {t["turn_id"]: t for t in self.turns}
        g1 = [c for c in self.coals if c["purpose"] == "g1"]
        self.assertTrue(g1)
        for coal in g1:
            for tid in coal["turn_ids"]:
                self.assertNotEqual(turn_ix[tid]["role"], "collector", coal["coalition_id"])
        collectors = [t for t in self.turns if t["role"] == "collector"]
        self.assertTrue(collectors)

    def test_one_student_does_not_hold_a_full_sequence(self):
        units = {u.unit_id: u for u in all_units() if u.kind == "sequence" and u.order == 4}
        for sid, turns in self.by_student.items():
            own = {t["marker"] for t in turns if t["role"] != "collector"}
            for unit in units.values():
                if unit.pack_id not in sid:
                    continue
                self.assertFalse(set(unit.markers) <= own, sid)


class VerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.turns = build_streams()
        cls.units = {u.unit_id: u for u in all_units()}

    def _atoms(self, turn, labels):
        from experiments.ocelot_edu_20261121.ocelot_edu.defenders import atoms_from_labels

        return atoms_from_labels(turn, labels)

    def test_static_redacts_triggers_and_keeps_pedagogy(self):
        field = next(t for t in self.turns if t["unit_id"] and t["unit_id"].endswith(".field"))
        ped = next(t for t in self.turns if t["unit_id"] and ".ped_" in t["unit_id"])
        ledger = Ledger(traj_id="static")
        field_out = authorize(self._atoms(field, static_labels(field)), self.units, ledger, field["turn_id"])
        ped_out = authorize(self._atoms(ped, static_labels(ped)), self.units, ledger, ped["turn_id"])
        self.assertNotIn(field["marker"], field_out["released"])
        self.assertIn(ped["marker"], ped_out["released"])
        self.assertIn(SCAFFOLD, field_out["released"])
        self.assertIn(SCAFFOLD, ped_out["released"])
        self.assertLessEqual(ledger.cum, B_STAR)

    def test_diagnosis_identity_escalates_and_sequence_does_not(self):
        diag = next(t for t in self.turns if t["unit_id"] and ".diag_" in t["unit_id"])
        seqs = [t for t in self.turns if t["unit_id"] and t["unit_id"].endswith(".seq3_a") and t["role"] == "collector"]
        self.assertGreaterEqual(len(seqs), 3)
        ledger = Ledger(traj_id="identity")
        diag_out = authorize(self._atoms(diag, identity_labels(diag)), self.units, ledger, diag["turn_id"])
        self.assertNotIn(diag["marker"], diag_out["released"])
        self.assertGreater(diag_out["escalations"], 0)
        for turn in seqs[:3]:
            out = authorize(self._atoms(turn, identity_labels(turn)), self.units, ledger, turn["turn_id"])
            self.assertIn(turn["marker"], out["released"])
            self.assertEqual(out["cost"], 0.0)
        self.assertLessEqual(ledger.cum, B_STAR)
        unit = self.units[seqs[0]["unit_id"]]
        self.assertGreater(unit.true_advantage(3), 0.0 + EPSILON_R)

    def test_two_diagnosis_fragments_charge_joint_base_then_escalate(self):
        unit = next(u for u in all_units() if u.kind == "diagnosis")
        atoms = [
            Atom(span=frag.text, field=unit.unit_id, kind="direct", necessity="helpful", op="identity", marker=frag.marker, protected=True)
            for frag in unit.fragments
        ]
        ledger = Ledger(traj_id="joint")
        cost, details = charge(atoms, self.units, ledger)
        self.assertAlmostEqual(sum(d["base"] for d in details), 3.0)
        self.assertAlmostEqual(cost, 12.0)
        out = authorize(atoms, self.units, ledger, "joint-turn")
        self.assertLessEqual(out["cum_after"], B_STAR)
        for frag in unit.fragments:
            self.assertNotIn(frag.marker, out["released"])

    def test_none_costs_zero_and_is_not_rewritten_with_gold(self):
        unit = next(u for u in all_units() if u.kind == "field")
        frag = unit.fragments[0]
        atom = Atom(span=frag.text, field="NONE", kind="direct", necessity="unnecessary", op="identity", marker=frag.marker, protected=True)
        ledger = Ledger(traj_id="none")
        out = authorize([atom], self.units, ledger, "none-turn")
        self.assertEqual(out["cost"], 0.0)
        self.assertIn(frag.marker, out["released"])
        self.assertEqual(out["atoms"][0]["field"], "NONE")

    def test_generalize_redact_and_drop_strip_markers(self):
        unit = next(u for u in all_units() if u.kind == "field")
        frag = unit.fragments[0]
        for op in ("generalize", "redact", "drop"):
            ledger = Ledger(traj_id=op)
            atom = Atom(span=frag.text, field=unit.unit_id, kind="direct", necessity="unnecessary", op=op, marker=frag.marker, protected=True)
            out = authorize([atom], self.units, ledger, op)
            self.assertNotIn(frag.marker, out["released"])
            self.assertLessEqual(out["cum_after"], B_STAR)

    def test_hash_chain_roundtrip_and_tamper(self):
        unit = next(u for u in all_units() if u.kind == "pedagogy")
        frag = unit.fragments[0]
        ledger = Ledger(traj_id="chain")
        atom = Atom(span=frag.text, field="NONE", kind="none", necessity="unnecessary", op="identity", marker=frag.marker)
        authorize([atom], self.units, ledger, "t1")
        authorize([atom], self.units, ledger, "t2")
        dumped = json.loads(json.dumps(ledger.entries))
        self.assertTrue(verify_stored_chain(dumped, ledger.public_key_hex()))
        dumped[1]["cost"] = 99
        self.assertFalse(verify_stored_chain(dumped, ledger.public_key_hex()))


class ScoringTest(unittest.TestCase):
    def test_bootstrap_and_verdicts(self):
        zeros = bootstrap_ci([0.0, 0.0, 0.0])
        self.assertEqual(zeros["low"], 0.0)
        self.assertEqual(zeros["high"], 0.0)
        self.assertEqual(verdict_gt_zero(zeros), "不支持")
        ones = bootstrap_ci([1.0, 1.0, 1.0])
        self.assertEqual(verdict_gt_zero(ones), "支持")
        self.assertEqual(verdict_gt_zero({"mean": 0.2, "low": -0.1, "high": 0.4}), "无法判定")
        self.assertEqual(verdict_gt_zero({"mean": None, "low": None, "high": None}), "无法判定")
        self.assertEqual(verdict_recall({"mean": 0.8, "low": 0.6, "high": 0.9}, 0.50), "支持")
        self.assertEqual(verdict_recall({"mean": 0.2, "low": 0.0, "high": 0.4}, 0.50), "不支持")

    def test_fan_out_ignores_completion_order(self):
        jobs = []
        for cid, view in (("c1", "SAME"), ("c2", "SAME"), ("c3", "OTHER")):
            jobs.append(
                {
                    "arm": "prompt",
                    "coalition_id": cid,
                    "view": view,
                    "pack_id": "p",
                    "k": 2,
                    "purpose": "g1",
                    "members": ["s"],
                }
            )
        attacks = [
            {"arm": "prompt", "coalition_id": "c2", "reconstruction": "quoted"},
            {"arm": "prompt", "coalition_id": "c3", "reconstruction": "other-quote"},
        ]
        full = fan_out_attacks(jobs, list(reversed(attacks)))
        by_id = {row["coalition_id"]: row["reconstruction"] for row in full}
        self.assertEqual(by_id["c1"], "quoted")
        self.assertEqual(by_id["c2"], "quoted")
        self.assertEqual(by_id["c3"], "other-quote")

    def test_prompt_parser_falls_back_on_inconsistent_pass2(self):
        turns = build_streams()
        turn = next(t for t in turns if t["unit_id"] and t["unit_id"].endswith(".field"))
        atoms = []
        for i, raw in enumerate(turn["atoms"]):
            atoms.append({"index": i, "field": "NONE", "kind": "none", "op": "identity"})
        pass1 = json.dumps({"atoms": atoms})
        pass2 = json.dumps({"answers": [{"id": "c0", "field": "NOT-THE-LABEL", "op": "drop"}]})
        labels, reason = labels_from_model(turn, pass1, pass2)
        self.assertEqual(reason, "pass2_inconsistent")
        self.assertEqual(labels[1]["op"], "redact")
        consistent = []
        for i in range(4):
            consistent.append({"id": f"c{i}", "field": "NONE", "op": "identity"})
        labels, reason = labels_from_model(turn, pass1, json.dumps({"answers": consistent}))
        self.assertEqual(reason, "model")
        self.assertTrue(all(lab["field"] == "NONE" for lab in labels))

    def test_attacker_view_hides_turn_ids_and_pass2_has_no_planted_label(self):
        turns = build_streams()
        turn = next(t for t in turns if t["marker"])
        release = {
            "arm": "ocelot_minus",
            "turn_id": turn["turn_id"],
            "released": "公共讲解，没有编号。",
        }
        coal = {
            "coalition_id": "c",
            "pack_id": turn["pack_id"],
            "k": 1,
            "purpose": "g1",
            "members": [turn["student_id"]],
            "turn_ids": [turn["turn_id"]],
        }
        view = attack_views([release], [coal], ["ocelot_minus"])[0]["view"]
        self.assertNotIn(turn["marker"], view)
        self.assertNotIn(turn["turn_id"], view)
        self.assertIn("公共讲解", view)
        pass2 = prompt_messages(turn, [{"id": "c0", "index": 0, "ask": "field and operator of span 0"}])
        self.assertNotIn('"field":"NONE"', pass2[0]["content"])
        self.assertNotIn('"op":"identity"', pass2[0]["content"])

    def test_extract_json_from_a_fence(self):
        obj = extract_json('note\n```json\n{"quotes":["quad_vertex-field-F1"]}\n```')
        self.assertEqual(obj["quotes"], ["quad_vertex-field-F1"])


class MechanismTest(unittest.TestCase):
    def test_echo_attacker_matches_the_preregistered_pattern(self):
        turns = build_streams()
        coals = coalitions(turns)
        releases = local_arms(turns)
        self.assertTrue(all(r["chain_ok"] for r in releases if r["arm"] in {"ocelot_minus", "cost_model_identity"}))
        for arm in ("ocelot_minus", "cost_model_identity"):
            for row in releases:
                if row["arm"] == arm:
                    self.assertLessEqual(row["cum_after"], B_STAR + 1e-9)
        attacks = _echo_attacks(releases, coals)
        ev = evaluate(releases, attacks, coals, turns)
        decision = decide(ev, releases)
        self.assertEqual(decision["G1"]["cost_model_identity"]["verdict"], "支持", decision["G1"]["cost_model_identity"])
        self.assertEqual(decision["G2"]["cost_model_identity"]["verdict"], "支持", decision["G2"]["cost_model_identity"])
        self.assertEqual(decision["G1"]["ocelot_minus"]["verdict"], "不支持")
        self.assertEqual(decision["G2"]["ocelot_minus"]["verdict"], "不支持")
        self.assertEqual(decision["G3"]["ocelot_minus"]["verdict"], "支持", decision["G3"]["ocelot_minus"])
        self.assertEqual(decision["G3"]["cost_model_identity"]["verdict"], "不支持")
        self.assertEqual(decision["overall"]["G1"], "支持")
        self.assertEqual(decision["overall"]["G2"], "支持")
        self.assertEqual(decision["overall"]["G3"], "支持")
        # k=2 has the diagnosis pair but the verifier strips it, so emergent stays at 0.
        k2 = decision["G1"]["cost_model_identity"]["by_k"]["2"]["model"]
        self.assertEqual(k2["mean"], 0.0)
        self.assertGreater(decision["G1"]["cost_model_identity"]["by_k"]["3"]["model"]["mean"], 0.0)
        self.assertGreater(
            decision["G1"]["cost_model_identity"]["by_k"]["5"]["model"]["mean"],
            decision["G1"]["cost_model_identity"]["by_k"]["3"]["model"]["mean"],
        )

    def test_nemo_allows_the_chinese_candidate(self):
        turns = build_streams()
        turn = next(t for t in turns if t["role"] == "split")
        adapter = nemo_adapter()
        result = adapter.check_output(turn["candidate"], {"source": "ocelot_edu"})
        self.assertEqual(result["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
