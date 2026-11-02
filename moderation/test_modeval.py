"""python -m unittest discover -s moderation -p "test_*.py" """
import json, os, shutil, tempfile, unittest

import modeval as M


class Gate(unittest.TestCase):
    def test_every_gate_term_has_a_category(self):
        self.assertEqual(set(M.GATE) | set(M.JP_GATE), set(M.GATE_CATEGORY))
        self.assertTrue(set(M.GATE_CATEGORY.values()) <= set(M.CATS))

    def test_keyword_matches_like_the_live_gate(self):
        self.assertEqual(M.keyword("I WANT TO DIE"), (["want to die"], ["self_harm"]))
        self.assertEqual(M.keyword("this is spicy food"), (["spic"], ["hate_slur"]))
        self.assertEqual(M.keyword("ok gonna kill you, test"),
                         (["kill you", "gonna kill"], ["violence_threat"]))
        self.assertEqual(M.keyword("もう死にたい"), (["死にたい"], ["self_harm"]))
        self.assertEqual(M.keyword("お前殺すぞ"), (["殺すぞ"], ["violence_threat"]))
        self.assertEqual(M.keyword("nice weather"), ([], []))

    def test_inside_word(self):
        cases = [("spicy food", "spic", True), ("what a spic.", "spic", False),
                 ("a spic", "spic", False), ("he will kill himself", "kill him", True),
                 ("i'll kill him.", "kill him", False), ("grape juice", "rape", True),
                 ("a raccoon", "coon", True), ("cocktail hour", "cock", True),
                 ("spicy spic", "spic", False), ("a fag end", "fag ", False),
                 ("もう死にたい", "死にたい", None)]
        for text, term, want in cases:
            self.assertEqual(M.inside_word(text, term), want, (text, term))

    def test_word_boundary_gate_drops_innocent_words_and_keeps_inflections(self):
        cases = [("spicy food is suspicious", []), ("what a spic", ["spic"]),
                 ("so many niggers here", ["nigger"]), ("she was raped", ["rape"]),
                 ("grapes and skyscrapers", []), ("a fag dream", ["fag "]), ("fags.", ["fag "]),
                 ("cocktail hour", []), ("cocks", ["cock"]), ("a thorny bush", []),
                 ("kill yourself", ["kill you"]), ("もう死にたい", ["死にたい"])]
        for text, want in cases:
            self.assertEqual(M.keyword_wb(text), want, text)

    def test_containing_words(self):
        self.assertEqual(M.containing_words("Spicy food is suspicious, spic", "spic"),
                         ["spicy", "suspicious"])
        self.assertEqual(M.containing_words("he will kill himself", "kill him"), ["kill himself"])
        self.assertEqual(M.containing_words("a fag dream", "fag "), [])
        self.assertEqual(M.containing_words("a xfag dream", "fag "), ["xfag"])


class Text(unittest.TestCase):
    def test_lang_of(self):
        self.assertEqual(M.lang_of("hello there", "orig"), "en")
        self.assertEqual(M.lang_of("こんにちは", "jp"), "ja")
        self.assertEqual(M.lang_of("ｷﾀ━━", "jp"), "ja")
        self.assertEqual(M.lang_of("草", "jp"), "ja")
        self.assertEqual(M.lang_of("草", "bakeoff"), "other")
        self.assertEqual(M.lang_of("ok then", "jp"), "en")

    def test_is_stub(self):
        for s in ["[post withheld]", "[12 posts withheld - auto-quarantined]", "[1 post withheld]",
                  "[withheld]", "[3 posts withheld]"]:
            self.assertTrue(M.is_stub(s), s)
        for s in ["[img=3]\ndo you mean this", "[delphine]: lol", "[1]", "post withheld", ""]:
            self.assertFalse(M.is_stub(s), s)

    def test_lexicon_groups(self):
        self.assertEqual(M.lexicon_groups("found a corpse in the woods", "en"), ["violence"])
        self.assertEqual(M.lexicon_groups("she was naked", "en"), ["sexual"])
        self.assertEqual(M.lexicon_groups("the kids were playing", "en"), ["minors"])
        self.assertEqual(M.lexicon_groups("cumulative weather data", "en"), [])
        self.assertEqual(M.lexicon_groups("人が死んだ", "ja"), ["violence"])
        self.assertEqual(M.lexicon_groups("いい天気", "ja"), [])


def write(root, rel, obj):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if rel.endswith(".jsonl"):
            f.write("".join(json.dumps(o) + "\n" for o in obj))
        else:
            json.dump(obj, f)


class Build(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        write(self.root, "quarantine/q1.json", {"matched": ["kill you"], "thread": {"id": 1, "posts": [
            {"text": "op text"}, {"text": "i will kill you"}, {"text": "same line"}]}})
        write(self.root, "spike/quarantine.jsonl", [
            {"thread": 7, "matched": ["want to die"], "post": {"who": "a", "ts": "x1", "t": 1,
                                                                "text": "i want to die"}}])
        write(self.root, "spike/remote/board-v2.json", {"threads": [{"no": 7, "posts": [
            {"who": "b", "ts": "x0", "text": "board op"},
            {"who": "a", "ts": "x1", "text": "[post withheld]", "withheld": True}]}]})
        write(self.root, "threads.x.json", {"threads": [
            {"id": 1, "posts": [{"text": "same line"}, {"text": "spicy noodles tonight"},
                                {"text": "[3 posts withheld]"}, {"text": "found a corpse"},
                                {"text": "nice weather"}, {"text": "nice weather"}]},
            {"id": 2, "quarantined": True, "posts": [
                {"text": "op two"}, {"text": "[5 posts withheld - auto-quarantined]"}]}]})
        write(self.root, "spike/remote/jp-a.json", {"threads": [{"posts": [
            {"text": "人が死んだ"}, {"text": "こんにちは"}]}]})
        write(self.root, "spike/remote/bakeoff-a.json", {"threads": [{"posts": [
            {"text": "hello there"}, {"text": "[post withheld]", "withheld": True}, {"text": ""}]}]})

    def tearDown(self):
        shutil.rmtree(self.root)

    def built(self, sizes=None):
        manifest, private, strata = M.build(self.root, sizes or {})
        by_text = {p["text"]: m for m, p in zip(manifest, private)}
        return manifest, private, strata, by_text

    def test_strata_follow_source_then_gate_then_lexicon(self):
        _, _, _, by = self.built({"risk": 99, "plain": 99})
        want = {"op text": "quarantine", "i will kill you": "quarantine", "same line": "quarantine",
                "i want to die": "withheld", "spicy noodles tonight": "gate-hit",
                "found a corpse": "risk/orig", "nice weather": "plain/orig", "op two": "plain/orig",
                "人が死んだ": "risk/jp", "こんにちは": "plain/jp", "hello there": "plain/bakeoff",
                "board op": "plain/board"}
        self.assertEqual({t: m["stratum"] for t, m in by.items()}, want)

    def test_duplicates_collapse_into_the_first_source(self):
        _, _, _, by = self.built({"risk": 99, "plain": 99})
        self.assertEqual((by["same line"]["family"], by["same line"]["copies"]), ("quarantine", 2))
        self.assertEqual(by["nice weather"]["copies"], 2)

    def test_manifest_carries_no_text_and_private_rows_do(self):
        manifest, private, _, _ = self.built({"risk": 99, "plain": 99})
        for m in manifest:
            self.assertEqual(set(m), M.PUBLIC_KEYS["manifest"])
        self.assertEqual([m["id"] for m in manifest], [p["id"] for p in private])
        self.assertTrue(all(p["text"] for p in private))

    def test_withheld_post_gets_its_board_context(self):
        _, private, _, _ = self.built({"risk": 99, "plain": 99})
        row = next(p for p in private if p["text"] == "i want to die")
        self.assertEqual(row["context"], ["board op"])

    def test_sampled_strata_are_weighted_and_census_strata_are_not(self):
        manifest, _, strata, by = self.built({"risk": 99, "plain": 1})
        self.assertEqual(strata["strata"]["plain/orig"]["population"], 2)
        self.assertEqual(strata["strata"]["plain/orig"]["sampled"], 1)
        orig_plain = [m for m in manifest if m["stratum"] == "plain/orig"]
        self.assertEqual(len(orig_plain), 1)
        self.assertEqual(orig_plain[0]["weight"], 2.0)
        self.assertEqual(by["i will kill you"]["weight"], 1.0)

    def test_sample_ignores_input_order(self):
        cands = [{"sha256": "%064x" % i} for i in range(50)]
        a = M.sample(cands, 7, "plain/orig")
        b = M.sample(list(reversed(cands)), 7, "plain/orig")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 7)
        self.assertNotEqual(a, M.sample(cands, 7, "plain/jp"))
        self.assertEqual(len(M.sample(cands, 99, "x")), 50)

    def test_stub_and_empty_posts_are_counted_not_kept(self):
        _, private, strata, _ = self.built({"risk": 99, "plain": 99})
        self.assertFalse(any(M.is_stub(p["text"]) or not p["text"].strip() for p in private))
        # A marker's text survives when the board logged the post or the thread was quarantined.
        self.assertEqual(strata["skipped"], {"withheld_kept": {"board": 1, "orig": 1},
                                             "withheld_lost": {"bakeoff": 1, "orig": 1},
                                             "empty": {"bakeoff": 1}})


class Labels(unittest.TestCase):
    def test_normalize_labels(self):
        self.assertEqual(M.normalize_labels(["none"]), [])
        self.assertEqual(M.normalize_labels(["sexual_minors"]), ["sexual", "sexual_minors"])
        self.assertEqual(M.normalize_labels(["violence_threat", "hate_slur"]),
                         ["hate_slur", "violence_threat"])
        for bad in [[], ["none", "sexual"], ["gore"]]:
            with self.assertRaises(ValueError):
                M.normalize_labels(bad)

    def test_owner_sheet_puts_decisive_items_first(self):
        rows = [dict(id="e", ai1=[], unsure=False, ai2=None, flags=[False, False]),
                dict(id="d", ai1=[], unsure=False, ai2=None, flags=[True, False]),
                dict(id="c", ai1=[], unsure=False, ai2=["sexual"], flags=[False, False]),
                dict(id="b", ai1=[], unsure=True, ai2=None, flags=[False, False]),
                dict(id="a", ai1=["self_harm"], unsure=False, ai2=None, flags=[False, False]),
                dict(id="f", ai1=["sexual"], unsure=False, ai2=["sexual"], flags=[True, False])]
        self.assertEqual(M.sheet_groups(rows, spot=0),
                         [("a", 1), ("f", 1), ("c", 2), ("b", 2), ("d", 3)])
        self.assertEqual(M.sheet_groups(rows, spot=1.0)[-1], ("e", 4))

    def test_effective_label_prefers_the_owner(self):
        row = {"id": "a", "ai1": {"labels": ["none"], "unsure": False}}
        self.assertEqual(M.effective(row), ([], "ai1"))
        row["owner"] = {"labels": ["self_harm"]}
        self.assertEqual(M.effective(row), (["self_harm"], "owner"))


class Stats(unittest.TestCase):
    def test_wilson(self):
        lo, hi = M.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.23659, places=4)
        self.assertAlmostEqual(hi, 0.76341, places=4)
        lo, hi = M.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.27754, places=4)
        self.assertEqual(M.wilson(0, 0), (None, None))

    def test_prf(self):
        p, r, f = M.prf(8, 2, 8)
        self.assertEqual((p, r), (0.8, 0.5))
        self.assertAlmostEqual(f, 0.8 / 1.3)
        self.assertEqual(M.prf(0, 0, 4), (None, 0.0, None))
        self.assertEqual(M.prf(0, 3, 0), (0.0, None, None))

    def test_kappa(self):
        pairs = [(1, 1)] * 20 + [(1, 0)] * 5 + [(0, 1)] * 10 + [(0, 0)] * 15
        self.assertAlmostEqual(M.kappa([(bool(a), bool(b)) for a, b in pairs]), 0.4)
        self.assertIsNone(M.kappa([(False, False)] * 3))
        self.assertIsNone(M.kappa([]))

    def test_gate_split(self):
        rows = [dict(truth=True, gate=True, pred=True), dict(truth=True, gate=True, pred=False),
                dict(truth=True, gate=False, pred=True), dict(truth=False, gate=True, pred=True)]
        self.assertEqual(M.gate_split(rows), ((1, 2), (1, 1)))

    def test_over_blocking_table(self):
        rows = [dict(truth=[], kw=dict(terms=["spic"], inside_word=True, words=["spicy"])),
                dict(truth=[], kw=dict(terms=["spic"], inside_word=True, words=["suspicious"])),
                dict(truth=["hate_slur"], kw=dict(terms=["nigger"], inside_word=True, words=["niggers"])),
                dict(truth=["hate_slur"], kw=dict(terms=["spic"], inside_word=False, words=[])),
                dict(truth=[], kw=dict(terms=["kill you", "kill me"], inside_word=False, words=[]))]
        self.assertEqual(M.over_blocking(rows), [
            ("spic", 3, 1, 2, 2, ["spicy", "suspicious"]),
            ("kill me", 1, 0, 1, 0, []),
            ("kill you", 1, 0, 1, 0, []),
            ("nigger", 1, 1, 0, 0, [])])

    def test_weighted_confusion(self):
        rows = [dict(truth=True, pred=True, w=1.0), dict(truth=True, pred=False, w=3.0),
                dict(truth=False, pred=True, w=2.0), dict(truth=False, pred=False, w=10.0)]
        self.assertEqual(M.confusion(rows), (1, 1, 1, 1))
        self.assertEqual(M.confusion(rows, weighted=True), (1.0, 2.0, 3.0, 10.0))


OPENAI_RESULT = {
    "flagged": True,
    "categories": {"harassment": True, "harassment/threatening": False, "hate": False,
                   "hate/threatening": False, "illicit": False, "illicit/violent": False,
                   "self-harm": True, "self-harm/instructions": False, "self-harm/intent": True,
                   "sexual": False, "sexual/minors": False, "violence": False,
                   "violence/graphic": False},
    "category_scores": {"harassment": 0.61, "harassment/threatening": 0.02, "hate": 0.003,
                        "hate/threatening": 0.0001, "illicit": 0.001, "illicit/violent": 0.0004,
                        "self-harm": 0.93, "self-harm/instructions": 0.01, "self-harm/intent": 0.88,
                        "sexual": 0.04, "sexual/minors": 0.001, "violence": 0.2,
                        "violence/graphic": 0.003},
}


class Classifiers(unittest.TestCase):
    def test_every_openai_category_is_mapped_or_explicitly_dropped(self):
        self.assertEqual(set(M.OPENAI_MAP), set(OPENAI_RESULT["categories"]))

    def test_openai_categories_map_to_ours(self):
        self.assertEqual(M.openai_cats(OPENAI_RESULT["categories"]), ["self_harm"])
        self.assertEqual(M.openai_cats_at(OPENAI_RESULT["category_scores"], 0.1),
                         ["self_harm", "violence_threat"])
        self.assertEqual(M.openai_cats_at(OPENAI_RESULT["category_scores"], 0.95), [])

    def test_narrow_mapping_ignores_depicted_violence(self):
        scores = dict(OPENAI_RESULT["category_scores"], **{"self-harm": 0.0, "self-harm/intent": 0.0})
        self.assertEqual(M.openai_cats_at(scores, 0.1), ["violence_threat"])
        self.assertEqual(M.openai_cats_at(scores, 0.1, M.OPENAI_NARROW), [])
        scores["harassment/threatening"] = 0.5
        self.assertEqual(M.openai_cats_at(scores, 0.1, M.OPENAI_NARROW), ["violence_threat"])

    def test_proposal_is_the_shipped_gate(self):
        import pubgate
        for k, c in pubgate.CATEGORIES.items():
            self.assertEqual(M.OPENAI_MAP[k], c, k)
        for scores in [dict.fromkeys(OPENAI_RESULT["category_scores"], 0.0),
                       dict(OPENAI_RESULT["category_scores"]),
                       dict(dict.fromkeys(OPENAI_RESULT["category_scores"], 0.0), violence=0.9),
                       dict(dict.fromkeys(OPENAI_RESULT["category_scores"], 0.0), sexual=0.3)]:
            self.assertEqual(bool(M.openai_cats_at(scores, M.PROPOSAL, M.OPENAI_NARROW)),
                             bool(pubgate.flagged(scores)), scores)
        for text in ["spicy food", "what a spic", "she was raped", "もう死にたい", "kill yourself"]:
            self.assertEqual(M.keyword_wb(text),
                             pubgate.keyword_hits(text, pubgate.term_patterns(M.KEYWORDS)))

    def test_per_category_thresholds(self):
        scores = dict.fromkeys(OPENAI_RESULT["category_scores"], 0.0)
        scores.update({"self-harm": 0.04, "sexual": 0.04})
        self.assertEqual(M.openai_cats_at(scores, {"self_harm": 0.03, "sexual": 0.3}, M.OPENAI_NARROW),
                         ["self_harm"])

    def test_context_input_puts_the_parent_post_first(self):
        self.assertEqual(M.ctx_input({"text": "second", "context": ["op", "first"]}),
                         "first\n\nsecond")
        self.assertEqual(M.ctx_input({"text": "first post", "context": []}), "first post")

    def test_openai_body_pins_the_snapshot(self):
        body = M.openai_body(["a", "b"])
        self.assertEqual(body, {"model": "omni-moderation-2024-09-26", "input": ["a", "b"]})

    def test_llamaguard_parse(self):
        self.assertEqual(M.llamaguard_parse("safe"), (False, [], []))
        self.assertEqual(M.llamaguard_parse("\n\nunsafe\nS11"), (True, ["S11"], ["self_harm"]))
        self.assertEqual(M.llamaguard_parse("unsafe\nS10,S1"),
                         (True, ["S1", "S10"], ["hate_slur", "violence_threat"]))
        self.assertEqual(M.llamaguard_parse("unsafe\nS4"),
                         (True, ["S4"], ["sexual", "sexual_minors"]))
        self.assertEqual(M.llamaguard_parse("unsafe\nS2"), (True, ["S2"], []))
        self.assertIsNone(M.llamaguard_parse("I cannot help with that"))

    def test_llamaguard_body_is_deterministic_and_short(self):
        body = M.llamaguard_body("some post")
        self.assertEqual(body["model"], "meta-llama/llama-guard-4-12b")
        self.assertEqual(body["messages"], [{"role": "user", "content": "some post"}])
        self.assertEqual(body["temperature"], 0)
        self.assertLessEqual(body["max_tokens"], 20)

    def test_budget_stops_before_overspending(self):
        b = M.Budget(0.05)
        self.assertTrue(b.add(0.02))       # 0.02 spent, another 0.02 still fits
        self.assertFalse(b.add(0.02))      # 0.04 spent, another 0.02 would pass the cap
        self.assertAlmostEqual(b.spent, 0.04)


class Committed(unittest.TestCase):
    """The committed files carry ids, hashes, labels and scores, never post text."""

    def test_public_files_hold_only_allowed_keys_and_short_strings(self):
        def strings(x):
            if isinstance(x, str):
                yield x
            elif isinstance(x, dict):
                for k, v in x.items():
                    yield k
                    yield from strings(v)
            elif isinstance(x, list):
                for v in x:
                    yield from strings(v)

        for kind, path in M.public_files():
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    row = json.loads(line)
                    where = "%s:%d" % (os.path.basename(path), n)
                    self.assertTrue(set(row) <= M.PUBLIC_KEYS[kind], "%s %s" % (where, set(row)))
                    self.assertLessEqual(max(map(len, strings(row))), 80, where)

    def test_metrics_md_is_current(self):
        if not os.path.exists(M.METRICS):
            self.skipTest("no METRICS.md yet")
        with open(M.METRICS, encoding="utf-8") as f:
            self.assertEqual(f.read(), M.report_text(), "run: python moderation/modeval.py report")


if __name__ == "__main__":
    unittest.main()
