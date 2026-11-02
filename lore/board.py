#!/usr/bin/env python3
"""The memory-on/off boards of PREREGISTRATION.md, written by Gemini 3.8 Flash through OpenRouter.

  python lore/board.py schedule             write lore/schedule.json (public: no model output)
  python lore/board.py dry                  print one page of each arm and the cost estimate; no calls
  python lore/board.py smoke                the pre-registered smoke test, kept out of the analysis
  python lore/board.py run [--design full|one|x] [--cap 20] [--workers 12]

Raw threads go to lore/private/ (gitignored) one file per thread, so a run can resume; `python
lore/board.py manifest` hashes them into lore/MANIFEST.sha256. The OpenRouter key comes from the file
named by LORE_ENV, else the repo's .env, and is never printed.

Everything a thread's scaffold needs (opener, cast, authors, timestamps, thread number) comes from
the seeded schedule and never from model output, so a target's memory and no-memory versions differ
only in whether the page shows its source.
"""
import argparse, datetime, hashlib, json, os, random, sys, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "spike"))
import generate as G
from openers import ALL as OPENERS
from live_board import GATE
import round3 as R            # post_json, retrying, clean_chat, cut: the bake-off's own call helpers

SEED = 20261102
POSTS = 24
CAST = 7
FIRST_SOURCE, FIRST_TARGET = 4471, 4494
MODEL = "google/gemini-3.8-flash"
PRICE_IN, PRICE_OUT = 0.825e-6, 4.125e-6      # $/token, OpenRouter listing checked 2026-11-02
BOARDS = {"x": "/x/", "misc": "/misc/"}
ASK = ("Here is a page from an imageboard:\n\n%s\n\n"
       "Write the next post in the last thread on the page, by %s. Reply with only the text of the post.")
PRIVATE = os.path.join(HERE, "private")

ORIGIN = datetime.datetime(2026, 10, 26, 9, 0, 0)    # a Monday; sources start here
TARGETS_AFTER = 3 * 86400                           # targets start the Thursday after
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GAP, BURST_GAP, AWAY_GAP = (40, 9 * 60), (5, 40), (2 * 3600, 6 * 3600)
ARRIVE_FROM = 13

# Topic tags per opener (openers.ALL order). A target never shares a tag with its source, so any
# carry-over crosses topics, as in generate17.py's design. "family" covers family and friends.
TAGS = {0: ("work", "kitchen"), 1: ("home", "kitchen"), 2: ("work", "identity"),
        3: ("home", "neighbour"), 4: ("family",), 5: ("work", "messaging"), 6: ("work",),
        7: ("public", "names"), 8: ("public",), 9: ("work", "messaging"), 10: ("home", "kitchen"),
        11: ("home", "neighbour"), 12: ("home", "kitchen"), 13: ("home", "identity", "messaging"),
        14: ("home", "neighbour"), 15: ("public",), 16: ("family", "messaging"),
        17: ("family", "messaging"), 18: ("family", "messaging", "names"), 19: ("family", "names"),
        20: ("public", "names"), 21: ("public", "neighbour"), 22: ("phone", "messaging", "identity")}


# ---- the schedule ----
def _match(rng, ok, forbid):
    """A random perfect matching source -> target over `ok`, avoiding forbid[s]; None if stuck."""
    order = list(ok)
    rng.shuffle(order)
    used, out = set(), {}

    def place(i):
        if i == len(order):
            return True
        s = order[i]
        cands = [t for t in ok[s] if t not in used and t != forbid.get(s)]
        rng.shuffle(cands)
        for t in cands:
            used.add(t)
            out[s] = t
            if place(i + 1):
                return True
            used.discard(t)
        return False
    return out if place(0) else None


def pairing(rng):
    ok = {s: [t for t in range(len(OPENERS)) if not set(TAGS[s]) & set(TAGS[t])]
          for s in range(len(OPENERS))}
    while True:
        d1 = _match(rng, ok, {})
        d2 = d1 and _match(rng, ok, d1)
        if d2:
            return d1, d2


def scaffold(rng, cast, pattern, n=POSTS):
    """Authors, seconds from the thread's start, and a flag per post. The OP is cast[0]; cast[-1]
    is held back to arrive at the first free post from ARRIVE_FROM."""
    op, late = cast[0], cast[-1]
    forced = {}
    if pattern == "away":
        for r in (rng.randint(6, 9), rng.randint(16, 20)):
            forced[r] = "returned"
    elif pattern == "burst":
        for lo, hi in ((3, 6), (11, 16)):
            b, k = rng.randint(lo, hi), rng.randint(2, 3)
            for j in range(k):
                forced[b + j] = "burst"
    authors, times, flags = [op], [0], [""]
    t, last, arrived = 0, op, False
    for m in range(2, n + 1):
        kind = forced.get(m, "")
        if kind:
            author = op
            gap = (rng.randint(*AWAY_GAP) if kind == "returned"
                   else rng.randint(*BURST_GAP) if forced.get(m - 1) == "burst" else rng.randint(*GAP))
        else:
            gap = rng.randint(*GAP)
            if m >= ARRIVE_FROM and not arrived:
                author, kind, arrived = late, "arrived", True
            elif (pattern == "away" and last != op and m + 1 not in forced
                  and rng.random() < G.OP_SHARE):
                author = op
            else:
                author = rng.choice([h for h in cast[1:] if h != last and (arrived or h != late)])
        t += gap
        authors.append(author)
        times.append(t)
        flags.append(kind)
        last = author
    return authors, times, flags


def _balanced(rng, counts):
    out = [p for p, k in counts for _ in range(k)]
    rng.shuffle(out)
    return out


def schedule(seed=SEED):
    rng = random.Random("%d:schedule" % seed)
    d1, d2 = pairing(rng)
    order = list(range(len(OPENERS)))
    rng.shuffle(order)
    patterns = _balanced(rng, [("away", 8), ("burst", 8), ("gone", 7)])
    sources, by_opener = [], {}
    for k, o in enumerate(order):
        r = random.Random("%d:source:%d" % (seed, o))
        cast = r.sample(G.NAMES, CAST)
        authors, times, flags = scaffold(r, cast, patterns[k])
        s = {"id": "s%02d" % k, "role": "source", "opener": o, "no": FIRST_SOURCE + k,
             "pattern": patterns[k], "cast": cast, "authors": authors, "times": times,
             "flags": flags, "start": k * 2400 + r.randint(0, 1200)}
        sources.append(s)
        by_opener[o] = s
    pairs = [(o, d[o]) for o in range(len(OPENERS)) for d in (d1, d2)]
    rng.shuffle(pairs)
    patterns = _balanced(rng, [("away", 16), ("burst", 15), ("gone", 15)])
    targets = []
    for k, (so, to) in enumerate(pairs):
        r = random.Random("%d:target:%d:%d" % (seed, so, to))
        src = by_opener[so]
        cast = r.sample([h for h in G.NAMES if h not in src["cast"]], CAST)
        authors, times, flags = scaffold(r, cast, patterns[k])
        targets.append({"id": "t%02d" % k, "role": "target", "source": src["id"], "opener": to,
                        "no": FIRST_TARGET + k, "pattern": patterns[k], "cast": cast,
                        "authors": authors, "times": times, "flags": flags,
                        "start": TARGETS_AFTER + k * 1200 + r.randint(0, 600),
                        "second": d2[so] == to})
    return {"seed": seed, "posts": POSTS, "tags": TAGS, "sources": sources, "targets": targets}


# ---- pages ----
def stamp(seconds):
    d = ORIGIN + datetime.timedelta(seconds=seconds)
    return "%02d/%02d/%02d(%s)%02d:%02d:%02d" % (d.month, d.day, d.year % 100, DAYS[d.weekday()],
                                                 d.hour, d.minute, d.second)


def render(board, no, posts):
    shown = [p for p in posts if p.get("text") and not p.get("withheld")]
    return "%s — thread %d\n\n%s" % (board, no, "\n\n".join("%s %s\n%s" % (p["who"], p["ts"], p["text"])
                                                             for p in shown))


def page(board, no, posts, source=None):
    """The target's page: on the memory board the whole source thread sits above it."""
    head = render(board, source["no"], source["posts"]) + "\n\n" if source else ""
    return head + render(board, no, posts)


def ask(page_text, author):
    return ASK % (page_text, author)


def stops(board, cast, source_cast):
    return ["\n\n", "\n" + board] + ["\n" + h for h in sorted(set(cast) | set(source_cast))]


def call_seed(board, thread_id, n):
    """Gemini's seed is a signed 32-bit int (anything larger is HTTP 400), hence 31 bits."""
    return int(hashlib.sha256(("%s|%s|%d" % (board, thread_id, n)).encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


# ---- generation ----
class OverBudget(Exception):
    pass


class Budget:
    def __init__(self, cap):
        self.cap, self.spent, self.calls, self.lock = cap, 0.0, 0, threading.Lock()

    def check(self):
        with self.lock:
            if self.spent >= self.cap:
                raise OverBudget("spent $%.4f of the $%.2f cap" % (self.spent, self.cap))

    def add(self, usd):
        with self.lock:
            self.spent += usd
            self.calls += 1


def run_thread(spec, board, complete, source=None, arm="none", budget=None):
    """Append-only: one call per post, nothing regenerated. `source` is the target's source thread
    (both arms, for the stop list); only arm "memory" puts it on the page. A post that hits the gate
    is withheld before the next page is built and goes to the returned quarantine list."""
    shown = source if arm == "memory" else None
    stop_list = stops(board, spec["cast"], source["cast"] if source else [])
    t0 = spec["start"]
    posts = [{"n": 1, "who": spec["authors"][0], "ts": stamp(t0), "t": t0,
              "text": OPENERS[spec["opener"]], "stop": "-"}]
    quarantine, spent = [], 0.0
    for n in range(2, POSTS + 1):
        author, t = spec["authors"][n - 1], t0 + spec["times"][n - 1]
        seed = call_seed(board, spec["id"], n)
        if budget:
            budget.check()
        r = complete(ask(page(board, spec["no"], posts, shown), author), seed)
        if budget:
            budget.add(r["cost"])
        spent += r["cost"]
        text = R.cut(R.clean_chat(r["text"]), stop_list).strip()
        p = {"n": n, "who": author, "ts": stamp(t), "t": t, "text": text, "seed": seed,
             "cost": r["cost"], "provider": r.get("provider")}
        if spec["flags"][n - 1]:
            p[spec["flags"][n - 1]] = True
        hits = [h for h in GATE if h in text.lower()]
        if hits:
            quarantine.append({"thread": spec["id"], "arm": arm, "board": board, "matched": hits,
                               "post": dict(p)})
            p.update(text="[post withheld]", withheld=True, matched=len(hits))
        posts.append(p)
    return {"id": spec["id"], "role": spec["role"], "arm": arm if spec["role"] == "target" else None,
            "board": board, "no": spec["no"], "opener": spec["opener"], "pattern": spec["pattern"],
            "cast": spec["cast"], "source": spec.get("source"),
            "source_no": source["no"] if source else None, "model": MODEL, "ask": ASK,
            "stops": stop_list, "spend": spent, "posts": posts, "quarantine": quarantine}


def gemini(key):
    """The bake-off's plain-Gemini call (round3.gemini_arm), with the page instruction and a seed."""
    def complete(prompt, seed):
        body = {"model": MODEL, "max_tokens": 1200, "temperature": 1.0, "reasoning": {"effort": "low"},
                "usage": {"include": True}, "seed": seed,
                "messages": [{"role": "user", "content": prompt}]}
        def call():     # a malformed reply raises KeyError/IndexError inside, so it is retried too
            d = R.post_json("https://openrouter.ai/api/v1/chat/completions", key, body)
            return d, d["choices"][0]["message"].get("content") or ""
        d, text = R.retrying(call)
        usage = d.get("usage") or {}
        return {"text": text, "cost": usage.get("cost", 0) or 0, "provider": d.get("provider"),
                "usage": usage}
    return complete


def openrouter_key():
    path = os.environ.get("LORE_ENV") or os.path.join(ROOT, ".env")
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("OPENROUTER_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("no OPENROUTER_API_KEY in %s" % path)


# ---- the run ----
DESIGNS = {"full": (("x", "misc"), True), "one": (("x", "misc"), False), "x": (("x",), True)}


def jobs(sched, design):
    """Sources first; then targets with both arms and both boards interleaved, so any drift in the
    model or the provider lands on every arm alike."""
    boards, both = DESIGNS[design]
    first = [("source", b, s, None) for s in sched["sources"] for b in boards]
    second = [("target", b, t, arm) for t in sched["targets"] if both or not t["second"]
              for b in boards for arm in ("memory", "none")]
    return first, second


def path_of(root, board_key, spec, arm):
    return os.path.join(root, board_key, spec["id"] + ("-" + arm if arm else "") + ".json")


def _save(path, thread, qlog):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    q = thread.pop("quarantine")
    if q:
        with open(qlog, "a", encoding="utf-8") as f:
            for x in q:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(thread, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def run(sched, design, complete, budget, root, workers=12, log=print):
    first, second = jobs(sched, design)
    by_id = {s["id"]: s for s in sched["sources"]}
    qlog = os.path.join(root, "quarantine.jsonl")

    def one(job):
        role, b, spec, arm = job
        path = path_of(root, b, spec, arm)
        if os.path.exists(path):
            return "have " + os.path.basename(path)
        source = None
        if role == "target":
            with open(path_of(root, b, by_id[spec["source"]], None), encoding="utf-8") as f:
                source = json.load(f)
        th = run_thread(spec, BOARDS[b], complete, source=source, arm=arm or "none", budget=budget)
        _save(path, th, qlog)
        return "%s %s %s $%.4f (total $%.3f)" % (b, spec["id"], arm or "source", th["spend"], budget.spent)

    for phase in (first, second):
        with ThreadPoolExecutor(workers) as ex:
            futures = [ex.submit(one, j) for j in phase]
            for fut in as_completed(futures):
                log(fut.result())


def estimate(sched, design):
    """Cost from the listed prices: ~4 characters a token, posts as long as the bake-off's plain
    Gemini (131 characters), and the output plus reasoning tokens that its logged $0.0023 a post
    implies."""
    post_chars, header_chars, ask_chars = 131, 30, len(ASK % ("", "someone"))
    first, second = jobs(sched, design)
    calls = (len(first) + len(second)) * (POSTS - 1)
    thread_chars = lambda n: 80 + n * (post_chars + header_chars)
    avg_in = sum(thread_chars(n) for n in range(POSTS - 1)) / (POSTS - 1) + ask_chars
    out_tokens = (0.0023 - avg_in / 4 * PRICE_IN) / PRICE_OUT
    per_post = avg_in / 4 * PRICE_IN + out_tokens * PRICE_OUT
    memory_extra = thread_chars(POSTS) / 4 * PRICE_IN
    n_mem = sum(1 for j in second if j[3] == "memory") * (POSTS - 1)
    return {"calls": calls, "per_post": per_post, "memory_extra": memory_extra,
            "usd": calls * per_post + n_mem * memory_extra, "threads": len(first) + len(second)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["schedule", "dry", "smoke", "run", "manifest"])
    ap.add_argument("--design", default="full", choices=sorted(DESIGNS))
    ap.add_argument("--cap", type=float, default=20.0)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    sched = schedule()

    if a.cmd == "schedule":
        with open(os.path.join(HERE, "schedule.json"), "w", encoding="utf-8") as f:
            json.dump(sched, f, indent=1)
        print("wrote lore/schedule.json: %d sources, %d targets" % (len(sched["sources"]), len(sched["targets"])))
    elif a.cmd == "dry":
        t = sched["targets"][0]
        s = next(x for x in sched["sources"] if x["id"] == t["source"])
        fake_source = {"no": s["no"], "cast": s["cast"],
                       "posts": [{"who": h, "ts": stamp(s["start"] + x), "text": "<source post %d>" % (i + 1)}
                                 for i, (h, x) in enumerate(zip(s["authors"], s["times"]))]}
        opener = [{"who": t["authors"][0], "ts": stamp(t["start"]), "text": OPENERS[t["opener"]]}]
        for arm, src in (("memory", fake_source), ("none", None)):
            print("=" * 30, arm, "=" * 30)
            print(ask(page(BOARDS["x"], t["no"], opener, src), t["authors"][1]))
        for d in sorted(DESIGNS):
            e = estimate(sched, d)
            print("%-5s %3d threads, %d calls, ~$%.4f a post (+$%.4f with memory): ~$%.2f"
                  % (d, e["threads"], e["calls"], e["per_post"], e["memory_extra"], e["usd"]))
    elif a.cmd == "smoke":
        root = os.path.join(PRIVATE, "smoke")
        complete, budget = gemini(openrouter_key()), Budget(cap=1.0)
        t = sched["targets"][0]
        s = next(x for x in sched["sources"] if x["id"] == t["source"])
        prompt = ask(page(BOARDS["x"], s["no"], [{"who": s["authors"][0], "ts": stamp(s["start"]),
                                                    "text": OPENERS[s["opener"]]}]), s["authors"][1])
        seed = call_seed(BOARDS["x"], s["id"], 2)
        same = [complete(prompt, seed) for _ in range(2)]
        for r in same:
            budget.add(r["cost"])
        print("seed check: the same call twice %s" % ("matched" if same[0]["text"] == same[1]["text"] else "differed"))
        mini = dict(sched, sources=[s], targets=[t])
        run(mini, "x", complete, budget, root, workers=3)
        print("smoke spend $%.4f over %d calls: $%.5f a call" % (budget.spent, budget.calls, budget.spent / budget.calls))
        with open(os.path.join(root, "seed-check.json"), "w", encoding="utf-8") as f:
            json.dump({"seed": seed, "matched": same[0]["text"] == same[1]["text"],
                       "providers": [r["provider"] for r in same]}, f, indent=1)
    elif a.cmd == "run":
        root = os.path.join(PRIVATE, "run")
        budget = Budget(cap=a.cap)
        try:
            run(sched, a.design, gemini(openrouter_key()), budget, root, workers=a.workers)
        finally:
            with open(os.path.join(root, "spend-%s.json" % datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")),
                      "w", encoding="utf-8") as f:
                json.dump({"design": a.design, "cap": a.cap, "spent": budget.spent, "calls": budget.calls}, f)
            print("spent $%.4f over %d calls" % (budget.spent, budget.calls))
    elif a.cmd == "manifest":
        lines = []
        for dirpath, _, files in os.walk(PRIVATE):
            for name in sorted(files):
                full = os.path.join(dirpath, name)
                with open(full, "rb") as f:
                    lines.append("%s *%s" % (hashlib.sha256(f.read()).hexdigest(),
                                             os.path.relpath(full, HERE).replace(os.sep, "/")))
        with open(os.path.join(HERE, "MANIFEST.sha256"), "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(lines, key=lambda l: l.split("*", 1)[1])) + "\n")
        print("hashed %d private files into lore/MANIFEST.sha256" % len(lines))


if __name__ == "__main__":
    main()
