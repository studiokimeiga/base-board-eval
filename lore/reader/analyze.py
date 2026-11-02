#!/usr/bin/env python3
"""The pre-registered analysis of the blind reader test (README.md).

  python lore/reader/analyze.py          writes lore/reader/RESULTS.md

Reads key.json and every export in ratings/. A triple counts only when it is fully rated: both
follow-ups on every scale, repost and pick-up answered, and a preference. Memory and no-memory
are mapped back from A and B through the key, and nothing else is looked at.
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCALES = ["believable", "interest", "joke", "deadpan", "overall"]


def sign_test(pos, neg):
    n = pos + neg
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(pos, neg) + 1)) / 2 ** n)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def complete(side):
    return (isinstance(side, dict) and all(isinstance(side.get(s), int) and not isinstance(side.get(s), bool)
                                           for s in SCALES)
            and isinstance(side.get("repost"), bool) and isinstance(side.get("pickup"), bool))


def rows(key, ratings):
    """One row per fully rated triple, with the two follow-ups as memory and none."""
    out = []
    for tid in sorted(ratings):
        r, k = ratings[tid], key.get(tid)
        if not k or not complete(r.get("A")) or not complete(r.get("B")) or r.get("prefer") not in ("A", "B"):
            continue
        mem, non = ("A", "B") if k["memory"] == "A" else ("B", "A")
        out.append({"triple": tid, "board": k["board"], "target": k["target"], "identified": k["identified"],
                    "memory": r[mem], "none": r[non], "prefers_memory": r["prefer"] == mem,
                    "seen": bool(r[mem].get("seen") or r[non].get("seen"))})
    return out


def summarize(rs, drop_seen=False):
    rs = [r for r in rs if not (drop_seen and r["seen"])]
    count = lambda xs: (sum(xs), len(xs))
    return {
        "n": len(rs),
        "prefer": {b: count([r["prefers_memory"] for r in rs if r["board"] == b]) for b in ("misc", "x")},
        "prefer_identified": count([r["prefers_memory"] for r in rs if r["identified"]]),
        "prefer_not_identified": count([r["prefers_memory"] for r in rs if not r["identified"]]),
        "pickup": {arm: count([r[arm]["pickup"] for r in rs]) for arm in ("memory", "none")},
        "pickup_identified": count([r["memory"]["pickup"] for r in rs if r["identified"]]),
        "repost": {arm: count([r[arm]["repost"] for r in rs]) for arm in ("memory", "none")},
        "diff": {s: [r["memory"][s] - r["none"][s] for r in rs] for s in SCALES},
        "diff_misc": {s: [r["memory"][s] - r["none"][s] for r in rs if r["board"] == "misc"] for s in SCALES},
    }


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def agreement(rs, calls):
    """The reader's 'picks up the earlier thread' against each machine call on the same follow-up:
    {instrument: {n, agree, kappa}} over the follow-ups that instrument scored."""
    out = {}
    for name, c in calls.items():
        pairs = [(r[arm]["pickup"], c[(r["board"], r["target"], arm)])
                 for r in rs for arm in ("memory", "none") if (r["board"], r["target"], arm) in c]
        out[name] = {"n": len(pairs), "agree": sum(a == b for a, b in pairs),
                     "kappa": kappa([a for a, _ in pairs], [b for _, b in pairs])}
    return out


def machine_calls(lore=os.path.dirname(HERE)):
    """The lore run's own calls on every follow-up: the tracker's transfer flag (results.json) and
    each judge family's 'borrows' (judging/), keyed (board, target, arm)."""
    calls = {}
    path = os.path.join(lore, "results.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            calls["tracker"] = {(t["board"], t["target"], t["arm"]): t["transfer"] for t in json.load(f)["targets"]}
    kpath = os.path.join(lore, "judging", "key.json")
    if os.path.exists(kpath):
        with open(kpath, encoding="utf-8") as f:
            jkey = json.load(f)
        for fam in ("claude", "gpt"):
            p = os.path.join(lore, "judging", "scores-%s.json" % fam)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    items = json.load(f)["items"]
                calls[fam] = {(jkey[i]["board"], jkey[i]["target"], jkey[i]["arm"]): v["borrows"]
                              for i, v in items.items()}
    return calls


def load(here=HERE):
    with open(os.path.join(here, "key.json"), encoding="utf-8") as f:
        key = json.load(f)
    raters = {}
    for p in sorted(glob.glob(os.path.join(here, "ratings", "*.json"))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        raters[d.get("rater") or os.path.basename(p)[:-5]] = d["ratings"]
    return key, raters


def frac(kn):
    k, n = kn
    lo, hi = wilson(k, n)
    return "%d/%d (%.0f–%.0f%%)" % (k, n, 100 * lo, 100 * hi) if n else "–"


def report(key, raters, calls=None):
    calls = machine_calls() if calls is None else calls
    out = ["# Results: the blind reader test", "",
           "Generated by `python lore/reader/analyze.py` from `key.json` and `ratings/`. Intervals are "
           "Wilson 95%; tests are exact two-sided sign tests. With 8 triples these are measurements of "
           "direction and size, not of significance (README.md).", ""]
    if not raters:
        return "\n".join(out + ["No ratings yet: put an export from `rate.html` in `lore/reader/ratings/`.", ""])
    for name, ratings in sorted(raters.items()):
        rs = rows(key, ratings)
        for label, s in (("all triples", summarize(rs)), ("without triples marked seen before", summarize(rs, True))):
            pm = s["prefer"]["misc"]
            out += ["## %s: %s (%d fully rated)" % (name, label, s["n"]), "",
                    "| | |", "|---|---|",
                    "| **R1** prefers the memory follow-up, /misc/ | %s, sign test p = %.3f |"
                    % (frac(pm), sign_test(pm[0], pm[1] - pm[0])),
                    "| R2 prefers the memory follow-up, /x/ | %s |" % frac(s["prefer"]["x"]),
                    "| R1b ... where the source was identified / not | %s / %s |"
                    % (frac(s["prefer_identified"]), frac(s["prefer_not_identified"])),
                    "| **R3** says it picks up the earlier thread: memory / no-memory | %s / %s |"
                    % (frac(s["pickup"]["memory"]), frac(s["pickup"]["none"])),
                    "| R3b ... memory follow-ups where the source was identified | %s |" % frac(s["pickup_identified"]),
                    "| would repost: memory / no-memory | %s / %s |" % (frac(s["repost"]["memory"]), frac(s["repost"]["none"])), "",
                    "| scale | memory − no-memory, mean (all) | higher / lower (all) | mean (/misc/) |",
                    "|---|---:|---:|---:|"]
            for sc in SCALES:
                d, dm = s["diff"][sc], s["diff_misc"][sc]
                out.append("| %s | %s | %d / %d | %s |" % (
                    sc, "%+.2f" % (sum(d) / len(d)) if d else "–", sum(x > 0 for x in d), sum(x < 0 for x in d),
                    "%+.2f" % (sum(dm) / len(dm)) if dm else "–"))
            out.append("")
        ag = agreement(rs, calls)
        if ag:
            out += ["**R5, the reader's 'picks up' against the machine calls** on the same follow-ups:", "",
                    "| instrument | follow-ups | agree | κ |", "|---|---:|---:|---:|"]
            for inst, v in ag.items():
                out.append("| %s | %d | %d | %s |" % (inst, v["n"], v["agree"],
                                                       "%.2f" % v["kappa"] if v["kappa"] is not None else "–"))
            out.append("")
    return "\n".join(out)


def main():
    key, raters = load()
    with open(os.path.join(HERE, "RESULTS.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(report(key, raters))
    print("wrote lore/reader/RESULTS.md (%d raters)" % len(raters))


if __name__ == "__main__":
    main()
