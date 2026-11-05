#!/usr/bin/env python3
"""Exploratory analyses of the lore boards: NOT pre-registered, decided after seeing the results.

  python lore/explore.py          writes lore/exploratory.json and prints a summary

Why they exist: memory targets turned out to write far longer posts than their no-memory twins (on
/x/, four times longer), and longer text overlaps any source by chance, so the pre-registered
transfer flag mixes source-specific transfer with length. These separate the two:

  identification   every target scored against every source its pairing rules allowed (no shared
                   topic tag, not its topic twin): the same target text for every candidate, so
                   length cannot help. Does its real source score highest? Chance is 1/candidates.
  register         post length of memory targets against their source's, and of no-memory twins
  genre            the pre-registered genre terms, memory against no-memory (H4 compared headers)
  gate             which words the substring gate withheld, and in which arm
"""
import json, os, re, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze as A
import board as B
import judge as J
import tracker as T


def score(r):
    """Transferred material: occurrences of items, plus five per reference."""
    return sum(i["uses"] for i in r["items"]) + 5 * len(r["references"])


def identification(run, common):
    """Every target against every source on its board but its topic twin. Candidates for the
    identification test are those its pairing rules allowed (no shared tag); the transfer flag
    against every unseen source shows how much a long text overlaps sources by chance."""
    sources = {k: v for k, v in run.items() if k[2] is None}
    twin = {(k[0], v["opener"]): v for k, v in sources.items()}
    out = {}
    for (b, tid, arm), t in sorted(run.items(), key=lambda kv: str(kv[0])):
        if arm is None:
            continue
        tw = twin.get((b, t["opener"]))
        scores, unseen_flags = {}, []
        for (sb, sid, _), s in sources.items():
            if sb != b or s is tw:
                continue
            bg = [x["posts"] for k, x in sources.items() if k != (b, sid, None)]
            r = T.track(t["posts"], s["posts"], bg, target_no=t["no"], source_no=s["no"],
                        source_shown=arm == "memory" and sid == t["source"],
                        topic_twin=tw["posts"] if tw else None, board=t["board"],
                        target_cast=t["cast"], common=common)
            if sid != t["source"]:
                unseen_flags.append(r["transfer"])
            if not set(B.TAGS[s["opener"]]) & set(B.TAGS[t["opener"]]):
                scores[sid] = score(r)
        real = scores[t["source"]]
        others = [v for k, v in scores.items() if k != t["source"]]
        out[(b, tid, arm)] = {"candidates": len(scores), "real": real, "top": real > max(others),
                              "percentile": (sum(v < real for v in others)
                                             + 0.5 * sum(v == real for v in others)) / len(others),
                              "unseen_flagged": sum(unseen_flags), "unseen": len(unseen_flags)}
    return out


def mean_len(t):
    return statistics.mean([len(p["text"]) for p in t["posts"][1:] if p.get("text") and not p.get("withheld")] or [0])


def corr(u, v):
    mu, mv = statistics.mean(u), statistics.mean(v)
    num = sum((a - mu) * (c - mv) for a, c in zip(u, v))
    den = (sum((a - mu) ** 2 for a in u) * sum((c - mv) ** 2 for c in v)) ** 0.5
    return num / den if den else None


def main():
    run = J.load_run()
    common = T.load_reference(T.REF_SHARE)
    ident = identification(run, common)
    report = {"note": "exploratory, not pre-registered"}
    lines = []
    for b in ("x", "misc"):
        for arm in ("memory", "none"):
            rows = [v for (bb, _, a), v in ident.items() if bb == b and a == arm]
            chance = sum(1 / r["candidates"] for r in rows)
            unseen = sum(r["unseen_flagged"] for r in rows) / sum(r["unseen"] for r in rows)
            report["identify_%s_%s" % (b, arm)] = {
                "top": sum(r["top"] for r in rows), "n": len(rows), "chance": chance,
                "mean_percentile": statistics.mean(r["percentile"] for r in rows),
                "flagged_against_unseen_sources": unseen}
            lines.append("%s %s: real source scores highest in %d/%d (chance %.1f), mean percentile %.2f; "
                         "flagged against sources it never saw %.0f%% of the time"
                         % (b, arm, sum(r["top"] for r in rows), len(rows), chance,
                            statistics.mean(r["percentile"] for r in rows), 100 * unseen))
    pairs = [(ident[(b, tid, "memory")]["top"], ident[(b, tid, "none")]["top"])
             for (b, tid, arm) in ident if arm == "memory"]
    bm, cm, p = A.mcnemar(pairs)
    up = sum(ident[(b, tid, "memory")]["percentile"] > ident[(b, tid, "none")]["percentile"]
             for (b, tid, arm) in ident if arm == "memory")
    down = sum(ident[(b, tid, "memory")]["percentile"] < ident[(b, tid, "none")]["percentile"]
               for (b, tid, arm) in ident if arm == "memory")
    report["identify_paired"] = {"memory_only": bm, "none_only": cm, "mcnemar_p": p,
                                 "percentile_higher": up, "percentile_lower": down,
                                 "percentile_sign_p": A.sign_test(up, down)}
    lines.append("paired: identified with memory only %d, without only %d, McNemar p = %.2g; "
                 "real-source percentile higher with memory in %d targets, lower in %d (p = %.2g)"
                 % (bm, cm, p, up, down, A.sign_test(up, down)))

    for b in ("x", "misc"):
        src, mem, none = [], [], []
        for (bb, tid, arm), t in run.items():
            if bb == b and arm == "memory":
                src.append(mean_len(run[(b, t["source"], None)]))
                mem.append(mean_len(t))
                none.append(mean_len(run[(b, tid, "none")]))
        longer = sum(m > n for m, n in zip(mem, none))
        report["register_%s" % b] = {"mean_chars_memory": statistics.mean(mem), "mean_chars_none": statistics.mean(none),
                                     "mean_chars_sources": statistics.mean(src), "r_memory_vs_source": corr(src, mem),
                                     "r_none_vs_source": corr(src, none), "memory_longer": longer, "n": len(mem),
                                     "sign_p": A.sign_test(longer, len(mem) - longer)}
        lines.append("%s register: memory posts %.0f chars, no-memory %.0f, sources %.0f; length follows the "
                     "source's at r = %.2f with memory, %.2f without; memory longer in %d/%d"
                     % (b, statistics.mean(mem), statistics.mean(none), statistics.mean(src),
                        corr(src, mem), corr(src, none), longer, len(mem)))

    for b in ("x", "misc"):
        diffs = [(A.genre_share(run[(b, tid, "memory")]["posts"][1:]), A.genre_share(run[(b, tid, "none")]["posts"][1:]))
                 for (bb, tid, arm) in run if bb == b and arm == "memory"]
        pos, neg = sum(m > n for m, n in diffs), sum(m < n for m, n in diffs)
        report["genre_%s" % b] = {"memory": statistics.mean(m for m, _ in diffs), "none": statistics.mean(n for _, n in diffs),
                                  "higher": pos, "lower": neg, "sign_p": A.sign_test(pos, neg)}
        lines.append("%s genre terms: memory %.3f of posts, no-memory %.3f; memory higher in %d, lower in %d (p = %.2g)"
                     % (b, report["genre_%s" % b]["memory"], report["genre_%s" % b]["none"], pos, neg, A.sign_test(pos, neg)))

    q = [json.loads(l) for l in open(os.path.join(B.PRIVATE, "run", "quarantine.jsonl"), encoding="utf-8")]
    gate = {}
    for d in q:
        text = d["post"]["text"].lower()
        whole = any(re.search(r"\b%s\b" % re.escape(m.strip()), text) for m in d["matched"])
        role = "source" if d["thread"].startswith("s") else d["arm"]
        key = "%s %s" % (d["board"], role)
        gate.setdefault(key, {"withheld": 0, "substring_only": 0})
        gate[key]["withheld"] += 1
        gate[key]["substring_only"] += not whole
    report["gate"] = gate
    lines.append("gate: %d posts withheld, %d of them on a substring inside an innocent word; by board and arm: %s"
                 % (len(q), sum(v["substring_only"] for v in gate.values()),
                    ", ".join("%s %d (%d substring)" % (k, v["withheld"], v["substring_only"]) for k, v in sorted(gate.items()))))
    with open(os.path.join(HERE, "exploratory.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
