#!/usr/bin/env python3
"""Round 12's owner A/B (spike/THINKING.md): Gemini's thinking level. Per opener, minimal vs low and
high vs low, sides shuffled and the pairs in a shuffled order, shown in probe.html?set=think.

  python calibration/probe/build_think.py            build the pairs
  python calibration/probe/build_think.py stats      lengths and thinking tokens per arm
  python calibration/probe/build_think.py analyze    the owner's picks (latest think-*.json export)

Reads spike/remote/r12/bakeoff-think12{min,low,high}.json. Writes private/items-think.json and
key-think.json; a pair whose thread can't be shown (build.screen) is left out and reported.
"""
import glob, json, os, random, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.dirname(HERE)
ROOT = os.path.dirname(CAL)
sys.path.insert(0, CAL)
import build as B

SEED = 20261112
SHOW = 12
R12 = os.path.join(ROOT, "spike", "remote", "r12")
ARMS = {"minimal": "bakeoff-think12min.json", "low": "bakeoff-think12low.json", "high": "bakeoff-think12high.json"}
COMPARE = ["minimal", "high"]          # each against low


def load(arm):
    return B.load_threads(os.path.join(R12, ARMS[arm]))


def build():
    rng = random.Random(SEED)
    low = {t["opener"]: t for t in load("low")}
    todo, skipped = [], []
    for arm in COMPARE:
        for t in load(arm):
            other = low.get(t["opener"])
            why = B.screen(t) or (B.screen(other) if other else "no low thread")
            if why:
                skipped.append("%s %s: %s" % (arm, t["opener"][:40], why))
                continue
            todo.append((arm, t, other))
    rng.shuffle(todo)
    items, key = [], {}
    for i, (arm, t, other) in enumerate(todo):
        sides = [(arm, t), ("low", other)]
        rng.shuffle(sides)
        pid = "k%02d" % (i + 1)
        pair, kp = {"id": pid, "lang": "en", "show": SHOW}, {"opener": t["opener"], "compare": arm}
        for side, (a, th) in zip("AB", sides):
            posts = B.render(th)
            pair[side] = posts
            kp[side] = {"arm": a, "file": ARMS[a], "posts": len(posts), "sha256": B.digest(posts)}
        items.append(pair)
        key[pid] = kp
    os.makedirs(os.path.join(HERE, "private"), exist_ok=True)
    with open(os.path.join(HERE, "private", "items-think.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"pairs": items}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "key-think.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(key, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("%d pairs" % len(items) + ("; left out: " + "; ".join(skipped) if skipped else ""))


def stats():
    for arm, name in ARMS.items():
        with open(os.path.join(R12, name), encoding="utf-8") as f:
            spend = json.load(f)["spend"]
        lens = [len(p.get("text") or "") for t in load(arm) for p in t["posts"][1:]]
        n = len(lens)
        print("%-7s %3d posts  median %3d chars  under 40: %2d%%  over 250: %2d%%  thinking %4d tokens/post  $%.4f/post"
              % (arm, n, statistics.median(lens), 100 * sum(x < 40 for x in lens) / n,
                 100 * sum(x > 250 for x in lens) / n, spend.get("think_tokens", 0) / max(spend.get("posts", 1), 1),
                 spend["usd"] / max(spend.get("posts", 1), 1)))


def analyze():
    with open(os.path.join(HERE, "key-think.json"), encoding="utf-8") as f:
        key = json.load(f)
    exports = sorted(glob.glob(os.path.join(HERE, "answers", "think-*.json")), key=os.path.getmtime)
    if len(sys.argv) > 2:
        exports = [sys.argv[2]]
    if not exports:
        raise SystemExit("no think-*.json export in calibration/probe/answers/")
    with open(exports[-1], encoding="utf-8") as f:
        answers = json.load(f)["answers"]
    for arm in COMPARE:
        wins = {arm: 0, "low": 0}
        other = {"both": 0, "neither": 0}
        print("\n%s vs low" % arm)
        for pid, k in sorted(key.items()):
            if k["compare"] != arm:
                continue
            a = answers.get(pid) or {}
            pick = a.get("pick")
            if pick in ("A", "B"):
                wins[k[pick]["arm"]] += 1
            elif pick:
                other[pick] += 1
            print("  %s %-50s %s%s" % (pid, k["opener"][:50], k[pick]["arm"] if pick in ("A", "B") else pick or "-",
                                       "  note: " + a["note"] if a.get("note") else ""))
        top = max(wins, key=wins.get)
        verdict = "%s wins" % top if wins[top] >= 5 and wins[min(wins, key=wins.get)] <= 1 else "split"
        print("  %s %d, low %d, both good %d, neither %d -> %s (rule in spike/THINKING.md)"
              % (arm, wins[arm], wins["low"], other["both"], other["neither"], verdict))


if __name__ == "__main__":
    {"stats": stats, "analyze": analyze}.get(sys.argv[1] if len(sys.argv) > 1 else "", build)()
