#!/usr/bin/env python3
"""Round 10's owner A/B (spike/MOVES.md): per-post moves vs plain Gemini, same opener, one pair per
opener, shown in probe.html?set=moves.

  python calibration/probe/build_moves.py            build the pairs
  python calibration/probe/build_moves.py stats      the mechanical predictions, from the threads
  python calibration/probe/build_moves.py analyze    the owner's picks (latest moves-*.json export)

Reads spike/remote/r10/bakeoff-{moves10,gemini9neutral}.json. Writes private/items-moves.json and
key-moves.json; a pair whose thread can't be shown (build.screen) is left out and reported.
"""
import glob, json, os, random, re, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.dirname(HERE)
ROOT = os.path.dirname(CAL)
sys.path.insert(0, CAL)
import build as B

SEED = 20261106
SHOW = 12
R10 = os.path.join(ROOT, "spike", "remote", "r10")
ARMS = {"moves": "bakeoff-moves10.json", "plain": "bakeoff-gemini9neutral.json"}
ANECDOTE = re.compile(r"\b(reminds? me of|happened to my|same thing happened|this is (literally |exactly )?"
                      r"(what|like when)|back when i|when i lived|my old (place|apartment|flat|job))", re.I)


def load(arm):
    return B.load_threads(os.path.join(R10, ARMS[arm]))


def build():
    rng = random.Random(SEED)
    moves, plain = load("moves"), load("plain")
    by_opener = {t["opener"]: t for t in plain}
    items, key, skipped = [], {}, []
    for i, m in enumerate(moves):
        p = by_opener.get(m["opener"])
        why = B.screen(m) or (B.screen(p) if p else "no plain thread")
        if why:
            skipped.append("%s: %s" % (m["opener"][:50], why))
            continue
        sides = [("moves", m), ("plain", p)]
        rng.shuffle(sides)
        pid = "m%02d" % (i + 1)
        pair, kp = {"id": pid, "lang": "en", "show": SHOW}, {"opener": m["opener"]}
        for side, (arm, t) in zip("AB", sides):
            posts = B.render(t)
            pair[side] = posts
            kp[side] = {"arm": arm, "file": ARMS[arm], "posts": len(posts), "sha256": B.digest(posts)}
        items.append(pair)
        key[pid] = kp
    os.makedirs(os.path.join(HERE, "private"), exist_ok=True)
    with open(os.path.join(HERE, "private", "items-moves.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"pairs": items}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "key-moves.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(key, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("%d pairs" % len(items) + ("; left out: " + "; ".join(skipped) if skipped else ""))


def stats():
    for arm in ARMS:
        lens, anec, withheld = [], 0, 0
        for t in load(arm):
            op = t["posts"][0]["who"]
            for p in t["posts"][1:]:
                if p["who"] == op:
                    continue
                text = p.get("text") or ""
                withheld += bool(p.get("withheld"))
                lens.append(len(text))
                anec += bool(ANECDOTE.search(text))
        n = len(lens)
        print("%-6s %3d replies  median %3d chars  under 40: %2d%%  over 250: %2d%%  anecdote: %d%%  withheld: %d"
              % (arm, n, statistics.median(lens), 100 * sum(x < 40 for x in lens) / n,
                 100 * sum(x > 250 for x in lens) / n, 100 * anec / n, withheld))


def analyze():
    with open(os.path.join(HERE, "key-moves.json"), encoding="utf-8") as f:
        key = json.load(f)
    exports = sorted(glob.glob(os.path.join(HERE, "answers", "moves-*.json")), key=os.path.getmtime)
    if len(sys.argv) > 2:
        exports = [sys.argv[2]]
    if not exports:
        raise SystemExit("no moves-*.json export in calibration/probe/answers/")
    with open(exports[-1], encoding="utf-8") as f:
        answers = json.load(f)["answers"]
    wins = {"moves": 0, "plain": 0}
    other, tags = {"both": 0, "neither": 0}, {}
    for pid, k in sorted(key.items()):
        a = answers.get(pid) or {}
        pick = a.get("pick")
        for side in "AB":
            for t in (a.get("tags") or {}).get(side, []):
                tags[(k[side]["arm"], t)] = tags.get((k[side]["arm"], t), 0) + 1
        if pick in ("A", "B"):
            wins[k[pick]["arm"]] += 1
        elif pick:
            other[pick] += 1
        print("%s %-55s %s%s" % (pid, k["opener"][:55], k[pick]["arm"] if pick in ("A", "B") else pick or "-",
                                 "  note: " + a["note"] if a.get("note") else ""))
    decided = wins["moves"] + wins["plain"]
    top = max(wins, key=wins.get)
    verdict = ("%s wins" % top if wins[top] >= 5 and decided - wins[top] <= 1 else "split")
    print("\nmoves %d, plain %d, both good %d, neither %d -> %s (rule in spike/MOVES.md)"
          % (wins["moves"], wins["plain"], other["both"], other["neither"], verdict))
    for (arm, t), c in sorted(tags.items()):
        print("  %-6s %-25s %d" % (arm, t, c))


if __name__ == "__main__":
    {"stats": stats, "analyze": analyze}.get(sys.argv[1] if len(sys.argv) > 1 else "", build)()
