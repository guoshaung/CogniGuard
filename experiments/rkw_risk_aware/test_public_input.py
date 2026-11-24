"""Regression checks for the scope, provenance and public-input-only decoder."""
import hashlib
import json
import unittest

from pilot import HERE, catalog, codebook, config, decode, ids, r0, render
from score import assess_rows


class PublicInputTests(unittest.TestCase):
    def setUp(self):
        self.families = catalog()
        self.settings = config()
        self.book = codebook(self.families, self.settings["seed"])

    def test_frozen_artifact_bytes(self):
        locked = json.loads((HERE / "FROZEN_SHA256.json").read_bytes())
        for filename, expected in locked.items():
            with self.subTest(filename=filename):
                self.assertEqual(hashlib.sha256((HERE / filename).read_bytes()).hexdigest(), expected)

    def test_registration(self):
        result = r0(self.families, self.book, self.settings)
        self.assertEqual(result["collisions"], 0)
        self.assertEqual(result["embedded_sources"], 12)

    def test_prediction_independent_of_scoring_references(self):
        family, other = self.families[:2]
        correct, wrong = ids(family)[0], ids(other)[1]
        text = render(family, self.book[correct], "rkw")
        base = dict(case="fixture", op="fixture", method="rkw", output=text, input=text)
        first, second = assess_rows([dict(base, source=[correct]), dict(base, source=[wrong])],
                                    self.families, self.book)
        blind = decode(text, self.families, self.book, "rkw")
        self.assertEqual(first["predicted"], second["predicted"])
        self.assertEqual(blind["sources"], [correct])
        self.assertTrue(first["exact"])
        self.assertFalse(second["exact"])

    def test_empty_and_plain(self):
        for family in self.families:
            for text in ("", render(family)):
                self.assertEqual(decode(text, self.families, self.book, "rkw")["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
