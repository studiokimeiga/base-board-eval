"""python -m unittest discover -s calibration

CALIBRATION_DATA lists the folders with the private inputs (the corpora, spike/remote), joined
like PATH; the tests that need them are skipped without them.
"""
import glob, json, os, shutil, subprocess, tempfile, unittest

import analyze as A
import judge as J

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HAVE_ITEMS = os.path.exists(os.path.join(HERE, "items.json"))
HAVE_R9_ITEMS = os.path.exists(os.path.join(HERE, "items-r9.json"))
DATA = os.environ.get("CALIBRATION_DATA", ROOT).split(os.pathsep)
R9_ARMS = ("gemini9neutral", "gemini9", "rolesshort9")


def have(*paths):
    return all(any(os.path.exists(os.path.join(d, p)) for d in DATA) for p in paths)


HAVE_DATA = have("threads.final.json", os.path.join("spike", "remote", "bakeoff-gemini.json"))
HAVE_R9_DATA = have(*(os.path.join("spike", "remote", "bakeoff-%s.json" % a) for a in R9_ARMS))


def key():
    return A.read_json(os.path.join(HERE, "key.json"))


def key_r9():
    return A.read_json(os.path.join(HERE, "key-r9.json"))


def round9_mean(family, arm, opener, scale):
    """A round 9 thread's mean over its five readings, worked out from the raw files: the key's
    letters, then each reading's score."""
    d = os.path.join(ROOT, "spike", "judging", "r9")
    letters, reads = A.read_json(os.path.join(d, "key.json")), {}
    for f in glob.glob(os.path.join(d, "scores-%s*.json" % family)):
        reads.update(A.read_json(f))
    pks = ["%d-v%d" % (opener, v) for v in range(1, 6)]
    return sum(reads["opener-" + pk][next(L for L, a in letters[pk].items() if a == arm)][scale] for pk in pks) / 5


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

    def test_round9_judges_are_not_told_some_threads_are_small_models(self):
        # every round 9 thread is Gemini's; nothing else in the prompt differs
        mixed = " Some threads were written by small base models and some by large chat models; nothing says which."
        self.assertEqual(J.gpt_prompt(self.item, "r9"), J.gpt_prompt(self.item).replace(mixed, ""))
        self.assertNotIn("small base models", J.gpt_prompt(self.item, "r9"))

    @unittest.skipUnless(HAVE_R9_ITEMS, "items-r9.json is private; build it first")
    def test_round9_claude_batches_cover_every_item_once_per_pass(self):
        for p in ("A", "B"):
            self.assertEqual(sorted(i for b in J.batches(p, "r9") for i in b), sorted(key_r9()))


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


class Readers(unittest.TestCase):
    """How the reader's exports reach the two sets' analyses."""
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for f in ["key.json", "key-r9.json"] + glob.glob(os.path.join(HERE, "scores-*.json")):
            shutil.copy(os.path.join(HERE, f), self.dir)
        os.mkdir(os.path.join(self.dir, "ratings"))

    def tearDown(self):
        shutil.rmtree(self.dir)

    def export(self, name, ratings, exported):
        with open(os.path.join(self.dir, "ratings", name), "w", encoding="utf-8") as f:
            json.dump({"rater": "test", "exported": exported, "ratings": ratings}, f)

    def flat(self, ids, v):
        return {i: {s: v for s in A.SCALES} | {"repost": False} for i in ids}

    def test_the_newest_export_wins_whatever_its_file_name(self):
        ids = sorted(key())
        # a second download on the same day is saved as "... (1).json", which sorts first
        self.export("ratings-test-2026-11-03.json", self.flat(ids[:1], 1), "2026-11-03T09:00:00.000Z")
        self.export("ratings-test-2026-11-03 (1).json", self.flat(ids, 3), "2026-11-03T10:00:00.000Z")
        reader = A.load(self.dir)[1]["reader:test"]
        self.assertEqual(len(reader), 30)
        self.assertEqual(reader[ids[0]]["overall"], 3)

    def test_a_later_export_without_a_rating_keeps_the_earlier_one(self):
        # a fresh browser's export holds an empty entry for the thread it was showing
        ids = sorted(key())
        self.export("ratings-test-2026-11-03.json", self.flat(ids, 3), "2026-11-03T09:00:00.000Z")
        self.export("ratings-test-2026-11-04.json", {ids[0]: {"stars": [], "seen": False, "note": ""}},
                    "2026-11-04T09:00:00.000Z")
        self.assertEqual(len(A.load(self.dir)[1]["reader:test"]), 30)

    def test_each_thread_takes_its_latest_rating(self):
        # rated again in another browser, whose export happens to be the older one
        ids = sorted(key())
        again, first = self.flat(ids[:1], 5), self.flat(ids, 2)
        again[ids[0]]["t"], first[ids[0]]["t"] = "2026-11-03T11:00:00.000Z", "2026-11-03T10:00:00.000Z"
        self.export("a.json", again, "2026-11-03T11:05:00.000Z")
        self.export("b.json", first, "2026-11-03T12:00:00.000Z")
        self.assertEqual(A.load(self.dir)[1]["reader:test"][ids[0]]["overall"], 5)

    def test_each_set_gets_its_own_exports_items(self):
        self.export("ratings-test-2026-11-03.json", self.flat(key(), 3), "2026-11-03T09:00:00.000Z")
        self.export("ratings-r9-test-2026-11-03.json", self.flat(key_r9(), 4), "2026-11-03T10:00:00.000Z")
        self.assertEqual(len(A.load(self.dir)[1]["reader:test"]), 30)
        self.assertEqual(len(A.load(self.dir, "r9")[1]["reader:test"]), 18)

    def test_a_reader_of_only_round_9_leaves_the_calibration_set_waiting(self):
        self.export("ratings-r9-test-2026-11-03.json", self.flat(key_r9(), 4), "2026-11-03T10:00:00.000Z")
        self.assertIn("The reader has not rated the set yet", A.build(self.dir).split("## Round 9 set")[0])

    def test_one_rated_thread_reports_no_correlation_yet(self):
        # Spearman's rho is undefined until the items differ
        self.export("ratings-test-2026-11-03.json", self.flat(sorted(key())[:1], 3), "2026-11-03T09:00:00.000Z")
        self.assertIn("**not enough ratings**", A.build(self.dir))


class Round9Set(unittest.TestCase):
    def test_six_threads_per_arm(self):
        counts = {}
        for v in key_r9().values():
            counts[v["source"]] = counts.get(v["source"], 0) + 1
        self.assertEqual(counts, {a: 6 for a in R9_ARMS})

    def test_ids_never_collide_with_the_calibration_set(self):
        # a reader's exports for the two sets are merged item by item
        self.assertFalse(set(key_r9()) & set(key()))

    def test_r3s_arms_share_all_six_openers(self):
        # rolesshort9 takes gemini9neutral's openers, so round 9's question is asked opener by opener
        openers = {a: sorted(v["thread"] for v in key_r9().values() if v["source"] == a) for a in R9_ARMS}
        self.assertEqual(openers["rolesshort9"], openers["gemini9neutral"])
        self.assertEqual(len(set(openers["gemini9"]) & set(openers["gemini9neutral"])), 4)

    @unittest.skipUnless(HAVE_R9_DATA, "needs round 9's private threads (CALIBRATION_DATA)")
    def test_build_is_deterministic_and_matches_key(self):
        import build as B
        items1, key1, _ = B.build_r9(DATA)
        items2, key2, _ = B.build_r9(DATA)
        self.assertEqual(items1, items2)
        self.assertEqual(key1, key_r9())

    @unittest.skipUnless(HAVE_R9_ITEMS, "items-r9.json is private; build it first")
    def test_items_match_key_hashes(self):
        import build as B
        items = A.read_json(os.path.join(HERE, "items-r9.json"))["items"]
        k = key_r9()
        self.assertEqual(sorted(i["id"] for i in items), sorted(k))
        for it in items:
            self.assertEqual(B.digest(it["posts"]), k[it["id"]]["sha256"], it["id"])

    @unittest.skipUnless(HAVE_R9_ITEMS, "items-r9.json is private; build it first")
    def test_threads_sit_on_round_9s_openers(self):
        # analyze.py takes thread n's round 9 scores from packet opener n + 1; the public scaffold,
        # each opener's posters in order, pins that
        scaffold = A.read_json(os.path.join(ROOT, "spike", "judging", "r9", "scaffold.json"))
        k = key_r9()
        for it in A.read_json(os.path.join(HERE, "items-r9.json"))["items"]:
            self.assertEqual([p["who"] for p in it["posts"]], scaffold[str(k[it["id"]]["thread"] + 1)], it["id"])


class Round9Build(unittest.TestCase):
    """build.py's rules for the round 9 set, on made-up threads so they run without private files."""
    WITHHELD = {"gemini9neutral": {1, 6}, "gemini9": {5, 7}, "rolesshort9": set()}    # as in round 9

    def setUp(self):
        self.empty, self.data = tempfile.mkdtemp(), tempfile.mkdtemp()
        remote = os.path.join(self.data, "spike", "remote")
        os.makedirs(remote)
        for arm, held in self.WITHHELD.items():
            threads = [{"posts": [{"who": "op%d" % n, "text": "opener %d" % n},
                                  {"who": "anon", "text": "[post withheld]" if n in held else "a reply"}]}
                       for n in range(8)]
            with open(os.path.join(remote, "bakeoff-%s.json" % arm), "w", encoding="utf-8") as f:
                json.dump({"arm": arm, "threads": threads}, f)

    def tearDown(self):
        shutil.rmtree(self.empty)
        shutil.rmtree(self.data)

    def test_a_screened_thread_gives_way_to_the_arms_next_opener(self):
        import build as B
        _, key, notes = B.build_r9([self.empty, self.data])
        got = {a: sorted(v["thread"] for v in key.values() if v["source"] == a) for a in R9_ARMS}
        # the first arm runs from opener 0; the others try its openers first, then their own next
        self.assertEqual(got, {"gemini9neutral": [0, 2, 3, 4, 5, 7], "gemini9": [0, 1, 2, 3, 4, 6],
                               "rolesshort9": [0, 2, 3, 4, 5, 7]})
        self.assertEqual(len(notes), 4)

    def test_a_missing_input_is_named(self):
        import build as B
        with self.assertRaises(SystemExit) as e:
            B.build_r9([self.empty])
        self.assertIn("bakeoff-gemini9neutral.json", str(e.exception))

    def test_by_default_a_set_without_its_files_is_skipped_by_name(self):
        # README.md's registered rebuild names one folder, which may not hold round 9's threads
        import build as B
        built, skipped = B.build_sets([self.empty, self.data])
        self.assertEqual(sorted(built), ["r9"])
        self.assertIn("threads.json", skipped["calibration"])

    def test_a_set_asked_for_must_build(self):
        import build as B
        with self.assertRaises(SystemExit):
            B.build_sets([self.empty, self.data], ["calibration", "r9"])


class Round9Analysis(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for f in ("key.json", "key-r9.json"):
            shutil.copy(os.path.join(HERE, f), self.dir)
        os.mkdir(os.path.join(self.dir, "ratings"))
        self.k = key_r9()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, name, obj):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def rate(self, scores):
        """scores(item id, arm) -> the reader's changes to a thread rated 3 on every scale."""
        ratings = {i: {s: 3 for s in A.SCALES} | {"repost": False} | scores(i, v["source"])
                   for i, v in self.k.items()}
        self.write(os.path.join("ratings", "r.json"), {"rater": "test", "ratings": ratings})
        return ratings

    def section(self, name):
        return A.build(self.dir).split("## Round 9 set")[1].split("### " + name)[1].split("\n### ")[0]

    def test_the_permutation_test_is_exact(self):
        # of the 20 ways to split 1..6 into three and three, only the two extremes are as far apart
        self.assertAlmostEqual(A.perm_p([1, 2, 3], [4, 5, 6]), 2 / 20)
        self.assertEqual(A.perm_p([2, 2], [2, 2]), 1.0)

    def test_the_primary_readings_follow_the_permutation_test(self):
        # humour is the mean of the two humour scales: 5, 1 and 3 by arm; six threads against six
        # that never overlap give p = 2 / 924
        joke = {"gemini9neutral": 5, "gemini9": 1, "rolesshort9": 5}
        deadpan = {"gemini9neutral": 5, "gemini9": 1, "rolesshort9": 1}
        interest = {"gemini9neutral": 3, "gemini9": 3, "rolesshort9": 5}
        self.rate(lambda i, a: {"joke": joke[a], "deadpan": deadpan[a], "interest": interest[a]})
        self.assertIn("- reader:test: humour **higher** (p = 0.002).", self.section("R1"))
        self.assertIn("- reader:test: humour **higher** (p = 0.002).", self.section("R2"))
        self.assertIn("- reader:test: interest **lower** (p = 0.002), humour **higher** (p = 0.002); "
                      "round 9's criterion **not met**.", self.section("R3"))

    def test_round_9s_criterion_is_met_when_the_reader_keeps_reading_and_laughs_more(self):
        more = {"gemini9neutral": 5, "gemini9": 3, "rolesshort9": 2}
        self.rate(lambda i, a: {"joke": more[a], "deadpan": more[a], "interest": more[a]})
        self.assertIn("; round 9's criterion **met**.", self.section("R3"))

    def test_a_reading_needs_p_below_0_05(self):
        self.assertEqual([A.reading(1, 0.049), A.reading(-1, 0.049), A.reading(1, 0.05)],
                         ["higher", "lower", "no clear difference"])

    def test_same_openers_pair_the_threads_by_opener(self):
        # humour = the opener's index, one point more under the neutral header. R1's arms share
        # openers 0, 2, 3 and 4 (means 4.50 against 2.67 over all six); R3's share all six
        def humour(i, a):
            return self.k[i]["thread"] + (a == "gemini9neutral")
        self.rate(lambda i, a: {"joke": humour(i, a), "deadpan": humour(i, a)})
        for q, whole, same in (("R1", "1.83", "1.00 over 4"), ("R3", "1.00", "1.00 over 6")):
            row = next(l for l in self.section(q).splitlines() if l.startswith("| reader:test | **humour** |"))
            self.assertTrue(row.startswith("| reader:test | **humour** | %s |" % whole), row)
            self.assertTrue(row.endswith("| %s |" % same), row)

    def test_seen_threads_are_left_out_of_the_second_figures(self):
        # three of the /x/ threads were seen before and rated funnier than the other three
        seen = sorted(i for i, v in self.k.items() if v["source"] == "gemini9")[:3]
        self.rate(lambda i, a: {"joke": 5 if a != "gemini9" or i in seen else 1, "seen": i in seen})
        r1 = self.section("R1")
        # humour = (joke + 3) / 2: 4 for the neutral arm; 4, 4, 4, 2, 2, 2 for /x/
        self.assertIn("| reader:test | **humour** | 1.00 |", r1)
        self.assertIn("Without seen items: humour 2.00 (9 threads)", r1)

    def test_a_comparison_waits_for_both_arms(self):
        ratings = self.rate(lambda i, a: {})
        self.write(os.path.join("ratings", "r.json"), {"rater": "test", "ratings": {
            i: v for i, v in ratings.items() if self.k[i]["source"] == "gemini9neutral"}})
        self.assertIn("- reader:test: waiting for ratings", self.section("R1"))

    def test_round_9s_judges_score_each_thread_by_its_five_readings(self):
        j = A.round9_judges(self.k)
        item = {(v["source"], v["thread"]): i for i, v in self.k.items()}
        # by hand from spike/judging/r9: key.json's letters, then each reading's score
        self.assertAlmostEqual(j["r9-claude"][item["gemini9", 0]]["overall"], 3.2)
        self.assertAlmostEqual(j["r9-claude"][item["gemini9", 1]]["overall"], 2.6)
        self.assertAlmostEqual(j["r9-claude"][item["rolesshort9", 0]]["overall"], 4.0)
        self.assertAlmostEqual(j["r9-gpt"][item["gemini9", 0]]["humour"], 2.2)
        self.assertAlmostEqual(j["r9-gpt"][item["gemini9", 1]]["humour"], 3.4)

    def test_the_readers_humour_meets_round_9s_humour_score(self):
        # a reader whose deliberate humour is round 9 Claude's humour for each thread
        self.rate(lambda i, a: {"joke": round9_mean("claude", a, self.k[i]["thread"] + 1, "humour")})
        row = next(l for l in self.section("R4").splitlines() if l.startswith("| reader:test vs r9-claude |"))
        self.assertEqual(row.split(" | ")[5], "1.00")             # the joke column

    def test_r4_reads_a_judge_only_once_every_thread_is_rated(self):
        ids = sorted(self.k)
        ratings = self.rate(lambda i, a: {"overall": ids.index(i) % 5 + 1})
        self.write(os.path.join("ratings", "r.json"), {"rater": "test", "ratings": {i: ratings[i] for i in ids[:4]}})
        line = next(l for l in self.section("R4").splitlines() if l.startswith("- reader:test vs r9-claude:"))
        self.assertIn("waiting for ratings (4 of 18 threads)", line)
        self.assertNotIn("**", line)

    def test_r4_gives_round_9s_two_families_against_each_other_for_reference(self):
        ids = sorted(self.k)
        claude, gpt = ([round9_mean(f, self.k[i]["source"], self.k[i]["thread"] + 1, "overall") for i in ids]
                       for f in ("claude", "gpt"))
        self.assertIn("For reference, round 9's Claude against its gpt-5.4: ρ = %.2f [" % A.spearman(claude, gpt),
                      self.section("R4"))

    def test_a_judge_on_the_readers_scales_is_compared_thread_by_thread(self):
        # a gpt-5.4 pass on this set (judge.py gpt --set r9) that agrees with the reader exactly
        ids = sorted(self.k)
        ratings = self.rate(lambda i, a: {"overall": ids.index(i) % 5 + 1})
        self.write("scores-r9-gpt.json", ratings)
        r4 = self.section("R4")
        self.assertIn("- reader:test vs gpt: ρ = 1.00", r4)
        self.assertIn("**usable as a first screen**", r4)
        self.assertIn("- reader:test vs r9-claude: ρ = ", r4)


def git_reads_checkout():
    # WSL's git can't follow a Windows worktree's .git file, for one
    try:
        return subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT, capture_output=True).returncode == 0
    except OSError:
        return False


class Private(unittest.TestCase):
    @unittest.skipUnless(git_reads_checkout(), "needs git and a checkout it can read")
    def test_thread_text_is_ignored_for_every_set(self):
        for f in ("items.json", "items-r9.json", "packets/c01.txt", "packets-r9/c31.txt"):
            r = subprocess.run(["git", "check-ignore", "-q", "calibration/" + f], cwd=ROOT)
            self.assertEqual(r.returncode, 0, f)


class Results(unittest.TestCase):
    def test_results_are_current(self):
        with open(A.RESULTS, encoding="utf-8") as f:
            self.assertEqual(f.read(), A.build(), "run python calibration/analyze.py")


if __name__ == "__main__":
    unittest.main()
