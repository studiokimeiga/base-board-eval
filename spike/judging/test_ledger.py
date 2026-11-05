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


    def test_means_do_not_depend_on_the_python_version(self):
        # builtin sum() gives 0.9999999999999999 here before Python 3.12 and 1.0 from 3.12 on
        self.assertEqual(L.mean([0.1] * 10), 0.1)
        self.assertEqual("%.2f" % L.mean([3.8, 4.2, 3.6, 4.0, 4.0, 3.8, 3.8, 4.2]), "3.92")

    def test_kappa(self):
        self.assertAlmostEqual(L.kappa([1, 1, 0, 0], [1, 1, 0, 0]), 1.0)
        self.assertAlmostEqual(L.kappa([1, 0, 1, 0], [1, 1, 0, 0]), 0.0)
        self.assertIsNone(L.kappa([1, 1], [1, 1]))


class Round9Analysis(unittest.TestCase):
    """The round 9 analysis on made-up scores, so it is fixed before any real ones exist."""
    ARMS = ["a", "b", "c", "d", "e"]

    def key(self):
        key = {}
        for p in (1, 2):
            for v in range(5):
                order = self.ARMS[v:] + self.ARMS[:v]
                key["%d-v%d" % (p, v + 1)] = dict(zip("ABCDE", order))
        return key

    def test_collapse_averages_the_readings_and_keeps_every_note(self):
        cells = {"claude": {("1-v1", "a"): {"overall": 2, "humour": 1, "main_failure": "x"},
                            ("1-v2", "a"): {"overall": 4, "humour": 2, "main_failure": "y"}}}
        c = L.collapse(cells)["claude"][("1", "a")]
        self.assertEqual((c["overall"], c["humour"], c["reads"]), (3, 1.5, 2))
        self.assertEqual(c["main_failure"], ["x", "y"])

    def test_position_is_measured_within_thread(self):
        key = self.key()
        # every arm's thread scores 3, plus 1 whenever it is read first
        cells = {"gpt": {(pk, arm): {"overall": 3 + (L == "A")}
                         for pk, letters in key.items() for L, arm in letters.items()}}
        pos, spread = L.latin_rows(cells, key)
        self.assertEqual(pos, ["| gpt | +0.80 | -0.20 | -0.20 | -0.20 | -0.20 |"])
        self.assertEqual(spread, ["gpt 0.32"])

    def test_versioned_keys_and_openers(self):
        self.assertTrue(L.versioned({"3-v1": {}}))
        self.assertFalse(L.versioned({"3": {}, "5ch-opener-3": {}}))
        self.assertEqual(L.opener("3-v2"), "3")
        self.assertEqual(L.opener("5ch-opener-3"), "5ch-opener-3")

    def test_note_patterns_on_round_8(self):
        # the reference values quoted in PREREGISTRATION-ROUND9.md
        key, cells = L.load_round("r8", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"})
        def count(judge, arm):
            vs = [v for (p, a), v in cells[judge].items() if a == arm]
            return [sum(bool(L.HORROR_NOTE.search(v["main_failure"])) for v in vs),
                    sum(bool(L.HORROR_NOTE.search(v["main_failure"]) and L.SAME_NOTE.search(v["main_failure"]))
                        for v in vs)]
        self.assertEqual(count("claude", "gemini"), [6, 3])
        self.assertEqual(count("gpt", "gemini"), [5, 2])
        self.assertEqual(count("claude", "rolesshort"), [0, 0])
        self.assertEqual(count("gpt", "rolesshort"), [1, 0])

    def test_nonsense_notes_on_round_7(self):
        # round 7's naifs, the reference for round 9's hybrid (PREREGISTRATION-ROUND9.md)
        key, cells = L.load_round("r7", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"})
        def count(judge, arm):
            return sum(bool(L.NONSENSE_NOTE.search(v["main_failure"]))
                       for (p, a), v in cells[judge].items() if a == arm)
        self.assertEqual([count("claude", a) for a in ("gemini", "roles", "naif", "naifroles")], [0, 0, 2, 2])
        self.assertEqual([count("gpt", a) for a in ("gemini", "roles", "naif", "naifroles")], [1, 0, 3, 1])


class Data(unittest.TestCase):
    def test_every_round_loads_and_letters_match_keys(self):
        for rnd, folder, judges, *_ in L.ROUNDS:
            if not L.ran(folder):
                continue
            key, cells = L.load_round(folder, judges)
            for judge, c in cells.items():
                self.assertTrue(c, "%s/%s has no scores" % (rnd, judge))
                for (packet, arm), v in c.items():
                    self.assertIn(arm, key[packet].values())
                    self.assertTrue(1 <= v["overall"] <= 5)

    def test_contrast_arms_exist(self):
        for rnd, folder, judges, title, contrasts in L.ROUNDS:
            if not L.ran(folder):          # pre-registered: its arms must at least have names
                arms = set(L.NAMES)
            else:
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
            if not L.ran(folder):
                continue
            key, _ = L.load_round(folder, judges)
            for name, letters in key.items():
                for arm in letters.values():
                    f = ("jp-%s-%s.json" % (arm, name.split("-")[0]) if folder.startswith("jp")
                         else "bakeoff-%s.json" % arm)
                    self.assertIn(f, raw["files"], rnd)
            self.assertEqual(raw["packets_vs_raw"][rnd]["differ"], [], rnd)


if __name__ == "__main__":
    unittest.main()
