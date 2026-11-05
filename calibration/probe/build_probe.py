#!/usr/bin/env python3
"""Build the taste probe: 14 side-by-side pairs, each changing one thing, so the owner's pick
says which way to go on one design decision (calibration/probe/PROBE.md).

  python calibration/probe/build_probe.py [--data DIR]...

DIR holds the private inputs (default: the repo root): the original corpora (threads.final.json),
spike/remote/ (the bake-off threads) and calibration/probe/private/bakeoff-gemini9neutral.json (a
fresh rep of round 9's neutral-header Gemini arm, written for this probe because every unseen
thread of the original rep has a withheld post). Each file is read from the first DIR that has it.
Writes

  calibration/probe/private/items-probe.json   the pairs as the owner sees them (private)
  calibration/probe/key-probe.json             pair -> which side is which, files, thread hashes

No thread here is in either blind calibration set (key.json, key-r9.json): the build checks it,
so the probe never spoils those sets.
"""
import argparse, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.dirname(HERE)
ROOT = os.path.dirname(CAL)
sys.path.insert(0, CAL)
sys.path.insert(0, os.path.join(ROOT, "spike"))
import build as B                              # screen, render, digest, find: the calibration set's rules
from jp_bakeoff import JP_GATE

SEED = 20261105
SHOW = 12                                       # posts shown before "show the rest"
FRESH = "calibration/probe/private/bakeoff-gemini9neutral.json"

# (pair id, decision, language, [(source, file, thread index), (source, file, thread index)])
# Every pair shares its opener. The order is the order they are shown: the decisions that change
# the most come first, so stopping early still covers them.
PAIRS = [
    ("p01", "engine", "en", [("smallcast", "spike/remote/bakeoff-cast.json", 7), ("gemini-neutral", FRESH, 7)]),
    ("p02", "jp-engine", "ja", [("jp-gemini", "spike/remote/jp-gemini-5ch.json", 0), ("jp-qwen", "spike/remote/jp-qwen235-5ch.json", 0)]),
    ("p03", "register", "en", [("gemini-x", "spike/remote/bakeoff-gemini.json", 6), ("gemini-neutral", FRESH, 6)]),
    ("p04", "engine", "en", [("smallcast", "spike/remote/bakeoff-cast.json", 3), ("gemini-neutral", FRESH, 3)]),
    ("p05", "naif", "en", [("roles-x-naif", "spike/remote/bakeoff-rolesshort9naif.json", 6), ("roles-x", "spike/remote/bakeoff-rolesshort9.json", 6)]),
    ("p06", "jp-tidy", "ja", [("jp-gemini", "spike/remote/jp-gemini-5ch.json", 3), ("jp-gpt", "spike/remote/jp-gpt54-5ch.json", 3)]),
    ("p07", "chaos", "en", [("small-t05", "threads.final.json", 20), ("small-t15-nodry", "threads.final.json", 66)]),
    ("p08", "roles", "en", [("roles-neutral", "spike/remote/bakeoff-rolesshort9neutral.json", 2), ("gemini-neutral", FRESH, 2)]),
    ("p09", "register", "en", [("roles-x", "spike/remote/bakeoff-rolesshort9.json", 1), ("roles-neutral", "spike/remote/bakeoff-rolesshort9neutral.json", 1)]),
    ("p10", "jp-engine", "ja", [("jp-gemini", "spike/remote/jp-gemini-5ch.json", 1), ("jp-qwen", "spike/remote/jp-qwen235-5ch.json", 1)]),
    ("p11", "engine", "en", [("smallcast", "spike/remote/bakeoff-cast.json", 4), ("gemini-neutral", FRESH, 4)]),
    ("p12", "qwen", "en", [("qwen-raw", "spike/remote/bakeoff-qwen235.json", 7), ("gemini-x", "spike/remote/bakeoff-gemini.json", 7)]),
    ("p13", "chaos", "en", [("small-t05", "threads.final.json", 5), ("small-t15-nodry", "threads.final.json", 51)]),
    ("p14", "jp-format", "ja", [("jp-gemini", "spike/remote/jp-gemini-5ch.json", 4), ("jp-gemini-named", "spike/remote/jp-gemini-named.json", 4)]),
]


def blind_threads():
    used = set()
    for name in ("key.json", "key-r9.json"):
        with open(os.path.join(CAL, name), encoding="utf-8") as f:
            for v in json.load(f).values():
                used.add((os.path.basename(v["file"]), v["thread"]))
    return used


def screen(t, lang):
    why = B.screen(t)
    if why or lang != "ja":
        return why
    blob = "\n".join(p.get("text") or "" for p in t["posts"])
    hit = next((h for h in JP_GATE if h in blob), None)
    return "JP gate term" if hit else None


def opener(t):
    return (t["posts"][0].get("text") or "").strip()


def build(data):
    rng = random.Random(SEED)
    used = blind_threads()
    items, key = [], {}
    for pid, decision, lang, sides in PAIRS:
        loaded = []
        for source, fname, i in sides:
            t = B.load_threads(B.find(data, fname))[i]
            if fname != FRESH and (os.path.basename(fname), i) in used:
                raise SystemExit("%s: %s thread %d is in a blind calibration set" % (pid, fname, i))
            why = screen(t, lang)
            if why:
                raise SystemExit("%s: %s thread %d can't be shown: %s" % (pid, fname, i, why))
            loaded.append((source, fname, i, t))
        if opener(loaded[0][3]) != opener(loaded[1][3]):
            raise SystemExit("%s: the two threads start from different openers" % pid)
        rng.shuffle(loaded)
        pair = {"id": pid, "lang": lang, "show": SHOW}
        kp = {"decision": decision, "lang": lang}
        for side, (source, fname, i, t) in zip("AB", loaded):
            posts = B.render(t)
            pair[side] = posts
            kp[side] = {"source": source, "file": fname, "thread": i, "posts": len(posts),
                        "sha256": B.digest(posts)}
        items.append(pair)
        key[pid] = kp
    return items, key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", action="append", help="folder with private inputs (repeatable)")
    a = ap.parse_args()
    items, key = build(a.data or [ROOT])
    os.makedirs(os.path.join(HERE, "private"), exist_ok=True)
    with open(os.path.join(HERE, "private", "items-probe.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"pairs": items}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "key-probe.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(key, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("%d pairs: %s" % (len(items), ", ".join("%s %s" % (p, key[p]["decision"]) for p in key)))


if __name__ == "__main__":
    main()
