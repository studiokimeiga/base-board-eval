#!/usr/bin/env python3
"""Build the blind reader set: an earlier thread, then its two follow-ups in a random order.

  python lore/reader/build.py --run <the lore run folder: lore/private/run of experiment/lore-transfer>

A triple is a source thread from the lore boards and one of its targets in both arms: the memory
follow-up, written with the source above it, and the no-memory one, written without it, from the
same opener, cast, timing and thread number. Writes

  lore/reader/items.json   what the reader sees: A and B, never which is which (private, gitignored)
  lore/reader/key.json     triple -> board, target, source, which side is memory, stratum, hashes

The selection is fixed by SEED and the rules in README.md, committed before anyone rated. Running
it again on the same run gives the same set, byte for byte.
"""
import argparse, hashlib, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LORE = os.path.dirname(HERE)
ROOT = os.path.dirname(LORE)
sys.path.insert(0, LORE)
sys.path.insert(0, os.path.join(ROOT, "spike"))
from live_board import GATE                 # the board's own list: generate.py's HARM + sexual terms

# Its own seed: lore/judge.py's items() and half() shared one, and that made its "random half"
# exactly one board (lore/REPORT.md, deviation 4).
SEED = 4471
QUOTAS = {("misc", True): 3, ("misc", False): 3, ("x", True): 1, ("x", False): 1}
BOARDS = {"x": "/x/", "misc": "/misc/"}
# calibration/build.py's list, verbatim: a person reads these, so anything near these topics is
# left out, matched as words rather than substrings.
EXCLUDE = re.compile(r"\b(rap(e|ed|ing|ist)|molest\w*|pedo\w*|paedo\w*|incest|suicid\w*|"
                     r"self[- ]harm|nazi\w*|hitler|fag\w*|paki\w*|retard\w*|nigg\w*|kike\w*|"
                     r"spics?|chinks?|trann\w*|dykes?|coons?|wetback\w*|towelhead\w*|cunt\w*|"
                     r"cock\w*|tits|porn\w*|sex\w*|naked|nude|horny|orgasm\w*|slut\w*|whore\w*|"
                     r"penis|vagina|dick)\b", re.I)


def screen(t):
    """Why a thread can't go in front of a reader, or None (calibration/build.py's screen)."""
    posts = t["posts"]
    if any(p.get("withheld") or (p.get("text") or "").startswith("[post withheld") for p in posts):
        return "has withheld posts"
    blob = "\n".join(p.get("text") or "" for p in posts)
    if any(h in blob.lower() for h in GATE):
        return "gate term"
    m = EXCLUDE.search(blob)
    return "excluded word %r" % m.group(0).lower() if m else None


def eligible(run):
    """{(board, target): source} for every target whose source and both arms pass the screen."""
    out = {}
    for (b, tid, arm), t in sorted(run.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
        if arm != "memory" or (b, tid, "none") not in run:
            continue
        s = run[(b, t["source"], None)]
        if not any(screen(x) for x in (s, t, run[(b, tid, "none")])):
            out[(b, tid)] = t["source"]
    return out


def select(el, identified, quotas, seed):
    """Fill each (board, identified) stratum at random, never using a source twice."""
    rng = random.Random("%d:select" % seed)
    chosen, used = [], set()
    for b in sorted({b for b, _ in quotas}):
        pool = sorted(k for k in el if k[0] == b)
        rng.shuffle(pool)
        need = {ident: quotas.get((b, ident), 0) for ident in (True, False)}
        for k in pool:
            ident = k in identified
            if need[ident] and el[k] not in used:
                chosen.append(k)
                used.add(el[k])
                need[ident] -= 1
        if any(need.values()):
            raise SystemExit("board %s: cannot fill %s" % (b, need))
    return chosen


def assign(chosen, seed):
    """Which side the memory follow-up goes on: A in exactly half of each board's triples (the
    odd one out at random)."""
    rng = random.Random("%d:sides" % seed)
    side = {}
    for b in sorted({b for b, _ in chosen}):
        ks = [k for k in chosen if k[0] == b]
        sides = ["A", "B"] * (len(ks) // 2) + ([rng.choice("AB")] if len(ks) % 2 else [])
        rng.shuffle(sides)
        side.update(zip(ks, sides))
    return side


def render(t):
    """Handles and text, numbered, the starter marked OP, under the board's own header.
    No timestamps, ids or model names."""
    shown = [p for p in t["posts"] if p.get("text") and not p.get("withheld")]
    op = shown[0]["who"]
    return {"header": "%s — thread %d" % (t["board"], t["no"]),
            "posts": [{"n": i + 1, "who": p["who"], "op": p["who"] == op, "text": p["text"].rstrip()}
                      for i, p in enumerate(shown)]}


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def make(run, chosen, side, identified, seed):
    rng = random.Random("%d:ids" % seed)
    order = list(chosen)
    rng.shuffle(order)
    items, key = [], {}
    for n, (b, tid) in enumerate(order):
        t = run[(b, tid, "memory")]
        mem, none, src = render(t), render(run[(b, tid, "none")]), render(run[(b, t["source"], None)])
        a, bb = (mem, none) if side[(b, tid)] == "A" else (none, mem)
        iid = "r%02d" % (n + 1)
        items.append({"id": iid, "source": src, "A": a, "B": bb})
        chars = lambda th: sum(len(p["text"]) for p in th["posts"])
        key[iid] = {"board": b, "target": tid, "source": t["source"], "memory": side[(b, tid)],
                    "identified": (b, tid) in identified, "chars": chars(src) + chars(mem) + chars(none),
                    "sha256": {"source": digest(src), "A": digest(a), "B": digest(bb)}}
    return sorted(items, key=lambda it: it["id"]), key


def identified_targets(run):
    """Memory targets whose source the length-matched identification test (lore/explore.py)
    picks out: the stratum the selection balances."""
    import explore as E, tracker as T
    ident = E.identification(run, T.load_reference(T.REF_SHARE))
    return {(b, tid) for (b, tid, arm), v in ident.items() if arm == "memory" and v["top"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    import judge as J
    run = J.load_run(a.run)
    identified = identified_targets(run)
    el = eligible(run)
    chosen = select(el, identified, QUOTAS, SEED)
    items, key = make(run, chosen, assign(chosen, SEED), identified, SEED)
    with open(os.path.join(HERE, "items.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"seed": SEED, "items": items}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "key.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(key, f, indent=1, sort_keys=True)
        f.write("\n")
    pool = {b: sum(1 for k in el if k[0] == b) for b in BOARDS}
    print("eligible triples: %s; built %d: %s" % (pool, len(items), ", ".join(
        "%s %s %s%s" % (i, key[i]["board"], key[i]["target"], " (identified)" if key[i]["identified"] else "")
        for i in sorted(key))))


if __name__ == "__main__":
    main()
