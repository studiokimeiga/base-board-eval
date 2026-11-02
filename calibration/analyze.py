#!/usr/bin/env python3
"""Compare the reader's blind ratings with the AI judges' on the calibration set, and on the
round 9 set.

  python calibration/analyze.py            write calibration/RESULTS.md
  python calibration/analyze.py --check    exit 1 if RESULTS.md is stale

Reads key.json and key-r9.json, the judges' scores-*.json, every export in ratings/ and round 9's
own judge scores (spike/judging/r9/), and computes exactly the hypotheses and questions fixed in
README.md before the reader rated anything.
"""
import glob, itertools, json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
JUDGING = os.path.join(os.path.dirname(HERE), "spike", "judging")
sys.path.insert(0, JUDGING)
from ledger import ROUNDS, collapse, load_round, mean, spearman            # noqa: E402

SCALES = ["believable", "interest", "joke", "deadpan", "overall"]
SOURCES = ["bestof", "smallrand", "gemini", "rolesshort", "qwenpick"]
HOSTED = ["gemini", "rolesshort", "qwenpick"]
PHONEBOOK = ("threads.json", 11)
RESULTS = os.path.join(HERE, "RESULTS.md")
BOOT = 2000
# The round 9 set (README.md, "The round 9 set"): its arms, and its questions as (name, arm,
# baseline, what it asks, the reader's primary readings). R3 is round 9's own question for the
# reader, whose criterion is met when both its readings come out higher.
R9_ARMS = ["gemini9neutral", "gemini9", "rolesshort9"]
R9_QUESTIONS = [("R1", "gemini9neutral", "gemini9", "the `/x/` label", ["humour"]),
                ("R2", "rolesshort9", "gemini9", "temperaments under `/x/`", ["humour"]),
                ("R3", "gemini9neutral", "rolesshort9", "round 9's question for the reader", ["interest", "humour"])]
R9_CRITERION = "R3"
# humour is the mean of the reader's two humour scales; round 9's judges scored a single one
R9_SCALES = ["humour", "interest", "joke", "deadpan", "overall"]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def complete(v):
    return all(isinstance(v.get(s), (int, float)) and not isinstance(v.get(s), bool) for s in SCALES)


def readers(here):
    """Each reader's ratings over all their exports. A thread takes its latest complete rating, by
    the rating's own time (else its export's), so an export from a fresh browser can't blank a
    thread rated before; the two sets never share an item id."""
    best = {}
    for f in glob.glob(os.path.join(here, "ratings", "*.json")):
        d = read_json(f)
        mine = best.setdefault("reader:" + (d.get("rater") or os.path.basename(f)[:-5]), {})
        for i, v in d["ratings"].items():
            when = (v.get("t") or d.get("exported") or "", d.get("exported") or "", f)
            if complete(v) and (i not in mine or when > mine[i][0]):
                mine[i] = (when, v)
    return {name: {i: v for i, (_, v) in r.items()} for name, r in best.items()}


def load(here=HERE, s=""):
    """key, {rater: {item: scores}}, and the items each reader had seen before, for the calibration
    set or (s="r9") the round 9 set. Two Claude passes are also averaged item by item into 'claude'."""
    x = "-" + s if s else ""
    key = read_json(os.path.join(here, "key%s.json" % x))
    raters, seen = {}, {}
    for p in ("A", "B"):
        merged = {}
        for f in sorted(glob.glob(os.path.join(here, "scores%s-claude-%s*.json" % (x, p)))):
            merged.update(read_json(f))
        if merged:
            raters["claude-" + p] = merged
    if os.path.exists(os.path.join(here, "scores%s-gpt.json" % x)):
        raters["gpt"] = read_json(os.path.join(here, "scores%s-gpt.json" % x))
    for name, r in readers(here).items():
        raters[name] = r
        seen[name] = {i for i, v in r.items() if v.get("seen") and i in key}
    for r in raters.values():
        for i in list(r):
            if i not in key or not complete(r[i]):
                del r[i]
    raters = {n: r for n, r in raters.items() if r}          # e.g. a reader of only the other set
    both = set(raters.get("claude-A", {})) & set(raters.get("claude-B", {}))
    if both:
        raters["claude"] = {i: {s: (raters["claude-A"][i][s] + raters["claude-B"][i][s]) / 2
                                for s in SCALES} for i in both}
    return key, raters, seen


def gap(pairs, scale):
    """mean(bestof) - mean(hosted) over (source, scores) pairs; hosted pools the bake-off arms."""
    b = [v[scale] for s, v in pairs if s == "bestof"]
    h = [v[scale] for s, v in pairs if s in HOSTED]
    return mean(b) - mean(h) if b and h else float("nan")


def pairs(key, scores, ids):
    return [(key[i]["source"], scores[i]) for i in ids if i in scores]


def rho(a, b, scale, ids, other=None):
    """Spearman ρ of a's scale against b's (or b's other scale) over the ids both rated; None
    until the items differ."""
    ids = [i for i in ids if i in a and i in b]
    return spearman([a[i][scale] for i in ids], [b[i][other or scale] for i in ids]), len(ids)


def usable(v):
    """H1's reading of a judge's ρ with the reader."""
    return ("not enough ratings" if v is None else "usable as a first screen" if v >= 0.6
            else "weak" if v >= 0.3 else "not usable")


def boot(stat, ids, key, seed=7):
    """Bootstrap 95% interval of stat(list of item ids), resampling items within each source."""
    rng = random.Random(seed)
    groups = {}
    for i in sorted(ids):
        groups.setdefault(key[i]["source"], []).append(i)
    vals = []
    for _ in range(BOOT):
        v = stat([rng.choice(g) for g in groups.values() for _ in g])
        if v is not None and v == v:
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def rank_of(scores, item):
    """1 = best on overall; tied items share their average rank."""
    mine = scores[item]["overall"]
    above = sum(v["overall"] > mine for v in scores.values())
    same = sum(v["overall"] == mine for v in scores.values())
    return above + (same + 1) / 2


def f2(x):
    return "–" if x is None or x != x else "%.2f" % x


def build(here=HERE):
    key, raters, seen = load(here)
    readers = sorted(r for r in raters if r.startswith("reader:"))
    judges = [r for r in ("claude", "claude-A", "claude-B", "gpt") if r in raters]
    main_judges = [r for r in ("claude", "gpt") if r in raters]
    lines = ["# Calibration results", "",
             "Generated by `python calibration/analyze.py` from `key.json`, the judges' "
             "`scores-*.json` and the reader's exports in `ratings/`. The hypotheses are the ones "
             "fixed in README.md before anything was rated. `claude` is the item-by-item mean of "
             "the two Claude passes.", "",
             "Raters so far: %s." % (", ".join("%s (%d items)" % (r, len(raters[r])) for r in raters)
                                     or "none"), ""]
    if not readers:
        lines += ["**The reader has not rated the set yet**, so H1 to H4 are waiting on them; only the "
                  "AI judges' side is below.", ""]

    lines += ["## Means by source", "",
              "| rater | source | n | %s | repost |" % " | ".join(SCALES),
              "|---|---|---:|%s" % ("---:|" * (len(SCALES) + 1))]
    for r in readers + judges:
        for s in SOURCES:
            ids = [i for i in raters[r] if key[i]["source"] == s]
            if not ids:
                continue
            rep = [bool(raters[r][i]["repost"]) for i in ids if raters[r][i].get("repost") is not None]
            lines.append("| %s | %s | %d | %s | %s |" % (
                r, s, len(ids), " | ".join(f2(mean([raters[r][i][c] for i in ids])) for c in SCALES),
                "%d of %d" % (sum(rep), len(rep)) if rep else "–"))
    lines.append("")

    names = readers + judges
    if len(names) > 1:
        lines += ["## Agreement", "", "Spearman ρ between two raters over the items both rated.", "",
                  "| pair | n | %s |" % " | ".join(SCALES), "|---|---:|%s" % ("---:|" * len(SCALES))]
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                x, y = raters[names[a]], raters[names[b]]
                lines.append("| %s vs %s | %d | %s |" % (
                    names[a], names[b], rho(x, y, "overall", list(key))[1],
                    " | ".join(f2(rho(x, y, c, list(key))[0]) for c in SCALES)))
        lines.append("")

    lines += ["## H1: does a judge agree with the reader on overall?", ""]
    if "claude-A" in raters and "claude-B" in raters:
        v, n = rho(raters["claude-A"], raters["claude-B"], "overall", list(key))
        lo, hi = boot(lambda s: rho(raters["claude-A"], raters["claude-B"], "overall", s)[0],
                      [i for i in key if i in raters["claude-A"] and i in raters["claude-B"]], key)
        lines += ["Ceiling, Claude pass A vs. pass B: ρ = %s [%s, %s] over %d items." % (
            f2(v), f2(lo), f2(hi), n), ""]
    for r in readers:
        for j in main_judges:
            ids = [i for i in key if i in raters[r] and i in raters[j]]
            v, n = rho(raters[r], raters[j], "overall", ids)
            lo, hi = boot(lambda s: rho(raters[r], raters[j], "overall", s)[0], ids, key)
            verdict = usable(v)
            unseen = [i for i in ids if i not in seen.get(r, set())]
            lines += ["- %s vs %s: ρ = %s [%s, %s] over %d items: **%s**. Without items the reader had "
                      "seen before: ρ = %s over %d." % (r, j, f2(v), f2(lo), f2(hi), n, verdict,
                                                         f2(rho(raters[r], raters[j], "overall", unseen)[0]),
                                                         len(unseen))]
    if not readers:
        lines.append("Waiting on the reader.")
    lines.append("")

    lines += ["## H2: the deadpan blind spot", "",
              "Gap = mean(bestof) − mean(gemini, rolesshort and qwenpick pooled).", "",
              "| rater | deadpan gap | overall gap |", "|---|---:|---:|"]
    for r in readers + judges:
        p = pairs(key, raters[r], list(key))
        lines.append("| %s | %s | %s |" % (r, f2(gap(p, "deadpan")), f2(gap(p, "overall"))))
    lines.append("")
    for r in readers:
        for j in main_judges:
            ids = [i for i in key if i in raters[r] and i in raters[j]]

            def diff(s, r=r, j=j):
                return gap(pairs(key, raters[r], s), "deadpan") - gap(pairs(key, raters[j], s), "deadpan")
            d = diff(ids)
            lo, hi = boot(diff, ids, key)
            verdict = "supported" if lo > 0 else "direction only" if d > 0 else "not supported"
            unseen = [i for i in ids if i not in seen.get(r, set())]
            lines.append("- reader gap minus %s gap: %s [%s, %s]: **%s**. Without seen items: %s." % (
                j, f2(d), f2(lo), f2(hi), verdict, f2(diff(unseen))))
    if not readers:
        lines.append("The reader's side is waiting.")
    lines.append("")

    lines += ["## H3: temperaments vs. plain Gemini", "",
              "| rater | joke: rolesshort − gemini | overall: rolesshort − gemini |", "|---|---:|---:|"]
    for r in readers + judges:
        cells = []
        for c in ("joke", "overall"):
            g = {s: [v[c] for i, v in raters[r].items() if key[i]["source"] == s] for s in ("rolesshort", "gemini")}
            cells.append(f2(mean(g["rolesshort"]) - mean(g["gemini"])) if g["rolesshort"] and g["gemini"] else "–")
        lines.append("| %s | %s | %s |" % (r, cells[0], cells[1]))
    lines.append("")

    pb = next((i for i, v in key.items() if (v["file"], v["thread"]) == PHONEBOOK), None)
    lines += ["## H4: the phonebook thread", ""]
    for r in readers + judges:
        if pb in raters[r]:
            k = rank_of(raters[r], pb)
            lines.append("- %s: overall %s, rank %s of %d%s." % (
                r, f2(raters[r][pb]["overall"]), f2(k), len(raters[r]), " (top 7)" if k <= 7 else ""))
    lines.append("")

    lines += ["## The prediction made for the AI judges", "",
              "Before judging: both families put gemini or rolesshort first on overall, bestof below "
              "both, and smallrand last.", ""]
    for j in judges:
        g = {s: [v["overall"] for i, v in raters[j].items() if key[i]["source"] == s] for s in SOURCES}
        if not all(g.values()):
            lines.append("- %s: not every source rated yet." % j)
            continue
        g = {s: mean(v) for s, v in g.items()}
        order = sorted(SOURCES, key=lambda s: (-g[s], s))
        top, low = max(g.values()), min(g.values())
        held = (max(g["gemini"], g["rolesshort"]) == top and g["bestof"] < min(g["gemini"], g["rolesshort"])
                and g["smallrand"] == low)
        ties = [s for s in SOURCES if s != "smallrand" and g[s] == low]
        lines.append("- %s: %s: **%s**%s." % (
            j, " ≥ ".join("%s %s" % (s, f2(g[s])) for s in order), "held" if held else "did not hold",
            " (smallrand tied for last with %s)" % ", ".join(ties) if held and ties else ""))
    lines.append("")
    if os.path.exists(os.path.join(here, "key-r9.json")):
        lines += round9(here)
    return "\n".join(lines)


def round9_judges(key):
    """Round 9's own judges on the round 9 set: each thread's mean over its five readings, on
    rubric v2, read side by side with the round's other arms. Round 9's packet for opener n held
    thread n - 1 of every arm's file (round3_judge.py)."""
    folder, judges = next((f, j) for rnd, f, j, *_ in ROUNDS if rnd == "9")
    if not os.path.exists(os.path.join(JUDGING, folder, "key.json")):
        return {}
    cells = collapse(load_round(folder, judges)[1])
    return {"r9-" + fam: {i: {s: c[(str(v["thread"] + 1), v["source"])][s] for s in ("interest", "humour", "overall")}
                          for i, v in key.items()}
            for fam, c in sorted(cells.items())}


def arm_diff(scores, key, a, b, scale, ids):
    """mean(a) - mean(b) on scale, over the given items of arms a and b."""
    x = [scores[i][scale] for i in ids if key[i]["source"] == a]
    y = [scores[i][scale] for i in ids if key[i]["source"] == b]
    return mean(x) - mean(y) if x and y else float("nan")


def perm_p(x, y):
    """Exact two-sided permutation test of mean(x) - mean(y): the share of all ways to split the
    pooled scores into groups of len(x) and len(y) whose difference is as far from zero or further."""
    if not x or not y:
        return float("nan")
    pool, k = x + y, len(x)
    total, obs = math.fsum(pool), abs(mean(x) - mean(y))
    sums = [math.fsum(c) for c in itertools.combinations(pool, k)]
    return sum(abs(s / k - (total - s) / (len(pool) - k)) >= obs - 1e-9 for s in sums) / len(sums)


def paired(scores, key, a, b, scale, ids):
    """The mean of a - b over the openers both arms have among ids (round 9's files hold one thread
    per opener, in the same order), and how many openers that is."""
    by = {}
    for i in ids:
        by.setdefault(key[i]["thread"], {})[key[i]["source"]] = scores[i][scale]
    d = [v[a] - v[b] for v in by.values() if a in v and b in v]
    return mean(d), len(d)


def reading(d, p):
    """A primary reading: higher or lower when the two-sided p is below 0.05."""
    return "higher" if p < 0.05 and d > 0 else "lower" if p < 0.05 and d < 0 else "no clear difference"


def f3(x):
    return "–" if x is None or x != x else "%.3f" % x


def round9(here):
    """The round 9 set's section of RESULTS.md: the questions fixed in README.md."""
    key, raters, seen = load(here, "r9")
    for r in raters.values():
        for v in r.values():
            v["humour"] = (v["joke"] + v["deadpan"]) / 2
    raters.update(round9_judges(key))
    readers_ = sorted(r for r in raters if r.startswith("reader:"))
    judges = [r for r in ("claude", "claude-A", "claude-B", "gpt", "r9-claude", "r9-gpt") if r in raters]
    lines = ["## Round 9 set", "",
             "The 18 round 9 threads in `key-r9.json`, rated apart from the set above, on the same page "
             "and scales (`rate.html?set=r9`); the questions are the ones fixed in README.md before the "
             "reader rated any of them. `r9-claude` and `r9-gpt` are round 9's own judges: each thread's "
             "mean over its five readings on rubric v2, read side by side with the round's other arms. "
             "`humour` is the mean of the reader's deliberate and deadpan humour; round 9's judges scored "
             "one humour scale. R1 to R3 give each difference of two arms' means, an exact two-sided "
             "permutation p over threads, and the difference over the openers both arms share. Only the "
             "**bold** scales are read for the reader: **higher** or **lower** when p < 0.05, once every "
             "thread of both arms is rated.", "",
             "Raters so far: %s." % (", ".join("%s (%d items)" % (r, len(raters[r])) for r in readers_ + judges)
                                     or "none"), ""]
    if not readers_:
        lines += ["**The reader has not rated this set yet**, so R1 to R4 are waiting on them; round 9's "
                  "judges are shown for reference.", ""]

    cols = ["believable", "interest", "joke", "deadpan", "humour", "overall"]
    lines += ["### Means by arm", "", "| rater | arm | n | %s | repost |" % " | ".join(cols),
              "|---|---|---:|%s" % ("---:|" * (len(cols) + 1))]
    for r in readers_ + judges:
        for a in R9_ARMS:
            ids = [i for i in raters[r] if key[i]["source"] == a]
            if not ids:
                continue
            rep = [bool(raters[r][i]["repost"]) for i in ids if raters[r][i].get("repost") is not None]
            lines.append("| %s | %s | %d | %s | %s |" % (
                r, a, len(ids), " | ".join(f2(mean([raters[r][i][c] for i in ids])) if c in raters[r][ids[0]]
                                           else "–" for c in cols),
                "%d of %d" % (sum(rep), len(rep)) if rep else "–"))
    lines.append("")

    for q, a, b, what, primary in R9_QUESTIONS:
        lines += ["### %s: %s (%s − %s)" % (q, what, a, b), "",
                  "| rater | scale | difference | p | same openers |", "|---|---|---:|---:|---:|"]
        found = {}                                      # (rater, scale) -> (difference, p)
        for r in readers_ + judges:
            ids = [i for i in raters[r] if key[i]["source"] in (a, b)]
            for c in R9_SCALES:
                if not ids or c not in raters[r][ids[0]]:
                    continue
                found[r, c] = (arm_diff(raters[r], key, a, b, c, ids),
                               perm_p(*([raters[r][i][c] for i in ids if key[i]["source"] == s] for s in (a, b))))
                d, n = paired(raters[r], key, a, b, c, ids)
                lines.append("| %s | %s | %s | %s | %s |" % (r, "**%s**" % c if c in primary else c,
                                                             f2(found[r, c][0]), f3(found[r, c][1]),
                                                             "%s over %d" % (f2(d), n) if n else "–"))
        lines.append("")
        full = sum(v["source"] in (a, b) for v in key.values())
        for r in readers_:
            ids = [i for i in raters[r] if key[i]["source"] in (a, b)]
            if len(ids) < full:
                lines.append("- %s: waiting for ratings (%d of the %d threads)." % (r, len(ids), full))
                continue
            unseen = [i for i in ids if i not in seen.get(r, set())]
            said = [reading(*found[r, c]) for c in primary]
            lines.append("- %s: %s%s. Without seen items: %s (%d threads)." % (
                r, ", ".join("%s **%s** (p = %s)" % (c, s, f3(found[r, c][1])) for c, s in zip(primary, said)),
                "; round 9's criterion **%s**" % ("met" if set(said) == {"higher"} else "not met")
                if q == R9_CRITERION else "",
                ", ".join("%s %s" % (c, f2(arm_diff(raters[r], key, a, b, c, unseen))) for c in primary),
                len(unseen)))
        if not readers_:
            lines.append("Waiting on the reader.")
        lines.append("")

    lines += ["### R4: does a judge rank these threads as the reader does?", "",
              "Spearman ρ between the reader and each judge over the threads both rated. Against round 9's "
              "judges, each of the reader's humour scales is set against their one humour score. The "
              "verdict is H1's, on overall, once the reader has rated all %d threads." % len(key), ""]
    if "r9-claude" in raters and "r9-gpt" in raters:
        rc, rg = raters["r9-claude"], raters["r9-gpt"]
        v, n = rho(rc, rg, "overall", list(key))
        lo, hi = boot(lambda s: rho(rc, rg, "overall", s)[0], [i for i in key if i in rc and i in rg], key)
        lines += ["For reference, round 9's Claude against its gpt-5.4: ρ = %s [%s, %s] over %d threads."
                  % (f2(v), f2(lo), f2(hi), n), ""]
    pairs_ = [(r, j, [i for i in key if i in raters[r] and i in raters[j]]) for r in readers_ for j in judges]
    pairs_ = [(r, j, ids) for r, j, ids in pairs_ if ids]
    if pairs_:
        lines += ["| pair | n | overall | interest | humour | joke | deadpan |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for r, j, ids in pairs_:
            lines.append("| %s vs %s | %d | %s |" % (r, j, len(ids), " | ".join(
                f2(rho(raters[r], raters[j], c, ids, c if c in raters[j][ids[0]] else "humour")[0])
                for c in ("overall", "interest", "humour", "joke", "deadpan"))))
        lines.append("")
    for r, j, ids in pairs_:
        v, n = rho(raters[r], raters[j], "overall", ids)
        lo, hi = boot(lambda s, r=r, j=j: rho(raters[r], raters[j], "overall", s)[0], ids, key)
        unseen = [i for i in ids if i not in seen.get(r, set())]
        lines.append("- %s vs %s: ρ = %s [%s, %s] over %d items: %s. Without items the reader had seen "
                     "before: ρ = %s over %d." % (
                         r, j, f2(v), f2(lo), f2(hi), n,
                         "**%s**" % usable(v) if n == len(key) else
                         "waiting for ratings (%d of %d threads)" % (n, len(key)),
                         f2(rho(raters[r], raters[j], "overall", unseen)[0]), len(unseen)))
    if not readers_:
        lines.append("Waiting on the reader.")
    lines.append("")
    return lines


def main():
    text = build()
    if sys.argv[1:] == ["--check"]:
        old = ""
        if os.path.exists(RESULTS):
            with open(RESULTS, encoding="utf-8") as f:
                old = f.read()
        if old != text:
            print("RESULTS.md is stale: run python calibration/analyze.py")
            sys.exit(1)
        print("RESULTS.md matches the inputs")
        return
    with open(RESULTS, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", RESULTS)


if __name__ == "__main__":
    main()
