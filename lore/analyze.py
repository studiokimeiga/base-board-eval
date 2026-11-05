#!/usr/bin/env python3
"""The pre-registered analysis (PREREGISTRATION.md) of the lore boards.

  python lore/analyze.py          writes lore/RESULTS.md and lore/results.json

Reads the private run (lore/private/run/), the public schedule, the frozen tracker with its
reference list, and whatever judge verdicts exist in lore/judging/. Every target is scored against
its source in both arms; the background is every other source on either board, and the topic twin
is the source written from the target's own opener on the same board.
"""
import json, math, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tracker as T

SEED = 20261102
GENRE = ("ghost ghosts ghostly haunt haunted haunting demon demons demonic entity entities paranormal "
         "supernatural occult ritual rituals cursed curse possessed possession apparition poltergeist "
         "exorcism seance ouija omen phantom specter spectre wraith doppelganger skinwalker cryptid "
         "eldritch liminal backrooms otherworldly uncanny eerie creepy sinister ominous unholy").split()
GENRE_PHRASES = ["shadow people", "shadow person", "the void", "not human", "another dimension",
                 "glitch in the matrix"]
GENRE_RX = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(x) for x in GENRE + GENRE_PHRASES))
GATE_WORDS = None


# ---- statistics ----
def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def sign_test(pos, neg):
    """Exact two-sided sign test (ties dropped by the caller)."""
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def mcnemar(pairs):
    """Exact McNemar on (memory, none) booleans: the sign test on discordant pairs."""
    b = sum(1 for m, n in pairs if m and not n)
    c = sum(1 for m, n in pairs if n and not m)
    return b, c, sign_test(b, c)


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def f_kappa(k):
    """κ for a table; undefined (both raters constant) shows as a dash."""
    return "–" if k is None else "%.2f" % k


def bootstrap_diff(clusters, reps=2000, seed=SEED):
    """95% interval for P(memory) - P(none), resampling clusters of (memory, none) pairs."""
    rng = random.Random(seed)
    stats = []
    for _ in range(reps):
        pick = [p for _ in clusters for p in rng.choice(clusters)]
        stats.append((sum(m for m, _ in pick) - sum(n for _, n in pick)) / len(pick))
    stats.sort()
    return stats[int(0.025 * reps)], stats[min(reps - 1, int(0.975 * reps))]


def genre_share(posts):
    texts = [p["text"].lower() for p in posts if p.get("text") and not p.get("withheld")]
    if not texts:
        return None
    return sum(1 for t in texts if GENRE_RX.search(t)) / len(texts)


# ---- loading and scoring ----
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def score_all(run, common):
    sources = {k: v for k, v in run.items() if k[2] is None}
    twin = {(k[0], v["opener"]): v for k, v in sources.items()}
    out = {}
    for (b, tid, arm), t in sorted(run.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
        if arm is None:
            continue
        s = sources[(b, t["source"], None)]
        bg = [x["posts"] for k, x in sources.items() if k != (b, t["source"], None)]
        tw = twin.get((b, t["opener"]))
        out[(b, tid, arm)] = T.track(t["posts"], s["posts"], bg, target_no=t["no"], source_no=s["no"],
                                     source_shown=arm == "memory", topic_twin=tw["posts"] if tw else None,
                                     board=t["board"], target_cast=t["cast"], common=common)
    return out


def safe(name):
    global GATE_WORDS
    if GATE_WORDS is None:
        sys.path.insert(0, os.path.dirname(HERE))
        from generate import HARM
        GATE_WORDS = [g.strip() for g in HARM] + ["cunt", "cock", "tits", "slut", "pussy", "porn", "rape"]
    return "[gated]" if any(g in name for g in GATE_WORDS) else name


def judges(folder):
    """{family: {(board, target, arm): verdict}} from lore/judging/."""
    key_path = os.path.join(folder, "key.json")
    if not os.path.exists(key_path):
        return {}
    key = load(key_path)
    out = {}
    for fam in ("gpt", "claude"):
        p = os.path.join(folder, "scores-%s.json" % fam)
        if os.path.exists(p):
            v = load(p)["items"]
            out[fam] = {(key[i]["board"], key[i]["target"], key[i]["arm"]): x for i, x in v.items()}
    return out


# ---- the report ----
def pct(k, n):
    lo, hi = wilson(k, n)
    return "%d/%d (%.0f%%, %.0f–%.0f)" % (k, n, 100 * k / n if n else 0, 100 * lo, 100 * hi)


def main(argv=None):
    import argparse
    from judge import load_run
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="the run folder (default lore/private/run)")
    ap.add_argument("--judging", default=os.path.join(HERE, "judging"))
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args(argv)
    run = load_run(a.run)
    sched = load(os.path.join(HERE, "schedule.json"))
    common = T.load_reference(T.REF_SHARE)
    res = score_all(run, common)
    jud = judges(a.judging)
    boards = sorted({k[0] for k in res}, key=["x", "misc"].index)
    targets = {t["id"]: t for t in sched["targets"]}
    paired = [(b, tid) for b, tid, arm in res if arm == "memory" and (b, tid, "none") in res]

    def has_numbers(r):
        return r["format_play"]["own_number"] + r["format_play"]["near_number"] > 0

    def lore(r, v):
        return bool(r["transfer"] and r["uptake"] >= 2 and v and v["borrows"] and v["kinds"]["reuse"] > 0)

    out = ["# Results: does lore spread between threads when the board has memory?", "",
           "Generated by `python lore/analyze.py` from the private run (hashes in `MANIFEST.sha256`), "
           "the public schedule, the frozen tracker (`REF_SHARE` %s) and the judges' verdicts in "
           "`lore/judging/`. Intervals are Wilson 95%%. Read `REPORT.md` for what it means." % T.REF_SHARE, ""]

    # per board
    out += ["## Per board", "",
            "| board | targets | transfer | grounded reference | uptake ≥2 posters | thread-number play | "
            "items per target | withheld posts | empty posts |",
            "|---|---:|---|---|---|---|---:|---:|---:|"]
    for b in boards:
        for arm in ("memory", "none"):
            rs = [res[(b, tid, arm)] for bb, tid in paired if bb == b]
            ts = [run[(b, tid, arm)] for bb, tid in paired if bb == b]
            posts = [p for t in ts for p in t["posts"][1:]]
            out.append("| %s %s | %d | %s | %s | %s | %s | %.2f | %d | %d |" % (
                {"x": "/x/", "misc": "/misc/"}[b], arm, len(rs),
                pct(sum(r["transfer"] for r in rs), len(rs)),
                pct(sum(bool(r["references"]) for r in rs), len(rs)),
                pct(sum(r["uptake"] >= 2 for r in rs), len(rs)),
                pct(sum(has_numbers(r) for r in rs), len(rs)),
                sum(len(r["items"]) for r in rs) / max(1, len(rs)),
                sum(1 for p in posts if p.get("withheld")), sum(1 for p in posts if not p.get("text"))))
    # sources too, for the record
    out += ["", "Sources, written with nothing above them: %s." % ", ".join(
        "%s %d threads, %d withheld posts" % ({"x": "/x/", "misc": "/misc/"}[b],
                                              sum(1 for k in run if k[0] == b and k[2] is None),
                                              sum(1 for k, t in run.items() if k[0] == b and k[2] is None
                                                  for p in t["posts"] if p.get("withheld")))
        for b in boards)]

    # H1
    out += ["", "## H1: the memory effect (primary)", "",
            "| scope | pairs | memory only | none only | McNemar p | difference, 95% interval |",
            "|---|---:|---:|---:|---:|---|"]
    summary = {}
    for scope, keep in [("both boards", lambda b: True)] + [({"x": "/x/", "misc": "/misc/"}[b], (lambda bb: lambda b: b == bb)(b)) for b in boards]:
        ps = [(b, tid) for b, tid in paired if keep(b)]
        pairs = [(res[(b, tid, "memory")]["transfer"], res[(b, tid, "none")]["transfer"]) for b, tid in ps]
        clusters = {}
        for (b, tid), pr in zip(ps, pairs):
            clusters.setdefault(targets[tid]["source"], []).append(pr)
        bm, cm, p = mcnemar(pairs)
        lo, hi = bootstrap_diff(list(clusters.values()))
        diff = (sum(m for m, _ in pairs) - sum(n for _, n in pairs)) / len(pairs)
        out.append("| %s | %d | %d | %d | %.4f | %+.2f (%+.2f to %+.2f) |" % (scope, len(pairs), bm, cm, p, diff, lo, hi))
        summary[scope] = {"pairs": len(pairs), "memory_only": bm, "none_only": cm, "p": p,
                          "diff": diff, "ci": [lo, hi]}
        if scope == "both boards":
            d = [sum(m for m, _ in c) - sum(n for _, n in c) for c in clusters.values()]
            pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
            robust = "Per-source sign test (robustness): %d sources more transfer with memory, %d fewer, p = %.4f." % (pos, neg, sign_test(pos, neg))
            items_d = [len(res[(b, tid, "memory")]["items"]) - len(res[(b, tid, "none")]["items"]) for b, tid in ps]
            items_line = ("Items per target, memory minus none: %d targets more, %d fewer, sign test p = %.4f."
                          % (sum(x > 0 for x in items_d), sum(x < 0 for x in items_d),
                             sign_test(sum(x > 0 for x in items_d), sum(x < 0 for x in items_d))))
    out += ["", robust, items_line]

    # judges
    if jud:
        out += ["", "## The blind judges", "",
                "Rates are over every item the judge saw; McNemar uses the targets judged in both arms.", "",
                "| judge | items | borrows: memory items | borrows: no-memory items | pairs | McNemar p | κ with tracker |",
                "|---|---:|---|---|---:|---:|---:|"]
        for fam, v in jud.items():
            ps = [(b, tid) for b, tid in paired if (b, tid, "memory") in v and (b, tid, "none") in v]
            pairs = [(v[(b, tid, "memory")]["borrows"], v[(b, tid, "none")]["borrows"]) for b, tid in ps]
            bm, cm, p = mcnemar(pairs)
            ks = [k for k in v if k in res]
            mem = [v[k]["borrows"] for k in ks if k[2] == "memory"]
            non = [v[k]["borrows"] for k in ks if k[2] == "none"]
            out.append("| %s | %d | %s | %s | %d | %.4f | %s |" % (
                fam, len(v), pct(sum(mem), len(mem)), pct(sum(non), len(non)), len(pairs), p,
                f_kappa(kappa([res[k]["transfer"] for k in ks], [v[k]["borrows"] for k in ks]))))
        out += ["", "By board (a family that judged only part of the items shows only what it saw):", "",
                "| judge | board | borrows: memory items | borrows: no-memory items |", "|---|---|---|---|"]
        for fam, v in jud.items():
            for b in boards:
                mem = [x["borrows"] for k, x in v.items() if k[0] == b and k[2] == "memory"]
                non = [x["borrows"] for k, x in v.items() if k[0] == b and k[2] == "none"]
                if mem or non:
                    out.append("| %s | %s | %s | %s |" % (fam, {"x": "/x/", "misc": "/misc/"}[b],
                                                         pct(sum(mem), len(mem)), pct(sum(non), len(non))))
        if len(jud) == 2:
            g, c = jud["gpt"], jud["claude"]
            ks = sorted(set(g) & set(c))
            kp = kappa([g[k]["borrows"] for k in ks], [c[k]["borrows"] for k in ks])
            out += ["", "Agreement between the families on %d shared items: κ = %s." % (len(ks), "%.2f" % kp if kp is not None else "–")]
        out += ["", "**H2, what kind of borrowing** (memory-arm items a judge says borrow; counts of each kind):", "",
                "| judge | reference | mix-up | reuse | coincidence |", "|---|---:|---:|---:|---:|"]
        for fam, v in jud.items():
            tot = {k: sum(x["kinds"][k] for kk, x in v.items() if kk[2] == "memory" and x["borrows"])
                   for k in ("reference", "mixup", "reuse", "coincidence")}
            out.append("| %s | %d | %d | %d | %d |" % (fam, tot["reference"], tot["mixup"], tot["reuse"], tot["coincidence"]))
        out += ["", "**L3, lore** (tracker transfer, at least two posters using it, and the judge calls a borrowing *reuse*):", "",
                "| judge | memory | none |", "|---|---|---|"]
        both = set(jud["gpt"]) & set(jud["claude"]) if len(jud) == 2 else set()
        for fam, v in list(jud.items()) + ([("either, on items both judged", None),
                                            ("both, on items both judged", None)] if both else []):
            row = []
            for arm in ("memory", "none"):
                if v is not None:          # a family on the items it judged
                    ks = [(b, tid, arm) for b, tid in paired if (b, tid, arm) in v]
                    k = sum(lore(res[x], v[x]) for x in ks)
                else:
                    ks = [(b, tid, arm) for b, tid in paired if (b, tid, arm) in both]
                    agree = any if fam.startswith("either") else all
                    k = sum(agree(lore(res[x], jud[f][x]) for f in jud) for x in ks)
                row.append(pct(k, len(ks)))
            out.append("| %s | %s | %s |" % (fam, row[0], row[1]))

    # H3
    pairs = [(has_numbers(res[(b, tid, "memory")]), has_numbers(res[(b, tid, "none")])) for b, tid in paired]
    bm, cm, p = mcnemar(pairs)
    out += ["", "## H3: thread-number play", "",
            "Targets mentioning their own thread number or a number near one on their page: memory %s, none %s; "
            "McNemar %d vs %d, p = %.4f. None of these count as memory." % (
                pct(sum(m for m, _ in pairs), len(pairs)), pct(sum(n for _, n in pairs), len(pairs)), bm, cm, p)]

    # H4
    if set(boards) == {"x", "misc"}:
        diffs, xs, ms = [], [], []
        for s in sched["sources"]:
            k1, k2 = ("x", s["id"], None), ("misc", s["id"], None)
            if k1 in run and k2 in run:
                diffs.append((genre_share(run[k1]["posts"][1:]), genre_share(run[k2]["posts"][1:])))
        for b, tid in paired:
            if b == "x" and ("misc", tid, "none") in run:
                diffs.append((genre_share(run[("x", tid, "none")]["posts"][1:]),
                              genre_share(run[("misc", tid, "none")]["posts"][1:])))
        diffs = [(x, m) for x, m in diffs if x is not None and m is not None]
        pos, neg = sum(x > m for x, m in diffs), sum(x < m for x, m in diffs)
        out += ["", "## H4: the board header", "",
                "Share of generated posts with a genre term, sources and no-memory targets paired across boards "
                "(%d pairs): /x/ %.3f, /misc/ %.3f. /x/ higher in %d pairs, lower in %d, sign test p = %.4f." % (
                    len(diffs), sum(x for x, _ in diffs) / len(diffs), sum(m for _, m in diffs) / len(diffs),
                    pos, neg, sign_test(pos, neg))]
        mt = {b: sum(res[(b, tid, "memory")]["transfer"] for bb, tid in paired if bb == b) for b in boards}
        out.append("Transfer on memory boards by header (open question): %s." % ", ".join(
            "%s %d of %d" % ({"x": "/x/", "misc": "/misc/"}[b], mt[b], sum(1 for bb, _ in paired if bb == b)) for b in boards))

    # H5
    out += ["", "## H5: recurrence (the same item reaches both targets of a source)", "",
            "| board | memory | none | items |", "|---|---:|---:|---|"]
    for b in boards:
        row, shown = {}, []
        for arm in ("memory", "none"):
            k = 0
            for s in sched["sources"]:
                ts = [t["id"] for t in sched["targets"] if t["source"] == s["id"] and (b, t["id"], arm) in res]
                if len(ts) == 2:
                    a1 = {i["item"] for i in res[(b, ts[0], arm)]["items"]}
                    a2 = {i["item"] for i in res[(b, ts[1], arm)]["items"]}
                    if a1 & a2:
                        k += 1
                        if arm == "memory":
                            shown.append("%s: %s" % (s["id"], ", ".join(sorted(safe(x) for x in a1 & a2))))
            row[arm] = k
        out.append("| %s | %d | %d | %s |" % ({"x": "/x/", "misc": "/misc/"}[b], row["memory"], row["none"], "; ".join(shown) or "–"))

    # every flagged target, for reading
    out += ["", "## Every flagged target", "", "Items are tracker items (gate-checked); refs are grounded references.", "",
            "| board | target | source | arm | items | refs | uptake | judges say borrows |", "|---|---|---|---|---|---|---:|---|"]
    rows = []
    for (b, tid, arm), r in sorted(res.items()):
        if not r["transfer"]:
            continue
        items = "; ".join("%s%s" % (safe(i["item"]), " ×%d" % i["uses"] if i["kind"] == "word" else "")
                          + (" (→ %s)" % ", ".join(safe(f) for f in i["fillers"][:3]) if i["construction"] else "")
                          for i in r["items"][:6])
        refs = ", ".join(sorted({"%s %s" % (x["kind"], safe(x["match"])) for x in r["references"]}))
        js = ", ".join("%s %s" % (f, "yes" if v.get((b, tid, arm), {}).get("borrows") else "no")
                       for f, v in jud.items() if (b, tid, arm) in v)
        out.append("| %s | %s | %s | %s | %s | %s | %d | %s |" % (
            {"x": "/x/", "misc": "/misc/"}[b], tid, targets[tid]["source"], arm, items or "–", refs or "–",
            r["uptake"], js or "–"))
        rows.append({"board": b, "target": tid, "arm": arm})

    spend = sum(t.get("spend", 0) for t in run.values())
    out += ["", "Generation spend logged in the thread files: $%.2f over %d threads." % (spend, len(run)), ""]
    with open(os.path.join(a.out, "RESULTS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"ref_share": T.REF_SHARE, "h1": summary,
                   "targets": [{"board": b, "target": tid, "arm": arm, "transfer": r["transfer"],
                                "items": [{"item": safe(i["item"]), "kind": i["kind"], "uses": i["uses"],
                                           "authors": len(i["authors"]), "construction": i["construction"],
                                           "origin": i["origin"]} for i in r["items"]],
                                "references": sorted({x["kind"] for x in r["references"]}),
                                "format_play": r["format_play"], "uptake": r["uptake"]}
                               for (b, tid, arm), r in sorted(res.items())]}, f, indent=1)
    return summary


if __name__ == "__main__":
    main()
