"""python -m unittest discover -s calibration"""
import json, os, shutil, tempfile, unittest

import analyze as A
import judge as J

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HAVE_ITEMS = os.path.exists(os.path.join(HERE, "items.json"))
DATA = os.environ.get("CALIBRATION_DATA", ROOT)
HAVE_DATA = os.path.exists(os.path.join(DATA, "threads.final.json")) and os.path.isdir(
    os.path.join(DATA, "spike", "remote"))


def key():
    return A.read_json(os.path.join(HERE, "key.json"))


class Key(unittest.TestCase):
    def test_six_items_per_source(self):
        counts = {}
        for v in key().values():
            counts[v["source"]] = counts.get(v["source"], 0) + 1
        self.assertEqual(counts, {s: 6 for s in A.SOURCES})

    def test_phonebook_is_in_the_set(self):
        self.assertTrue(any((v["file"], v["thread"]) == A.PHONEBOOK for v in key().values()))

    @unittest.skipUnless(HAVE_ITEMS, "items.json is private; build it first")
    def test_items_match_key_hashes(self):
        import build as B
        items = A.read_json(os.path.join(HERE, "items.json"))["items"]
        k = key()
        self.assertEqual(sorted(i["id"] for i in items), sorted(k))
        for it in items:
            self.assertEqual(B.digest(it["posts"]), k[it["id"]]["sha256"], it["id"])

    @unittest.skipUnless(HAVE_DATA, "needs the private corpora and spike/remote (CALIBRATION_DATA)")
    def test_build_is_deterministic_and_matches_key(self):
        import build as B
        items1, key1, _ = B.build(DATA)
        items2, key2, _ = B.build(DATA)
        self.assertEqual(items1, items2)
        self.assertEqual(key1, key())


class Prompts(unittest.TestCase):
    item = {"id": "c99", "posts": [{"n": 1, "who": "fatima", "op": True, "text": "hello"},
                                   {"n": 2, "who": "lucia", "op": False, "text": "> quote\nreply"}]}

    def test_every_scale_reaches_both_judges_and_the_page(self):
        rubric = A.read_json(os.path.join(HERE, "rubric.json"))
        prompt = J.gpt_prompt(self.item)
        for s in rubric["scales"]:
            self.assertIn("- %s: %s" % (s["id"], s["ask"]), prompt)
            self.assertIn('"%s":n' % s["id"], J.SHAPE)
        self.assertIn("1. fatima (OP): hello", prompt)
        with open(os.path.join(HERE, "rate.html"), encoding="utf-8") as f:
            self.assertIn('fetch("rubric.json")', f.read())

    @unittest.skipUnless(HAVE_ITEMS, "items.json is private; build it first")
    def test_claude_batches_cover_every_item_once_per_pass(self):
        for p in ("A", "B"):
            ids = [i for b in J.batches(p) for i in b]
            self.assertEqual(sorted(ids), sorted(key()))
        self.assertNotEqual(J.batches("A"), J.batches("B"))


class Analysis(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(os.path.join(HERE, "key.json"), self.dir)
        self.k = key()
        ids = sorted(self.k)
        # a judge that likes hosted threads, a second pass that agrees, and a reader who is the reverse
        def score(i, flip):
            hosted = self.k[i]["source"] in A.HOSTED
            v = 4 if hosted != flip else 2
            return {s: v for s in A.SCALES} | {"repost": False}
        self.write("scores-claude-A1.json", {i: score(i, False) for i in ids})
        self.write("scores-claude-B1.json", {i: score(i, False) for i in ids})
        os.mkdir(os.path.join(self.dir, "ratings"))
        ratings = {i: score(i, True) | {"seen": self.k[i]["source"] == "bestof"} for i in ids}
        self.write(os.path.join("ratings", "r.json"), {"rater": "test", "ratings": ratings})

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, name, obj):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def test_load_merges_passes_and_reads_the_reader(self):
        key, raters, seen = A.load(self.dir)
        self.assertEqual(set(raters), {"claude-A", "claude-B", "claude", "reader:test"})
        self.assertEqual(len(seen["reader:test"]), 6)
        self.assertEqual(len(raters["claude"]), 30)

    def test_gap_and_agreement(self):
        key, raters, _ = A.load(self.dir)
        ids = list(key)
        self.assertAlmostEqual(A.gap(A.pairs(key, raters["reader:test"], ids), "deadpan"), 2.0)
        self.assertAlmostEqual(A.gap(A.pairs(key, raters["claude"], ids), "deadpan"), -2.0)
        self.assertAlmostEqual(A.rho(raters["claude-A"], raters["claude-B"], "overall", ids)[0], 1.0)
        self.assertAlmostEqual(A.rho(raters["reader:test"], raters["claude"], "overall", ids)[0], -1.0)

    def test_report_reaches_verdicts(self):
        text = A.build(self.dir)
        self.assertIn("**not usable**", text)
        self.assertIn("**supported**", text)
        self.assertNotIn("has not rated", text)

    def test_partial_passes_do_not_make_an_empty_average(self):
        ids = sorted(self.k)
        os.remove(os.path.join(self.dir, "ratings", "r.json"))
        self.write("scores-claude-A1.json", {i: A.read_json(os.path.join(self.dir, "scores-claude-A1.json"))[i]
                                             for i in ids[:10]})
        self.write("scores-claude-B1.json", {i: A.read_json(os.path.join(self.dir, "scores-claude-B1.json"))[i]
                                             for i in ids[20:]})
        key, raters, _ = A.load(self.dir)
        self.assertNotIn("claude", raters)
        self.assertIn("not every source rated yet", A.build(self.dir))

    def test_rank_of_shares_ties(self):
        scores = {"a": {"overall": 5}, "b": {"overall": 3}, "c": {"overall": 3}}
        self.assertEqual(A.rank_of(scores, "a"), 1)
        self.assertEqual(A.rank_of(scores, "b"), 2.5)


class Results(unittest.TestCase):
    def test_results_are_current(self):
        with open(A.RESULTS, encoding="utf-8") as f:
            self.assertEqual(f.read(), A.build(), "run python calibration/analyze.py")


if __name__ == "__main__":
    unittest.main()
