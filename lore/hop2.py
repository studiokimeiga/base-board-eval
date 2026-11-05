#!/usr/bin/env python3
"""The second hop (lore/hop2/PREREGISTRATION.md): does an invention that reached a thread from its
source carry on into a third thread that never saw the source?

  python lore/hop2.py priors                      the priors the rule picks from #4's public results
  python lore/hop2.py schedule                    write lore/hop2/schedule.json (no model output)
  python lore/hop2.py dry                         one page of each arm and the cost estimate; no calls
  python lore/hop2.py smoke                       the pre-registered smoke test, kept out of the analysis
  python lore/hop2.py run [--design full|four] [--cap 8]
  python lore/hop2.py manifest                    hash lore/hop2/private/ into lore/hop2/MANIFEST.sha256
  python lore/hop2.py packets                     the blind judge's items, and the key
  python lore/hop2.py claude-prompt N [--half]    the exact prompt for Claude batch N (of judge.BATCHES)
  python lore/hop2.py collect [--half]            public verdicts from the judge's private replies
  python lore/hop2.py analyze                     lore/hop2/RESULTS.md and lore/hop2/results.json

Generation 1 (#4's run: the sources, the priors and their shams) is read in place from --gen1
(default lore/private/run), and every file must match its hash in lore/MANIFEST.sha256. The
OpenRouter key comes from the file named by LORE_ENV, as for board.py, and is never printed.

A generation-2 target is written twice, with the same opener, cast, author order, timestamps,
thread number and seeds: on the lore arm under its prior (a generation-1 memory target that
inherited an item from its source), on the sham arm under the prior's no-memory twin. The source is
on neither page.
"""
import argparse, collections, datetime, glob, hashlib, json, os, random, re, statistics, sys, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze as A
import board as B
import explore as E
import judge as J
import tracker as T

SEED = B.SEED
BOARD, BOARD_KEY = "/misc/", "misc"
DESIGNS = {"full": 6, "four": 4}          # targets per prior; "four" keeps each prior's ranks 0-3
FIRST = 4540                              # generation 1 used 4471-4539
START = 7 * 86400                         # Mon 11/02/26 09:00, after every generation-1 thread ended
ARMS = ("lore", "sham")
DIR = os.path.join(HERE, "hop2")
PRIVATE = os.path.join(DIR, "private")
GEN1 = os.path.join(B.PRIVATE, "run")
MANIFEST1 = os.path.join(HERE, "MANIFEST.sha256")
ITEM_SEED = "%d:hop2:items" % SEED        # shuffles the judge's item ids
HALF_SEED = "%d:hop2:half" % SEED         # draws the judge's fallback half: apart from ITEM_SEED
# Dollars a call = a + b * prompt characters + c * reply characters: least squares over #4's 5,290
# logged calls (a is mostly the reasoning tokens every call spends).
COST = (0.001544, 1.404e-07, 4.168e-07)


def write_text(path, text):
    """Unix newlines on every platform: the same bytes, and hashes, on Windows and Linux."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path, obj):
    write_text(path, json.dumps(obj, indent=1))


# ---- the priors ----
def item_words(item):
    """The words of a tracker item: a word, a phrase, or a pair ("rep + union")."""
    return {w for part in item.split(" + ") for w in part.split()}


def priors(results, sched1, claude=None, board=BOARD_KEY):
    """The rule: every generation-1 memory target on `board` whose source recurred under #4's H5,
    i.e. whose source's two memory targets share a tracker item (results.json). Its lore items are
    the shared ones. `confirmed` marks a source whose two memory targets the blind Claude judge both
    found borrowing from it (`claude`: {(board, target, arm): verdict}, as analyze.judges gives)."""
    items = {(r["board"], r["target"], r["arm"]): {i["item"] for i in r["items"]} for r in results["targets"]}
    out = []
    for s in sched1["sources"]:
        ts = sorted(t["id"] for t in sched1["targets"] if t["source"] == s["id"])
        if len(ts) != 2 or any((board, t, "memory") not in items for t in ts):
            continue
        shared = items[(board, ts[0], "memory")] & items[(board, ts[1], "memory")]
        if not shared:
            continue
        confirmed = bool(claude) and all((claude.get((board, t, "memory")) or {}).get("borrows") for t in ts)
        words = sorted(set().union(*map(item_words, shared)))
        for t in ts:
            out.append({"prior": t, "source": s["id"], "board": board, "items": sorted(shared),
                        "words": words, "confirmed": confirmed})
    return out


# ---- the schedule ----
def eligible(prior, sched1):
    """Openers sharing no topic tag with the prior's opener or with its source's."""
    p = next(t for t in sched1["targets"] if t["id"] == prior)
    s = next(x for x in sched1["sources"] if x["id"] == p["source"])
    banned = set(B.TAGS[p["opener"]]) | set(B.TAGS[s["opener"]])
    return [o for o in range(len(B.OPENERS)) if not set(B.TAGS[o]) & banned]


def assign(rng, options, per, tries=500):
    """`per` distinct openers for each prior from its options, spreading use over the openers as
    evenly as the options allow: the best of `tries` seeded greedy passes (lowest maximum use, then
    lowest sum of squares). {prior: openers in rank order}."""
    best = None
    for _ in range(tries):
        counts, out = collections.Counter(), {}
        order = sorted(options)
        rng.shuffle(order)
        for p in order:
            pool = list(options[p])
            rng.shuffle(pool)
            pool.sort(key=lambda o: counts[o])         # least used first, ties in random order
            out[p] = pool[:per]
            counts.update(out[p])
        key = (max(counts.values()), sum(v * v for v in counts.values()))
        if best is None or key < best[0]:
            best = (key, out)
    return best[1]


def in_design(target, design):
    return target["rank"] < DESIGNS[design]


def schedule(prs, sched1, seed=SEED):
    rng = random.Random("%d:hop2:schedule" % seed)
    by_id = {t["id"]: t for t in sched1["targets"]}
    src = {s["id"]: s for s in sched1["sources"]}
    ids = sorted(p["prior"] for p in prs)
    openers = assign(rng, {p: eligible(p, sched1) for p in ids}, DESIGNS["full"])
    slots = [(p, o, rank) for p in ids for rank, o in enumerate(openers[p])]
    rng.shuffle(slots)
    n = len(slots)
    patterns = B._balanced(rng, [("away", n - 2 * (n // 3)), ("burst", n // 3), ("gone", n // 3)])
    targets = []
    for k, (pid, o, rank) in enumerate(slots):
        r = random.Random("%d:hop2:target:%s:%d" % (seed, pid, o))
        p = by_id[pid]
        s = src[p["source"]]
        cast = r.sample([h for h in B.G.NAMES if h not in p["cast"] and h not in s["cast"]], B.CAST)
        authors, times, flags = B.scaffold(r, cast, patterns[k])
        targets.append({"id": "u%02d" % k, "role": "hop2", "prior": pid, "source": s["id"], "opener": o,
                        "rank": rank, "no": FIRST + k, "pattern": patterns[k], "cast": cast,
                        "authors": authors, "times": times, "flags": flags,
                        "start": START + k * 1200 + r.randint(0, 600)})
    half = {}
    for design in DESIGNS:
        hr, chosen = random.Random(HALF_SEED), []
        for pid in ids:
            mine = sorted(t["id"] for t in targets if t["prior"] == pid and in_design(t, design))
            hr.shuffle(mine)
            chosen += mine[:len(mine) // 2]
        half[design] = sorted(chosen)
    return {"seed": seed, "posts": B.POSTS, "board": BOARD, "designs": DESIGNS, "priors": prs,
            "targets": targets, "half": half}


# ---- generation 1, read in place ----
def load_gen1(root=GEN1, manifest=MANIFEST1):
    """judge.load_run, except that every file must match its SHA-256 in #4's manifest, where it is
    listed as private/run/<board>/<file>. manifest=None skips the check (tests only)."""
    want = {}
    if manifest is not None:
        with open(manifest, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    digest, path = line.rstrip("\n").split(" *", 1)
                    want[path] = digest
    run = {}
    for b in B.BOARDS:
        for path in sorted(glob.glob(os.path.join(root, b, "*.json"))):
            name = os.path.basename(path)
            with open(path, "rb") as f:
                raw = f.read()
            rel = "private/run/%s/%s" % (b, name)
            if manifest is not None and want.get(rel) != hashlib.sha256(raw).hexdigest():
                raise ValueError("%s does not match %s" % (rel, manifest))
            tid, _, arm = name[:-5].partition("-")
            run[(b, tid, arm or None)] = json.loads(raw.decode("utf-8"))
    if not run:
        raise ValueError("no generation-1 threads in %s (pass --gen1)" % root)
    # every board's threads feed the tracker's background, so a partial copy (say /misc/ alone)
    # would change rarity filtering without an error: require all the manifest lists
    found = {"private/run/%s/%s.json" % (b, "%s-%s" % (tid, arm) if arm else tid) for b, tid, arm in run}
    required = {rel for rel in want if rel.count("/") == 3 and rel.split("/")[2] in B.BOARDS
                and rel.startswith("private/run/") and rel.endswith(".json")}
    missing = sorted(required - found)
    if missing:
        raise ValueError("generation 1 in %s is incomplete: %d listed threads missing, e.g. %s"
                         % (root, len(missing), ", ".join(missing[:3])))
    return run


def above_pair(gen1, prior):
    """The prior and its sham: twins with the same number, opener, cast, authors and timestamps."""
    p, s = gen1[(BOARD_KEY, prior, "memory")], gen1[(BOARD_KEY, prior, "none")]
    for k in ("no", "opener", "cast"):
        if p[k] != s[k]:
            raise ValueError("%s: the prior and its sham differ in %s" % (prior, k))
    if [(x["who"], x.get("ts")) for x in p["posts"]] != [(x["who"], x.get("ts")) for x in s["posts"]]:
        raise ValueError("%s: the prior and its sham differ in authors or timestamps" % prior)
    return p, s


# ---- generation 2 ----
def generate_target(spec, above, arm, complete, budget=None):
    posts, stop_list, quarantine, spent = B.generate(spec, BOARD, complete, above=above,
                                                     above_cast=above["cast"], arm=arm, budget=budget)
    return {"id": spec["id"], "role": "hop2", "arm": arm, "board": BOARD, "no": spec["no"],
            "opener": spec["opener"], "pattern": spec["pattern"], "cast": spec["cast"],
            "prior": spec["prior"], "source": spec["source"], "above_no": above["no"], "model": B.MODEL,
            "ask": B.ASK, "stops": stop_list, "spend": spent, "posts": posts, "quarantine": quarantine}


def path_of(root, spec, arm):
    return os.path.join(root, BOARD_KEY, "%s-%s.json" % (spec["id"], arm))


def cap_for(design, cap=None):
    """The hard cap in dollars: the one given, else the design's pre-registered cap."""
    return cap if cap is not None else {"full": 8.0, "four": 6.0}[design]


def run(sched2, design, gen1, complete, budget, root, workers=12, log=print):
    """Both arms of every target in the design, interleaved, so any drift in the model or the provider
    lands on both alike. Resumable: a thread already written is kept, never regenerated; a thread is
    saved only when complete. A failure anywhere, or an interrupt, halts the budget, so every running
    thread stops at its next call and nothing queued starts; the first failure is the one raised."""
    pairs = {p["prior"]: above_pair(gen1, p["prior"]) for p in sched2["priors"]}   # all checked first
    jobs = [(t, arm) for t in sched2["targets"] if in_design(t, design) for arm in ARMS]
    qlog, lock, failed = os.path.join(root, "quarantine.jsonl"), threading.Lock(), []

    def one(job):
        spec, arm = job
        path = path_of(root, spec, arm)
        if os.path.exists(path):
            return "have " + os.path.basename(path)
        prior, sham = pairs[spec["prior"]]
        try:
            th = generate_target(spec, prior if arm == "lore" else sham, arm, complete, budget)
        except BaseException as e:
            with lock:
                failed.append(e)
            budget.halt()
            raise
        with lock:                       # the quarantine log is shared by every worker
            B._save(path, th, qlog)
        return "%s %s $%.4f (total $%.3f)" % (spec["id"], arm, th["spend"], budget.spent)

    ex = ThreadPoolExecutor(workers)
    try:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            log(fut.result())
    except BaseException as e:
        with lock:
            cause = failed[0] if failed else e
        budget.halt()
        ex.shutdown(wait=True, cancel_futures=True)
        raise cause
    ex.shutdown(wait=True)


def load_run(root):
    """{(board key, target id, arm): thread} for every hop-2 thread written."""
    out = {}
    for path in glob.glob(os.path.join(root, BOARD_KEY, "*.json")):
        tid, _, arm = os.path.basename(path)[:-5].partition("-")
        with open(path, encoding="utf-8") as f:
            out[(BOARD_KEY, tid, arm)] = json.load(f)
    return out


def estimate(sched2, design, gen1, reply_factor=1.5):
    """Dollars for a design, from COST: replies `reply_factor` times as long as the posts of the
    thread above them (at least 90 characters, the no-memory length), headers about 30 characters."""
    usd = 0.0
    for t in sched2["targets"]:
        if not in_design(t, design):
            continue
        for above in above_pair(gen1, t["prior"]):
            reply = max(90.0, reply_factor * E.mean_len(above))
            fixed = len(B.ask(B.page(BOARD, t["no"], [], above), "someone")) + len(B.OPENERS[t["opener"]]) + 30
            for n in range(2, B.POSTS + 1):
                usd += COST[0] + COST[1] * (fixed + (n - 2) * (reply + 30)) + COST[2] * reply
    return usd


# ---- measurement ----
def identify(t, real, candidates, sources, exclude, common):
    """explore.py's length-matched test (explore.identification): the target is scored against every
    candidate source with the frozen tracker, the same target text each time, so post length cannot
    favour one candidate over another. Is its real source the highest? `sources` maps keys to every
    generation-0 thread (a candidate's background is all the others), and material in `exclude`
    (posts) counts for no candidate. No page showed the source, so its number is never a reference."""
    scores, result = {}, None
    for c in candidates:
        s = sources[c]
        bg = [x["posts"] for k, x in sources.items() if k != c]
        r = T.track(t["posts"], s["posts"], bg, target_no=t["no"], source_no=s["no"], source_shown=False,
                    topic_twin=exclude, board=t["board"], target_cast=t["cast"], common=common)
        scores[c] = E.score(r)
        if c == real:
            result = r
    real_score = scores[real]
    others = [v for k, v in scores.items() if k != real]
    return {"candidates": len(scores), "real": real_score, "top": real_score > max(others),
            "percentile": (sum(v < real_score for v in others) + 0.5 * sum(v == real_score for v in others)) / len(others),
            "result": result, "scores": scores}


def lore_hit(result, words):
    """Does a tracker result carry one of a lineage's lore words, in any of its items?"""
    return any(item_words(i["item"]) & set(words) for i in result["items"])


def twin_of(sources, opener):
    """The generation-0 source on the board written from this opener: what the topic gives anyway."""
    return next(k for k, s in sorted(sources.items(), key=lambda kv: str(kv[0]))
                if k[0] == BOARD_KEY and s["opener"] == opener)


def score_target(q, sched2, gen1, common):
    """Everything the analysis needs about one hop-2 thread (PREREGISTRATION.md, Measurement)."""
    sources = {k: v for k, v in gen1.items() if k[2] is None}
    prior, sham = above_pair(gen1, q["prior"])
    q_twin, p_twin = twin_of(sources, q["opener"]), twin_of(sources, prior["opener"])
    exclude = sources[q_twin]["posts"] + sources[p_twin]["posts"] + sham["posts"]
    real = (BOARD_KEY, q["source"], None)
    unrelated = [k for k, s in sources.items() if k[0] == BOARD_KEY
                 and not set(B.TAGS[s["opener"]]) & set(B.TAGS[q["opener"]])]
    cands = [k for k in unrelated if k != p_twin]
    if real not in cands:
        raise ValueError("%s: its source is not a candidate" % q["id"])
    ident = identify(q, real, cands, sources, exclude, common)
    robust = identify(q, real, unrelated, sources, sources[q_twin]["posts"], common)   # explore.py's exactly
    lineage = {p["source"]: p for p in sched2["priors"]}
    cross = {}
    for sid, p in lineage.items():
        key = (BOARD_KEY, sid, None)
        if sid == q["source"] or key in (q_twin, p_twin):
            continue
        r = T.track(q["posts"], sources[key]["posts"], [x["posts"] for k, x in sources.items() if k != key],
                    target_no=q["no"], source_no=sources[key]["no"], source_shown=False, topic_twin=exclude,
                    board=q["board"], target_cast=q["cast"], common=common)
        cross[sid] = lore_hit(r, p["words"])
    res = ident["result"]
    return {"top": ident["top"], "percentile": ident["percentile"], "candidates": ident["candidates"],
            "real": ident["real"], "robust_top": robust["top"], "lore": lore_hit(res, lineage[q["source"]]["words"]),
            "cross": cross, "names": sorted({r["match"] for r in res["references"] if r["kind"] == "handle"}),
            "references": res["references"], "transfer": res["transfer"], "uptake": res["uptake"],
            "items": res["items"], "len": E.mean_len(q),
            "above_len": E.mean_len(prior if q["arm"] == "lore" else sham)}


# ---- the blind judge ----
def items(run2, gen1):
    """Every hop-2 thread as Thread B, with its lineage source as Thread A; ids shuffled with
    ITEM_SEED, so nothing in a packet tells the arm."""
    keys = sorted(run2)
    ids = ["h%03d" % i for i in range(len(keys))]
    random.Random(ITEM_SEED).shuffle(ids)
    out = []
    for item_id, k in zip(ids, keys):
        q = run2[k]
        s = gen1[(BOARD_KEY, q["source"], None)]
        out.append({"item": item_id, "target": k[1], "arm": k[2],
                    "text": J.PROMPT_HOP2 % (J.render(s), J.render(q))})
    return sorted(out, key=lambda x: x["item"])


def _norm(s):
    s = str(s).lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def _found(quote, text):
    """Is a judge's quote in this normalised text? Its longest stretch between ellipses, first 40
    characters, so a trimmed or elided quote still counts."""
    parts = re.split(r"\.\.\.|…", str(quote))
    probe = _norm(max(parts, key=lambda p: len(_norm(p))))[:40]
    return bool(probe) and probe in text


def misfiled(texts, replies):
    """Answers filed under the wrong item: fewer than half of their quotes from Thread B are in the
    item's own Thread B, and at least half are in another item's. {item: [the items they fit]}. An
    answer that quotes nothing cannot be checked, and passes."""
    threads = {}
    for i, t in texts.items():
        a, b = t.split("=== Thread A (earlier) ===\n", 1)[1].split("\n\n=== Thread B (later) ===\n", 1)
        threads[i] = (_norm(a), _norm(b))
    out = {}
    for i, v in replies.items():
        bs = [x.get("b", "") for x in (v.get("borrowings") or []) if isinstance(x, dict)]
        if not bs or i not in threads or 2 * sum(_found(q, threads[i][1]) for q in bs) >= len(bs):
            continue
        fits = sorted(o for o in threads if o != i and 2 * sum(_found(q, threads[o][1]) for q in bs) >= len(bs))
        if fits:
            out[i] = fits
    return out


def rejudge_prompt(item_id, folder):
    """One item for one fresh judge, who cannot file it under another id."""
    return ("You are one of several independent judges. Below is one file. It holds one judging item: "
            "instructions and two imageboard threads. Read it and answer its question exactly as it asks. "
            "Do not read any other file, do not look for answer keys, and do not run any code.\n\n"
            "Write your answer into one JSON file, %s\\claude-rejudge-%s.json, mapping the item id (the file "
            "name without .txt) to the JSON object the item asks for. Reply with only the number of items you "
            "wrote.\n\n%s\\items\\%s.txt" % (folder, item_id, folder, item_id))


def as_dict(reply):
    if isinstance(reply, dict):
        return reply
    m = re.search(r"\{.*\}", reply or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def verdicts(folder):
    """{(target, arm): verdict} from hop2/judging/ (key.json and scores-claude.json), or {}."""
    kp, sp = os.path.join(folder, "key.json"), os.path.join(folder, "scores-claude.json")
    if not (os.path.exists(kp) and os.path.exists(sp)):
        return {}
    key = A.load(kp)
    return {(key[i]["target"], key[i]["arm"]): v for i, v in A.load(sp)["items"].items()}


# ---- the analysis ----
def l4(p, lore_only, sham_only, content_lore, content_sham):
    """The pre-registered verdict on #4's L4 criterion "survives more than one hop" (PREREGISTRATION.md):
    (a) the source is identified in more lore than sham targets, McNemar p < 0.05; (b) more lore than
    sham targets carry a lore item of a confirmed lineage that the blind judge says is borrowed."""
    a = lore_only > sham_only and p < 0.05
    b = content_lore > content_sham
    if a and b:
        return "met: the source's material survives two hops above the sham rate, and a named invention is among it"
    if a:
        return "partly: source material survives two hops above the sham rate, but no named invention of a confirmed lineage does"
    if b:
        return "partly: an invention of a confirmed lineage reached a third thread, but the rate is not distinguishable from the sham"
    return "not met: no evidence that material survives a second hop"


def analyze(gen1, run2, sched2, judging, out, common, design="full"):
    specs = {t["id"]: t for t in sched2["targets"]}
    # a reduced design is analysed on its own targets only, even if the run holds more
    run2 = {k: v for k, v in run2.items() if k[1] in specs and in_design(specs[k[1]], design)}
    lineage = {p["source"]: p for p in sched2["priors"]}
    jud = verdicts(judging)
    res = {k: score_target(q, sched2, gen1, common) for k, q in sorted(run2.items())}
    tids = sorted({k[1] for k in res if (BOARD_KEY, k[1], "lore") in res and (BOARD_KEY, k[1], "sham") in res})
    get = lambda tid, arm: res[(BOARD_KEY, tid, arm)]
    L = ["# Results: does lore survive a second hop?", "",
         "Generated by `python lore/hop2.py analyze` from the private hop-2 run (hashes in `hop2/MANIFEST.sha256`), "
         "generation 1 (checked against `MANIFEST.sha256`), the public schedule, the frozen tracker "
         "(`REF_SHARE` %s) and Claude's verdicts in `hop2/judging/`. Intervals are Wilson 95%%; the interval "
         "for a difference resamples priors. Read `REPORT.md` for what it means." % T.REF_SHARE, ""]

    # threads
    L += ["## Threads", "", "| arm | targets | mean post length | withheld posts | empty posts | spend |",
          "|---|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        ts = [run2[(BOARD_KEY, tid, arm)] for tid in tids]
        posts = [p for t in ts for p in t["posts"][1:]]
        L.append("| %s | %d | %.0f | %d | %d | $%.2f |" % (
            arm, len(ts), statistics.mean(E.mean_len(t) for t in ts) if ts else 0,
            sum(1 for p in posts if p.get("withheld")), sum(1 for p in posts if not p.get("text")),
            sum(t.get("spend", 0) for t in ts)))

    def paired(field, keep=lambda tid: True):
        ps = [(get(tid, "lore")[field], get(tid, "sham")[field]) for tid in tids if keep(tid)]
        bm, cm, p = A.mcnemar(ps)
        clusters = collections.defaultdict(list)
        for tid in tids:
            if keep(tid):
                clusters[specs[tid]["prior"]].append((get(tid, "lore")[field], get(tid, "sham")[field]))
        lo, hi = A.bootstrap_diff(list(clusters.values())) if clusters else (0.0, 0.0)
        return {"pairs": len(ps), "lore": sum(m for m, _ in ps), "sham": sum(n for _, n in ps),
                "lore_only": bm, "sham_only": cm, "p": p,
                "diff": (sum(m for m, _ in ps) - sum(n for _, n in ps)) / len(ps) if ps else 0.0, "ci": [lo, hi]}

    def row(name, s):
        return "| %s | %d | %s | %s | %d | %d | %.4f | %+.2f (%+.2f to %+.2f) |" % (
            name, s["pairs"], A.pct(s["lore"], s["pairs"]), A.pct(s["sham"], s["pairs"]),
            s["lore_only"], s["sham_only"], s["p"], s["diff"], s["ci"][0], s["ci"][1])

    head = ["| scope | pairs | lore | sham | lore only | sham only | McNemar p | difference, 95% interval |",
            "|---|---:|---|---|---:|---:|---:|---|"]
    confirmed = lambda tid: lineage[specs[tid]["source"]]["confirmed"]
    h1 = paired("top")
    L += ["", "## H1: the source identified two hops away (primary)", "",
          "The lineage source scores highest among the candidates (explore.py's test), though no page showed it.", ""] + head
    L.append(row("all priors", h1))
    sub = paired("top", confirmed)
    L.append(row("confirmed lineages", sub))
    rob = paired("robust_top")
    L.append(row("robustness: explore.py's exclusions", rob))
    up = sum(get(t, "lore")["percentile"] > get(t, "sham")["percentile"] for t in tids)
    down = sum(get(t, "lore")["percentile"] < get(t, "sham")["percentile"] for t in tids)
    chance = sum(1 / get(t, "lore")["candidates"] for t in tids)
    L += ["", "Mean percentile of the source among the candidates: lore %.2f, sham %.2f; higher on the lore arm "
          "in %d targets, lower in %d (sign test p = %.4f). Chance of being highest: %.1f targets per arm." % (
              statistics.mean(get(t, "lore")["percentile"] for t in tids) if tids else 0,
              statistics.mean(get(t, "sham")["percentile"] for t in tids) if tids else 0,
              up, down, A.sign_test(up, down), chance)]

    # per lineage and prior
    L += ["", "## Per lineage and prior", "",
          "| source | lore items | prior | targets | identified: lore | sham | lore item: lore | sham |",
          "|---|---|---|---:|---:|---:|---:|---:|"]
    for p in sorted(sched2["priors"], key=lambda x: (x["source"], x["prior"])):
        mine = [tid for tid in tids if specs[tid]["prior"] == p["prior"]]
        L.append("| %s%s | %s | %s | %d | %d | %d | %d | %d |" % (
            p["source"], "" if p["confirmed"] else " (unconfirmed)", ", ".join(A.safe(x) for x in p["items"]),
            p["prior"], len(mine), sum(get(t, "lore")["top"] for t in mine), sum(get(t, "sham")["top"] for t in mine),
            sum(get(t, "lore")["lore"] for t in mine), sum(get(t, "sham")["lore"] for t in mine)))

    # H2
    h2 = paired("lore")
    cross = [v for t in tids for v in get(t, "lore")["cross"].values()]
    h2.update(cross_hits=sum(cross), cross_n=len(cross))
    L += ["", "## H2: the named item survives", "",
          "A tracker item of the source in the new thread contains one of its lineage's lore words.", ""] + head
    L.append(row("all priors", h2))
    L += ["", "Chance at the same length: lore-arm targets carry another lineage's lore words in %s of "
          "target × lineage checks." % A.pct(h2["cross_hits"], h2["cross_n"])]

    # H3. The judge's outcomes count only over a complete scope: every target, or the pre-registered
    # fallback half. A partial or interrupted judging leaves the verdict pending.
    both = {t for t in tids if (t, "lore") in jud and (t, "sham") in jud}
    half = set(sched2.get("half", {}).get(design, ())) & set(tids)
    if tids and set(tids) <= both:
        scope = "all"
        judged = list(tids)
    elif half and half <= both:
        scope = "half"
        judged = sorted(half)
    else:
        scope = None
        judged = sorted(both)
    h3 = {"pairs": len(judged), "lore_only": 0, "sham_only": 0, "p": 1.0}
    L += ["", "## H3: the blind judge (Claude)", ""]
    if jud:
        L += ["Judging scope: %s." % ({"all": "every target", "half": "the pre-registered half"}.get(scope)
              or "incomplete, %d of %d targets judged in both arms; the numbers below are descriptive and "
                 "the verdict waits" % (len(both), len(tids))), ""]
        ps = [(jud[(t, "lore")]["borrows"], jud[(t, "sham")]["borrows"]) for t in judged]
        bm, cm, p = A.mcnemar(ps)
        h3 = {"pairs": len(ps), "lore": sum(m for m, _ in ps), "sham": sum(n for _, n in ps),
              "lore_only": bm, "sham_only": cm, "p": p}
        kinds = {k: sum(jud[(t, "lore")]["kinds"][k] for t in judged if jud[(t, "lore")]["borrows"]) for k in J.KINDS}
        ks = [(BOARD_KEY, t, a) for t in judged for a in ARMS]
        kp = A.kappa([res[k]["top"] for k in ks], [jud[(k[1], k[2])]["borrows"] for k in ks])
        L += ["Borrows from the source (a sham-arm yes is wrong by construction): lore %s, sham %s; "
              "McNemar %d vs %d, p = %.4f, over %d targets judged in both arms." % (
                  A.pct(h3["lore"], len(ps)), A.pct(h3["sham"], len(ps)), bm, cm, p, len(ps)), "",
              "Kinds of borrowing in lore-arm items judged to borrow: %s. Agreement with H1's outcome: κ = %s." % (
                  ", ".join("%s %d" % kv for kv in kinds.items()), "%.2f" % kp if kp is not None else "–")]
    else:
        L.append("No verdicts yet.")

    # H4
    def lore_level(k):
        v = jud.get((k[1], k[2]))
        return bool(res[k]["transfer"] and res[k]["uptake"] >= 2 and v and v["borrows"] and v["kinds"]["reuse"] > 0)
    h4 = {arm: sum(lore_level((BOARD_KEY, t, arm)) for t in judged) for arm in ARMS}
    L += ["", "## H4: lore at the second hop (L3 in the new thread)", "",
          "Tracker transfer from the source, used by at least two posters, and the judge calls a borrowing *reuse*: "
          "lore %s, sham %s." % (A.pct(h4["lore"], len(judged)), A.pct(h4["sham"], len(judged)))]

    # H5
    L += ["", "## H5: register", ""]
    for arm in ARMS:
        u = [get(t, arm)["above_len"] for t in tids]
        v = [get(t, arm)["len"] for t in tids]
        r = E.corr(u, v) if len(tids) > 2 else None
        L.append("- %s: posts %.0f characters, the thread above %.0f; r = %s." % (
            arm, statistics.mean(v) if v else 0, statistics.mean(u) if u else 0, "%.2f" % r if r is not None else "–"))
    longer = sum(get(t, "lore")["len"] > get(t, "sham")["len"] for t in tids)
    shorter = sum(get(t, "lore")["len"] < get(t, "sham")["len"] for t in tids)
    L.append("- lore-arm posts longer than their sham twin's in %d targets, shorter in %d (sign test p = %.4f)." % (
        longer, shorter, A.sign_test(longer, shorter)))

    # names
    names = {arm: sum(bool(get(t, arm)["names"]) for t in tids) for arm in ARMS}
    L += ["", "## Two-hop names", "",
          "A poster of the source, never on the page, is named in the new thread: lore %s, sham %s." % (
              A.pct(names["lore"], len(tids)), A.pct(names["sham"], len(tids)))]

    # the verdict
    content = {arm: sum(1 for t in judged if confirmed(t) and get(t, arm)["lore"] and jud[(t, arm)]["borrows"])
               for arm in ARMS}
    if scope:
        verdict = l4(h1["p"], h1["lore_only"], h1["sham_only"], content["lore"], content["sham"])
    else:
        verdict = "pending: criterion (b) needs Claude's verdicts on every target or the pre-registered half " \
                  "(%d of %d targets judged in both arms); criterion (a) alone %s" % (
                      len(both), len(tids),
                      "holds" if h1["lore_only"] > h1["sham_only"] and h1["p"] < 0.05 else "does not hold")
    L += ["", "## The verdict on L4 (\"survives more than one hop\")", "",
          "(a) H1: %d lore-only against %d sham-only targets, p = %.4f. (b) Targets carrying a lore item of a "
          "confirmed lineage that the judge says is borrowed: lore %d, sham %d." % (
              h1["lore_only"], h1["sham_only"], h1["p"], content["lore"], content["sham"]), "",
          "**%s.**" % verdict]

    # every flagged target
    L += ["", "## Every flagged target", "",
          "Items are tracker items of the source (gate-checked); names are its posters.", "",
          "| target | prior | source | arm | identified | lore item | items | names | judge |",
          "|---|---|---|---|---|---|---|---|---|"]
    for (b, tid, arm), r in sorted(res.items()):
        if not (r["top"] or r["lore"] or r["names"]):
            continue
        its = "; ".join("%s%s" % (A.safe(i["item"]), " ×%d" % i["uses"] if i["kind"] == "word" else "") for i in r["items"][:6])
        v = jud.get((tid, arm))
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            tid, specs[tid]["prior"], specs[tid]["source"], arm, "yes" if r["top"] else "no",
            "yes" if r["lore"] else "no", its or "–", ", ".join(A.safe(n) for n in r["names"]) or "–",
            ("yes" if v["borrows"] else "no") if v else "–"))
    L += ["", "Generation spend logged in the thread files: $%.2f over %d threads." % (
        sum(t.get("spend", 0) for t in run2.values()), len(run2)), ""]

    summary = {"design": design, "judging_scope": scope, "h1": h1, "h1_confirmed": sub, "h1_robust": rob, "h2": h2, "h3": h3,
               "h4": h4, "names": names, "content": content, "l4": verdict}
    write_text(os.path.join(out, "RESULTS.md"), "\n".join(L))
    write_json(os.path.join(out, "results.json"), {"ref_share": T.REF_SHARE, "summary": summary, "targets": [
        {"target": tid, "arm": arm, "prior": specs[tid]["prior"], "source": specs[tid]["source"],
         "top": r["top"], "percentile": r["percentile"], "candidates": r["candidates"], "real": r["real"],
         "robust_top": r["robust_top"], "lore": r["lore"], "cross": r["cross"],
         "names": [A.safe(n) for n in r["names"]], "transfer": r["transfer"], "uptake": r["uptake"],
         "items": [{"item": A.safe(i["item"]), "kind": i["kind"], "uses": i["uses"], "authors": len(i["authors"])}
                   for i in r["items"]],
         "len": r["len"], "above_len": r["above_len"]} for (b, tid, arm), r in sorted(res.items())]})
    return summary


# ---- the command line ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["priors", "schedule", "dry", "smoke", "run", "manifest", "packets",
                                    "claude-prompt", "collect", "analyze"])
    ap.add_argument("n", nargs="?", type=int)
    ap.add_argument("--gen1", default=GEN1, help="generation 1's run folder (default lore/private/run)")
    ap.add_argument("--design", default="full", choices=sorted(DESIGNS))
    ap.add_argument("--cap", type=float, default=None, help="dollars (default: the design's, $8 full, $6 four)")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--half", action="store_true", help="Claude judges the pre-registered half")
    ap.add_argument("--item", help="claude-prompt for one item, judged again on its own")
    a = ap.parse_args()
    sched1 = B.schedule()
    sched_path = os.path.join(DIR, "schedule.json")
    judging_priv, judging_pub = os.path.join(PRIVATE, "judging"), os.path.join(DIR, "judging")

    if a.cmd == "priors":
        for p in priors(A.load(os.path.join(HERE, "results.json")), sched1, A.judges(os.path.join(HERE, "judging")).get("claude")):
            print(p["source"], p["prior"], ", ".join(p["items"]), "(confirmed)" if p["confirmed"] else "")
        return
    if a.cmd == "schedule":
        prs = priors(A.load(os.path.join(HERE, "results.json")), sched1, A.judges(os.path.join(HERE, "judging")).get("claude"))
        os.makedirs(DIR, exist_ok=True)
        write_json(sched_path, schedule(prs, sched1))
        print("wrote lore/hop2/schedule.json: %d priors, %d targets" % (len(prs), DESIGNS["full"] * len(prs)))
        return
    sched2 = A.load(sched_path)
    if a.cmd == "manifest":
        print("hashed %d private files into lore/hop2/MANIFEST.sha256"
              % B.manifest(PRIVATE, DIR, os.path.join(DIR, "MANIFEST.sha256")))
        return
    gen1 = load_gen1(a.gen1) if a.cmd in ("dry", "smoke", "run", "packets", "analyze") else None

    if a.cmd == "dry":
        t = sched2["targets"][0]
        prior, sham = above_pair(gen1, t["prior"])
        opener = [{"who": t["authors"][0], "ts": B.stamp(t["start"]), "text": B.OPENERS[t["opener"]]}]
        for arm, above in (("lore", prior), ("sham", sham)):
            fake = dict(above, posts=[dict(p, text="<%s post %d>" % ("prior" if arm == "lore" else "sham", i + 1))
                                      for i, p in enumerate(above["posts"]) if p.get("text") and not p.get("withheld")])
            print("=" * 30, arm, "=" * 30)
            print(B.ask(B.page(BOARD, t["no"], opener, fake), t["authors"][1]))
        for d in sorted(DESIGNS):
            n = sum(in_design(t, d) for t in sched2["targets"])
            print("%-4s %2d targets, %3d threads: ~$%.2f (replies 1.5x the thread above), ~$%.2f (2x)"
                  % (d, n, 2 * n, estimate(sched2, d, gen1), estimate(sched2, d, gen1, 2.0)))
    elif a.cmd in ("smoke", "run"):
        smoke = a.cmd == "smoke"
        root = os.path.join(PRIVATE, "smoke" if smoke else "run")
        before = B.prior_spend(root)        # the cap bounds the total across resumed runs
        budget = B.Budget(cap=1.0 if smoke else cap_for(a.design, a.cap), spent=before)
        mini = dict(sched2, targets=sched2["targets"][:1]) if smoke else sched2
        try:
            run(mini, "full" if smoke else a.design, gen1, B.gemini(B.openrouter_key()), budget, root,
                workers=2 if smoke else a.workers)
        finally:
            os.makedirs(root, exist_ok=True)
            write_json(os.path.join(root, "spend-%s.json" % datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")),
                       {"design": "smoke" if smoke else a.design, "cap": budget.cap,
                        "spent": budget.spent - before, "calls": budget.calls})
            print("spent $%.4f over %d calls ($%.5f a call; total $%.4f of the $%.2f cap)"
                  % (budget.spent - before, budget.calls, (budget.spent - before) / max(1, budget.calls),
                     budget.spent, budget.cap))
    elif a.cmd == "packets":
        os.makedirs(os.path.join(judging_priv, "items"), exist_ok=True)
        os.makedirs(judging_pub, exist_ok=True)
        its = items(load_run(os.path.join(PRIVATE, "run")), gen1)
        for it in its:
            write_text(os.path.join(judging_priv, "items", it["item"] + ".txt"), it["text"])
        write_json(os.path.join(judging_pub, "key.json"), {it["item"]: {"target": it["target"], "arm": it["arm"]}
                                                          for it in its})
        print("wrote %d items" % len(its))
    elif a.cmd == "claude-prompt":
        if a.item:
            print(rejudge_prompt(a.item, judging_priv))
            return
        key = A.load(os.path.join(judging_pub, "key.json"))
        ids = sorted(key)
        if a.half:
            inside = set(sched2["half"][a.design])
            ids = [i for i in ids if key[i]["target"] in inside]
        print(J.claude_prompt(a.n, J.batches(ids)[a.n - 1], folder=judging_priv))
    elif a.cmd == "collect":
        key = A.load(os.path.join(judging_pub, "key.json"))
        replies, again = {}, {}
        for p in sorted(glob.glob(os.path.join(judging_priv, "claude-[0-9]*.json"))):
            replies.update(A.load(p))
        for p in sorted(glob.glob(os.path.join(judging_priv, "claude-rejudge-*.json"))):
            again.update(A.load(p))
        replies.update(again)                # a re-judged item replaces its batch answer
        texts = {}
        for i in key:
            with open(os.path.join(judging_priv, "items", i + ".txt"), encoding="utf-8") as f:
                texts[i] = f.read()
        mis = misfiled(texts, {k: as_dict(v) for k, v in replies.items()})
        vs = {k: J.parse(json.dumps(v) if isinstance(v, dict) else v) for k, v in sorted(replies.items()) if k not in mis}
        scope = "all"
        if a.half:
            inside = set(sched2["half"][a.design])
            vs = {k: v for k, v in vs.items() if key[k]["target"] in inside}
            scope = "half"
        write_json(os.path.join(judging_pub, "scores-claude.json"),
                   {"judge": "claude", "scope": scope, "unparsed": sorted(k for k, v in vs.items() if v is None),
                    "misfiled": mis, "rejudged": sorted(again),
                    "items": {k: v for k, v in vs.items() if v is not None}})
        print("claude: %d items (%s), %d unparsed, %d misfiled and left out %s, %d re-judged, %d of %d in the key" % (
            len(vs), scope, sum(v is None for v in vs.values()), len(mis), sorted(mis), len(again), len(vs), len(key)))
    elif a.cmd == "analyze":
        s = analyze(gen1, load_run(os.path.join(PRIVATE, "run")), sched2, judging_pub, DIR,
                    T.load_reference(T.REF_SHARE), a.design)
        print("H1 %d lore-only vs %d sham-only, p = %.4f; L4 %s" % (s["h1"]["lore_only"], s["h1"]["sham_only"],
                                                                   s["h1"]["p"], s["l4"]))


if __name__ == "__main__":
    main()
