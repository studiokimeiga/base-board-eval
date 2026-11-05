"""python -m unittest discover -s lore -p "test_*.py"

Expected values are worked by hand (Wilson from its formula, exact tests from binomial counts)."""
import unittest

import analyze as A


class Stats(unittest.TestCase):
    def test_wilson(self):
        lo, hi = A.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.27754, places=4)
        lo, hi = A.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.23659, places=4)
        self.assertAlmostEqual(hi, 0.76341, places=4)
        self.assertEqual(A.wilson(0, 0), (0.0, 0.0))

    def test_exact_two_sided_sign_test(self):
        self.assertAlmostEqual(A.sign_test(8, 0), 2 / 256)
        self.assertAlmostEqual(A.sign_test(1, 7), 18 / 256)
        self.assertEqual(A.sign_test(4, 4), 1.0)
        self.assertEqual(A.sign_test(0, 0), 1.0)

    def test_mcnemar_uses_only_discordant_pairs(self):
        pairs = [(True, False)] * 6 + [(False, True)] + [(True, True)] * 3 + [(False, False)] * 5
        self.assertEqual(A.mcnemar(pairs), (6, 1, 16 / 128))

    def test_kappa(self):
        self.assertAlmostEqual(A.kappa([True, True, False, False], [True, False, False, False]), 0.5)
        self.assertAlmostEqual(A.kappa([True, False], [True, False]), 1.0)
        self.assertIsNone(A.kappa([True, True], [True, True]))

    def test_undefined_kappa_formats_as_a_dash(self):
        # a null run (nobody borrows, by tracker or judge) must still produce its report
        self.assertEqual(A.f_kappa(A.kappa([False] * 4, [False] * 4)), "–")
        self.assertEqual(A.f_kappa(0.5), "0.50")

    def test_cluster_bootstrap(self):
        always = [[(True, False), (True, False)]] * 5
        self.assertEqual(A.bootstrap_diff(always), (1.0, 1.0))
        mixed = [[(True, False)], [(False, False)], [(True, True)], [(False, True)]]
        lo, hi = A.bootstrap_diff(mixed)
        self.assertTrue(-1.0 <= lo < 0 < hi <= 1.0)
        self.assertEqual(A.bootstrap_diff(mixed), (lo, hi))


class Genre(unittest.TestCase):
    def test_whole_words_and_phrases_only(self):
        posts = [{"text": "the ghost took it"}, {"text": "a shadow person at the door"},
                 {"text": "shadows everywhere"}, {"text": "my ghostwriter quit"},
                 {"text": "honestly creepy af"}, {"text": "[post withheld]", "withheld": True}]
        self.assertAlmostEqual(A.genre_share(posts), 3 / 5)

    def test_no_posts(self):
        self.assertIsNone(A.genre_share([]))


if __name__ == "__main__":
    unittest.main()
