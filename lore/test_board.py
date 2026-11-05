"""python -m unittest discover -s lore -p "test_*.py"

The schedule, the pages and one thread's generation loop, with the model call replaced by a fake:
the network is the only thing not exercised here.
"""
import unittest

import board as B

S = B.schedule()
SOURCES = {s["id"]: s for s in S["sources"]}


def gaps(spec):
    return [b - a for a, b in zip(spec["times"], spec["times"][1:])]


class Pairing(unittest.TestCase):
    def test_every_source_has_two_targets_with_no_topic_in_common(self):
        by_source = {}
        for t in S["targets"]:
            by_source.setdefault(t["source"], []).append(t)
        self.assertEqual(len(by_source), 23)
        for sid, ts in by_source.items():
            s = SOURCES[sid]
            self.assertEqual(len(ts), 2)
            self.assertNotEqual(ts[0]["opener"], ts[1]["opener"])
            for t in ts:
                self.assertFalse(set(B.TAGS[t["opener"]]) & set(B.TAGS[s["opener"]]),
                                 (s["opener"], t["opener"]))

    def test_every_opener_is_one_source_and_two_targets(self):
        self.assertEqual(sorted(s["opener"] for s in S["sources"]), list(range(23)))
        counts = {}
        for t in S["targets"]:
            counts[t["opener"]] = counts.get(t["opener"], 0) + 1
        self.assertEqual(counts, {i: 2 for i in range(23)})

    def test_every_opener_has_tags(self):
        self.assertEqual(sorted(B.TAGS), list(range(23)))

    def test_the_schedule_is_fixed_by_its_seed(self):
        self.assertEqual(B.schedule(), S)
        self.assertNotEqual(B.schedule(seed=1)["targets"], S["targets"])

    def test_thread_numbers(self):
        self.assertEqual(sorted(s["no"] for s in S["sources"]), list(range(4471, 4494)))
        self.assertEqual(sorted(t["no"] for t in S["targets"]), list(range(4494, 4540)))

    def test_a_target_never_shares_a_handle_with_its_source(self):
        for t in S["targets"]:
            self.assertEqual(len(set(t["cast"])), 7)
            self.assertFalse(set(t["cast"]) & set(SOURCES[t["source"]]["cast"]))


class Timing(unittest.TestCase):
    def test_patterns_are_balanced(self):
        def count(specs):
            c = {}
            for x in specs:
                c[x["pattern"]] = c.get(x["pattern"], 0) + 1
            return c
        self.assertEqual(count(S["sources"]), {"away": 8, "burst": 8, "gone": 7})
        self.assertEqual(count(S["targets"]), {"away": 16, "burst": 15, "gone": 15})

    def test_every_thread_has_24_posts_and_starts_with_its_op(self):
        for x in S["sources"] + S["targets"]:
            self.assertEqual(len(x["authors"]), 24)
            self.assertEqual(len(x["times"]), 24)
            self.assertEqual(x["authors"][0], x["cast"][0])
            self.assertTrue(all(a != b or x["pattern"] == "burst" and a == x["cast"][0]
                                for a, b in zip(x["authors"], x["authors"][1:])))

    def test_an_op_who_is_gone_never_posts_again(self):
        for x in S["sources"] + S["targets"]:
            if x["pattern"] == "gone":
                self.assertNotIn(x["cast"][0], x["authors"][1:])

    def test_a_bursty_op_posts_only_in_two_bursts_seconds_apart(self):
        for x in S["sources"] + S["targets"]:
            if x["pattern"] != "burst":
                continue
            op_posts = [n for n, a in enumerate(x["authors"], 1) if a == x["cast"][0] and n > 1]
            runs = []
            for n in op_posts:
                if runs and n == runs[-1][-1] + 1:
                    runs[-1].append(n)
                else:
                    runs.append([n])
            self.assertEqual(len(runs), 2, op_posts)
            self.assertTrue(3 <= runs[0][0] <= 6 and 11 <= runs[1][0] <= 16, runs)
            for run in runs:
                self.assertIn(len(run), (2, 3))
                for n in run[1:]:
                    self.assertTrue(5 <= x["times"][n - 1] - x["times"][n - 2] <= 40)

    def test_an_away_op_comes_back_after_hours_twice(self):
        for x in S["sources"] + S["targets"]:
            if x["pattern"] != "away":
                continue
            big = [n for n, g in enumerate(gaps(x), 2) if g >= 2 * 3600]
            self.assertEqual(len(big), 2)
            self.assertTrue(6 <= big[0] <= 9 and 16 <= big[1] <= 20, big)
            for n in big:
                self.assertEqual(x["authors"][n - 1], x["cast"][0])
                self.assertLessEqual(x["times"][n - 1] - x["times"][n - 2], 6 * 3600)

    def test_other_gaps_are_ordinary(self):
        for x in S["sources"] + S["targets"]:
            for g in gaps(x):
                self.assertTrue(5 <= g <= 540 or 2 * 3600 <= g <= 6 * 3600, g)

    def test_a_latecomer_arrives_at_the_first_free_post_from_13(self):
        # the last handle of the cast is held back, so someone new is always there to arrive
        for x in S["sources"] + S["targets"]:
            late = x["cast"][-1]
            n = next(n for n in range(13, 25) if x["authors"][n - 1] != x["cast"][0])
            self.assertEqual(x["authors"].index(late) + 1, n)

    def test_targets_start_after_their_sources_end(self):
        for t in S["targets"]:
            s = SOURCES[t["source"]]
            self.assertGreater(t["start"], s["start"] + s["times"][-1])


SRC = {"id": "s00", "no": 4480, "cast": ["ruth", "omar"], "posts": [
    {"who": "ruth", "ts": "10/26/26(Mon)09:00:00", "text": "my mug is gone"},
    {"who": "omar", "ts": "10/26/26(Mon)09:01:00", "text": "[post withheld]", "withheld": True},
    {"who": "omar", "ts": "10/26/26(Mon)09:02:00", "text": "the mug is in the void"}]}
TGT_POSTS = [{"who": "yusuf", "ts": "10/29/26(Thu)09:00:00", "text": "my bike moved"}]


class Pages(unittest.TestCase):
    def test_memory_page_is_the_whole_source_then_the_target(self):
        page = B.page("/x/", 4512, TGT_POSTS, SRC)
        self.assertEqual(page, "/x/ — thread 4480\n\n"
                               "ruth 10/26/26(Mon)09:00:00\nmy mug is gone\n\n"
                               "omar 10/26/26(Mon)09:02:00\nthe mug is in the void\n\n"
                               "/x/ — thread 4512\n\n"
                               "yusuf 10/29/26(Thu)09:00:00\nmy bike moved")

    def test_no_memory_page_is_only_the_target(self):
        self.assertEqual(B.page("/misc/", 4512, TGT_POSTS, None),
                         "/misc/ — thread 4512\n\nyusuf 10/29/26(Thu)09:00:00\nmy bike moved")

    def test_the_instruction_differs_between_arms_only_in_the_page(self):
        a = B.ask(B.page("/x/", 4512, TGT_POSTS, SRC), "colm")
        b = B.ask(B.page("/x/", 4512, TGT_POSTS, None), "colm")
        tail = ("\n\nWrite the next post in the last thread on the page, by colm. "
                "Reply with only the text of the post.")
        self.assertTrue(a.startswith("Here is a page from an imageboard:\n\n/x/ — thread 4480"))
        self.assertTrue(b.startswith("Here is a page from an imageboard:\n\n/x/ — thread 4512"))
        self.assertTrue(a.endswith(tail) and b.endswith(tail))


class Seeds(unittest.TestCase):
    def test_every_seed_fits_a_signed_32_bit_int(self):
        # Gemini rejects generation_config.seed outside TYPE_INT32 with HTTP 400
        seeds = [B.call_seed(b, x["id"], n) for b in B.BOARDS.values()
                 for x in S["sources"] + S["targets"] for n in range(2, B.POSTS + 1)]
        self.assertTrue(all(0 <= s <= 2 ** 31 - 1 for s in seeds))
        self.assertGreater(len(set(seeds)), len(seeds) * 0.99)

    def test_the_seed_that_gemini_refused(self):
        self.assertLessEqual(B.call_seed("/x/", "s13", 2), 2 ** 31 - 1)


class Generation(unittest.TestCase):
    def spec(self):
        t = S["targets"][0]
        return t, SOURCES[t["source"]]

    def test_both_arms_get_the_same_scaffold_and_stops_but_only_memory_sees_the_source(self):
        t, s = self.spec()
        source = dict(s, posts=[{"who": s["cast"][0], "ts": "x", "text": "the quokka ledger"}])
        seen = {}

        def fake(prompt, seed):
            seen.setdefault(arm, []).append((prompt, seed))
            return {"text": "ok", "cost": 0.001, "provider": "fake"}

        for arm in ("memory", "none"):
            out = B.run_thread(t, "/x/", fake, source=source, arm=arm)
            self.assertEqual([p["who"] for p in out["posts"]], t["authors"])
            self.assertEqual(out["stops"][:2], ["\n\n", "\n/x/"])
            self.assertEqual(set(out["stops"][2:]), {"\n" + h for h in t["cast"] + s["cast"]})
        self.assertTrue(all("quokka ledger" in p for p, _ in seen["memory"]))
        self.assertFalse(any("quokka ledger" in p for p, _ in seen["none"]))
        self.assertEqual([x for _, x in seen["memory"]], [x for _, x in seen["none"]])

    def test_a_gated_post_is_withheld_before_the_next_page(self):
        t, s = self.spec()
        calls = []

        def fake(prompt, seed):
            calls.append(prompt)
            return {"text": "i will kill you" if len(calls) == 1 else "fine", "cost": 0, "provider": "f"}

        out = B.run_thread(t, "/x/", fake, source=None, arm="none")
        self.assertTrue(out["posts"][1]["withheld"])
        self.assertEqual(out["posts"][1]["text"], "[post withheld]")
        self.assertNotIn("kill you", calls[1])
        self.assertEqual(out["quarantine"][0]["matched"], ["kill you"])

    def test_stop_strings_cut_a_post_that_runs_into_another(self):
        t, s = self.spec()
        other = t["cast"][1]
        fake = lambda prompt, seed: {"text": "first line\n%s 10/29 next" % other, "cost": 0, "provider": "f"}
        out = B.run_thread(t, "/x/", fake, source=None, arm="none")
        self.assertEqual(out["posts"][1]["text"], "first line")

    def test_spend_cap_stops_before_the_next_call(self):
        t, s = self.spec()
        budget = B.Budget(cap=0.0025)
        fake = lambda prompt, seed: {"text": "ok", "cost": 0.001, "provider": "f"}
        with self.assertRaises(B.OverBudget):
            B.run_thread(t, "/x/", fake, source=None, arm="none", budget=budget)
        self.assertAlmostEqual(budget.spent, 0.003)

    def test_a_resumed_run_starts_from_what_earlier_runs_spent(self):
        # resuming with the same --cap must not grant a fresh cap (review of PR #4)
        import json, os, shutil, tempfile
        root = tempfile.mkdtemp()
        try:
            for name, usd in (("spend-20261101T100000Z.json", 7.5), ("spend-20261101T120000Z.json", 4.25)):
                with open(os.path.join(root, name), "w", encoding="utf-8") as f:
                    json.dump({"design": "full", "cap": 20, "spent": usd, "calls": 10}, f)
            self.assertAlmostEqual(B.prior_spend(root), 11.75)
            self.assertEqual(B.prior_spend(os.path.join(root, "missing")), 0.0)
            budget = B.Budget(cap=12.0, spent=B.prior_spend(root))
            budget.add(0.5)
            with self.assertRaises(B.OverBudget):
                budget.check()
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
