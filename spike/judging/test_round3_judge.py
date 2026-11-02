"""round3_judge.py's round 9 tools, offline: python -m unittest discover -s spike/judging -p "test_*.py"
The API is stubbed; nothing here touches the network or the real packets."""
import importlib.util, json, os, sys, tempfile, threading, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import round3


def load_judge(round_):
    """round3_judge.py picks its round from argv at import, so load a copy for round 9."""
    argv, sys.argv = sys.argv, ["round3_judge.py", "test", round_]
    try:
        spec = importlib.util.spec_from_file_location("round3_judge_" + round_,
                                                      os.path.join(HERE, "round3_judge.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


RJ = load_judge("r9")
SCORE = {"interest": 3, "humour": 2, "emergence": 3, "coherence": 4, "variety": 3, "overall": 3,
         "best_lines": ["#2: x"], "main_failure": "none"}


class Assignments(unittest.TestCase):
    def test_each_reading_goes_to_one_claude_judge_who_sees_each_opener_once(self):
        seen = []
        for s, names in RJ.judge_assignment():
            self.assertEqual(len({n.split("-")[1] for n in names}), 4, s)
            seen += names
        self.assertEqual(sorted(seen), sorted("opener-%d-v%d" % (p, v) for p in range(1, 9) for v in range(1, 6)))

    def test_each_thread_goes_to_one_claude_tagger_who_sees_every_opener(self):
        seen = []
        for k, names in RJ.tag_assignment():
            self.assertEqual(sorted(int(n.split("-")[1]) for n in names), list(range(1, 9)), k)
            seen += names
        self.assertEqual(sorted(seen), sorted("tag-%d-%s" % (p, L) for p in range(1, 9) for L in "ABCDE"))


class Checks(unittest.TestCase):
    def test_scores_need_every_letter_and_whole_numbers_from_1_to_5(self):
        RJ.checked_scores({"A": dict(SCORE), "B": dict(SCORE)}, ["A", "B"])
        for bad in ({"A": dict(SCORE)},                                  # a letter missing
                    {"A": dict(SCORE, overall=3.5), "B": dict(SCORE)},   # not a whole number
                    {"A": dict(SCORE, humour=6), "B": dict(SCORE)},      # out of range
                    {"A": dict(SCORE, overall=True), "B": dict(SCORE)},  # a bool is not a score
                    {"A": {k: v for k, v in SCORE.items() if k != "variety"}, "B": dict(SCORE)}):
            with self.assertRaises(ValueError):
                RJ.checked_scores(bad, ["A", "B"])

    def test_tags_are_reply_numbers_from_2_to_24(self):
        self.assertEqual(RJ.checked_tags({"horror": [9, 3, 3]}), {"horror": [3, 9]})
        for bad in ({"horror": [1]}, {"horror": [25]}, {"horror": "3"}, {}):
            with self.assertRaises(ValueError):
                RJ.checked_tags(bad)


class AskAll(unittest.TestCase):
    def test_a_malformed_reply_is_asked_again_paid_for_and_never_asked_twice(self):
        tmp = tempfile.mkdtemp()
        for p in (1, 2):
            RJ.write(os.path.join(tmp, "opener-%d-v1.txt" % p),
                     "OPENER %d: x\n\n====\nTHREAD A\n====\n1. a (OP): x\n\n====\nTHREAD B\n====\n1. a (OP): x\n" % p)
        calls, lock = [], threading.Lock()

        def fake_post_json(url, key, body, timeout=240):
            prompt = body["messages"][0]["content"]
            self.assertTrue(prompt.startswith(RJ.GPT_INTRO + RJ.RUBRIC_V2 + RJ.GPT_REPLY))
            self.assertEqual((body["model"], body["reasoning"], body["usage"]),
                             ("openai/gpt-5.4", {"effort": "low"}, {"include": True}))
            with lock:
                calls.append(prompt)
                first = len(calls) == 1
            reply = "here you go: {not json" if first else json.dumps({"A": SCORE, "B": SCORE})
            return {"choices": [{"message": {"content": reply}}], "usage": {"total_tokens": 10, "cost": 0.5}}

        with mock.patch.object(RJ, "R3", tmp), mock.patch.object(round3, "post_json", fake_post_json), \
                mock.patch.object(RJ, "read_env", lambda: {"OPENROUTER_API_KEY": "test"}), \
                mock.patch.object(sys, "argv", ["round3_judge.py", "gpt", "r9", "--paid"]), \
                mock.patch("builtins.print"):
            RJ.gpt()
            RJ.gpt()              # a rerun asks only what is missing: nothing
        self.assertEqual(len(calls), 3)
        usage = RJ.read_json(os.path.join(tmp, "usage-scores-gpt.json"))
        self.assertEqual(sorted(u["tries"] for u in usage.values()), [1, 2])
        self.assertEqual(sum(u["cost"] for u in usage.values()), 1.5)
        self.assertEqual(sorted(RJ.read_json(os.path.join(tmp, "scores-gpt.json"))), ["opener-1-v1", "opener-2-v1"])


if __name__ == "__main__":
    unittest.main()
