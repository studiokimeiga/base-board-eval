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
import glob, hashlib, json, math, os, re, statistics, sys, time

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
    # pre-registered in spike/PREREGISTRATION-ROUND9.md, contrasts included
    ("9", "r9", {"claude": "scores-claude-*.json", "gpt": "scores-gpt.json"},
     "An occasional small-model post, and the /x/ label against a neutral header (pre-registered)",
     [("rolesshort9naif", "rolesshort9"), ("gemini9neutral", "gemini9"),
      ("rolesshort9neutral", "rolesshort9"), ("rolesshort9", "gemini9"),
      ("rolesshort9neutral", "gemini9neutral")]),
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
    "9": "Both on rubric v2, verbatim (`RUBRIC_V2`). Five new arms, generated together, with flagged "
         "posts withheld before they entered the context. Every packet was read in five letter orders "
         "(a Latin square per opener), so each family read each thread five times, once in each "
         "position; a thread's scores here are the mean of its five readings.",
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
    "gemini9": "Gemini 3.8 Flash (chat), /x/ header",
    "rolesshort9": "Gemini, short temperaments, /x/ header",
    "rolesshort9naif": "short temperaments + 1 post in 8 by gemma-4-E4B base, /x/ header",
    "gemini9neutral": "Gemini 3.8 Flash (chat), neutral header",
    "rolesshort9neutral": "Gemini, short temperaments, neutral header",
    "swallow70": "Llama-3.3-Swallow-70B base, raw", "swallow70dry": "Swallow-70B base + XTC/DRY",
    "deepseek": "DeepSeek V4 Flash (chat)", "gpt54": "GPT-5.4 (chat)",
    "sonnet": "Claude Sonnet 5.5 (chat)",
}
# jp_bakeoff.py ran its self-hosted arms raw unless the name says XTC/DRY
JP_NAMES = {"g31": "gemma-4-31B base, raw"}
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


def ran(folder):
    """A round enters the ledger once its packets exist; round 9 was listed before it ran."""
    return os.path.exists(os.path.join(HERE, folder, "key.json"))


def versioned(key):
    """Round 9 read every opener's packet in five letter orders, keyed '3-v1' to '3-v5'."""
    return any("-v" in pk for pk in key)


def opener(pk):
    return pk.split("-v")[0]


def collapse(cells):
    """A thread read in several letter orders scores the mean of its readings, so a packet is again
    one opener. The readings' main_failure notes are kept, as a list."""
    out = {}
    for judge, c in cells.items():
        reads = {}
        for (pk, arm), v in c.items():
            reads.setdefault((opener(pk), arm), []).append(v)
        out[judge] = {k: dict({d: mean([v[d] for v in vs]) for d in DIMS if d in vs[0]},
                              main_failure=[v["main_failure"] for v in vs], reads=len(vs))
                      for k, vs in reads.items()}
    return out


# ---- report ----
def f2(x):
    return "–" if x is None or x != x else "%.2f" % x


def signed(x):
    return "%+.2f" % x


def arm_table(cells, judge, arms, packets, names=NAMES):
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
        out.append("| | %s | %d | %s | %d |" % (names.get(arm, arm), n,
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
            if versioned(key):
                continue          # balanced by design, and measured on its own in its round
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


def latin_rows(cells, key):
    """A round read in every letter order (round 9): each reading's overall minus the mean of the
    same thread's readings, by position, isolates position; how far the readings of one thread
    spread is the judge's own noise."""
    pos_rows, noise = [], []
    for judge in ("claude", "gpt"):
        reads = {}
        for (pk, arm), v in cells.get(judge, {}).items():
            letter = next(L for L, a in key[pk].items() if a == arm)
            reads.setdefault((opener(pk), arm), []).append(("ABCDE".index(letter), v["overall"]))
        if not reads:
            continue
        by_pos, spread = [[] for _ in range(5)], []
        for rs in reads.values():
            m = mean([s for p, s in rs])
            for p, s in rs:
                by_pos[p].append(s - m)
            spread.append(mean([abs(s - m) for p, s in rs]))
        pos_rows.append("| %s | %s |" % (judge, " | ".join(signed(mean(x)) for x in by_pos)))
        noise.append("%s %.2f" % (judge, mean(spread)))
    return pos_rows, noise


# ---- round 9: creepypasta drift ----
# A judge's main_failure note names the horror register / says the posters sound the same / calls
# the thread nonsense (round 7's naifs drew "dream-logic word salad").
HORROR_NOTE = re.compile(r"ominous|creep|horror|dread|cryptic|oracle|eerie|spooky|sinister|occult|"
                         r"paranormal|supernatural|ghost|haunt|menac|portent|doom|uncanny|macabre", re.I)
SAME_NOTE = re.compile(r"\bsame\b|alike|uniform|one-note|monoton|homogen|samey|interchangeable", re.I)
NONSENSE_NOTE = re.compile(r"salad|nonsense|incoheren|garbled|gibberish|broken|dream-logic|"
                           r"non sequitur|schizo", re.I)
LABEL_PAIRS = [("gemini9neutral", "gemini9"), ("rolesshort9neutral", "rolesshort9")]
R9_ORDER = ["gemini9", "gemini9neutral", "rolesshort9", "rolesshort9neutral", "rolesshort9naif"]


def notes(v):
    """The main_failure notes behind a cell: one per reading."""
    m = v["main_failure"]
    return m if isinstance(m, list) else [m]


def note_shares(v):
    """Shares of a cell's readings whose note names horror, horror and sameness, and nonsense."""
    ns = notes(v)
    return (mean([bool(HORROR_NOTE.search(n)) for n in ns]),
            mean([bool(HORROR_NOTE.search(n) and SAME_NOTE.search(n)) for n in ns]),
            mean([bool(NONSENSE_NOTE.search(n)) for n in ns]))


def load_tags(folder, key):
    """{tagger family: {(opener, arm): set of HORROR post numbers}}. Tag files are named by the
    thread's letter in version 1 of its packet: tag-3-B is key['3-v1']['B']."""
    d, tags = os.path.join(HERE, folder), {}
    for fam, pattern in (("claude", "tags-claude-*.json"), ("gpt", "tags-gpt.json")):
        got = {}
        for f in sorted(glob.glob(os.path.join(d, pattern))):
            got.update(read_json(f))
        for name, v in got.items():
            _, p, letter = name.split("-")
            tags.setdefault(fam, {})[(p, key["%s-v1" % p][letter])] = set(v["horror"]) & set(range(2, 25))
    return tags


def kappa(a, b):
    """Cohen's kappa for two raters' yes/no labels of the same items."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else None


def paired_row(measure, label, diffs):
    w, t, l = sum(x > 0 for x in diffs), sum(x == 0 for x in diffs), sum(x < 0 for x in diffs)
    return "| %s | %s | %d | %+.0f pts | %d/%d/%d | %.3f |" % (
        measure, label, len(diffs), 100 * mean(diffs), w, t, l, sign_test(w, l))


def pct(x):
    return "–" if x is None else "%.0f%%" % (100 * x)


def drift_section(folder, key, cells, arms):
    """Round 9's pre-registered drift measures: the share of posts 2-24 the blind taggers label
    HORROR (primary: the two families' mean, neutral against /x/ pooled over both pairs) and the
    share of non-OP posters with a HORROR post; then the judges' notes."""
    scaffold = read_json(os.path.join(HERE, folder, "scaffold.json"))
    tags = load_tags(folder, key)
    fams = [f for f in ("gpt", "claude") if f in tags]
    openers = sorted({opener(pk) for pk in key}, key=int)
    out = ["**Creepypasta drift** (pre-registered). HORROR posts: the share of posts 2–24 a blind "
           "tagger labelled HORROR (`TAG_DEFINITION` in `round3_judge.py`; each thread labelled alone, "
           "once by gpt-5.4 and once by a Claude subagent, neither told the arm). Posters: the share "
           "of non-OP posters with at least one HORROR post.", ""]
    if not fams:
        out += ["Tags pending.", ""]
    else:
        def share(fam, p, arm):
            return len(tags[fam][(p, arm)]) / 23

        def posters(fam, p, arm):
            who = scaffold[p]
            non_op = {w for w in who[1:] if w != who[0]}
            return len({who[n - 1] for n in tags[fam][(p, arm)] if who[n - 1] != who[0]}) / len(non_op)

        both = {(p, a): mean([share(f, p, a) for f in fams]) for p in openers for a in arms}
        head = ["HORROR posts, %s" % f for f in fams] + ["mean"] + ["posters, %s" % f for f in fams]
        out += ["| arm | %s |" % " | ".join(head), "|---|%s" % ("---:|" * len(head))]
        for arm in arms:
            cols = [mean([share(f, p, arm) for p in openers]) for f in fams]
            cols += [mean([both[(p, arm)] for p in openers])]
            cols += [mean([posters(f, p, arm) for p in openers]) for f in fams]
            out.append("| %s | %s |" % (NAMES.get(arm, arm), " | ".join(pct(c) for c in cols)))
        out += ["", "| drift measure | paired | openers | Δ | W/T/L | p |", "|---|---|---:|---:|---|---:|"]
        pooled = {f: [] for f in fams + ["mean"]}
        for arm, base in LABEL_PAIRS:
            diffs = [both[(p, arm)] - both[(p, base)] for p in openers]
            pooled["mean"] += diffs
            for f in fams:
                pooled[f] += [share(f, p, arm) - share(f, p, base) for p in openers]
            out.append(paired_row("HORROR posts, taggers' mean", "%s vs %s" % (arm, base), diffs))
        out.append(paired_row("HORROR posts, taggers' mean", "**neutral vs /x/, both pairs (H2)**",
                              pooled["mean"]))
        for f in fams:
            out.append(paired_row("HORROR posts, %s" % f, "neutral vs /x/, both pairs", pooled[f]))
        if len(fams) == 2:
            a = [n in tags["gpt"][(p, arm)] for p in openers for arm in arms for n in range(2, 25)]
            b = [n in tags["claude"][(p, arm)] for p in openers for arm in arms for n in range(2, 25)]
            out += ["", "The two taggers agree on %d of %d post labels (Cohen's κ = %s)."
                    % (sum(x == y for x, y in zip(a, b)), len(a), f2(kappa(a, b)))]
        out.append("")
    out += ["**Judges' notes.** The share of a family's readings per arm (8 openers × 5) whose "
            "main_failure names the horror register (`HORROR_NOTE`), names it and says the posters "
            "sound alike (`SAME_NOTE`, the \"single ominous voice\"), or calls the thread nonsense "
            "(`NONSENSE_NOTE`).", ""]
    judges = [j for j in ("claude", "gpt")
              if all((p, a) in cells.get(j, {}) for p in openers for a in arms)]   # complete families only
    head = ["%s, %s" % (m, j) for m in ("horror", "horror + same", "nonsense") for j in judges]
    out += ["| arm | %s |" % " | ".join(head), "|---|%s" % ("---:|" * len(head))]
    for arm in arms:
        ns = {j: [note_shares(cells[j][(p, arm)]) for p in openers] for j in judges}
        out.append("| %s | %s |" % (NAMES.get(arm, arm), " | ".join(
            pct(mean([s[m] for s in ns[j]])) for m in range(3) for j in judges)))
    out += ["", "| judges' notes | paired | openers | Δ | W/T/L | p |", "|---|---|---:|---:|---|---:|"]
    for j in judges:
        for arm, base in LABEL_PAIRS:
            out.append(paired_row("horror, %s" % j, "%s vs %s" % (arm, base),
                                  [note_shares(cells[j][(p, arm)])[0] - note_shares(cells[j][(p, base)])[0]
                                   for p in openers]))
        out.append(paired_row("nonsense, %s" % j, "rolesshort9naif vs rolesshort9",
                              [note_shares(cells[j][(p, "rolesshort9naif")])[2] -
                               note_shares(cells[j][(p, "rolesshort9")])[2] for p in openers]))
    return out + [""]


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
    r9 = [(name, s) for name, s in sorted(raw["files"].items()) if "header" in s]
    if r9:
        out += ["", "**Round 9 files** also record the board header, posts cut off by the token limit "
                "(Gemini's `finish_reason` \"length\", llama-server's \"limit\"), who wrote each post, and "
                "which gate terms the withheld posts matched (from the arm's private quarantine file, "
                "which keeps the withheld text).", "",
                "| file | header | saved (UTC) | cut by token limit | posts by writer: n, withheld, mean chars | withheld terms |",
                "|---|---|---|---:|---|---|"]
        for name, s in r9:
            out.append("| %s | `%s` | %s | %d | %s | %s |" % (
                name, s["header"], s["saved_utc"], s["cut_by_max_tokens"],
                "; ".join("%s: %d, %d, %.0f" % (m, v["posts"], v["withheld"], v["mean_chars"])
                          for m, v in s["by_model"].items()),
                ", ".join("%s ×%d" % kv for kv in s["withheld_terms"].items()) or "none"))
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
        lines += ["## Round %s: %s" % (rnd, title), ""]
        if not ran(folder):
            lines += ["Not run yet. Pre-registered in `spike/PREREGISTRATION-ROUND%s.md`, with these "
                      "contrasts (arm vs baseline): %s." % (rnd, "; ".join("%s vs %s" % c for c in contrasts)), ""]
            continue
        key, by_reading = load_round(folder, judges)
        cells = collapse(by_reading) if versioned(key) else by_reading
        rounds_cells.append((rnd, folder, cells))
        keys.append(key)
        arms = sorted({a for letters in key.values() for a in letters.values()})
        packets = sorted({opener(pk) for pk in key})
        lines += [RUBRICS[rnd], ""]
        for judge in judges:
            c = cells[judge]
            got = sorted({p for p, a in c})
            note = "" if len(got) == len(packets) else " (scored %d of %d packets)" % (
                len(got), len(packets))
            lines += ["**%s**%s" % (judge, note), ""]
            lines += arm_table(c, judge, arms, got,
                                dict(NAMES, **JP_NAMES) if folder.startswith("jp") else NAMES) + [""]
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
        if versioned(key):
            pos, spread = latin_rows(by_reading, key)
            lines += ["**Readings.** On average a thread's five overall scores sat this far from their "
                      "own mean: %s. Position, as each reading's overall minus the mean of the same "
                      "thread's five readings, by letter (A is read first):" % ", ".join(spread), "",
                      "| judge | A | B | C | D | E |", "|---|---:|---:|---:|---:|---:|"] + pos + [""]
            lines += drift_section(folder, key, cells, [a for a in R9_ORDER if a in arms])
    lines += ["## Same threads, different rounds", "",
              "Arms that reappear were re-judged from the same file in `spike/remote/` (checked "
              "against the packets in the next section). Movement mixes judge noise with changes "
              "of rubric and of the threads they were compared against. The last two columns pair "
              "every two judgings of the same thread.", "",
              "| judge | arm | overall mean by round | spread of means | mean abs. change per thread | re-judgings that moved ≥1 point |",
              "|---|---|---|---:|---:|---|"] + rejudged(rounds_cells) + [""]
    firsts = []
    for (rnd, folder, cells), key in zip(rounds_cells, keys):
        if versioned(key):
            firsts.append("round %s: every arm equally often, by design (left out of this table)" % rnd)
            continue
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
        if not ran(folder):
            continue
        d = os.path.join(HERE, folder)
        key = read_json(os.path.join(d, "key.json"))
        same, bad = 0, []
        for pk, letters in sorted(key.items()):
            name = pk if folder.startswith("jp") else "opener-%s" % pk
            data = read_bytes(os.path.join(d, name + ".txt"))
            header = data.decode("utf-8").splitlines()[0]
            text = rebuild_packet(folder, name, letters, header)
            # rounds 1-8 were written in text mode on Windows, which turns every "\n", including
            # one inside a post's own "\r\n", into "\r\n"; round 9 writes "\n" on every platform
            if data in (text.encode("utf-8"), text.replace("\n", "\r\n").encode("utf-8")):
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


def round9_stats(d, remote):
    """What round 9's files record beyond the rest: the board header, when the file was last saved,
    posts cut off by max_tokens (the API's finish_reason), each writer's posts, and which gate
    terms the withheld posts matched (from the arm's private quarantine file)."""
    posts = [p for t in d["threads"] for p in t["posts"][1:]]
    by_model = {}
    for p in posts:
        by_model.setdefault(p["model"], []).append(p)
    terms = {}
    q = os.path.join(remote, "quarantine-%s.jsonl" % d["arm"])
    if os.path.exists(q):
        with open(q, encoding="utf-8") as f:
            for line in f:
                for h in json.loads(line)["matched"]:
                    terms[h.strip()] = terms.get(h.strip(), 0) + 1
    return {"header": d["header"], "saved_utc": d.get("saved_utc"),
            # Gemini's finish_reason "length", llama-server's stop_type "limit"
            "cut_by_max_tokens": sum(p["stop"].split(", ")[-1] in ("length", "limit") for p in posts),
            "by_model": {m: {"posts": len(ps), "withheld": sum(bool(p.get("withheld")) for p in ps),
                             "mean_chars": round(mean([len(p["text"]) for p in ps]), 1)}
                         for m, ps in sorted(by_model.items())},
            "withheld_terms": dict(sorted(terms.items()))}


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
        if d.get("gate") == "before context":        # round 9 on
            files[os.path.basename(f)].update(round9_stats(d, remote))
    # a checkout resets key.json's file time, so a round keeps the time first recorded for it
    old = read_json(RAW_STATS).get("packets_built", {}) if os.path.exists(RAW_STATS) else {}
    keys = {}
    for rnd, folder, *_ in ROUNDS:
        if ran(folder):
            k = os.path.join(HERE, folder, "key.json")
            keys[rnd] = old.get(rnd) or time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(os.path.getmtime(k)))
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
