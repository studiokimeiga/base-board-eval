#!/usr/bin/env python3
"""Recompute every bake-off score from the blind judges' score files.

  python spike/judging/ledger.py            rewrite spike/judging/LEDGER.md
  python spike/judging/ledger.py --check    exit 1 if LEDGER.md doesn't match the score files
  python spike/judging/ledger.py rawstats   refresh raw-stats.json from spike/remote/ (private)

Only each round's key.json (packet letter -> arm) and the judges' scores-*.json are read, so
the ledger can be checked without the thread text, which stays private. The one exception is
raw-stats.json (post lengths, withheld posts, file hashes and times), which `rawstats` computes
from the private threads; it is committed like any other input.
"""
import glob, hashlib, json, math, os, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
LEDGER = os.path.join(HERE, "LEDGER.md")
RAW_STATS = os.path.join(HERE, "raw-stats.json")

# (round, folder, {judge: score-file glob}, what it asked, contrasts as (arm, baseline))
ROUNDS = [
    ("1-2", "", {"claude": "scores-[0-9]*.json"},
     "Does size matter? Base and fine-tuned models on the same seeded scaffold",
     [("qwen235", "cast"), ("g31", "cast"), ("l70", "cast")]),
    ("3", "r3", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "Fixing Qwen's flatness; chat models",
     [("pick", "qwen235"), ("qwenhot", "qwen235"), ("mix", "qwen235")]),
    ("4", "r4", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "Can Hermes be stabilised? Gemini in English",
     [("hermespen", "hermes405"), ("hermesguard", "hermes405"), ("hermespick", "hermes405"),
      ("gemini", "pick")]),
    ("5", "r5", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "Does a picker lift Gemini?",
     [("geminipick", "gemini")]),
    ("6", "r6", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "Temperature",
     [("geminit15", "gemini"), ("geminit19", "gemini"), ("qwent14", "qwen235"),
      ("qwent18", "qwen235")]),
    ("7", "r7", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "Poster temperaments, and small-model naif posters",
     [("roles", "gemini"), ("naif", "gemini"), ("naifroles", "gemini"), ("naifroles", "roles")]),
    ("8", "r8", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "Temperaments with post length controlled, one rubric for both judges",
     [("roles", "gemini"), ("rolesshort", "gemini"), ("rolesshort", "roles")]),
    ("JP", "jp", {"claude": "scores-claude-*.json"},
     "Japanese: 5ch and named-handle formats",
     [("gemini", "qwen235")]),
    ("JP-5", "jp-r5", {"claude": "scores-claude-all.json", "gpt": "scores-gpt.json"},
     "Japanese picker, 5ch format",
     [("geminipick", "gemini")]),
]
# What each judge was actually told. Verbatim Claude prompts are in prompts/, the gpt-5.4
# prompts are built by round3_judge.py and jp_judge.py.
RUBRICS = {
    "1-2": "Claude only, rubric v1 (interest, humour, emergence, coherence, overall).",
    "3": "Both on rubric v1; Claude's copy adds a note about long posts. gpt-5.4 ran on the free "
         "daily allowance, which ran out after 6 of the 8 packets.",
    "4": "Both on rubric v1 (Claude's copy with the long-post note).",
    "5": "Both on rubric v1 (Claude's copy with the long-post note). gpt-5.4 also did the picking.",
    "6": "Claude was also told to count deadpan and sincerely-wrong humour; gpt-5.4 was not "
         "(rubric v1). Humour is comparable within a judge, not between them.",
    "7": "Claude on rubric v2 (adds contrast, sincerely-wrong humour and a variety score); gpt-5.4 "
         "on rubric v1, so it never scored variety.",
    "8": "Both on rubric v2. The gemini and roles threads are the same files judged in rounds 4 "
         "and 7; only rolesshort is new.",
    "JP": "Claude only, Japanese rubric (naturalness first). 6 openers x 2 formats; Sonnet ran in "
          "the 5ch format only.",
    "JP-5": "Both on the Japanese rubric. gpt-5.4 also did the picking.",
}
NAMES = {
    "cast": "original cast (gemma-4-E4B / Qwen3-4B / Olmo-3-7B), XTC + DRY",
    "g31": "gemma-4-31B base, XTC + DRY", "l70": "Llama-3.1-70B base, XTC + DRY",
    "euryale70": "Euryale 70B, raw", "hermes405": "Hermes 3 405B, raw",
    "qwen235": "Qwen3-235B, raw continuation", "mix": "Qwen + Hermes mixed cast",
    "qwenhot": "Qwen3-235B, temp 1.15 + frequency penalty",
    "pick": "Qwen3-235B best-of-3, gpt-5.4 picker", "kimi": "Kimi K3 (chat)",
    "echo": "Echo (chat)", "hermespen": "Hermes 405B + repetition penalties",
    "hermesguard": "Hermes 405B + penalties + breakdown guard",
    "hermespick": "Hermes 405B + penalties + guard + picker",
    "gemini": "Gemini 3.8 Flash (chat)", "geminipick": "Gemini 3.8 Flash best-of-3, gpt-5.4 picker",
    "geminit15": "Gemini 3.8 Flash, temp 1.5", "geminit19": "Gemini 3.8 Flash, temp 1.9",
    "qwent14": "Qwen3-235B raw, temp 1.4 / min_p 0.1",
    "qwent18": "Qwen3-235B raw, temp 1.8 / min_p 0.15",
    "roles": "Gemini, posters given temperaments",
    "naif": "Gemini + 2 small-model (gemma-4-E4B) naif posters",
    "naifroles": "Gemini + naifs + temperaments",
    "rolesshort": "Gemini, temperaments + per-role post length",
    "swallow70": "Llama-3.3-Swallow-70B base, raw", "swallow70dry": "Swallow-70B base + XTC/DRY",
    "deepseek": "DeepSeek V4 Flash (chat)", "gpt54": "GPT-5.4 (chat)",
    "sonnet": "Claude Sonnet 5.5 (chat)",
}
DIMS = ["overall", "naturalness", "interest", "humour", "emergence", "coherence", "variety"]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ---- statistics (exact, small-n) ----
def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sign_test(wins, losses):
    """Two-sided exact sign test, ties already dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def ranks(xs):
    """1-based ranks, ties get the average rank."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = mean(rx), mean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


# ---- loading ----
def packet_key(name):
    """'opener-3' -> '3' (English keys), '5ch-opener-3' stays as is (Japanese keys)."""
    return name.split("-", 1)[1] if name.startswith("opener-") else name


def load_round(folder, judges):
    d = os.path.join(HERE, folder)
    key = read_json(os.path.join(d, "key.json"))
    cells = {}                     # judge -> {(packet, arm): scores}
    for judge, pattern in judges.items():
        scored = {}
        for f in sorted(glob.glob(os.path.join(d, pattern))):
            scored.update(read_json(f))
        cells[judge] = {}
        for name, threads in scored.items():
            pk = packet_key(name)
            if set(threads) != set(key[pk]):
                raise SystemExit("%s/%s: %s scored letters %s, key has %s"
                                 % (folder or ".", judge, name, sorted(threads), sorted(key[pk])))
            for letter, v in threads.items():
                cells[judge][(pk, key[pk][letter])] = v
    return key, cells


# ---- report ----
def f2(x):
    return "–" if x is None or x != x else "%.2f" % x


def signed(x):
    return "%+.2f" % x


def arm_table(cells, judge, arms, packets):
    dims = [d for d in DIMS if any(d in v for (p, a), v in cells.items())]
    rows = []
    top = {p: max(v["overall"] for (q, a), v in cells.items() if q == p) for p in packets}
    for arm in arms:
        mine = {p: v for (p, a), v in cells.items() if a == arm}
        if not mine:
            continue
        m = {d: mean([v[d] for v in mine.values() if d in v]) for d in dims}
        best = sum(v["overall"] == top[p] for p, v in mine.items())
        rows.append((m["overall"], arm, len(mine), m, best))
    rows.sort(key=lambda r: (-r[0], r[1]))
    out = ["| %s | arm | n | %s | best/tied |" % (judge, " | ".join(dims)),
           "|---|---|---:|%s---:|" % ("---:|" * len(dims))]
    for _, arm, n, m, best in rows:
        out.append("| | %s | %d | %s | %d |" % (NAMES.get(arm, arm), n,
                                                 " | ".join(f2(m[d]) for d in dims), best))
    return out


def contrast_rows(cells, judge, contrasts):
    out = []
    for arm, base in contrasts:
        pk = sorted({p for (p, a) in cells if a == arm} & {p for (p, a) in cells if a == base})
        if not pk:
            continue
        cols = []
        for d in ("overall", "humour"):
            diffs = [cells[(p, arm)][d] - cells[(p, base)][d] for p in pk]
            w, t, l = (sum(x > 0 for x in diffs), sum(x == 0 for x in diffs),
                       sum(x < 0 for x in diffs))
            cols.append("%s | %d/%d/%d | %.3f" % (signed(mean(diffs)), w, t, l, sign_test(w, l)))
        out.append("| %s | %s vs %s | %d | %s |" % (judge, arm, base, len(pk), " | ".join(cols)))
    return out


def agreement(cells):
    if not {"claude", "gpt"} <= set(cells):
        return None
    common = sorted(set(cells["claude"]) & set(cells["gpt"]))
    rho = spearman([cells["claude"][c]["overall"] for c in common],
                   [cells["gpt"][c]["overall"] for c in common])
    packets = sorted({p for p, a in common})
    same = 0
    for p in packets:
        tops = []
        for j in ("claude", "gpt"):
            sc = {a: cells[j][(q, a)]["overall"] for (q, a) in common if q == p}
            hi = max(sc.values())
            tops.append({a for a, s in sc.items() if s == hi})
        same += bool(tops[0] & tops[1])
    return rho, len(common), same, len(packets)


def rejudged(rounds_cells):
    """The same thread files scored again in later rounds, per judge and language."""
    out = []
    for judge in ("claude", "gpt"):
        seen = {}                          # (language, arm) -> [(round, {packet: overall})]
        for rnd, folder, cells in rounds_cells:
            lang = "JP" if folder.startswith("jp") else "EN"
            for (p, a), v in cells.get(judge, {}).items():
                for r, scores in seen.setdefault((lang, a), []):
                    if r == rnd:
                        scores[p] = v["overall"]
                        break
                else:
                    seen[(lang, a)].append((rnd, {p: v["overall"]}))
        for lang, arm in sorted(seen):
            runs = seen[(lang, arm)]
            if len(runs) < 2:
                continue
            diffs = []
            for i in range(len(runs)):
                for j in range(i + 1, len(runs)):
                    pk = set(runs[i][1]) & set(runs[j][1])
                    diffs += [abs(runs[i][1][p] - runs[j][1][p]) for p in pk]
            avgs = [mean(list(s.values())) for r, s in runs]
            means = ", ".join("%s %s (n=%d)" % (r, f2(m), len(s)) for (r, s), m in zip(runs, avgs))
            moved = sum(d >= 1 for d in diffs)
            out.append("| %s | %s%s | %s | %.2f | %.2f | %d of %d |" % (
                judge, NAMES.get(arm, arm), " (JP)" if lang == "JP" else "", means,
                max(avgs) - min(avgs), mean(diffs), moved, len(diffs)))
    return out


def position_rows(rounds_cells, keys):
    """Score minus its packet's mean, by where the thread sat in the packet (letters are in
    reading order), per judge over every round; and which arm each round showed first."""
    out = []
    for judge in ("claude", "gpt"):
        by = {"first": [], "middle": [], "last": []}
        for (rnd, folder, cells), key in zip(rounds_cells, keys):
            for pk, letters in key.items():
                sc = {L: cells.get(judge, {}).get((pk, a)) for L, a in letters.items()}
                sc = {L: v["overall"] for L, v in sc.items() if v}
                if len(sc) < 2:
                    continue
                m = mean(list(sc.values()))
                order = sorted(sc)
                for i, L in enumerate(order):
                    pos = "first" if i == 0 else "last" if i == len(order) - 1 else "middle"
                    by[pos].append(sc[L] - m)
        out.append("| %s | %s |" % (judge, " | ".join("%s (n=%d)" % (signed(mean(by[p])), len(by[p]))
                                                     for p in ("first", "middle", "last"))))
    return out


def raw_section():
    if not os.path.exists(RAW_STATS):
        return ["raw-stats.json is missing; run `ledger.py rawstats` where spike/remote/ exists."]
    raw = read_json(RAW_STATS)
    checked = raw["packets_vs_raw"]
    out = ["Computed by `ledger.py rawstats` from the private thread files (SHA-256 in "
           "`raw-stats.json` and `spike/MANIFEST.sha256`).", "",
           "**Packets against raw files.** Each judging packet was rebuilt from `key.json` and "
           "the raw files as they are now, in the packet scripts' own format, and compared byte "
           "for byte: %s. %s"
           % ("; ".join("round %s %d of %d identical%s" % (
               r, v["identical"], v["packets"], " (differ: %s)" % ", ".join(v["differ"])
               if v["differ"] else "") for r, v in checked.items()),
              "So the files below are exactly what the judges read, including the five files "
              "re-copied from the Modal volume at 06:20Z, after round 1-2 was judged."
              if all(not v["differ"] for v in checked.values()) else
              "Where a packet differs, its raw files are not exactly what the judges read."), "",
           "**Length.** Posts 2 onward (everything after the opener) are counted, as in the "
           "round 7 and 8 notes; a withheld post counts as the 15 characters of `[post withheld]`. "
           "Spend is the API cost the generator logged in the file (OpenRouter or Echo), without "
           "judging; – where the arm ran on Modal or logged nothing.",
           "",
           "| file | modified (UTC) | threads | posts | withheld | empty | mean chars | median | p90 | spend $ |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, s in sorted(raw["files"].items()):
        out.append("| %s | %s | %d | %d | %d | %d | %.0f | %d | %d | %s |" % (
            name, s["modified"], s["threads"], s["posts"], s["withheld"], s["empty"],
            s["mean_chars"], s["median_chars"], s["p90_chars"],
            "–" if s["spend_usd"] is None else "%.3f" % s["spend_usd"]))
    return out


def build():
    lines = ["# Bake-off ledger", "",
             "Generated by `python spike/judging/ledger.py` from the blind judges' score files in "
             "`spike/judging/`. Don't edit it by hand: `ledger.py --check` fails when it is stale.", "",
             "A packet is one opener with every arm's thread side by side, lettered at random; "
             "judges never saw `key.json`. Means are over packets, and n is how many packets an "
             "arm was scored in. Compare arms within one round and one judge family only: the "
             "rubric, the mix of arms and the judges changed between rounds, and the last section "
             "shows how far the same threads moved when judged again.", "",
             "Paired rows compare two arms packet by packet (arm minus baseline). W/T/L counts "
             "packets where the arm scored higher, the same, or lower; p is a two-sided exact sign "
             "test with ties dropped. With 6 to 8 packets nothing below about p = 0.03 is reachable "
             "unless an arm wins every packet, so read these as effect sizes with honest noise, "
             "not as proof.", ""]
    rounds_cells, keys = [], []
    for rnd, folder, judges, title, contrasts in ROUNDS:
        key, cells = load_round(folder, judges)
        rounds_cells.append((rnd, folder, cells))
        keys.append(key)
        arms = sorted({a for letters in key.values() for a in letters.values()})
        packets = sorted(key)
        lines += ["## Round %s: %s" % (rnd, title), "", RUBRICS[rnd], ""]
        for judge in judges:
            c = cells[judge]
            got = sorted({p for p, a in c})
            note = "" if len(got) == len(packets) else " (scored %d of %d packets)" % (
                len(got), len(packets))
            lines += ["**%s**%s" % (judge, note), ""]
            lines += arm_table(c, judge, arms, got) + [""]
        rows = []
        for judge in judges:
            rows += contrast_rows(cells[judge], judge, contrasts)
        if rows:
            lines += ["| judge | paired | packets | overall Δ | W/T/L | p | humour Δ | W/T/L | p |",
                      "|---|---|---:|---:|---|---:|---:|---|---:|"] + rows + [""]
        ag = agreement(cells)
        if ag:
            rho, n, same, np_ = ag
            lines += ["Judge agreement on overall: Spearman ρ = %s over %d threads; the two "
                      "families' top thread (ties allowed) coincide in %d of %d packets."
                      % (f2(rho), n, same, np_), ""]
    lines += ["## Same threads, different rounds", "",
              "Arms that reappear were re-judged from the same file in `spike/remote/` (checked "
              "against the packets in the next section). Movement mixes judge noise with changes "
              "of rubric and of the threads they were compared against. The last two columns pair "
              "every two judgings of the same thread.", "",
              "| judge | arm | overall mean by round | spread of means | mean abs. change per thread | re-judgings that moved ≥1 point |",
              "|---|---|---|---:|---:|---|"] + rejudged(rounds_cells) + [""]
    firsts = []
    for (rnd, folder, cells), key in zip(rounds_cells, keys):
        counts = {}
        for letters in key.values():
            a = letters[min(letters)]
            counts[a] = counts.get(a, 0) + 1
        top = max(counts, key=lambda a: (counts[a], a))
        firsts.append("round %s: %s %d of %d" % (rnd, top, counts[top], len(key)))
    lines += ["## Position in the packet", "",
              "Overall score minus its packet's mean, by where the thread sat (threads are read in "
              "letter order). Letters were assigned at random, so this adds noise rather than favouring "
              "an arm on average, but with 6 to 8 packets one arm can land first more often by chance. "
              "The arm shown first most often: %s." % "; ".join(firsts), "",
              "| judge | first | middle | last |", "|---|---:|---:|---:|"] + position_rows(rounds_cells, keys) + [""]
    lines += ["## Post length and withheld posts", ""] + raw_section() + [""]
    return "\n".join(lines)


def rebuild_packet(folder, name, letters, header):
    """The packet text the judges read, rebuilt from the raw files in the scripts' format
    (round3_judge.py for English rounds, jp_judge.py for Japanese)."""
    remote = os.path.join(SPIKE, "remote")
    out = [header + "\n"]
    jp = folder.startswith("jp")
    fmt = name.split("-")[0] if jp else None
    op = header.split(": ", 1)[1]
    for L in sorted(letters):
        arm = letters[L]
        f = "jp-%s-%s.json" % (arm, fmt) if jp else "bakeoff-%s.json" % arm
        t = next(t for t in read_json(os.path.join(remote, f))["threads"]
                 if t["opener"] == op)
        out.append("=" * 20 + "\nTHREAD %s\n" % L + "=" * 20)
        for n, p in enumerate(t["posts"]):
            if jp:
                who = ("ID:" + p["who"]) if fmt == "5ch" else p["who"]
                out.append("%d %s%s: %s" % (p["n"], who, " (OP)" if p["who"] == t["op"] else "",
                                            p["text"] or "(empty)"))
            else:
                out.append("%d. %s%s: %s" % (n + 1, p["who"],
                                             " (OP)" if p["who"] == t["posts"][0]["who"] else "",
                                             p["text"] or "(empty)"))
        out.append("")
    return "\n".join(out)


def verify_packets():
    """Is every packet byte-identical to one rebuilt from today's raw files?"""
    result = {}
    for rnd, folder, *_ in ROUNDS:
        d = os.path.join(HERE, folder)
        key = read_json(os.path.join(d, "key.json"))
        same, bad = 0, []
        for pk, letters in sorted(key.items()):
            name = pk if folder.startswith("jp") else "opener-%s" % pk
            data = read_bytes(os.path.join(d, name + ".txt"))
            header = data.decode("utf-8").splitlines()[0]
            text = rebuild_packet(folder, name, letters, header)
            # the packets were written in text mode on Windows, which turns every "\n",
            # including one inside a post's own "\r\n", into "\r\n"
            if b"\r\n" in data:
                text = text.replace("\n", "\r\n")
            if text.encode("utf-8") == data:
                same += 1
            else:
                bad.append(name)
        result[rnd] = {"identical": same, "packets": len(key), "differ": bad}
    return result


def spend_of(d):
    """API dollars the generator logged: round3.py writes spend.usd, openrouter_arm.py
    spend.cost, jp_bakeoff.py spend_usd. Echo's credits and Modal GPU time were never logged."""
    s = d.get("spend")
    usd = s.get("usd", s.get("cost")) if isinstance(s, dict) else d.get("spend_usd")
    return round(usd, 4) if usd else None


def rawstats():
    """Hash and measure the private thread files; writes raw-stats.json."""
    remote = os.path.join(SPIKE, "remote")
    files = {}
    for f in sorted(glob.glob(os.path.join(remote, "bakeoff-*.json")) +
                    glob.glob(os.path.join(remote, "jp-*.json"))):
        d = read_json(f)
        posts = [p for t in d["threads"] for p in t["posts"][1:]]
        lens = sorted(len(p["text"] or "") for p in posts)
        files[os.path.basename(f)] = {
            "sha256": hashlib.sha256(read_bytes(f)).hexdigest(),
            "modified": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(os.path.getmtime(f))),
            "threads": len(d["threads"]), "posts": len(posts),
            "withheld": sum(bool(p.get("withheld")) or p["text"] == "[post withheld]"
                            for p in posts),
            "empty": sum(not p["text"] for p in posts),
            "mean_chars": round(mean(lens), 1), "median_chars": lens[len(lens) // 2],
            "p90_chars": lens[int(len(lens) * 0.9)], "spend_usd": spend_of(d)}
    keys = {}
    for rnd, folder, *_ in ROUNDS:
        k = os.path.join(HERE, folder, "key.json")
        keys[rnd] = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(os.path.getmtime(k)))
    packets = verify_packets()
    with open(RAW_STATS, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"files": files, "packets_built": keys, "packets_vs_raw": packets}, f,
                  indent=1, sort_keys=True)
    print("wrote", RAW_STATS, len(files), "files;",
          ", ".join("%s %d/%d" % (r, v["identical"], v["packets"]) for r, v in packets.items()))


def main():
    if sys.argv[1:] == ["rawstats"]:
        rawstats()
        return
    text = build()
    if sys.argv[1:] == ["--check"]:
        old = read_bytes(LEDGER).decode("utf-8") if os.path.exists(LEDGER) else ""
        if old != text:
            print("LEDGER.md is stale: run python spike/judging/ledger.py")
            sys.exit(1)
        print("LEDGER.md matches the score files")
        return
    with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", LEDGER)


if __name__ == "__main__":
    main()
