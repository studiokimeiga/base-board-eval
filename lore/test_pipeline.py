"""python -m unittest discover -s lore -p "test_*.py"

The whole pipeline on a fake model: board.run writes an /x/ board, judge.items builds blind packets
from it, analyze scores it. The fake plants an invented word from the source into half of the
memory-arm targets and nothing else, so the analysis must find the memory effect and keep the
no-memory arm clean. Nothing here touches the network.
"""
import hashlib, os, re, shutil, tempfile, unittest

import analyze as A
import board as B
import judge as J

# stop words only, so the planted coinage is the only thing in a post the tracker can count
WORDS = "ok sure maybe that what you mean lol yeah i guess same here to me once just them about it".split()


def fake(prompt, seed):
    rng = int(hashlib.sha256(str(seed).encode()).hexdigest(), 16)
    words = [WORDS[(rng >> (5 * i)) % len(WORDS)] for i in range(8)]
    heads = re.findall(r"— thread (\d+)", prompt)
    if len(heads) == 1 and int(heads[0]) < B.FIRST_TARGET:      # a source: give it a coinage
        words.append("zq%sblat" % heads[0])
    elif len(heads) == 2 and int(heads[1]) % 2 == 0:             # half the memory targets copy it
        words.append("zq%sblat" % heads[0])
    return {"text": " ".join(words), "cost": 0.0, "provider": "fake"}


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.root = os.path.join(cls.tmp, "run")
        B.run(B.schedule(), "x", fake, B.Budget(cap=1.0), cls.root, workers=4, log=lambda *_: None)
        cls.summary = A.main(["--run", cls.root, "--judging", os.path.join(cls.tmp, "none"),
                              "--out", cls.tmp])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_every_thread_is_written(self):
        run = J.load_run(self.root)
        self.assertEqual(sum(1 for k in run if k[2] is None), 23)
        self.assertEqual(sum(1 for k in run if k[2] == "memory"), 46)
        self.assertEqual(sum(1 for k in run if k[2] == "none"), 46)

    def test_the_planted_effect_is_found_and_the_control_stays_clean(self):
        h1 = self.summary["both boards"]
        planted = sum(1 for t in B.schedule()["targets"] if t["no"] % 2 == 0)
        self.assertEqual(h1["pairs"], 46)
        self.assertEqual(h1["memory_only"], planted)
        self.assertEqual(h1["none_only"], 0)
        self.assertLess(h1["p"], 0.001)
        self.assertGreater(h1["ci"][0], 0)

    def test_blind_items_cover_both_arms(self):
        its = J.items(J.load_run(self.root))
        self.assertEqual(len(its), 92)
        self.assertEqual({i["arm"] for i in its}, {"memory", "none"})

    def test_results_file_is_written(self):
        with open(os.path.join(self.tmp, "RESULTS.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("## H1: the memory effect (primary)", text)


if __name__ == "__main__":
    unittest.main()
