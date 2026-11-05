"""Regression tests for the generation scripts in spike/ (no network, no models, no money).

python -m unittest discover -s spike/judging -p "test_*.py"
"""
import json, os, random, shutil, subprocess, sys, tempfile, threading, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
ROOT = os.path.dirname(SPIKE)
for p in (ROOT, SPIKE):
    if p not in sys.path:
        sys.path.insert(0, p)

import generate as G
import round3 as R3
import bakeoff as B
import live_board as LB


def git_ignored(path):
    """True/False from `git check-ignore`, None when git or the repo isn't available."""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT,
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return {0: True, 1: False}.get(r.returncode)


def fake_thread(oi, rep, tid):
    return {"posts": [{"who": "op", "text": "the opener"}, {"who": "anon", "text": "a reply"}]}


def keep_generate_globals():
    """main() reconfigures generate.py's globals; put them back afterwards."""
    return mock.patch.multiple(G, complete=G.complete, POSTS_PER_THREAD=G.POSTS_PER_THREAD,
                               CHECK_AT=G.CHECK_AT, RETURN_AT=G.RETURN_AT, ARRIVE_AT=G.ARRIVE_AT)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)


class Round3Output(TempDir):
    def test_missing_output_dir_is_created_before_generating(self):
        out = os.path.join(self.tmp, "not", "there", "yet")
        with keep_generate_globals(), \
                mock.patch.dict(os.environ, {"BAKEOFF_OUT": out}), \
                mock.patch.object(sys, "argv", ["round3.py", "gemini"]), \
                mock.patch.object(R3, "build", return_value=(lambda *a: ("x", "eos"), 2)), \
                mock.patch.object(G, "gen_thread", side_effect=fake_thread), \
                mock.patch("builtins.print"):
            R3.main()
        with open(os.path.join(out, "bakeoff-gemini.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["threads"]), len(R3.OPENER_PICKS))


class Round3Budget(TempDir):
    def test_concurrent_reads_never_see_a_half_written_file(self):
        budget = os.path.join(self.tmp, "openai_budget.json")
        errors, stop = [], threading.Event()

        def writer():
            try:
                for _ in range(300):
                    R3.budget_add(1)
            except Exception as e:          # pragma: no cover - the failure being tested
                errors.append(e)

        def reader():
            try:
                while not stop.is_set():
                    R3.budget_left()
            except Exception as e:
                errors.append(e)

        with mock.patch.object(R3, "BUDGET", budget), \
                mock.patch.dict(R3.SPEND, {"openai_tokens": 0}):
            readers = [threading.Thread(target=reader) for _ in range(4)]
            writers = [threading.Thread(target=writer) for _ in range(3)]
            for t in readers + writers:
                t.start()
            for t in writers:
                t.join()
            stop.set()
            for t in readers:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(R3.budget_left(), R3.DAILY_CAP - 900)


class BakeoffOutput(TempDir):
    def run_cast(self):
        with keep_generate_globals(), \
                mock.patch.object(B, "SPIKE", self.tmp), \
                mock.patch.object(sys, "argv", ["bakeoff.py", "--arm", "cast", "--models", self.tmp]), \
                mock.patch.object(B, "start_server", side_effect=lambda *a, **k: mock.MagicMock()), \
                mock.patch.object(G, "wait_ready", return_value=True), \
                mock.patch.object(G, "gen_thread", side_effect=fake_thread), \
                mock.patch("builtins.print"):
            B.main()

    def test_default_output_is_the_private_remote_dir(self):
        self.run_cast()
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "bakeoff-cast.json")))
        with open(os.path.join(self.tmp, "remote", "bakeoff-cast.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["threads"]), len(B.OPENER_PICKS))

    def test_default_output_is_gitignored(self):
        ignored = git_ignored(os.path.join(SPIKE, "remote", "bakeoff-cast.json"))
        if ignored is None:
            self.skipTest("git not available")
        self.assertTrue(ignored)

if __name__ == "__main__":
    unittest.main()
