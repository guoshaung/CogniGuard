"""Stage-1b checks that do not call a model."""

from __future__ import annotations

import hashlib
import subprocess
import unittest
from pathlib import Path

from experiments.ocelot_edu_20261122_real.ocelot_edu.assets import assert_no_secret, load_packages, secret_strings
from experiments.ocelot_edu_20261122_real.ocelot_edu.constants import B_STAR, MU_ADVERSARIAL, ROUND1_PROTOCOL_SHA256
from experiments.ocelot_edu_20261122_real.ocelot_edu.costmodel import (
    Meas,
    _pair_extrapolation,
    all_views,
    bits,
    covering_views,
    jeffreys,
    predicted_cost,
    single_base,
    trajectory_increment,
)
from experiments.ocelot_edu_20261122_real.ocelot_edu.defenders import static_labels
from experiments.ocelot_edu_20261122_real.ocelot_edu.prompts import FIGURE8, PASS2_TAIL
from experiments.ocelot_edu_20261122_real.ocelot_edu.score import (
    cluster_bootstrap,
    combine,
    g1_qualifies,
    gap_blocks,
    verdict_gt_zero,
)
from experiments.ocelot_edu_20261122_real.ocelot_edu.stimuli import ASSIGN, iter_turns
from experiments.ocelot_edu_20261122_real.ocelot_edu.textutil import contains_text
from experiments.ocelot_edu_20261122_real.ocelot_edu.verifier import Atom, Ledger, apply_op, authorize, verify_entry

ROOT = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parents[1]


class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packages = load_packages()

    def test_pack_shape(self):
        self.assertEqual([pkg.package_id for pkg in self.packages], [f"PKG-0{i}" for i in range(1, 6)])
        self.assertEqual(sum(len(pkg.units) for pkg in self.packages), 45)
        layers = sorted({target.layer for pkg in self.packages for target in pkg.targets})
        self.assertEqual(layers, ["表达", "诊断映射", "顺序"])
        self.assertEqual(sum(len(pkg.targets) for pkg in self.packages), 15)

    def test_views_cover_private_units_only(self):
        package = self.packages[0]
        views = all_views(package.leakage_unit_ids)
        self.assertEqual(len(views), 57)
        self.assertNotIn("U2", {unit for view in views for unit in view})
        covered = sum(len(covering_views(package.leakage_unit_ids, target.unit_ids)) for target in package.targets)
        self.assertEqual(covered, 24)

    def test_assignment_ignores_cost(self):
        self.assertEqual(ASSIGN[5], "U7")
        turns = [turn for turn in iter_turns(self.packages[0]) if turn["student"] == 0 and turn["role"] == "private"]
        self.assertEqual([atom["unit_id"] for atom in turns[0]["atoms"]], ["U2", "U4"])

    def test_static_rule_redacts_layers_and_misses_anchor(self):
        turn = next(turn for turn in iter_turns(self.packages[0]) if turn["student"] == 5 and turn["role"] == "private")
        labels = static_labels(turn)
        by_id = {atom["unit_id"]: label for atom, label in zip(turn["atoms"], labels)}
        self.assertEqual(by_id["U2"]["op"], "identity")
        self.assertEqual(by_id["U7"]["field"], "NONE")
        seq = next(turn for turn in iter_turns(self.packages[0]) if turn["student"] == 0 and turn["role"] == "private")
        seq_labels = static_labels(seq)
        self.assertEqual(seq_labels[1]["op"], "redact")
        self.assertEqual(seq_labels[1]["field"], "U4")

    def test_repository_has_no_asset_prose(self):
        secrets = secret_strings(self.packages)
        for path in EXP.rglob("*"):
            if not path.is_file():
                continue
            if "artifacts" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix not in {".py", ".md", ".json", ".gitignore"}:
                continue
            blob = path.read_text(encoding="utf-8")
            assert_no_secret(blob, secrets)

    def test_round1_protocol_untouched(self):
        target = ROOT / "experiments" / "ocelot_edu_20261121" / "EXPERIMENT_PROTOCOL.md"
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        self.assertEqual(digest, ROUND1_PROTOCOL_SHA256)


class CostTests(unittest.TestCase):
    def test_jeffreys_and_bits(self):
        self.assertAlmostEqual(jeffreys(0, 8), 0.5 / 9)
        self.assertAlmostEqual(bits(1.0, 0.5), 1.0)
        self.assertEqual(bits(0.25, 0.5), 0.0)

    def test_pair_formula_ignores_triple_hits(self):
        target = ("a", "b", "c")
        base = {}
        for view in [(), ("a",), ("b",), ("c",), ("a", "b"), ("a", "c"), ("b", "c")]:
            base[("P", _key(view), "T")] = 0
        low = Meas(8, dict(base))
        high = Meas(8, {**base, ("P", "a,b,c", "T"): 8})
        self.assertAlmostEqual(
            predicted_cost(low, "P", target, "T", target),
            predicted_cost(high, "P", target, "T", target),
        )
        self.assertAlmostEqual(predicted_cost(low, "P", target, "T", target), 0.0)
        measured = bits(jeffreys(8, 8), jeffreys(0, 8))
        self.assertGreater(measured - predicted_cost(high, "P", target, "T", target), 0.18)

    def test_declared_pair_is_priced_when_the_pair_is_recovered(self):
        hits = {}
        for view, count in {
            (): 0,
            ("a",): 0,
            ("b",): 0,
            ("x",): 0,
            ("a", "b"): 8,
            ("a", "x"): 0,
            ("b", "x"): 0,
        }.items():
            hits[("P", _key(view), "T")] = count
        meas = Meas(8, hits)
        full = bits(jeffreys(8, 8), jeffreys(0, 8))
        pred = _pair_extrapolation(meas, "P", ("a", "b", "x"), "T", ("a", "b"), jeffreys(0, 8))
        self.assertAlmostEqual(pred, full, places=6)

    def test_anchor_unit_has_no_declared_cost(self):
        packages = load_packages()
        package = packages[0]
        hits = {}
        for target in package.targets:
            hits[(package.package_id, "", target.target_id)] = 0
            hits[(package.package_id, "U7", target.target_id)] = 8
        cost = single_base(Meas(8, hits), package.package_id, "U7", package.targets)
        self.assertEqual(cost, 0.0)

    def test_second_fragment_pays_the_measured_pair_increment(self):
        hits = {}
        for view, count in {(): 0, ("a",): 0, ("b",): 0, ("a", "b"): 8}.items():
            hits[("P", _key(view), "T")] = count
        meas = Meas(8, hits)

        class Target:
            target_id = "T"
            unit_ids = ("a", "b")

        first = trajectory_increment(meas, "P", "b", set(), [Target()])
        second = trajectory_increment(meas, "P", "b", {"a"}, [Target()])
        self.assertAlmostEqual(first, 0.0)
        self.assertGreater(second, 1.0)


class RuleTests(unittest.TestCase):
    def test_g1_window(self):
        self.assertTrue(g1_qualifies([3.0, 3.0]))
        self.assertFalse(g1_qualifies([1.0, 1.0]))
        self.assertFalse(g1_qualifies([0.0, 3.0]))
        self.assertFalse(g1_qualifies([5.0, 1.0]))

    def test_empty_is_undecided_and_zero_is_not_supported(self):
        self.assertEqual(verdict_gt_zero({"mean": None, "low": None, "high": None}), "无法判定")
        zero = cluster_bootstrap([[0.0], [0.0], [0.0], [0.0], [0.0]])
        self.assertEqual(verdict_gt_zero(zero), "不支持")
        ones = cluster_bootstrap([[1.0], [1.0], [1.0], [1.0], [1.0]])
        self.assertEqual(verdict_gt_zero(ones), "支持")
        self.assertEqual(combine(["不支持", "无法判定"]), "无法判定")
        self.assertEqual(combine(["不支持", "支持"]), "支持")
        self.assertTrue(gap_blocks(1.0, 0.8))
        self.assertFalse(gap_blocks(1.0, 0.9))

    def test_verifier_escalates_instead_of_crossing_the_budget(self):
        ledger = Ledger("t", budget=B_STAR, mu=MU_ADVERSARIAL)
        atoms = [Atom("U4", "secret-text", "U4", "identity", False, True)]
        out = authorize(atoms, ledger, "turn", lambda field, already: 3.0)
        self.assertLessEqual(out["cum_after"], B_STAR)
        self.assertNotIn("secret-text", out["released"])
        self.assertTrue(verify_entry(ledger.entries[0], out["public_key"], "GENESIS"))
        ledger.entries[0]["cost"] = 99
        self.assertFalse(verify_entry(ledger.entries[0], out["public_key"], "GENESIS"))

    def test_small_identity_cost_stays_and_utility_text_is_restored(self):
        ledger = Ledger("t2")
        atoms = [
            Atom("U2", "public-scaffold", "NONE", "identity", True, False),
            Atom("U4", "secret-text", "U4", "identity", False, True),
        ]
        out = authorize(atoms, ledger, "turn", lambda field, already: 0.25 if field == "U4" else 0.0)
        self.assertLessEqual(out["cum_after"], B_STAR)
        self.assertIn("secret-text", out["released"])
        self.assertIn("public-scaffold", out["released"])
        self.assertTrue(contains_text(out["released"], "public-scaffold"))

    def test_prompts_do_not_plant_the_pass2_answer(self):
        self.assertIn("more restrictive operator", FIGURE8)
        self.assertNotIn('"field": "NONE"', PASS2_TAIL)
        self.assertNotIn("identity", PASS2_TAIL)
        self.assertEqual(apply_op("abc", "drop"), "")


class RepoTests(unittest.TestCase):
    def test_readme_sentence_and_gitignore(self):
        readme = (EXP / "README.md").read_text(encoding="utf-8")
        self.assertIn("上一轮使用了自建的合成单元，G1、G2 是按构造成立的，不用于判定。", readme)
        proc = subprocess.run(
            ["git", "check-ignore", "-q", "experiments/ocelot_edu_20261122_real/artifacts/cache/x.json"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)


def _key(view) -> str:
    return ",".join(view)


if __name__ == "__main__":
    unittest.main()
