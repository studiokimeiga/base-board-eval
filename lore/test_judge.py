"""python -m unittest discover -s lore -p "test_*.py" """
import unittest

import judge as J


def thread(board, no, tid, posts, source=None, arm=None):
    return {"board": board, "no": no, "id": tid, "source": source, "arm": arm,
            "posts": [{"who": w, "text": t} for w, t in posts]}


RUN = {
    ("x", "s00", None): thread("/x/", 4471, "s00", [("ruth", "my mug is gone"), ("omar", "the void took it")]),
    ("x", "t00", "memory"): thread("/x/", 4494, "t00", [("yusuf", "my bike moved"), ("colm", "the void")], "s00", "memory"),
    ("x", "t00", "none"): thread("/x/", 4494, "t00", [("yusuf", "my bike moved"), ("colm", "a thief")], "s00", "none"),
    ("misc", "s00", None): thread("/misc/", 4471, "s00", [("ruth", "my mug is gone"), ("omar", "hr took it")]),
    ("misc", "t00", "memory"): thread("/misc/", 4494, "t00", [("yusuf", "my bike moved"), ("colm", "hr")], "s00", "memory"),
    ("misc", "t00", "none"): thread("/misc/", 4494, "t00", [("yusuf", "my bike moved"), ("colm", "rain")], "s00", "none"),
}


class Parse(unittest.TestCase):
    def test_reads_the_json_inside_prose_or_a_code_fence(self):
        reply = 'Here you go:\n```json\n{"borrowings": [], "borrows": false, "confidence": 4}\n```'
        self.assertEqual(J.parse(reply), {"borrows": False, "confidence": 4,
                                          "kinds": {"reference": 0, "mixup": 0, "reuse": 0, "coincidence": 0}})

    def test_counts_each_kind_and_drops_unknown_ones(self):
        reply = ('{"borrowings": [{"b": "x", "a": "y", "kind": "reuse"}, {"kind": "reuse"},'
                 ' {"kind": "mixup"}, {"kind": "vibes"}, "junk"], "borrows": true, "confidence": "5"}')
        self.assertEqual(J.parse(reply)["kinds"], {"reference": 0, "mixup": 1, "reuse": 2, "coincidence": 0})
        self.assertEqual(J.parse(reply)["confidence"], 5)
        self.assertTrue(J.parse(reply)["borrows"])

    def test_no_json_is_unparsed(self):
        self.assertIsNone(J.parse("I can't tell."))
        self.assertIsNone(J.parse('{"borrows": tru'))
        self.assertIsNone(J.parse(None))

    def test_a_bad_confidence_is_kept_as_unknown(self):
        self.assertIsNone(J.parse('{"borrowings": [], "borrows": false, "confidence": "high"}')["confidence"])


class Items(unittest.TestCase):
    def test_every_target_arm_is_an_item_with_its_source_as_thread_a(self):
        its = J.items(RUN)
        self.assertEqual(len(its), 4)
        for it in its:
            a, b = it["text"].split("=== Thread A (earlier) ===\n", 1)[1].split("\n\n=== Thread B (later) ===\n", 1)
            self.assertTrue(a.startswith("%s — thread 4471" % ("/x/" if it["board"] == "x" else "/misc/")))
            self.assertTrue(b.startswith("%s — thread 4494" % ("/x/" if it["board"] == "x" else "/misc/")))

    def test_nothing_in_an_item_tells_the_arm(self):
        its = J.items(RUN)
        for it in its:
            self.assertNotIn("memory", it["text"])
            self.assertNotIn(it["arm"], it["item"])
        mem = next(i for i in its if i["board"] == "x" and i["arm"] == "memory")["text"]
        none = next(i for i in its if i["board"] == "x" and i["arm"] == "none")["text"]
        self.assertEqual(mem.split("=== Thread B")[0], none.split("=== Thread B")[0])

    def test_item_ids_are_shuffled_but_fixed(self):
        a, b = J.items(RUN), J.items(RUN)
        self.assertEqual([(i["item"], i["arm"]) for i in a], [(i["item"], i["arm"]) for i in b])
        order = [(i["board"], i["target"], i["arm"]) for i in sorted(a, key=lambda i: i["item"])]
        self.assertNotEqual(order, sorted(order))

    def test_withheld_posts_are_not_shown(self):
        t = thread("/x/", 4494, "t00", [("yusuf", "my bike moved"), ("colm", "[post withheld]")])
        t["posts"][1]["withheld"] = True
        self.assertEqual(J.render(t), "/x/ — thread 4494\n\nyusuf\nmy bike moved")


class Splits(unittest.TestCase):
    IDS = ["i%03d" % i for i in range(184)]

    def test_batches_cover_every_item_once(self):
        bs = J.batches(self.IDS)
        self.assertEqual(len(bs), J.BATCHES)
        self.assertEqual(sorted(x for b in bs for x in b), self.IDS)

    def test_the_half_is_fixed_and_half(self):
        h = J.half(self.IDS)
        self.assertEqual(len(h), 92)
        self.assertEqual(h, J.half(list(reversed(self.IDS))))
        self.assertNotEqual(h, self.IDS[:92])


class HalfSeed(unittest.TestCase):
    """#4's half reused items()'s seed, which made it exactly the /misc/ board."""

    @staticmethod
    def two_boards():
        run = {}
        for b, board in (("x", "/x/"), ("misc", "/misc/")):
            run[(b, "s00", None)] = thread(board, 4471, "s00", [("ruth", "my mug is gone")])
            for k in range(23):
                for arm in ("memory", "none"):
                    run[(b, "t%02d" % k, arm)] = thread(board, 4494 + k, "t%02d" % k, [("yusuf", "hi")], "s00", arm)
        return run

    def test_the_old_seed_reproduces_the_half_of_4_which_is_one_board(self):
        its = J.items(self.two_boards())
        self.assertEqual(J.half([i["item"] for i in its]), sorted(i["item"] for i in its if i["board"] == "misc"))

    def test_a_half_seeded_apart_mixes_boards_and_arms(self):
        its = J.items(self.two_boards())
        h = set(J.half([i["item"] for i in its], seed=J.HALF_SEED))
        self.assertEqual(len(h), 46)
        self.assertEqual({(i["board"], i["arm"]) for i in its if i["item"] in h},
                         {("x", "memory"), ("x", "none"), ("misc", "memory"), ("misc", "none")})


if __name__ == "__main__":
    unittest.main()
