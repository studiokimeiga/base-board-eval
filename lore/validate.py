#!/usr/bin/env python3
"""Validate the lore tracker on two boards that already exist, before it is used on new ones.

  python lore/validate.py --data <folder with spike/remote/ and the original corpora>

  v2.1      the live board (spike/remote/board-v21.json): 18 threads, 5 with an earlier thread
            above them, hand-labelled in PREREGISTRATION.md before the tracker existed
  memory    the local board-memory run (threads.memory.json, experiments/generate17.py): the
            "physical number" prior came back as "physical X" in both of its targets

Every thread is also scored against every earlier thread it was never shown (sham pairs), which
is the false-positive rate the pre-registration's A4 bounds. Writes lore/VALIDATION.md and
lore/validation.json: item names and flags only, no thread text, gate-checked.
"""
import argparse, hashlib, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
import tracker as T
import generate17 as M
from generate import HARM

GATE = HARM + ["cunt", "cock", "tits", "orgasm", "slut", "fap", "pussy", "blowjob", "porn", "rape"]
A4_MAX = 0.15


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def safe(name):
    return "[gated]" if any(g.strip() in name for g in GATE) else name


def summary(res):
    return {"transfer": res["transfer"],
            "items": [{"item": safe(i["item"]), "kind": i["kind"], "uses": i["uses"],
                       "authors": len(i["authors"]), "construction": i["construction"],
                       "fillers": [safe(f) for f in i["fillers"]], "origin": i["origin"]}
                      for i in res["items"]],
            "references": [{"kind": r["kind"], "post": r["post"], "match": safe(r["match"])}
                           for r in res["references"]],
            "format_play": res["format_play"], "uptake": res["uptake"]}


# ---- v2.1 ----
def v21(data, common):
    path = os.path.join(data, "spike", "remote", "board-v21.json")
    board = json.load(open(path, encoding="utf-8"))
    threads = sorted(board["threads"], key=lambda t: t["no"])
    by_no = {t["no"]: t for t in threads}
    shown_by = {}
    for t in threads:
        if t.get("prior"):
            shown_by.setdefault(t["prior"], set()).add(t["no"])
    pairs = []
    for t in threads:
        for s in threads:
            if s["no"] >= t["no"]:
                continue
            real = t.get("prior") == s["no"]
            bg = [x["posts"] for x in threads
                  if x["no"] not in {t["no"], s["no"]} | shown_by.get(s["no"], set())]
            res = T.track(t["posts"], s["posts"], bg, target_no=t["no"], source_no=s["no"],
                          source_shown=real, board="/x/", target_cast=t.get("pool", ()),
                          common=common)
            pairs.append({"target": t["no"], "source": s["no"], "real": real, **summary(res)})
    own = {}
    for t in threads:   # format play on each thread's own page, scored against nothing shown
        res = T.track(t["posts"], [], [x["posts"] for x in threads if x is not t],
                      target_no=t["no"], board="/x/", target_cast=t.get("pool", ()))
        own[t["no"]] = res["format_play"]
    return {"file": "spike/remote/board-v21.json", "sha256": sha256(path), "pairs": pairs,
            "format_play": own, "by_no": by_no}


# ---- the local memory run ----
def fetch(data, path, sel):
    d = json.load(open(os.path.join(data, path), encoding="utf-8"))
    for t in (d["threads"] if isinstance(d, dict) else d):
        if all(t.get(k) == v for k, v in sel.items()):
            return t
    raise SystemExit("prior not found: %s %s" % (path, sel))


def shown_part(t):
    """What generate17.prior_block put on the page: the first PRIOR_POSTS posts, empty ones skipped."""
    return [p for p in t["posts"][:M.PRIOR_POSTS] if p.get("text")]


def memory(data, common):
    path = os.path.join(data, "threads.memory.json")
    run = json.load(open(path, encoding="utf-8"))
    priors = {"coined:%s" % name: shown_part(fetch(data, src, sel))
              for name, rx, src, sel in M.COINAGES}
    priors["plain"] = shown_part(fetch(data, *M.PLAIN))
    targets = [t for t in run["threads"] if not t.get("quarantined")]
    pairs = []
    for t in targets:
        for label, s in priors.items():
            real = t.get("prior") == label
            shown_s = {x["id"] for x in targets if x.get("prior") == label}
            bg = ([x["posts"] for x in targets if x["id"] != t["id"] and x["id"] not in shown_s]
                  + [p for l, p in priors.items() if l != label])
            twins = [x["posts"] for x in targets if x["opener_index"] == t["opener_index"]
                     and x["id"] != t["id"] and x["id"] not in shown_s]
            twin = [p for posts in twins for p in posts]
            res = T.track(t["posts"], s, bg, target_no=4471, source_no=4468, source_shown=real,
                          topic_twin=twin, board="/x/", target_cast=t.get("participants", ()),
                          common=common)
            pairs.append({"target": t["id"], "arm": t["arm"], "opener": t["opener_index"],
                          "source": label, "real": real, **summary(res)})
    return {"file": "threads.memory.json", "sha256": sha256(path), "pairs": pairs,
            "quarantined": [t["id"] for t in run["threads"] if t.get("quarantined")]}


def rate(pairs):
    k = sum(p["transfer"] for p in pairs)
    lo, hi = wilson(k, len(pairs))
    return k, len(pairs), lo, hi


def items_line(p, n=6):
    parts = []
    for i in p["items"][:n]:
        s = i["item"]
        if i["kind"] == "word":
            s += " ×%d" % i["uses"] + (" (→ %s)" % ", ".join(i["fillers"][:3]) if i["construction"] else "")
        parts.append(s)
    refs = {}
    for r in p["references"]:
        refs[(r["kind"], r["match"])] = refs.get((r["kind"], r["match"]), 0) + 1
    for (kind, match), k in refs.items():
        parts.append("ref:%s %s" % (kind, match) + (" (%d posts)" % k if k > 1 else ""))
    return "; ".join(parts) or "–"


GRID = (0.05, 0.03, 0.02, 0.01)     # reference cuts tried, most permissive first


def evaluate(data, common):
    v, m = v21(data, common), memory(data, common)
    real_v = [p for p in v["pairs"] if p["real"]]
    real_m = [p for p in m["pairs"] if p["real"]]
    a1 = [p for p in real_m if p["target"] in (11, 15)]
    p4483 = next(p for p in real_v if p["target"] == 4483)
    ok = {
        "A1": len(a1) == 2 and all(p["transfer"] and any(i["item"] == "physical" for i in p["items"])
                                   for p in a1),
        "A2": p4483["transfer"] and bool(p4483["items"]),
        "A3": all(not any(r["kind"] == "number" for r in p["references"])
                  for p in v["pairs"] + m["pairs"] if not p["real"] or p.get("target") == 4481),
    }
    sv = rate([p for p in v["pairs"] if not p["real"]])
    sm = rate([p for p in m["pairs"] if not p["real"]])
    ok["A4"] = sv[0] / sv[1] <= A4_MAX and sm[0] / sm[1] <= A4_MAX
    return v, m, ok, sv, sm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    manifest = open(os.path.join(ROOT, "spike", "MANIFEST.sha256"), encoding="utf-8").read()

    # The cut is chosen by rule, not by eye: the most permissive one whose sham rate stays within
    # A4 on both boards. tracker.REF_SHARE must be that cut, so the frozen tracker is the one shown.
    grid = [(None,) + evaluate(a.data, None)[2:]]
    for cut in GRID:
        grid.append((cut,) + evaluate(a.data, T.load_reference(cut))[2:])
    for cut, g, gv, gm in grid:
        print("cut %-5s %s  v2.1 sham %d/%d  memory sham %d/%d" % (cut, g, gv[0], gv[1], gm[0], gm[1]))
    chosen = next((cut for cut, ok, sv, sm in grid[1:] if ok["A4"]), None)
    if chosen != getattr(T, "REF_SHARE", None):
        raise SystemExit("the rule picks a reference cut of %s; set tracker.REF_SHARE to it" % chosen)
    v, m, ok, (kv, nv, lov, hiv), (km, nm, lom, him) = evaluate(a.data, T.load_reference(chosen))
    a1_ok, a2_ok, a3_ok, a4_ok = ok["A1"], ok["A2"], ok["A3"], ok["A4"]
    assert v["sha256"] in manifest, "board-v21.json does not match spike/MANIFEST.sha256"
    real_v = [p for p in v["pairs"] if p["real"]]
    sham_v = [p for p in v["pairs"] if not p["real"]]
    real_m = [p for p in m["pairs"] if p["real"]]
    sham_m = [p for p in m["pairs"] if not p["real"]]

    labels = {4479: "none", 4480: "none", 4483: "transfer (mix-up)", 4484: "none", 4488: "none"}
    out = ["# Lore tracker validation", "",
           "Generated by `python lore/validate.py --data <private folder>` from files checked by hash:",
           "", "| file | sha256 |", "|---|---|",
           "| `%s` | `%s` (matches `spike/MANIFEST.sha256`) |" % (v["file"], v["sha256"]),
           "| `%s` | `%s` |" % (m["file"], m["sha256"]), "",
           "Thresholds: an item is rare if it is in at most %d%% of the background threads (at least 1) "
           "and in at most %d%% of the project's other English threads (`reference.json`, built by "
           "`lore/reference.py`); thread-like numbers within %d of a number on the page are format play."
           % (T.DF_SHARE * 100, chosen * 100, T.NEAR),
           "", "## Changes made before freezing", "",
           "The pre-registration allows tuning on this validation data only. Each step was a response to "
           "what the sham pairs flagged; the sham rates are from this script at the time.", "",
           "1. **As first committed** (`3cf410d`), with no reference list: A4 failed, v2.1 sham 52/148 (35%), "
           "memory run 10/95. On a board of 18 short threads, words like \"told\", \"agree\" and \"whole\" are "
           "rare, and so is the cast's profanity.",
           "2. **Reference list** (`reference.py`: the project's 916 other English threads), cut picked by the rule "
           "below (5%): v2.1 sham 21/148 (14%), memory run 4/95. A4 passed, but v2.1 thread 4480 was flagged on "
           "\"first place\", and four sham flags were \"thread with\" in a post about a daily thread. Not committed.",
           "3. **Phrases of ordinary words must recur** (as single words must), unless one of their words is rare; "
           "**earlier-thread phrases** are only the explicit forms (\"the other thread\", \"last thread\", "
           "\"that thread\"). The rule still picks 5%. This is the frozen tracker.", "",
           "## Choosing the reference cut", "",
           "The cut is picked by rule, not by eye: the most permissive of %s whose sham rate meets A4 on both "
           "boards. Every row, for the frozen tracker:" % ", ".join("%d%%" % (c * 100) for c in GRID), "",
           "| reference cut | A1 | A2 | A3 | A4 | v2.1 sham | memory-run sham |", "|---|---|---|---|---|---:|---:|"]
    for cut, g, gv, gm in grid:
        out.append("| %s | %s | %s | %s | %s | %d/%d (%.0f%%) | %d/%d (%.0f%%) |" % (
            "no reference list" if cut is None else "%d%%%s" % (cut * 100, " **chosen**" if cut == chosen else ""),
            *("pass" if g[k] else "FAIL" for k in ("A1", "A2", "A3", "A4")),
            gv[0], gv[1], 100 * gv[0] / gv[1], gm[0], gm[1], 100 * gm[0] / gm[1]))
    out += ["", "## Acceptance criteria (PREREGISTRATION.md), at the chosen cut", "",
           "| | criterion | result |", "|---|---|---|",
           "| A1 | both \"physical number\" targets (11, 15) flagged with \"physical\" | %s |" % ("**pass**" if a1_ok else "**FAIL**"),
           "| A2 | v2.1 thread 4483 flagged with 4475's material | %s |" % ("**pass**" if a2_ok else "**FAIL**"),
           "| A3 | 4481's numbers are format play; no unshown number is a reference | %s |" % ("**pass**" if a3_ok else "**FAIL**"),
           "| A4 | sham-pair transfer rate ≤ %d%% in each dataset | %s: v2.1 %d/%d (%.0f%%), memory run %d/%d (%.0f%%) |"
           % (A4_MAX * 100, "**pass**" if a4_ok else "**FAIL**", kv, nv, 100 * kv / nv, km, nm, 100 * km / nm),
           "", "## v2.1: the five threads with an earlier thread above them", "",
           "| target ← source | hand label | tracker | what it found |", "|---|---|---|---|"]
    for p in real_v:
        out.append("| %d ← %d | %s | %s | %s |" % (p["target"], p["source"], labels[p["target"]],
                                                  "transfer" if p["transfer"] else "none", items_line(p)))
    out += ["", "Sham pairs (each thread against every earlier thread it was not shown): "
            "**%d of %d** flagged, %.1f%% (95%% CI %.1f–%.1f%%)." % (kv, nv, 100 * kv / nv, 100 * lov, 100 * hiv),
            "", "Flagged sham pairs:", ""]
    for p in sham_v:
        if p["transfer"]:
            out.append("- %d vs %d: %s" % (p["target"], p["source"], items_line(p)))
    fp = v["format_play"]
    out += ["", "Format play on each v2.1 page (scored against nothing): thread numbers near the page's own, "
            "post numbers, board name, \"this thread\"/OP talk.", "",
            "| thread | own no. | near no. | post no. | board name | thread talk |", "|---|---:|---:|---:|---:|---:|"]
    for no in sorted(fp):
        f = fp[no]
        if any(f.values()):
            out.append("| %d | %d | %d | %d | %d | %d |" % (no, f["own_number"], f["near_number"],
                                                         f["post_number"], f["board_name"], f["self_ref"]))
    out += ["", "## The local memory run: every target against its own prior", "",
            "Quarantined threads %s are skipped. Target number 4471, prior shown as 4468, as in "
            "`generate17.py`." % m["quarantined"], "",
            "| id | arm | opener | prior | tracker | what it found |", "|---:|---|---:|---|---|---|"]
    for p in real_m:
        out.append("| %d | %s | %d | %s | %s | %s |" % (p["target"], p["arm"], p["opener"], p["source"],
                                                       "transfer" if p["transfer"] else "none", items_line(p)))
    out += ["", "Sham pairs (each target against each prior it was not shown): "
            "**%d of %d** flagged, %.1f%% (95%% CI %.1f–%.1f%%)." % (km, nm, 100 * km / nm, 100 * lom, 100 * him),
            "", "Flagged sham pairs:", ""]
    for p in sham_m:
        if p["transfer"]:
            out.append("- %d (%s) vs %s: %s" % (p["target"], p["arm"], p["source"], items_line(p)))
    out.append("")
    with open(os.path.join(HERE, "VALIDATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    with open(os.path.join(HERE, "validation.json"), "w", encoding="utf-8") as f:
        json.dump({"criteria": {"A1": a1_ok, "A2": a2_ok, "A3": a3_ok, "A4": a4_ok},
                   "thresholds": {"df_share": T.DF_SHARE, "near": T.NEAR},
                   "v21": {k: v[k] for k in ("file", "sha256", "pairs")},
                   "memory": {k: m[k] for k in ("file", "sha256", "pairs", "quarantined")}},
                  f, indent=1, ensure_ascii=False)
    print("A1 %s  A2 %s  A3 %s  A4 %s (v2.1 %d/%d, memory %d/%d)" % (a1_ok, a2_ok, a3_ok, a4_ok, kv, nv, km, nm))


if __name__ == "__main__":
    main()
