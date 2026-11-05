"""Scores stay bound to the packets the judges read (no network: urlopen is blocked).

python -m unittest discover -s spike/judging -p "test_*.py"
"""
import importlib, json, os, shutil, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
for p in (SPIKE, HERE):                    # SPIKE: gpt() imports round3's budget helpers
    if p not in sys.path:
        sys.path.insert(0, p)

import packet_record as PR


def import_judge(name, argv):
    """The judge scripts read their round from sys.argv at import time."""
    with mock.patch.object(sys, "argv", argv):
        return importlib.import_module(name)


R3J = import_judge("round3_judge", ["round3_judge.py", "report", "r8"])
JPJ = import_judge("jp_judge", ["jp_judge.py", "report", "r5"])

NO_NETWORK = mock.patch("urllib.request.urlopen", side_effect=AssertionError("network call"))


def thread(opener, arm, n=4):
    return {"opener": opener, "op": "op", "posts": [
        {"n": k + 1, "who": "op" if k % 2 == 0 else "anon%d" % k, "text": "%s says %d\r\nmore" % (arm, k)}
        for k in range(n)]}


def scores_for(letters):
    return {L: {"overall": 3, "interest": 3, "humour": 2, "emergence": 2, "coherence": 4,
                "naturalness": 3} for L in letters}


class FileBytes(unittest.TestCase):
    def test_matches_what_text_mode_writes(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        text = "OPENER 1: x\n\n1. a (OP): line\r\nwith a stray CR\n2. b: (empty)"
        p = os.path.join(tmp, "t.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        with open(p, "rb") as f:
            self.assertEqual(PR.file_bytes(text), f.read())


class Round3Binding(unittest.TestCase):
    OPENERS = ["my mug moves", "a text from my own number"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, "remote"))
        self.folder = os.path.join(self.tmp, "judging", "r8")
        for arm in R3J.ARMS:
            self.write_arm(arm)
        for p in (mock.patch.object(R3J, "SPIKE", self.tmp), mock.patch.object(R3J, "ROOT", self.tmp),
                  mock.patch.object(R3J, "R3", self.folder), mock.patch("builtins.print"), NO_NETWORK):
            p.start()
            self.addCleanup(p.stop)
        with open(os.path.join(self.tmp, ".env"), "w") as f:
            f.write("OPENAI_API_KEY=test-not-a-key\nOPENROUTER_API_KEY=test-not-a-key\n")

    def write_arm(self, arm, tweak=""):
        threads = [thread(o, arm + tweak) for o in self.OPENERS]
        with open(os.path.join(self.tmp, "remote", "bakeoff-%s.json" % arm), "w", encoding="utf-8") as f:
            json.dump({"arm": arm, "threads": threads}, f)

    def read(self, name):
        with open(os.path.join(self.folder, name), "rb") as f:
            return f.read()

    def score_opener_1(self, *more):
        key = json.loads(self.read("key.json"))
        with open(os.path.join(self.folder, "scores-gpt.json"), "w", encoding="utf-8") as f:
            json.dump({"opener-" + i: scores_for(key[i]) for i in ("1",) + more}, f)

    def test_packets_records_what_it_wrote(self):
        R3J.packets()
        rec = PR.load(self.folder)
        key = json.loads(self.read("key.json"))
        self.assertEqual(sorted(rec), ["opener-1", "opener-2"])
        for i in ("1", "2"):
            self.assertEqual(rec["opener-" + i]["sha256"], PR.sha256(self.read("opener-%s.txt" % i)))
            self.assertEqual(rec["opener-" + i]["key"], key[i])

    def test_repacketing_unchanged_threads_is_allowed(self):
        R3J.packets()
        self.score_opener_1()
        before = self.read("opener-1.txt")
        R3J.packets()
        self.assertEqual(self.read("opener-1.txt"), before)

    def test_repacketing_a_scored_round_with_new_threads_is_refused(self):
        R3J.packets()
        self.score_opener_1()
        packet, key = self.read("opener-1.txt"), self.read("key.json")
        self.write_arm(R3J.ARMS[1], tweak=" regenerated")
        with self.assertRaises(SystemExit):
            R3J.packets()
        self.assertEqual(self.read("opener-1.txt"), packet)
        self.assertEqual(self.read("key.json"), key)

    def test_unscored_round_can_be_repacketed(self):
        R3J.packets()
        self.write_arm(R3J.ARMS[1], tweak=" regenerated")
        R3J.packets()
        self.assertEqual(PR.load(self.folder)["opener-1"]["sha256"], PR.sha256(self.read("opener-1.txt")))

    def test_report_refuses_scores_for_a_changed_packet(self):
        R3J.packets()
        self.score_opener_1()
        R3J.report()                                        # bound: fine
        with open(os.path.join(self.folder, "opener-1.txt"), "ab") as f:
            f.write(b"\nmore posts")
        with self.assertRaises(SystemExit):
            R3J.report()

    def test_report_refuses_scores_under_a_different_key(self):
        R3J.packets()
        self.score_opener_1()
        key = json.loads(self.read("key.json"))
        letters = list(key["1"])
        key["1"] = dict(zip(letters, reversed(list(key["1"].values()))))
        with open(os.path.join(self.folder, "key.json"), "w") as f:
            json.dump(key, f)
        with self.assertRaises(SystemExit):
            R3J.report()

    def test_report_refuses_scores_with_no_recorded_packet(self):
        R3J.packets()
        self.score_opener_1()
        os.remove(os.path.join(self.folder, PR.RECORD))
        with self.assertRaises(SystemExit):
            R3J.report()

    def test_gpt_refuses_before_skipping_or_scoring_against_changed_packets(self):
        R3J.packets()
        self.score_opener_1()
        with open(os.path.join(self.folder, "opener-1.txt"), "ab") as f:
            f.write(b"\nmore posts")
        with self.assertRaises(SystemExit):
            R3J.gpt()

    def test_gpt_refuses_to_score_an_unrecorded_packet(self):
        R3J.packets()
        self.score_opener_1("2")                            # so opener-9 is the only one left
        with open(os.path.join(self.folder, "opener-9.txt"), "w", encoding="utf-8") as f:
            f.write("OPENER 9: left over from another run\n")
        with mock.patch("round3.budget_left", return_value=10**6), self.assertRaises(SystemExit):
            R3J.gpt()


class JapaneseBinding(unittest.TestCase):
    OPENERS = ["上司が毎朝", "隣の部屋から"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, "remote"))
        self.folder = os.path.join(self.tmp, "judging", "jp-r5")
        for arm in JPJ.ARMS:
            self.write_arm(arm)
        for p in (mock.patch.object(JPJ, "SPIKE", self.tmp), mock.patch.object(JPJ, "ROOT", self.tmp),
                  mock.patch.object(JPJ, "JP", self.folder), mock.patch("builtins.print"), NO_NETWORK):
            p.start()
            self.addCleanup(p.stop)

    def write_arm(self, arm, tweak=""):
        with open(os.path.join(self.tmp, "remote", "jp-%s-5ch.json" % arm), "w", encoding="utf-8") as f:
            json.dump({"threads": [thread(o, arm + tweak) for o in self.OPENERS]}, f, ensure_ascii=False)

    def test_scored_packets_are_bound(self):
        JPJ.packets()
        with open(os.path.join(self.folder, "key.json")) as f:
            key = json.load(f)
        with open(os.path.join(self.folder, "scores-gpt.json"), "w", encoding="utf-8") as f:
            json.dump({"5ch-opener-1": scores_for(key["5ch-opener-1"])}, f)
        JPJ.report()
        self.write_arm(JPJ.ARMS[0], tweak=" regenerated")
        with self.assertRaises(SystemExit):
            JPJ.packets()
        with open(os.path.join(self.folder, "5ch-opener-1.txt"), "ab") as f:
            f.write(b"\nmore")
        with self.assertRaises(SystemExit):
            JPJ.report()


class CommittedRounds(unittest.TestCase):
    """Every committed score file is bound to the packet MANIFEST.sha256 lists for it."""
    FOLDERS = {"r3": "round3", "r4": "round3", "r5": "round3", "r6": "round3", "r7": "round3",
               "r8": "round3", "jp": "jp", "jp-r5": "jp"}

    def manifest(self):
        out = {}
        with open(os.path.join(SPIKE, "MANIFEST.sha256"), encoding="utf-8") as f:
            for line in f:
                h, path = line.split()
                path = path.lstrip("*")
                folder, _, name = path[len("judging/"):].rpartition("/")
                if path.startswith("judging/") and name.endswith(".txt") and "opener-" in name:
                    out.setdefault(folder, {})[name[:-4]] = h
        return out

    def test_records_match_manifest_and_keys(self):
        manifest = self.manifest()
        for folder, kind in self.FOLDERS.items():
            d = os.path.join(HERE, folder)
            rec = PR.load(d)
            self.assertEqual({n: r["sha256"] for n, r in rec.items()}, manifest[folder], folder)
            with open(os.path.join(d, "key.json")) as f:
                key = json.load(f)
            key_of = (lambda n: key.get(n.split("-")[1])) if kind == "round3" else key.get
            self.assertTrue(PR.scored(d) <= set(rec), folder)
            PR.check(d, key_of)              # raises SystemExit on any mismatch


if __name__ == "__main__":
    unittest.main()
