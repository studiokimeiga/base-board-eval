"""Round 9's generation logic, checked offline: `python -m unittest discover -s spike -p "test_*.py"`.
Every API is stubbed, so nothing here touches the network or spends anything."""
import json, os, sys, tempfile, threading, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import round3 as R

# Written into PREREGISTRATION-ROUND9.md before generation; a change here changes the design.
PLAN = [[6, 11, 22], [3, 15, 20], [2, 16, 23], [3, 13, 20],
        [9, 13, 20], [8, 10, 18], [2, 15, 20], [9, 11, 18]]


def chat_post_number(doc):
    """The chat instruction carries the thread without the new post's header (the author is named
    in the instruction instead), so it holds one header fewer than the raw prompt."""
    return R.post_number(doc.split("Here is an imageboard thread so far:\n\n", 1)[1]) + 1


class Run:
    """Runs round3.main() for an arm with stub writers, which get the number of the post they
    write; records every prompt each writer saw."""

    def __init__(self, arm, gemini=None, naif=None, out=None):
        self.arm, self.prompts, self.naif_prompts = arm, [], []
        self.gemini = gemini or (lambda n: "post %d" % n)
        self.naif = naif or (lambda n: "naif post %d" % n)
        self.out = out or tempfile.mkdtemp()
        self.lock = threading.Lock()

    def fake_post_json(self, url, key, body, timeout=240):
        doc = body["messages"][0]["content"]
        with self.lock:
            self.prompts.append(doc)
        text = self.gemini(chat_post_number(doc))
        return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"cost": 0.001}}

    def fake_llama(self, port, prompt, stops):
        with self.lock:
            self.naif_prompts.append(prompt)
        return self.naif(R.post_number(prompt)), "eos"

    def __call__(self):
        env = dict(R.ENV, OPENROUTER_API_KEY="test")
        with mock.patch.object(R, "post_json", self.fake_post_json), \
                mock.patch.object(R, "LLAMA_COMPLETE", self.fake_llama), \
                mock.patch.object(R, "ENV", env), \
                mock.patch.object(R.G, "BOARD_HEADER", R.X_HEADER), \
                mock.patch.dict(R.SPEND, {"usd": 0.0, "openai_tokens": 0, "calls": 0}), \
                mock.patch.dict(os.environ, {"BAKEOFF_OUT": self.out}), \
                mock.patch.object(sys, "argv", ["round3.py", self.arm]), \
                mock.patch("builtins.print"):
            R.main()
        with open(os.path.join(self.out, "bakeoff-%s.json" % self.arm), encoding="utf-8") as f:
            return json.load(f)


class Plan(unittest.TestCase):
    def test_small_model_posts_are_the_preregistered_ones(self):
        R.scaffold()
        got = [R.naif_posts(R.opener_index(t)) for t in R.OPENER_PICKS]
        self.assertEqual(got, PLAN)

    def test_one_small_model_post_per_third_and_never_the_op(self):
        d = Run("rolesshort9")()
        for t, posts in zip(d["threads"], PLAN):
            op = t["posts"][0]["who"]
            for (lo, hi), n in zip(R.NAIF_BLOCKS, posts):
                self.assertTrue(lo <= n <= hi)
                self.assertNotEqual(t["posts"][n - 1]["who"], op)


class Generation(unittest.TestCase):
    def test_every_post_number_is_seen_correctly(self):
        run = Run("gemini9")
        d = run()
        self.assertEqual(len(d["threads"]), 8)
        for t in d["threads"]:
            self.assertEqual([p["n"] for p in t["posts"]], list(range(1, 25)))
            self.assertEqual([p["text"] for p in t["posts"][1:]], ["post %d" % n for n in range(2, 25)])

    def test_neutral_header_replaces_the_board_label_and_nothing_else(self):
        runs = {arm: Run(arm) for arm in ("gemini9", "gemini9neutral")}
        data = {arm: run() for arm, run in runs.items()}
        for arm, header in (("gemini9", "/x/ — thread 4471"), ("gemini9neutral", "thread 4471")):
            self.assertEqual(data[arm]["header"], header)
            for doc in runs[arm].prompts:
                self.assertTrue(doc.startswith("Here is an imageboard thread so far:\n\n%s\n\n" % header))
        x = sorted(p.replace("/x/ — thread 4471", "thread 4471", 1) for p in runs["gemini9"].prompts)
        self.assertEqual(x, sorted(runs["gemini9neutral"].prompts))

    def test_gate_withholds_a_post_before_the_next_prompt(self):
        def gemini(n):
            return "this salsa is spicy" if n == 5 else "post %d" % n   # "spic" is on the list
        run = Run("rolesshort9", gemini=gemini)
        d = run()
        for t in d["threads"]:
            p5 = t["posts"][4]
            self.assertEqual(p5["text"], "[post withheld]")
            self.assertTrue(p5["withheld"])
            self.assertTrue(p5["stop"].startswith("withheld"))
            self.assertNotIn("withheld", t["posts"][5])
        later = [p for p in run.prompts if chat_post_number(p) > 5]
        self.assertTrue(later)
        for doc in later:
            self.assertNotIn("spicy", doc)
            self.assertIn("[post withheld]", doc)
        with open(os.path.join(run.out, "quarantine-rolesshort9.jsonl"), encoding="utf-8") as f:
            q = [json.loads(line) for line in f]
        self.assertEqual(len(q), 8)
        self.assertEqual({(x["n"], x["text"], tuple(x["matched"])) for x in q},
                         {(5, "this salsa is spicy", ("spic",))})

    def test_small_model_writes_exactly_its_posts(self):
        run = Run("rolesshort9naif")
        d = run()
        self.assertEqual(sorted(R.post_number(p) for p in run.naif_prompts),
                         sorted(n for posts in PLAN for n in posts))
        for t, posts in zip(d["threads"], PLAN):
            self.assertEqual(t["naif_posts"], posts)
            for p in t["posts"][1:]:
                naif = p["n"] in posts
                self.assertEqual(p["model"], R.NAIF_LABEL if naif else R.GEMINI_LABEL)
                self.assertEqual(p["text"], ("naif post %d" if naif else "post %d") % p["n"])
                self.assertNotIn("arm", p)

    def test_small_model_posts_pass_the_gate_too(self):
        run = Run("rolesshort9naif", naif=lambda n: "kill you all")
        d = run()
        for t in d["threads"]:
            for n in t["naif_posts"]:
                self.assertEqual(t["posts"][n - 1]["text"], "[post withheld]")

    def test_rerun_keeps_finished_threads(self):
        first = Run("gemini9")
        d = first()
        path = os.path.join(first.out, "bakeoff-gemini9.json")
        d["threads"] = d["threads"][:5]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
        again = Run("gemini9", out=first.out)
        d2 = again()
        self.assertEqual(len(again.prompts), 3 * 23)
        self.assertEqual([t["opener"] for t in d2["threads"]], R.OPENER_PICKS)
        # spend is cumulative: the first run paid for all 8 threads, the rerun for 3 more
        self.assertAlmostEqual(d2["spend"]["usd"], 0.001 * 23 * (8 + 3))


REMOTE = os.path.join(R.SPIKE, "remote")


def real(arm):
    with open(os.path.join(REMOTE, "bakeoff-%s.json" % arm), encoding="utf-8") as f:
        return json.load(f)


@unittest.skipUnless(all(os.path.exists(os.path.join(REMOTE, "bakeoff-%s.json" % a)) for a in R.R9),
                     "round 9's private files aren't here")
class RealFiles(unittest.TestCase):
    """The generated round 9 files, where they exist, against the pre-registered design."""

    def test_every_arm_wrote_eight_full_threads_under_its_header(self):
        for arm, header in R.R9.items():
            d = real(arm)
            self.assertEqual((d["header"], d["gate"]), (header, "before context"), arm)
            self.assertEqual([t["opener"] for t in d["threads"]], R.OPENER_PICKS, arm)
            for t in d["threads"]:
                self.assertEqual([p["n"] for p in t["posts"]], list(range(1, 25)), arm)

    def test_the_small_model_wrote_exactly_the_planned_posts(self):
        for arm in R.R9:
            for t, plan in zip(real(arm)["threads"], PLAN):
                mine = [p["n"] for p in t["posts"][1:] if p["model"] == R.NAIF_LABEL]
                self.assertEqual(mine, plan if arm == "rolesshort9naif" else [], arm)
                self.assertTrue(all(p["model"] in (R.NAIF_LABEL, R.GEMINI_LABEL) for p in t["posts"][1:]))

    def test_no_stored_post_holds_a_gate_term(self):
        for arm in R.R9:
            for t in real(arm)["threads"]:
                for p in t["posts"][1:]:
                    self.assertFalse([h for h in R.GATE if h in p["text"].lower()], (arm, p["n"]))
                    self.assertEqual(bool(p.get("withheld")), p["stop"].startswith("withheld"))

    def test_every_arm_has_the_same_scaffold_as_a_dry_run(self):
        R.scaffold()
        for i, text in enumerate(R.OPENER_PICKS):
            with mock.patch.object(R.G, "complete", lambda port, prompt, stops: ("", "dry run")), \
                    mock.patch("sys.stdout"):
                dry = [(p["who"], p["ts"]) for p in R.G.gen_thread(R.opener_index(text), 0, 0)["posts"]]
            for arm in R.R9:
                self.assertEqual([(p["who"], p["ts"]) for p in real(arm)["threads"][i]["posts"]], dry, arm)


if __name__ == "__main__":
    unittest.main()
