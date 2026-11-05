"""python -m unittest discover -s spike/judging -p "test_*.py" """
import unittest

import ledger as L


class Stats(unittest.TestCase):
    def test_sign_test(self):
        self.assertAlmostEqual(L.sign_test(8, 0), 2 / 256)
        self.assertAlmostEqual(L.sign_test(7, 1), 18 / 256)
        self.assertAlmostEqual(L.sign_test(1, 7), 18 / 256)
        self.assertEqual(L.sign_test(4, 4), 1.0)
        self.assertEqual(L.sign_test(0, 0), 1.0)

    def test_ranks_average_ties(self):
        self.assertEqual(L.ranks([3, 1, 2, 2]), [4.0, 1.0, 2.5, 2.5])

    def test_spearman(self):
        self.assertAlmostEqual(L.spearman([1, 2, 3], [10, 20, 30]), 1.0)
        self.assertAlmostEqual(L.spearman([1, 2, 3], [3, 2, 1]), -1.0)
        self.assertAlmostEqual(L.spearman([1, 2, 2, 3], [1, 2, 3, 4]), 4.5 / (4.5 * 5) ** 0.5)
        self.assertIsNone(L.spearman([2, 2, 2], [1, 2, 3]))


class Data(unittest.TestCase):
    def test_every_round_loads_and_letters_match_keys(self):
        for rnd, folder, judges, *_ in L.ROUNDS:
            key, cells = L.load_round(folder, judges)
            for judge, c in cells.items():
                self.assertTrue(c, "%s/%s has no scores" % (rnd, judge))
                for (packet, arm), v in c.items():
                    self.assertIn(arm, key[packet].values())
                    self.assertTrue(1 <= v["overall"] <= 5)

    def test_contrast_arms_exist(self):
        for rnd, folder, judges, title, contrasts in L.ROUNDS:
            key, _ = L.load_round(folder, judges)
            arms = {a for letters in key.values() for a in letters.values()}
            for arm, base in contrasts:
                self.assertIn(arm, arms, rnd)
                self.assertIn(base, arms, rnd)

    def test_ledger_is_current(self):
        with open(L.LEDGER, encoding="utf-8") as f:
            self.assertEqual(f.read(), L.build(), "run python spike/judging/ledger.py")

    def test_round8_headline(self):
        # the result the session ended on, before it could be written up
        key, cells = L.load_round("r8", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"})
        def m(judge, arm, dim):
            return L.mean([v[dim] for (p, a), v in cells[judge].items() if a == arm])
        self.assertAlmostEqual(m("claude", "roles", "humour"), 3.875)
        self.assertAlmostEqual(m("claude", "gemini", "humour"), 2.0)
        self.assertAlmostEqual(m("gpt", "gemini", "overall"), 4.375)
        self.assertAlmostEqual(m("gpt", "rolesshort", "overall"), 3.0)

    def test_raw_stats_cover_every_judged_arm(self):
        raw = L.read_json(L.RAW_STATS)
        for rnd, folder, judges, *_ in L.ROUNDS:
            key, _ = L.load_round(folder, judges)
            for name, letters in key.items():
                for arm in letters.values():
                    f = ("jp-%s-%s.json" % (arm, name.split("-")[0]) if folder.startswith("jp")
                         else "bakeoff-%s.json" % arm)
                    self.assertIn(f, raw["files"], rnd)
            self.assertEqual(raw["packets_vs_raw"][rnd]["differ"], [], rnd)


if __name__ == "__main__":
    unittest.main()
