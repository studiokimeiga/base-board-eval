"""python -m unittest discover -s lore/reader -p "test_*.py"

Hand-built boards and ratings, so every expected value is worked out by hand."""
import unittest

import analyze as A
import build as Bd


def thread(board, no, tid, texts, source=None, arm=None, withheld=()):
    posts = [{"who": "h%d" % (i % 3), "text": t} for i, t in enumerate(texts)]
    for i in withheld:
        posts[i].update(text="[post withheld]", withheld=True)
    return {"board": board, "no": no, "id": tid, "source": source, "arm": arm, "posts": posts}


def run_of(boards):
    """boards: {board: [(source id, [target ids])]} -> a run dict as judge.load_run returns."""
    run, no = {}, 4471
    for b, sources in boards.items():
        name = {"x": "/x/", "misc": "/misc/"}[b]
        for sid, tids in sources:
            run[(b, sid, None)] = thread(name, no, sid, ["source opener %s" % sid, "a reply"])
            no += 1
            for tid in tids:
                for arm in ("memory", "none"):
                    reply = ("seen reply %s" if arm == "memory" else "blind reply %s") % tid
                    run[(b, tid, arm)] = thread(name, no, tid, ["target opener %s" % tid, reply], sid, arm)
                no += 1
    return run


class Screen(unittest.TestCase):
    def test_clean_thread_passes(self):
        self.assertIsNone(Bd.screen(thread("/x/", 1, "s", ["my mug is gone", "check the cupboard"])))

    def test_withheld_post_fails(self):
        self.assertEqual(Bd.screen(thread("/x/", 1, "s", ["a", "b"], withheld=[1])), "has withheld posts")

    def test_gate_substring_fails(self):
        self.assertEqual(Bd.screen(thread("/x/", 1, "s", ["a", "i will kill you"])), "gate term")

    def test_stricter_word_list_fails_as_a_word_only(self):
        self.assertEqual(Bd.screen(thread("/x/", 1, "s", ["a", "a naked mole rat"])), "excluded word 'naked'")
        self.assertIsNone(Bd.screen(thread("/x/", 1, "s", ["a", "dickens wrote it"])))

    def test_a_triple_needs_all_three_threads_clean(self):
        run = run_of({"misc": [("s00", ["t00", "t01"])]})
        run[("misc", "t01", "none")]["posts"][1].update(text="[post withheld]", withheld=True)
        self.assertEqual(Bd.eligible(run), {("misc", "t00"): "s00"})


class Select(unittest.TestCase):
    RUN = run_of({"misc": [("s%02d" % i, ["t%02d" % (2 * i), "t%02d" % (2 * i + 1)]) for i in range(8)],
                  "x": [("s%02d" % i, ["t%02d" % (2 * i), "t%02d" % (2 * i + 1)]) for i in range(8, 12)]})
    # identified: on /misc/ the even targets of s00-s03, on /x/ t16 and t18
    IDENT = {("misc", "t00"), ("misc", "t02"), ("misc", "t04"), ("misc", "t06"), ("x", "t16"), ("x", "t18")}
    QUOTAS = {("misc", True): 3, ("misc", False): 3, ("x", True): 1, ("x", False): 1}

    def chosen(self, seed=7):
        return Bd.select(Bd.eligible(self.RUN), self.IDENT, self.QUOTAS, seed)

    def test_quotas_are_met(self):
        got = {}
        for b, tid in self.chosen():
            k = (b, (b, tid) in self.IDENT)
            got[k] = got.get(k, 0) + 1
        self.assertEqual(got, self.QUOTAS)

    def test_at_most_one_target_per_source(self):
        el = Bd.eligible(self.RUN)
        srcs = [el[c] for c in self.chosen()]
        self.assertEqual(len(srcs), len(set(srcs)))

    def test_fixed_by_its_seed(self):
        self.assertEqual(self.chosen(7), self.chosen(7))
        self.assertTrue(any(self.chosen(7) != self.chosen(s) for s in (8, 9, 10)))

    def test_a_stratum_that_cannot_be_filled_is_an_error(self):
        with self.assertRaises(SystemExit):
            Bd.select(Bd.eligible(self.RUN), self.IDENT, {**self.QUOTAS, ("x", True): 3}, 7)


class Assign(unittest.TestCase):
    def test_memory_is_first_in_exactly_half_of_each_board(self):
        chosen = [("misc", "t%02d" % i) for i in range(6)] + [("x", "t10"), ("x", "t11")]
        side = Bd.assign(chosen, 3)
        self.assertEqual(sum(side[c] == "A" for c in chosen if c[0] == "misc"), 3)
        self.assertEqual(sum(side[c] == "A" for c in chosen if c[0] == "x"), 1)
        self.assertEqual(side, Bd.assign(chosen, 3))

    def test_which_triples_get_memory_first_is_shuffled(self):
        chosen = [("misc", "t%02d" % i) for i in range(6)]
        patterns = {tuple(Bd.assign(chosen, s)[c] for c in chosen) for s in range(1, 6)}
        self.assertGreater(len(patterns), 1)
        self.assertTrue(any(p != ("A", "A", "A", "B", "B", "B") for p in patterns))


class Items(unittest.TestCase):
    def test_items_hide_the_arm_and_the_key_maps_it_back(self):
        run = run_of({"misc": [("s00", ["t00"]), ("s01", ["t01"])], "x": [("s02", ["t02"])]})
        chosen = [("misc", "t00"), ("misc", "t01"), ("x", "t02")]
        side = {("misc", "t00"): "A", ("misc", "t01"): "B", ("x", "t02"): "A"}
        items, key = Bd.make(run, chosen, side, {("misc", "t00")}, seed=5)
        self.assertEqual(len(items), 3)
        text = repr(items)
        self.assertNotIn("memory", text)
        self.assertNotIn("none", text)
        for it in items:
            k = key[it["id"]]
            mem, other = (it["A"], it["B"]) if k["memory"] == "A" else (it["B"], it["A"])
            self.assertEqual(mem["posts"][1]["text"], "seen reply %s" % k["target"])
            self.assertEqual(other["posts"][1]["text"], "blind reply %s" % k["target"])
            self.assertEqual(it["source"]["posts"][0]["text"], "source opener %s" % k["source"])
            self.assertTrue(it["source"]["posts"][0]["op"])
        self.assertEqual({k["board"] for k in key.values()}, {"misc", "x"})
        self.assertEqual(key[next(i for i, k in key.items() if k["target"] == "t00")]["identified"], True)

    def test_triple_ids_do_not_follow_the_selection_order(self):
        run = run_of({"misc": [("s%02d" % i, ["t%02d" % i]) for i in range(8)]})
        chosen = [("misc", "t%02d" % i) for i in range(8)]
        items, key = Bd.make(run, chosen, {c: "A" for c in chosen}, set(), seed=5)
        order = [key[it["id"]]["target"] for it in sorted(items, key=lambda it: it["id"])]
        self.assertNotEqual(order, sorted(order))


# ---- analysis ----
KEY = {"r1": {"board": "misc", "target": "t00", "source": "s00", "memory": "A", "identified": True},
       "r2": {"board": "misc", "target": "t01", "source": "s01", "memory": "B", "identified": False},
       "r3": {"board": "x", "target": "t02", "source": "s02", "memory": "B", "identified": True}}


def side(over=3, pick=False, **kw):
    s = {"believable": 3, "interest": 3, "joke": 3, "deadpan": 3, "overall": over, "repost": False,
         "pickup": pick, "seen": False}
    s.update(kw)
    return s


RATINGS = {"r1": {"A": side(over=5, pick=True), "B": side(over=2), "prefer": "A"},
           "r2": {"A": side(over=4), "B": side(over=3, pick=True), "prefer": "A"},
           "r3": {"A": side(over=2), "B": side(over=4, pick=True), "prefer": "B"}}


class Analysis(unittest.TestCase):
    def test_sides_are_mapped_to_memory_and_none(self):
        rows = A.rows(KEY, RATINGS)
        r = {x["triple"]: x for x in rows}
        self.assertTrue(r["r1"]["prefers_memory"])
        self.assertFalse(r["r2"]["prefers_memory"])         # chose A, and memory was B
        self.assertTrue(r["r3"]["prefers_memory"])
        self.assertEqual(r["r1"]["memory"]["overall"], 5)
        self.assertEqual(r["r2"]["memory"]["overall"], 3)
        self.assertEqual(r["r2"]["none"]["overall"], 4)

    def test_incomplete_triples_are_left_out(self):
        partial = dict(RATINGS, r3={"A": side(), "B": {"overall": 3}, "prefer": "B"})
        self.assertEqual(sorted(x["triple"] for x in A.rows(KEY, partial)), ["r1", "r2"])

    def test_summary_counts(self):
        s = A.summarize(A.rows(KEY, RATINGS))
        self.assertEqual(s["prefer"]["misc"], (1, 2))
        self.assertEqual(s["prefer"]["x"], (1, 1))
        # R1b refines the /misc/ hypothesis, so /x/ (r3) stays out (review of PR #8)
        self.assertEqual(s["prefer_identified"], (1, 1))
        self.assertEqual(s["prefer_not_identified"], (0, 1))
        self.assertEqual(s["pickup"]["memory"], (3, 3))
        self.assertEqual(s["pickup"]["none"], (0, 3))
        self.assertEqual(s["diff"]["overall"], [3, -1, 2])

    def test_the_readers_pickup_is_compared_with_each_machine_call(self):
        rs = A.rows(KEY, RATINGS)
        # memory follow-ups: picked up in r1, r2, r3; no-memory: none picked up
        calls = {"tracker": {("misc", "t00", "memory"): True, ("misc", "t00", "none"): False,
                             ("misc", "t01", "memory"): False, ("misc", "t01", "none"): False,
                             ("x", "t02", "memory"): True, ("x", "t02", "none"): True},
                 "claude": {("misc", "t00", "memory"): True, ("misc", "t00", "none"): False}}
        ag = A.agreement(rs, calls)
        self.assertEqual(ag["tracker"]["n"], 6)
        self.assertEqual(ag["tracker"]["agree"], 4)          # r2 memory and r3 none disagree
        self.assertEqual(ag["claude"]["n"], 2)
        self.assertEqual(ag["claude"]["agree"], 2)

    def test_a_triple_seen_before_is_reported_both_ways(self):
        seen = dict(RATINGS, r1={"A": side(over=5, pick=True, seen=True), "B": side(over=2), "prefer": "A"})
        s = A.summarize(A.rows(KEY, seen), drop_seen=True)
        self.assertEqual(s["prefer"]["misc"], (0, 1))

    def test_r5_is_reported_with_and_without_seen_triples(self):
        # review of PR #8: R5 was emitted once, unfiltered, under the filtered section
        seen = dict(RATINGS, r1={"A": side(over=5, pick=True, seen=True), "B": side(over=2), "prefer": "A"})
        calls = {"tracker": {("misc", "t00", "memory"): True, ("misc", "t00", "none"): False,
                             ("misc", "t01", "memory"): False, ("misc", "t01", "none"): False,
                             ("x", "t02", "memory"): True, ("x", "t02", "none"): True}}
        text = A.report(KEY, {"me": seen}, calls)
        parts = text.split("## me: ")[1:]
        self.assertEqual(len(parts), 2)
        self.assertIn("| tracker | 6 | 4 |", parts[0])         # all three triples
        self.assertIn("| tracker | 4 | 2 |", parts[1])         # r1 dropped: r2 and r3 remain

    def test_the_latest_export_wins_whatever_the_filename(self):
        import json, os, shutil, tempfile
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "key.json"), "w", encoding="utf-8") as f:
                json.dump(KEY, f)
            os.mkdir(os.path.join(tmp, "ratings"))
            for name, when, ratings in (("ratings-me-2026-11-02 (1).json", "2026-11-02T18:00:00Z", RATINGS),
                                        ("ratings-me-2026-11-02.json", "2026-11-02T09:00:00Z",
                                         {"r1": RATINGS["r1"]})):
                with open(os.path.join(tmp, "ratings", name), "w", encoding="utf-8") as f:
                    json.dump({"rater": "me", "exported": when, "ratings": ratings}, f)
            _, raters = A.load(tmp)
            self.assertEqual(sorted(raters["me"]), ["r1", "r2", "r3"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
