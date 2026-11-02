"""python -m unittest discover -s lore -p "test_*.py"

The second hop (hop2.py, hop2/PREREGISTRATION.md): the prior rule on #4's public results, the
schedule, the pages and the generation loop, the check of generation 1 against its manifest, the
length-matched identification, and the whole pipeline on a fake model that plants an effect, which
must be found. Nothing here touches the network.
"""
import glob, hashlib, json, os, re, shutil, tempfile, unittest

import analyze as A
import board as B
import explore as E
import hop2 as H
import judge as J
import tracker as T

HERE = os.path.dirname(os.path.abspath(__file__))
S1 = B.schedule()
SOURCES = {s["id"]: s for s in S1["sources"]}
TARGETS = {t["id"]: t for t in S1["targets"]}
COMMON = T.load_reference(T.REF_SHARE)


def real_priors():
    return H.priors(A.load(os.path.join(HERE, "results.json")), S1,
                    A.judges(os.path.join(HERE, "judging")).get("claude"))


def thread(board, no, tid, posts, cast=None, opener=0, **extra):
    t = {"board": board, "no": no, "id": tid, "opener": opener,
         "cast": cast if cast is not None else sorted({w for w, _ in posts}),
         "posts": [{"who": w, "ts": B.stamp(3 * 86400 + 60 * i), "text": x} for i, (w, x) in enumerate(posts)]}
    t.update(extra)
    return t


class Priors(unittest.TestCase):
    def test_the_rule_picks_every_misc_target_whose_source_recurred(self):
        # RESULTS.md, H5 row for /misc/ (s05 lavender, s07 duck/union rep, s09 offer, s19 hedge
        # trimmer), and Claude's verdicts in its "Every flagged target" table
        got = {(p["source"], p["prior"]): (p["items"], p["words"], p["confirmed"]) for p in real_priors()}
        duck = (["duck", "rep + union", "union rep"], ["duck", "rep", "union"], True)
        hedge = (["hedge + trimmer", "hedge trimmer"], ["hedge", "trimmer"], True)
        self.assertEqual(got, {("s05", "t20"): (["lavender"], ["lavender"], True),
                               ("s05", "t21"): (["lavender"], ["lavender"], True),
                               ("s07", "t16"): duck, ("s07", "t44"): duck,
                               ("s09", "t07"): (["offer"], ["offer"], False),
                               ("s09", "t29"): (["offer"], ["offer"], False),
                               ("s19", "t17"): hedge, ("s19", "t28"): hedge})

    def test_only_an_item_both_memory_targets_share_counts_and_only_on_misc(self):
        # s13's targets are t00 and t18, s08's are t01 and t26 (schedule.json)
        results = {"targets": [
            {"board": "misc", "target": "t00", "arm": "memory", "items": [{"item": "quokka"}, {"item": "pad"}]},
            {"board": "misc", "target": "t18", "arm": "memory", "items": [{"item": "quokka"}]},
            {"board": "misc", "target": "t00", "arm": "none", "items": [{"item": "ledger"}]},
            {"board": "misc", "target": "t18", "arm": "none", "items": [{"item": "ledger"}]},
            {"board": "misc", "target": "t01", "arm": "memory", "items": [{"item": "kelp"}]},
            {"board": "misc", "target": "t26", "arm": "memory", "items": [{"item": "brine"}]},
            {"board": "x", "target": "t01", "arm": "memory", "items": [{"item": "same"}]},
            {"board": "x", "target": "t26", "arm": "memory", "items": [{"item": "same"}]}]}
        prs = H.priors(results, S1)
        self.assertEqual([(p["source"], p["prior"], p["items"], p["confirmed"]) for p in prs],
                         [("s13", "t00", ["quokka"], False), ("s13", "t18", ["quokka"], False)])
        yes, no = {"borrows": True}, {"borrows": False}
        self.assertFalse(H.priors(results, S1, {("misc", "t00", "memory"): yes, ("misc", "t18", "memory"): no})[0]["confirmed"])
        self.assertTrue(H.priors(results, S1, {("misc", "t00", "memory"): yes, ("misc", "t18", "memory"): yes})[0]["confirmed"])

    def test_item_words(self):
        self.assertEqual(H.item_words("rep + union"), {"rep", "union"})
        self.assertEqual(H.item_words("union rep"), {"union", "rep"})
        self.assertEqual(H.item_words("carpet + filled + shin"), {"carpet", "filled", "shin"})
        self.assertEqual(H.item_words("duck"), {"duck"})


class Schedule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prs = real_priors()
        cls.s2 = H.schedule(cls.prs, S1)
        cls.by_prior = {}
        for t in cls.s2["targets"]:
            cls.by_prior.setdefault(t["prior"], []).append(t)

    def test_every_prior_gets_six_openers_unrelated_to_it_and_to_its_source(self):
        self.assertEqual(sorted(self.by_prior), ["t07", "t16", "t17", "t20", "t21", "t28", "t29", "t44"])
        for pid, ts in self.by_prior.items():
            p, s = TARGETS[pid], SOURCES[TARGETS[pid]["source"]]
            self.assertEqual(sorted(t["rank"] for t in ts), list(range(6)))
            self.assertEqual(len({t["opener"] for t in ts}), 6)
            for t in ts:
                self.assertEqual(t["source"], s["id"])
                self.assertFalse(set(B.TAGS[t["opener"]]) & (set(B.TAGS[p["opener"]]) | set(B.TAGS[s["opener"]])),
                                 (pid, t["opener"]))

    def test_opener_use_is_as_even_as_the_tags_allow(self):
        # 48 targets over 23 openers: two openers must be used three times, none need more
        counts = {}
        for t in self.s2["targets"]:
            counts[t["opener"]] = counts.get(t["opener"], 0) + 1
        self.assertEqual(max(counts.values()), 3)

    def test_a_cast_never_shares_a_handle_with_its_prior_or_its_source(self):
        for t in self.s2["targets"]:
            p = TARGETS[t["prior"]]
            self.assertEqual(len(set(t["cast"])), 7)
            self.assertFalse(set(t["cast"]) & (set(p["cast"]) | set(SOURCES[p["source"]]["cast"])))

    def test_numbers_patterns_and_posts(self):
        ts = self.s2["targets"]
        self.assertEqual(sorted(t["no"] for t in ts), list(range(4540, 4588)))
        self.assertEqual(len({t["id"] for t in ts}), 48)
        c = {}
        for t in ts:
            c[t["pattern"]] = c.get(t["pattern"], 0) + 1
            self.assertEqual(len(t["authors"]), 24)
            self.assertEqual(t["authors"][0], t["cast"][0])
        self.assertEqual(c, {"away": 16, "burst": 16, "gone": 16})

    def test_every_target_starts_after_its_prior_ended(self):
        for t in self.s2["targets"]:
            p = TARGETS[t["prior"]]
            self.assertGreater(t["start"], p["start"] + p["times"][-1])

    def test_the_schedule_is_fixed_by_its_seed(self):
        self.assertEqual(H.schedule(self.prs, S1), self.s2)
        self.assertNotEqual(H.schedule(self.prs, S1, seed=1)["targets"], self.s2["targets"])

    def test_the_four_design_keeps_the_first_four_ranks(self):
        four = [t for t in self.s2["targets"] if H.in_design(t, "four")]
        self.assertEqual(len(four), 32)
        self.assertTrue(all(t["rank"] < 4 for t in four))

    def test_the_judge_half_is_half_of_each_priors_targets_and_shuffled(self):
        for design, per in (("full", 3), ("four", 2)):
            half = set(self.s2["half"][design])
            for pid, ts in self.by_prior.items():
                mine = [t for t in ts if H.in_design(t, design)]
                self.assertEqual(sum(t["id"] in half for t in mine), per, (design, pid))
        lowest = {t["id"] for t in self.s2["targets"] if t["rank"] < 3}
        self.assertNotEqual(set(self.s2["half"]["full"]), lowest)


def prior_pair(pid="t16", lore="the duck union handles this now"):
    """A prior and its sham with the prior's real scaffold: the same number, opener and cast."""
    p = TARGETS[pid]
    posts = [(p["cast"][0], "my roommate labels everything"), (p["cast"][1], lore)]
    sham = [(p["cast"][0], "my roommate labels everything"), (p["cast"][1], "just talk to them")]
    mk = lambda ps, arm: thread("/misc/", p["no"], pid, ps, cast=p["cast"], opener=p["opener"],
                                arm=arm, source=p["source"])
    return mk(posts, "memory"), mk(sham, "none")


class Generation(unittest.TestCase):
    def test_both_arms_share_everything_but_the_thread_above(self):
        spec = H.schedule(real_priors(), S1)["targets"][0]
        prior, sham = prior_pair(spec["prior"])
        src = SOURCES[spec["source"]]
        seen = {}

        def fake(prompt, seed):
            seen.setdefault(arm, []).append((prompt, seed))
            return {"text": "ok", "cost": 0.001, "provider": "fake"}

        out = {}
        for arm, above in (("lore", prior), ("sham", sham)):
            out[arm] = H.generate_target(spec, above, arm, fake)
        self.assertEqual([p["who"] for p in out["lore"]["posts"]], spec["authors"])
        self.assertEqual([p["who"] for p in out["sham"]["posts"]], spec["authors"])
        self.assertEqual(out["lore"]["stops"], out["sham"]["stops"])
        self.assertEqual(set(out["lore"]["stops"][2:]), {"\n" + h for h in spec["cast"] + prior["cast"]})
        self.assertEqual([x for _, x in seen["lore"]], [x for _, x in seen["sham"]])
        self.assertTrue(all("duck union" in p for p, _ in seen["lore"]))
        self.assertFalse(any("duck union" in p for p, _ in seen["sham"]))
        for arm in ("lore", "sham"):
            for p, _ in seen[arm]:
                self.assertIn("/misc/ — thread %d\n\n" % prior["no"], p)
                self.assertNotIn("— thread %d\n" % src["no"], p)    # the source is never on the page
            self.assertEqual((out[arm]["arm"], out[arm]["prior"], out[arm]["source"], out[arm]["above_no"]),
                             (arm, spec["prior"], spec["source"], prior["no"]))

    def test_a_sham_must_share_its_priors_scaffold(self):
        prior, sham = prior_pair()
        run = {("misc", "t16", "memory"): prior, ("misc", "t16", "none"): sham}
        self.assertEqual(H.above_pair(run, "t16"), (prior, sham))
        bad = dict(sham, cast=list(reversed(sham["cast"])))
        with self.assertRaises(ValueError):
            H.above_pair({("misc", "t16", "memory"): prior, ("misc", "t16", "none"): bad}, "t16")
        late = dict(sham, posts=[sham["posts"][0], dict(sham["posts"][1], ts="10/30/26(Fri)09:00:00")])
        with self.assertRaises(ValueError):
            H.above_pair({("misc", "t16", "memory"): prior, ("misc", "t16", "none"): late}, "t16")


class Filing(unittest.TestCase):
    """A judge that answers several items in one file can file an answer under the wrong id."""
    TEXTS = {i: J.PROMPT_HOP2 % ("/misc/ — thread 4478\n\nruth\n%s" % a, "/misc/ — thread 4541\n\nzed\n%s" % b)
             for i, a, b in (("h000", "the quokka ledger is mine", "the quokka keeps a ledger now"),
                             ("h001", "the wombat ate my yoghurt", "a wombat ate it again"))}

    def test_an_answer_whose_quotes_belong_to_another_item_is_caught(self):
        right = {"borrowings": [{"b": "the quokka keeps a ledger", "a": "the quokka ledger is mine"}], "borrows": True}
        wrong = {"borrowings": [{"b": "the quokka keeps a ledger", "a": "the quokka ledger"}], "borrows": True}
        self.assertEqual(H.misfiled(self.TEXTS, {"h000": right, "h001": wrong}), {"h001": ["h000"]})

    def test_quotes_survive_curly_quotes_ellipses_and_case(self):
        ok = {"borrowings": [{"b": "A Wombat ate it…", "a": "‘the wombat’ ate my yoghurt"}], "borrows": True}
        self.assertEqual(H.misfiled(self.TEXTS, {"h001": ok}), {})

    def test_an_answer_with_nothing_to_quote_cannot_be_checked_and_passes(self):
        self.assertEqual(H.misfiled(self.TEXTS, {"h000": {"borrowings": [], "borrows": False}}), {})


class Caps(unittest.TestCase):
    def test_each_design_defaults_to_its_pre_registered_cap(self):
        self.assertEqual((H.cap_for("full"), H.cap_for("four"), H.cap_for("four", 3.0)), (8.0, 6.0, 3.0))


class Estimate(unittest.TestCase):
    def test_a_target_costs_its_calls_at_the_fitted_rates(self):
        spec = dict(H.schedule(real_priors(), S1)["targets"][0], rank=0)
        prior, sham = prior_pair(spec["prior"])
        gen1 = {("misc", spec["prior"], "memory"): prior, ("misc", spec["prior"], "none"): sham}
        a, b, c = H.COST
        want = 0.0
        for above in (prior, sham):
            # both priors' replies are short, so a reply is the 90-character floor; 23 calls, the
            # n-th page holding n - 2 earlier replies of 90 + 30 characters: 0 + 1 + ... + 22 = 253
            fixed = len(B.ask(B.page("/misc/", spec["no"], [], above), "someone")) + len(B.OPENERS[spec["opener"]]) + 30
            want += 23 * a + b * (23 * fixed + 253 * 120) + c * 23 * 90
        self.assertAlmostEqual(H.estimate({"targets": [spec]}, "full", gen1), want)


class Gen1Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "run")
        os.makedirs(os.path.join(self.root, "misc"))
        with open(os.path.join(self.root, "misc", "s00.json"), "w", encoding="utf-8") as f:
            f.write('{"posts": []}')
        self.manifest = os.path.join(self.tmp, "MANIFEST.sha256")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_manifest(self, digest):
        with open(self.manifest, "w", encoding="utf-8") as f:
            f.write("%s *private/run/misc/s00.json\n" % digest)

    def test_a_file_whose_hash_matches_loads(self):
        self.write_manifest(hashlib.sha256(b'{"posts": []}').hexdigest())
        self.assertEqual(H.load_gen1(self.root, self.manifest), {("misc", "s00", None): {"posts": []}})

    def test_a_changed_file_is_refused(self):
        self.write_manifest(hashlib.sha256(b'{"posts": [1]}').hexdigest())
        with self.assertRaises(ValueError):
            H.load_gen1(self.root, self.manifest)

    def test_a_folder_with_no_run_in_it_is_refused(self):
        with self.assertRaises(ValueError):
            H.load_gen1(os.path.join(self.tmp, "elsewhere"), None)

    def test_a_file_the_manifest_does_not_list_is_refused(self):
        with open(self.manifest, "w", encoding="utf-8") as f:
            f.write("")
        with self.assertRaises(ValueError):
            H.load_gen1(self.root, self.manifest)


class Identification(unittest.TestCase):
    """explore.py's test, held to its definition, and the exclusions hop 2 adds."""

    def test_it_is_explore_identification_on_a_generation_one_run(self):
        tmp = tempfile.mkdtemp()
        try:
            from test_pipeline import fake
            root = os.path.join(tmp, "run")
            B.run(B.schedule(), "x", fake, B.Budget(cap=1.0), root, workers=4, log=lambda *_: None)
            run = J.load_run(root)
            want = E.identification(run, COMMON)
            sources = {k: v for k, v in run.items() if k[2] is None}
            twin = {(k[0], v["opener"]): v for k, v in sources.items()}
            for (b, tid, arm), t in run.items():
                if arm is None:
                    continue
                cands = [k for k, s in sources.items() if k[0] == b
                         and not set(B.TAGS[s["opener"]]) & set(B.TAGS[t["opener"]])]
                got = H.identify(t, (b, t["source"], None), cands, sources,
                                 twin[(b, t["opener"])]["posts"], COMMON)
                w = want[(b, tid, arm)]
                self.assertEqual((got["top"], got["percentile"], got["candidates"], got["real"]),
                                 (w["top"], w["percentile"], w["candidates"], w["real"]), (b, tid, arm))
        finally:
            shutil.rmtree(tmp)

    def test_material_the_sham_prior_also_has_never_counts(self):
        src = thread("/misc/", 4478, "s07", [("ruth", "my bike moved"), ("omar", "a quokka and a ledger"),
                                            ("ruth", "the quokka ledger again")])
        other = thread("/misc/", 4479, "s08", [("ines", "my yoghurt"), ("mei", "a wombat ate it"),
                                              ("ines", "wombat again")])
        bg = thread("/misc/", 4480, "s09", [("li", "gym"), ("bo", "machines")])
        sources = {("misc", "s07", None): src, ("misc", "s08", None): other, ("misc", "s09", None): bg}
        sham_prior = [{"who": "kai", "text": "we keep a ledger"}]
        q = lambda text: thread("/misc/", 4541, "u01", [("zed", "my sister sends links"), ("amy", text),
                                                      ("zed", text)], cast=["zed", "amy"])
        cands = [("misc", "s07", None), ("misc", "s08", None)]
        lore = H.identify(q("the quokka keeps a ledger"), cands[0], cands, sources, sham_prior, COMMON)
        self.assertTrue(lore["top"])
        self.assertEqual([i["item"] for i in lore["result"]["items"]], ["quokka"])
        self.assertTrue(H.lore_hit(lore["result"], {"quokka"}))
        self.assertFalse(H.lore_hit(lore["result"], {"ledger"}))
        only_ledger = H.identify(q("a ledger, a ledger"), cands[0], cands, sources, sham_prior, COMMON)
        self.assertFalse(only_ledger["top"])
        self.assertEqual(only_ledger["real"], 0)

    def test_two_hop_names_are_references(self):
        src = thread("/misc/", 4478, "s07", [("gustav", "ducks took my bike spot"), ("omar", "union rep")])
        bg = thread("/misc/", 4480, "s09", [("li", "gym"), ("bo", "machines")])
        sources = {("misc", "s07", None): src, ("misc", "s09", None): bg}
        q = thread("/misc/", 4541, "u01", [("zed", "my sister sends links"), ("amy", "ask gustav, he knows")],
                   cast=["zed", "amy"])
        got = H.identify(q, ("misc", "s07", None), list(sources), sources, [], COMMON)
        self.assertEqual([(r["kind"], r["match"]) for r in got["result"]["references"]], [("handle", "gustav")])
        self.assertTrue(got["top"])


class Verdict(unittest.TestCase):
    def test_the_pre_registered_l4_rule(self):
        # (McNemar p, lore-only, sham-only, lore targets with a judged lore item, sham targets with one)
        cases = [((0.01, 5, 0, 1, 0), "met"), ((0.01, 5, 0, 0, 0), "partly: source material"),
                 ((0.01, 5, 0, 1, 1), "partly: source material"), ((0.30, 2, 0, 2, 0), "partly: an invention"),
                 ((0.30, 2, 1, 0, 0), "not met"), ((0.01, 0, 5, 0, 0), "not met"),
                 ((0.049, 6, 0, 1, 0), "met"), ((0.05, 6, 0, 1, 0), "partly: an invention")]
        for args, want in cases:
            self.assertTrue(H.l4(*args).startswith(want), (args, H.l4(*args)))


# ---- the whole pipeline on fake models ----
COINAGE = re.compile(r"zq\d+blat")


def fake_hop2(prompt, seed):
    """Copies the coinage of the thread above, if it has one, into the even-numbered targets."""
    from test_pipeline import WORDS
    rng = int(hashlib.sha256(str(seed).encode()).hexdigest(), 16)
    words = [WORDS[(rng >> (5 * i)) % len(WORDS)] for i in range(8)]
    heads = [int(x) for x in re.findall(r"— thread (\d+)", prompt)]
    above = prompt.split("— thread %d" % heads[1])[0]
    if heads[1] % 2 == 0:
        words += COINAGE.findall(above)[:1]
    return {"text": " ".join(words), "cost": 0.0, "provider": "fake"}


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_pipeline import fake
        cls.tmp = tempfile.mkdtemp()
        gen1 = os.path.join(cls.tmp, "gen1")
        B.run(B.schedule(), "full", fake, B.Budget(cap=1.0), gen1, workers=4, log=lambda *_: None)
        os.makedirs(os.path.join(cls.tmp, "j1"))
        A.main(["--run", gen1, "--judging", os.path.join(cls.tmp, "j1"), "--out", cls.tmp])
        cls.gen1 = J.load_run(gen1)
        cls.prs = H.priors(A.load(os.path.join(cls.tmp, "results.json")), S1)
        cls.s2 = H.schedule(cls.prs, S1)
        cls.root = os.path.join(cls.tmp, "hop2")
        H.run(cls.s2, "full", cls.gen1, fake_hop2, B.Budget(cap=1.0), cls.root, workers=4, log=lambda *_: None)
        cls.run2 = H.load_run(cls.root)
        cls.items = H.items(cls.run2, cls.gen1)
        key = {i["item"]: {"target": i["target"], "arm": i["arm"]} for i in cls.items}
        jdir = os.path.join(cls.tmp, "j2")
        os.makedirs(jdir)
        planted = lambda i: key[i]["arm"] == "lore" and next(
            t for t in cls.s2["targets"] if t["id"] == key[i]["target"])["no"] % 2 == 0
        with open(os.path.join(jdir, "key.json"), "w", encoding="utf-8") as f:
            json.dump(key, f)
        with open(os.path.join(jdir, "scores-claude.json"), "w", encoding="utf-8") as f:
            json.dump({"judge": "claude", "scope": "all", "items": {i: {
                "borrows": planted(i), "confidence": 4,
                "kinds": {"reference": 0, "mixup": 0, "coincidence": 0, "reuse": int(planted(i))}}
                for i in key}}, f)
        cls.summary = H.analyze(cls.gen1, cls.run2, cls.s2, jdir, cls.tmp, COMMON)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def planted(self):
        return sum(1 for t in self.s2["targets"] if t["no"] % 2 == 0)

    def test_the_fake_gives_the_rule_priors_to_test(self):
        # a source recurs when both of its targets have even numbers (test_pipeline.fake)
        want = sorted(t["id"] for s in S1["sources"] for t in S1["targets"] if t["source"] == s["id"]
                      and all(u["no"] % 2 == 0 for u in S1["targets"] if u["source"] == s["id"]))
        self.assertEqual(sorted(p["prior"] for p in self.prs), want)
        self.assertGreater(len(want), 0)

    def test_every_thread_is_written(self):
        self.assertEqual(sorted({(k[1], k[2]) for k in self.run2}),
                         sorted((t["id"], a) for t in self.s2["targets"] for a in ("lore", "sham")))

    def test_a_rerun_keeps_what_was_written_and_calls_nothing(self):
        def boom(prompt, seed):
            raise AssertionError("regenerated a thread that was already written")
        H.run(self.s2, "full", self.gen1, boom, B.Budget(cap=1.0), self.root, workers=2, log=lambda *_: None)

    def test_a_failure_stops_the_run_instead_of_draining_the_queue(self):
        # one worker, 23 calls a thread: the first thread is saved, the second fails at its 7th
        # call, and none of the 94 queued threads makes a call
        calls = []

        def flaky(prompt, seed):
            calls.append(seed)
            if len(calls) == 30:
                raise RuntimeError("gave up after 6 tries")
            return {"text": "ok", "cost": 0.0, "provider": "fake"}

        root = os.path.join(self.tmp, "stopped")
        with self.assertRaises(RuntimeError):
            H.run(self.s2, "full", self.gen1, flaky, B.Budget(cap=1.0), root, workers=1, log=lambda *_: None)
        self.assertEqual(len(calls), 30)
        self.assertEqual(len(H.load_run(root)), 1)

    def test_analysis_before_judging_leaves_the_verdict_pending(self):
        out, empty = os.path.join(self.tmp, "unjudged"), os.path.join(self.tmp, "no-verdicts")
        os.makedirs(out)
        os.makedirs(empty)
        s = H.analyze(self.gen1, self.run2, self.s2, empty, out, COMMON)
        self.assertTrue(s["l4"].startswith("pending"), s["l4"])
        self.assertEqual(s["h1"]["lore_only"], self.planted())

    def test_material_the_sham_prior_shares_with_the_source_never_counts(self):
        # stop words around the coinage, so it can only count as a word: the frozen tracker excludes
        # a phrase only when the excluded thread has that phrase, as #4's topic twins did
        t = self.s2["targets"][0]
        coin = "zq%dblat" % SOURCES[t["source"]]["no"]
        posts = [{"who": t["authors"][0], "text": B.OPENERS[t["opener"]]},
                 {"who": t["authors"][1], "text": "ok " + coin}, {"who": t["authors"][2], "text": "lol " + coin}]
        q = dict(t, board="/misc/", arm="lore", posts=posts)
        got = H.score_target(q, self.s2, self.gen1, COMMON)
        self.assertTrue(got["top"] and got["lore"])
        unrelated = sum(1 for o in range(len(B.OPENERS)) if not set(B.TAGS[o]) & set(B.TAGS[t["opener"]]))
        self.assertEqual(got["candidates"], unrelated - 1)       # the prior's topic twin is out
        gen1 = dict(self.gen1)
        key = ("misc", t["prior"], "none")
        sham = gen1[key]
        gen1[key] = dict(sham, posts=[sham["posts"][0], dict(sham["posts"][1], text=coin)] + sham["posts"][2:])
        got = H.score_target(q, self.s2, gen1, COMMON)
        self.assertFalse(got["top"] or got["lore"])
        self.assertEqual(got["real"], 0)

    def test_the_planted_second_hop_is_found_and_the_sham_stays_clean(self):
        h1 = self.summary["h1"]
        self.assertEqual((h1["pairs"], h1["lore_only"], h1["sham_only"]), (len(self.s2["targets"]), self.planted(), 0))
        self.assertLess(h1["p"], 0.001)
        self.assertGreater(h1["ci"][0], 0)
        h2 = self.summary["h2"]
        self.assertEqual((h2["lore_only"], h2["sham_only"], h2["cross_hits"]), (self.planted(), 0, 0))

    def test_judge_items_show_the_source_and_never_the_arm(self):
        self.assertEqual(len(self.items), 2 * len(self.s2["targets"]))
        by_target = {}
        for it in self.items:
            self.assertNotIn(it["arm"], it["text"])
            self.assertNotIn(it["arm"], it["item"])
            t = next(x for x in self.s2["targets"] if x["id"] == it["target"])
            a, b = it["text"].split("=== Thread A (earlier) ===\n", 1)[1].split("\n\n=== Thread B (later) ===\n", 1)
            self.assertTrue(a.startswith("/misc/ — thread %d\n" % SOURCES[t["source"]]["no"]))
            self.assertTrue(b.startswith("/misc/ — thread %d\n" % t["no"]))
            by_target.setdefault(it["target"], []).append(a)
        self.assertTrue(all(len(v) == 2 and v[0] == v[1] for v in by_target.values()))

    def test_the_judge_and_the_verdict_are_reported(self):
        self.assertEqual((self.summary["h3"]["lore_only"], self.summary["h3"]["sham_only"]), (self.planted(), 0))
        self.assertTrue(self.summary["l4"].startswith("partly: source material"))   # fakes are not confirmed
        with open(os.path.join(self.tmp, "RESULTS.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("## H1: the source identified two hops away (primary)", text)

    def test_what_it_writes_is_the_same_bytes_on_windows_and_linux(self):
        written = [os.path.join(self.tmp, n) for n in ("RESULTS.md", "results.json")]
        written += glob.glob(os.path.join(self.root, "misc", "*.json"))[:3]
        H.write_json(os.path.join(self.tmp, "schedule.json"), self.s2)
        written.append(os.path.join(self.tmp, "schedule.json"))
        for p in written:
            with open(p, "rb") as f:
                self.assertNotIn(b"\r", f.read(), p)


if __name__ == "__main__":
    unittest.main()
