"""python -m unittest discover -s spike -p "test_pubgate.py" """
import json, os, random, shutil, tempfile, unittest

import pubgate as P

TERMS = ["kill you", "spic", "rape", "fag ", "nigger", "cock", "死にたい"]
SCORES = dict.fromkeys(["harassment", "harassment/threatening", "hate", "hate/threatening",
                        "illicit", "illicit/violent", "self-harm", "self-harm/instructions",
                        "self-harm/intent", "sexual", "sexual/minors", "violence",
                        "violence/graphic"], 0.0)


def scores(**kw):
    return dict(SCORES, **kw)


class Keywords(unittest.TestCase):
    def test_word_boundaries_with_plain_inflections(self):
        pats = P.term_patterns(TERMS)
        cases = [("spicy food is suspicious", []), ("what a spic", ["spic"]),
                 ("so many niggers here", ["nigger"]), ("she was raped", ["rape"]),
                 ("grapes and skyscrapers", []), ("a fag dream", ["fag "]), ("fags.", ["fag "]),
                 ("cocktail hour", []), ("cocks", ["cock"]), ("kill yourself", ["kill you"]),
                 ("もう死にたい", ["死にたい"]), ("SPIC", ["spic"])]
        for text, want in cases:
            self.assertEqual(P.keyword_hits(text, pats), want, text)


class Classifier(unittest.TestCase):
    def test_flagged_uses_our_categories_at_the_threshold(self):
        self.assertEqual(P.flagged(scores(violence=0.99, harassment=0.99)), [])
        self.assertEqual(P.flagged(scores(sexual=0.3)), ["sexual"])
        self.assertEqual(P.flagged(scores(sexual=0.29)), [])
        self.assertEqual(P.flagged(dict(SCORES, **{"harassment/threatening": 0.5, "self-harm/intent": 0.4})),
                         ["harassment/threatening", "self-harm/intent"])

    def test_request_pins_the_snapshot(self):
        self.assertEqual(P.request(["a", "b"]), {"model": "omni-moderation-2024-09-26",
                                                  "input": ["a", "b"]})


class Gate(unittest.TestCase):
    def gate(self, results=None, fail=False):
        calls = []

        def moderate(texts):
            calls.append(list(texts))
            if fail:
                raise RuntimeError("HTTP 503")
            return [dict(SCORES, **(results or {})) for _ in texts]

        return P.Gate(TERMS, moderate=moderate), calls

    def test_clean_post_passes(self):
        g, calls = self.gate()
        v = g.check("the stove was off all along")
        self.assertFalse(v["hold"])
        self.assertEqual(calls, [["the stove was off all along"]])

    def test_keyword_hit_holds_without_a_model_verdict(self):
        g, _ = self.gate()
        v = g.check("i will kill you")
        self.assertTrue(v["hold"])
        self.assertEqual(v["terms"], ["kill you"])

    def test_classifier_hit_holds(self):
        g, _ = self.gate({"self-harm/intent": 0.8})
        v = g.check("a post with no listed word")
        self.assertEqual((v["hold"], v["categories"]), (True, ["self-harm/intent"]))

    def test_unreachable_classifier_holds_the_post(self):
        g, _ = self.gate(fail=True)
        v = g.check("anything at all")
        self.assertTrue(v["hold"])
        self.assertIn("503", v["error"])

    def test_keyword_only_gate_never_calls_out(self):
        g = P.Gate(TERMS)
        self.assertFalse(g.check("the stove was off all along")["hold"])
        self.assertTrue(g.check("i will kill you")["hold"])

    def test_reply_is_also_scored_with_its_parent(self):
        g, calls = self.gate()
        g.check("yes", before="earlier post")
        self.assertEqual(calls, [["yes", "earlier post\n\nyes"]])

    def test_log_entry_has_the_reasons_and_short_scores(self):
        g, _ = self.gate({"sexual": 0.91234567})
        e = P.log_entry(g.check("x"))
        self.assertEqual(e["categories"], ["sexual"])
        self.assertEqual(e["scores"]["sexual"], 0.9123)
        self.assertEqual(set(e), {"terms", "categories", "scores", "error"})


class LiveBoard(unittest.TestCase):
    """The board withholds a held post before anyone sees it and keeps its text in the log."""

    def setUp(self):
        import live_board as LB
        self.LB, self.dir = LB, tempfile.mkdtemp()
        self.saved = LB.STATE, LB.QUARANTINE
        LB.STATE = os.path.join(self.dir, "board.json")
        LB.QUARANTINE = os.path.join(self.dir, "quarantine.jsonl")

    def tearDown(self):
        self.LB.STATE, self.LB.QUARANTINE = self.saved
        shutil.rmtree(self.dir)

    def test_held_reply_is_withheld_and_logged_with_its_text(self):
        board = self.LB.Board(["gemma"], random.Random(1), P.Gate(TERMS))
        who = next(iter(board.regulars))
        p = board.post(who, "ts", "i will kill you", "stop")
        held = board.screen(p, 4471)
        self.assertTrue(held)
        self.assertEqual((p["text"], p["withheld"]), ("[post withheld]", True))
        with open(self.LB.QUARANTINE, encoding="utf-8") as f:
            row = json.loads(f.read())
        self.assertEqual((row["thread"], row["post"]["text"], row["matched"]),
                         (4471, "i will kill you", ["kill you"]))

    def test_clean_reply_is_untouched(self):
        board = self.LB.Board(["gemma"], random.Random(1), P.Gate(TERMS))
        p = board.post(next(iter(board.regulars)), "ts", "the stove was off", "stop")
        self.assertFalse(board.screen(p, 4471))
        self.assertEqual(p["text"], "the stove was off")
        self.assertFalse(os.path.exists(self.LB.QUARANTINE))


class JapaneseBakeoff(unittest.TestCase):
    def test_held_post_is_withheld_and_logged(self):
        import jp_bakeoff as JP
        d = tempfile.mkdtemp()
        try:
            texts = iter(["普通のレス", "もう死にたい"] + ["普通のレス"] * 40)
            log = os.path.join(d, "q.jsonl")
            t = JP.thread(0, lambda *a: next(texts), "5ch", "test", P.Gate(JP.JP_GATE), log)
            held = [p for p in t["posts"] if p.get("withheld")]
            self.assertEqual([p["text"] for p in held], ["[post withheld]"])
            with open(log, encoding="utf-8") as f:
                row = json.loads(f.read())
            self.assertEqual((row["post"]["text"], row["matched"]), ("もう死にたい", ["死にたい"]))
        finally:
            shutil.rmtree(d)


class ModalBoard(unittest.TestCase):
    """The key Modal hands the board and the Japanese runs resolves like the scripts' own."""

    def setUp(self):
        import sys
        from unittest import mock
        self.dir = tempfile.mkdtemp()
        fake = mock.MagicMock()
        fake.Secret.from_dict.side_effect = lambda d: d
        self.patches = [mock.patch.dict(sys.modules, {"modal": fake}),
                        mock.patch.dict(os.environ, {}, clear=False)]
        for p in self.patches:
            p.start()
        os.environ.pop("OPENAI_API_KEY", None)
        sys.modules.pop("modal_board", None)
        import modal_board
        self.MB = modal_board
        self.MB.ROOT = self.dir

    def tearDown(self):
        import sys
        for p in reversed(self.patches):
            p.stop()
        sys.modules.pop("modal_board", None)
        shutil.rmtree(self.dir)

    def env_file(self, text):
        with open(os.path.join(self.dir, ".env"), "w", encoding="utf-8") as f:
            f.write(text)

    def test_key_from_the_environment_reaches_the_secret(self):
        os.environ["OPENAI_API_KEY"] = "sk-env"
        self.assertEqual(self.MB._openai_secret(), {"OPENAI_API_KEY": "sk-env"})

    def test_environment_wins_over_env_file(self):
        self.env_file("OPENAI_API_KEY=sk-file\n")
        os.environ["OPENAI_API_KEY"] = "sk-env"
        self.assertEqual(self.MB._openai_secret(), {"OPENAI_API_KEY": "sk-env"})

    def test_quoted_env_file_value_is_unquoted(self):
        self.env_file('OPENAI_API_KEY="sk-quoted"\n')
        self.assertEqual(self.MB._openai_secret(), {"OPENAI_API_KEY": "sk-quoted"})


if __name__ == "__main__":
    unittest.main()
