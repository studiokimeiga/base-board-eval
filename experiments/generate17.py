#!/usr/bin/env python3
"""Board memory: does a coinage survive contact with a fresh, unrelated thread?

The Samejima question. 鮫島事件 works because it is a BOARD-level fact, not a thread: a
referent that recurs in unrelated threads until it feels like received knowledge rather
than a bit someone just invented. Thirty-two posts in isolation cannot produce that.

So give the document a past. Above the new thread sits a real, closed, earlier thread from
this project's own corpus -- model output, not my prose, so nothing authored is added. Each
prior carries a coinage the models invented themselves:

    "l car"            a fictional class of subway carriage, discussed with etiquette rules
    "the phone thing"  a folk ritual involving calling a number that changes
    "physical number"  the phonebook that is in your head
    "mug-washer"       an occupation, tipped

Each is paired with a new opener on an UNRELATED topic, so any recurrence is genuine
cross-topic carryover rather than the model just staying on subject.

  A_none    no prior thread. the current config.
  B_coined  one real prior thread above, containing a coinage.
  C_plain   one real prior thread above with no coinage -- controls for the mere presence
            of a preceding thread, which is a format change on its own.

Measured: does the coinage appear in the new thread, and when it does, is it EXPLAINED or
WITHHELD? Explanation is the move that makes our threads legible; withholding is the move
that makes Samejima eerie. They are opposites, and which one appears is the finding.
"""
import json, os, random, re, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
OUT = os.path.join(HERE, "threads.memory.json")

VOICES = {
    "gemma": dict(file="arm1b.gguf",  port=8181, label="gemma-4-E4B base [Q8_0]"),
    "olmo":  dict(file="olmo-q8.gguf", port=8182, label="Olmo-3-1025-7B [Q8_0]"),
    "qwen":  dict(file="qwen-q8.gguf", port=8183, label="Qwen3-4B-Base [Q8_0]"),
}
CAST = ["gemma", "qwen", "olmo", "gemma", "olmo", "qwen", "gemma"]

# coinage -> (detector, source file, selector). All four were invented by the models.
COINAGES = [
    ("l car",           r"\bl[- ]?cars?\b",  "threads.sweep.json",
     dict(arm="t05_p50", opener_index=1, rep=0)),
    ("the phone thing", r"phone thing",      "threads.xtc2.json", dict(id=16)),
    ("physical number", r"physical numbers?", "threads.json",
     dict(model="gemma-4-E4B base [Q8_0 diagnostic]", opener_index=5)),
    ("mug-washer",      r"mug[- ]?wash",     "threads.run5.json", dict(id=110)),
]
# a prior thread with nothing quotable in it, for the C_plain control
PLAIN = ("threads.blind.json", dict(arm="A_old", opener_index=11))

# new openers, deliberately unrelated to every coinage's subject
NEW_OPENERS = [
    "my flatmate has started buying the exact brand of yoghurt i buy",
    "my sister has started sending me links with no message attached",
    "the barista has written a different name on my cup three times this week",
    "my friend has started saying my name at the end of every sentence",
    "someone at work leaves every meeting five minutes early and nobody has ever mentioned it",
    "my dad has started forwarding me his own emails",
    "my upstairs neighbour vacuums at the same time every night and i've started waiting for it",
    "our group chat renamed itself and nobody will say who did it",
]

PRIOR_POSTS = 10          # how much of the earlier thread to show
POSTS_PER_THREAD = 32
POOL_SIZE = 7
OP_SHARE = 0.22
RETURN_AT = {7, 19, 31}
ARRIVE_AT = {13, 25}
BIG_GAP = (2 * 3600, 6 * 3600)

SAMPLING = {"temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "top_k": 0,
            "repeat_penalty": 1.0, "n_predict": 120}
EXTRA = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=2, dry_penalty_last_n=8192,
             xtc_threshold=0.05, xtc_probability=0.5)
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

HARM = ["kill myself", "killing myself", "kill me", "want to die", "wanna die", "end my life",
        "end it all", "should die", "better off dead", "suicide", "hang myself", "hurt myself",
        "cut myself", "rather die", "kill you", "kill them", "kill him", "kill her",
        "kill everyone", "going to kill", "gonna kill", "murder you", "shoot you", "shoot up",
        "beat you to death", "you will die", "faggot", "fag ", "nigger", "nigga", "tranny",
        "kike", "spic", "chink", "retard", "wetback", "towelhead", "paki ", "dyke", "coon"]

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NAMES = """marcus ines yusuf brenda kenji priya dmitri oona hakim lucia niall fatima gustav mei
teodor ruth emeka astrid javier noor calvin sanne tomas aisha erik rosa kwame liesel omar bridget
hiro valeria stefan nadia colm yara piotr greta samir delphine boris mira angus zainab luca hedda
tariq paloma finn sofia""".split()


def stamp(secs, base_day=30, base=23 * 3600 + 14 * 60 + 2):
    t = base + secs
    day = base_day + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (day, DAYS[(3 + (day - 30)) % 7],
                                             t // 3600, (t % 3600) // 60, t % 60)


def fetch_thread(path, sel):
    d = json.load(open(os.path.join(HERE, path)))
    ts = d["threads"] if isinstance(d, dict) else d
    for t in ts:
        if all(t.get(k) == v for k, v in sel.items()):
            return t
    return None


def prior_block(t, number):
    """Render an earlier thread as a closed block above the new one. Model output only."""
    lines = ["/x/ — thread %d" % number, ""]
    who = set()
    for p in t["posts"][:PRIOR_POSTS]:
        if not p.get("text"):
            continue
        lines.append("%s %s" % (p["who"], p["ts"]))
        lines.append(p["text"])
        lines.append("")
        who.add(p["who"])
    return "\n".join(lines), who


def gen(arm, oi, prior, tid):
    """Append-only: nothing regenerated, retried, edited or skipped."""
    rng = random.Random(90909 + oi)                 # same scaffold across arms
    pool = rng.sample([n for n in NAMES], POOL_SIZE)
    voice_of = {n: CAST[i] for i, n in enumerate(pool)}
    op = pool[0]
    text = NEW_OPENERS[oi]

    head, prior_who = ("", set())
    if prior:
        head, prior_who = prior_block(prior["thread"], 4468)
        head += "\n"

    stops = ["\n\n"] + ["\n" + h for h in set(pool) | prior_who]
    secs, author, seen = 0, op, {op}
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": text, "voice": voice_of[op]}]
    doc = head + "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), text)

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(40, 9 * 60)
        if n in RETURN_AT:
            secs += rng.randint(*BIG_GAP); author = op
        elif n in ARRIVE_AT:
            unseen = [h for h in pool if h not in seen]
            author = rng.choice(unseen) if unseen else rng.choice([h for h in pool if h != author])
        elif rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])
        v = voice_of[author]
        prompt = doc + "\n\n%s %s\n" % (author, stamp(secs))
        body = dict(SAMPLING); body.update(EXTRA)
        body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True)
        req = urllib.request.Request("http://127.0.0.1:%d/completion" % VOICES[v]["port"],
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                out = json.load(r).get("content", "")
        except Exception:
            out = ""
        posts.append({"n": n, "who": author, "ts": stamp(secs), "text": out.strip(), "voice": v})
        seen.add(author)
        doc = prompt + out
        sys.stdout.write("." if n % 10 else str(n // 10)); sys.stdout.flush()

    return {"id": tid, "arm": arm, "opener_index": oi, "participants": pool, "cast": voice_of,
            "prior": (prior or {}).get("label"), "coinage": (prior or {}).get("coinage"),
            "detector": (prior or {}).get("rx"), "posts": posts}


def wait_ready(port, proc, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=2) as r:
                if json.load(r).get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    coined = []
    for name, rx, path, sel in COINAGES:
        t = fetch_thread(path, sel)
        if not t:
            print("missing coinage source: %s" % name); return
        coined.append(dict(label="coined:%s" % name, coinage=name, rx=rx, thread=t))
    pl = fetch_thread(*PLAIN)
    if not pl:
        print("missing plain prior"); return
    plain = dict(label="plain", coinage=None, rx=None, thread=pl)

    procs = {}
    for k, v in VOICES.items():
        p = os.path.join(MODELS, v["file"])
        procs[k] = start_server(p, v["port"], cast=True)
        if not wait_ready(v["port"], procs[k]):
            print("failed to load %s" % k)
            for q in procs.values(): q.kill()
            return

    jobs = ([("A_none", oi, None) for oi in range(len(NEW_OPENERS))]
            + [("B_coined", oi, coined[oi % len(coined)]) for oi in range(len(NEW_OPENERS))]
            + [("C_plain", oi, plain) for oi in range(len(NEW_OPENERS))])
    print("%d threads: %d openers x 3 arms" % (len(jobs), len(NEW_OPENERS)), flush=True)

    threads, nq, tid = [], 0, 0
    for arm, oi, prior in jobs:
        tid += 1
        print("\n[%d/%d] %-9s op%-2d %-18s " % (tid, len(jobs), arm, oi,
              (prior or {}).get("label", "-")), end="", flush=True)
        t = gen(arm, oi, prior, tid)
        blob = " ".join(p["text"] for p in t["posts"]).lower()
        hits = [h for h in HARM if h in blob]
        if hits:
            nq += 1
            qd = os.path.join(HERE, "quarantine"); os.makedirs(qd, exist_ok=True)
            os.chmod(qd, 0o700)
            qp = os.path.join(qd, "memory-%d-%s-op%d.json" % (tid, arm, oi))
            with open(qp, "w") as f:
                json.dump({"matched": hits, "thread": t}, f, indent=1)
            os.chmod(qp, 0o600)
            t = {k: t[k] for k in ("id", "arm", "opener_index", "prior", "coinage")}
            t.update(quarantined=True, posts=[{"n": 1, "who": "?", "ts": "-", "text": "[withheld]"}])
            sys.stdout.write("[quarantined]")
        threads.append(t)
        with open(OUT, "w") as f:
            json.dump({"version": 17, "injected_text": "none (priors are model output)",
                       "prior_posts_shown": PRIOR_POSTS,
                       "openers": NEW_OPENERS, "quarantined": nq, "threads": threads}, f, indent=1)

    for p in procs.values():
        p.send_signal(signal.SIGTERM)
        try: p.wait(timeout=25)
        except Exception: p.kill()
    print("\n\ndone: %d threads, %d quarantined" % (len(threads), nq))


if __name__ == "__main__":
    main()
