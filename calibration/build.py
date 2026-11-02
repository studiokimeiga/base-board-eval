#!/usr/bin/env python3
"""Build the blind calibration set: 30 threads from five sources, in a random order; and the
round 9 set, 18 threads from three round 9 arms, rated on its own.

  python calibration/build.py [--data DIR]... [--set calibration|r9]...

DIR holds private inputs (default: the repo root): the original corpora (threads*.json, from the
gated dataset) and spike/remote/ (the bake-off threads). Give --data more than once when they are
in different folders; each file is read from the first DIR that has it. Writes, for each set
(both unless --set says which)

  calibration/items.json, items-r9.json   the threads as the rater and the judges see them (private, gitignored)
  calibration/key.json, key-r9.json       item id -> source, file and thread, plus a hash of the rendered thread

The selection is fixed by the seeds and the rules below. The calibration set was committed before
any of its items was rated or judged, the round 9 set before the reader rated any of it. Running it
again on the same files gives the same sets, byte for byte.
"""
import argparse, hashlib, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "spike"))
from live_board import GATE                 # the board's own list: generate.py's HARM + sexual terms

SEED = 20261102
PER_SOURCE = 6
# The six BEST-OF.md threads, in the corpora they came from. BEST-OF.md shows the office
# statistics thread as its first 20 posts; the set uses whole threads for every source.
BEST_OF = [("threads.json", 11), ("threads.xtc.json", 3), ("threads.sweep.json", 51),
           ("threads.fmt.json", 1), ("threads.final.json", 41), ("threads.final.json", 10)]
# Unselected threads from the recommended config (run 14), the same corpus as two of the above
SMALL_POOL = "threads.final.json"
# Bake-off arms (spike/remote/). qwenpick is Qwen3-235B raw continuation, best-of-3 with a
# gpt-5.4 picker; rolesshort is Gemini with per-poster temperaments and post length (round 8).
HOSTED = [("gemini", "bakeoff-gemini.json"), ("rolesshort", "bakeoff-rolesshort.json"),
          ("qwenpick", "bakeoff-pick.json")]
# The round 9 set (README.md, "The round 9 set"): plain Gemini under the neutral header, its /x/
# twin, and short temperaments under /x/. Its ids follow the calibration set's, so a reader's
# exports for the two sets never share an id.
ROUND9 = [("gemini9neutral", "bakeoff-gemini9neutral.json"), ("gemini9", "bakeoff-gemini9.json"),
          ("rolesshort9", "bakeoff-rolesshort9.json")]
R9_SEED = 2026110209
R9_FIRST = 31
# Stricter than the board's gate: a person reads these, so anything near these topics is
# left out, matched as words rather than substrings.
EXCLUDE = re.compile(r"\b(rap(e|ed|ing|ist)|molest\w*|pedo\w*|paedo\w*|incest|suicid\w*|"
                     r"self[- ]harm|nazi\w*|hitler|fag\w*|paki\w*|retard\w*|nigg\w*|kike\w*|"
                     r"spics?|chinks?|trann\w*|dykes?|coons?|wetback\w*|towelhead\w*|cunt\w*|"
                     r"cock\w*|tits|porn\w*|sex\w*|naked|nude|horny|orgasm\w*|slut\w*|whore\w*|"
                     r"penis|vagina|dick)\b", re.I)


def find(data, name):
    """name, a path inside a data folder, in the first of the data folders that has it."""
    for d in data:
        if os.path.exists(os.path.join(d, name)):
            return os.path.join(d, name)
    raise SystemExit("%s is in none of: %s (pass the folder that has it with --data)" % (name, ", ".join(data)))


def load_threads(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d["threads"] if isinstance(d, dict) else d


def screen(t):
    """Why a thread can't go in front of a reader, or None."""
    if t.get("quarantined"):
        return "quarantined"
    posts = t["posts"]
    if any(p.get("withheld") or (p.get("text") or "").startswith("[post withheld") for p in posts):
        return "has withheld posts"
    blob = "\n".join(p.get("text") or "" for p in posts)
    if any(h in blob.lower() for h in GATE):
        return "gate term"
    m = EXCLUDE.search(blob)
    return "excluded word %r" % m.group(0).lower() if m else None


def render(t):
    """What everyone sees: handles and text, numbered, the starter marked OP. No timestamps,
    ids, file names or model names."""
    op = t["posts"][0]["who"]
    return [{"n": i + 1, "who": p["who"], "op": p["who"] == op, "text": (p.get("text") or "").rstrip()}
            for i, p in enumerate(t["posts"])]


def digest(posts):
    return hashlib.sha256(json.dumps(posts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def hosted(arms, data, notes):
    """Each bake-off arm takes 6 of the 8 openers, rotated so every opener appears two or three
    times across the three arms; a thread that fails the screen gives way to the arm's next
    unused opener."""
    chosen = []
    for k, (source, fname) in enumerate(arms):
        threads = load_threads(find(data, os.path.join("spike", "remote", fname)))
        order = [(2 * k + j) % len(threads) for j in range(len(threads))]
        got = 0
        for i in order:
            why = screen(threads[i])
            if why:
                notes.append("%s: skipped %s[%d] (%s)" % (source, fname, i, why))
                continue
            chosen.append((source, "spike/remote/" + fname, i, threads[i]))
            got += 1
            if got == PER_SOURCE:
                break
        if got < PER_SOURCE:
            raise SystemExit("%s: only %d threads pass the screen" % (source, got))
    return chosen


def label(chosen, first=1):
    """Ids c<first>, c<first + 1>, ... in the order of chosen, and the public key."""
    items, key = [], {}
    for n, (source, fname, i, t) in enumerate(chosen):
        iid = "c%02d" % (first + n)
        posts = render(t)
        items.append({"id": iid, "posts": posts})
        key[iid] = {"source": source, "file": fname, "thread": i, "posts": len(posts),
                    "chars": sum(len(p["text"]) for p in posts), "sha256": digest(posts)}
    return items, key


def build(data):
    data = [data] if isinstance(data, str) else data
    rng = random.Random(SEED)
    chosen, notes = [], []
    corpora = {}

    def corpus(name):
        if name not in corpora:
            corpora[name] = load_threads(find(data, name))
        return corpora[name]

    for name, i in BEST_OF:
        t = corpus(name)[i]
        why = screen(t)
        if why:
            raise SystemExit("BEST-OF thread %s[%d] fails the screen: %s" % (name, i, why))
        chosen.append(("bestof", name, i, t))

    pool = [i for i in range(len(corpus(SMALL_POOL))) if (SMALL_POOL, i) not in BEST_OF]
    rng.shuffle(pool)
    for i in pool:
        why = screen(corpus(SMALL_POOL)[i])
        if why:
            notes.append("smallrand: skipped %s[%d] (%s)" % (SMALL_POOL, i, why))
            continue
        chosen.append(("smallrand", SMALL_POOL, i, corpus(SMALL_POOL)[i]))
        if sum(c[0] == "smallrand" for c in chosen) == PER_SOURCE:
            break

    chosen += hosted(HOSTED, data, notes)
    rng.shuffle(chosen)
    items, key = label(chosen)
    return items, key, notes


def build_r9(data):
    """The round 9 set: six threads from each ROUND9 arm, by the rules above, ids from c31."""
    data = [data] if isinstance(data, str) else data
    notes = []
    chosen = hosted(ROUND9, data, notes)
    random.Random(R9_SEED).shuffle(chosen)
    items, key = label(chosen, R9_FIRST)
    return items, key, notes


# set -> (file suffix, builder, seed)
SETS = {"calibration": ("", build, SEED), "r9": ("-r9", build_r9, R9_SEED)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", action="append", help="a folder with private inputs; repeatable")
    ap.add_argument("--set", action="append", choices=sorted(SETS), help="build only this set; repeatable")
    a = ap.parse_args()
    for name in a.set or ["calibration", "r9"]:
        sfx, make, seed = SETS[name]
        items, key, notes = make(a.data or [ROOT])
        with open(os.path.join(HERE, "items%s.json" % sfx), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"seed": seed, "items": items}, f, ensure_ascii=False, indent=1)
        with open(os.path.join(HERE, "key%s.json" % sfx), "w", encoding="utf-8", newline="\n") as f:
            json.dump(key, f, indent=1, sort_keys=True)
        for line in notes:
            print(line)
        counts = {}
        for v in key.values():
            counts[v["source"]] = counts.get(v["source"], 0) + 1
        print("%s: built %d items:" % (name, len(items)), counts)


if __name__ == "__main__":
    main()
