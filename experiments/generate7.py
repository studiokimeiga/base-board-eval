#!/usr/bin/env python3
"""Long threads, mixed cast. Product prototype + natural experiment.

WHY MIXED: the paraphrase chorus -- six posters restating one idea in different
words -- is the tell that survived DRY, because the n-grams genuinely differ.
No sampler can fix it; every post conditions on the same short context and no
participant has persistent state. Different checkpoints DO have different
register, so the cast is the fix.

CAST (per participant, fixed for the whole thread)
  gemma-4-E4B base @ Q8_0  -- OP + 2 others. highest ceiling, carries a thread.
  Olmo-3-1025-7B @ Q8_0    -- 2 posters. never breaks, never surprises; makes the
                              board feel populated and gives the weird something
                              ordinary to be weird against.
  Qwen3-4B-Base @ Q8_0     -- 2 posters. the only arm that produced real hostility
                              and flat contradiction. the ones who pick fights.

WHY 50 POSTS: the phonebook thread sustained its premise for ~10 posts, which is
most of a 16-post thread. That was the format ceiling, not the model's limit.
Cache reuse means each post prefills ~24 new tokens, so 50 posts costs ~3x 16, not 10x.

WHY THESE 4 OPENERS: the only ones where the reader and I independently agreed a
thread was worth reposting.

THREE SERVERS AT ONCE, deliberately breaking the earlier one-at-a-time rule: a
mixed cast would otherwise need a model reload per post. ~20GB of weights on 64GB.
All three at Q8_0 so no voice is handicapped by quantisation -- the Q4_K_M of the
gemma base checkpoint was a confirmed broken file.

Per-post model attribution is stored. Which checkpoint produced the lines that get
flagged is the experiment hiding inside the prototype.
"""
import json, os, random, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
OUT = os.path.join(HERE, "threads.upd.json")

VOICES = {
    "gemma": dict(file="arm1b.gguf",  port=8094, label="gemma-4-E4B base [Q8_0]"),
    "olmo":  dict(file="olmo-q8.gguf", port=8095, label="Olmo-3-1025-7B [Q8_0]"),
    "qwen":  dict(file="qwen-q8.gguf", port=8096, label="Qwen3-4B-Base [Q8_0]"),
}
# slot 0 is OP
CAST = ["gemma", "qwen", "olmo", "gemma", "olmo", "qwen", "gemma"]

OPENERS = [
    dict(t="someone at work keeps taking my mug, washing it, and putting it back in a different cupboard",
         seeded=False, note="best flag rate in run5, 4/14"),
    dict(t="does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
         seeded=True),
    dict(t="my landlord says there is no apartment 12 in this building but my lease says 12 and my key works",
         seeded=True),
    dict(t="just got a text from my own number asking if i left the stove on",
         seeded=True, note="produced the phonebook thread"),
]

POSTS_PER_THREAD = 32
REPS = 6
POOL_SIZE = 7
OP_SHARE = 0.22

# The only new injection in this run, and the smallest one that can work. At these
# positions the OP is forced to post and its turn is seeded with one or two words.
# Nothing about WHAT develops is specified -- only that the poster is reporting rather
# than restating. The 50-post run showed the real problem was that no new information
# ever entered the document: the OP had one fact and every later post was commentary
# on it. Static at 16 posts is tolerable; at 50 it either loops or drifts into procedure.
UPDATE_AT = {7, 13, 19, 25, 31}
UPDATE_STEMS = ["update: ", "ok so "]

SAMPLING = {"temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "top_k": 0,
            "repeat_penalty": 1.0, "n_predict": 120}
# allowed_length 4 -> 2 and window 256 -> whole context. "i'm glad" is three tokens and
# slid through free before; 9 of 19 long threads collapsed into a chant. This will also
# suppress name-addressing, which is the price -- chants ruined half the corpus, names
# improved a handful of posts.
DRY = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=2, dry_penalty_last_n=8192)
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

# expanded after thread 29 slipped through: the run5 list covered self-harm phrasing
# only and had no coverage for slurs or violence toward others.
HARM = [
    "kill myself", "killing myself", "kill me", "want to die", "wanna die", "end my life",
    "end it all", "should die", "better off dead", "suicide", "hang myself", "hurt myself",
    "cut myself", "rather die",
    # violence toward others
    "kill you", "kill them", "kill him", "kill her", "kill everyone", "kill you all",
    "going to kill", "gonna kill", "murder you", "shoot you", "shoot up", "beat you to death",
    "get killed", "you will die", "i'll end you",
    # slurs
    "faggot", "fag ", "nigger", "nigga", "tranny", "kike", "spic", "chink", "retard",
    "wetback", "towelhead", "paki ", "dyke", "coon",
]

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NAMES = """marcus ines yusuf brenda kenji priya dmitri oona hakim lucia niall fatima gustav mei
teodor ruth emeka astrid javier noor calvin sanne tomas aisha erik rosa kwame liesel omar bridget
hiro valeria stefan nadia colm yara piotr greta samir delphine boris mira angus zainab luca hedda
tariq paloma finn sofia""".split()


def stamp(secs):
    t = 23*3600 + 14*60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (day, DAYS[(3+(day-30)) % 7],
                                             t//3600, (t % 3600)//60, t % 60)


def complete(port, prompt, stops):
    body = dict(SAMPLING); body.update(DRY)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True)
    req = urllib.request.Request("http://127.0.0.1:%d/completion" % port,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.load(r)
        return d.get("content", ""), d.get("stop_type", "?")
    except Exception as e:
        return "", "error"


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


def gen_thread(oi, rep, tid):
    """Append-only. Nothing regenerated, retried, edited or skipped."""
    rng = random.Random(70707 + oi*1000 + rep)
    pool = rng.sample(NAMES, POOL_SIZE)
    voice_of = {name: CAST[i] for i, name in enumerate(pool)}
    stops = ["\n\n"] + ["\n" + h for h in pool]
    op = pool[0]
    text = OPENERS[oi]["t"]

    secs, author = 0, op
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": text,
              "voice": voice_of[op], "model": VOICES[voice_of[op]]["label"], "stop": "-"}]
    doc = "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), text)

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(40, 9*60)
        seed = ""
        if n in UPDATE_AT:
            author = op
            seed = rng.choice(UPDATE_STEMS)
        elif rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])
        v = voice_of[author]
        prompt = doc + "\n\n%s %s\n%s" % (author, stamp(secs), seed)
        out, why = complete(VOICES[v]["port"], prompt, stops)
        posts.append({"n": n, "who": author, "ts": stamp(secs), "text": (seed + out).strip(),
                      "voice": v, "model": VOICES[v]["label"], "stop": why,
                      "seeded_update": bool(seed)})
        doc = prompt + out
        if n % 10 == 0:
            sys.stdout.write(str(n//10)); sys.stdout.flush()
        else:
            sys.stdout.write("."); sys.stdout.flush()

    return {"id": tid, "opener_index": oi, "rep": rep, "seeded": OPENERS[oi]["seeded"],
            "participants": pool, "cast": voice_of, "posts": posts}


def quarantine(t, tid, hits):
    qd = os.path.join(HERE, "quarantine")
    os.makedirs(qd, exist_ok=True); os.chmod(qd, 0o700)
    qp = os.path.join(qd, "long-thread-%d-op%d-rep%d.json" % (tid, t["opener_index"], t["rep"]))
    with open(qp, "w") as f:
        json.dump({"note": "auto-quarantined at generation", "matched": hits, "thread": t}, f, indent=1)
    os.chmod(qp, 0o600)
    w = len(t["posts"]) - 1
    stub = {k: t[k] for k in ("id", "opener_index", "rep", "seeded", "participants", "cast")}
    stub.update(quarantined=True, matched=hits, posts=[t["posts"][0],
        {"n": 2, "who": t["posts"][1]["who"], "ts": t["posts"][1]["ts"],
         "text": "[%d posts withheld - auto-quarantined]" % w}])
    return stub


def main():
    procs = {}
    for k, v in VOICES.items():
        p = os.path.join(MODELS, v["file"])
        if not os.path.exists(p):
            print("missing %s" % v["file"]); return
        print("loading %-6s %s" % (k, v["file"]), flush=True)
        procs[k] = start_server(p, v["port"], cast=True)
        if not wait_ready(v["port"], procs[k]):
            print("failed to load %s" % k)
            for q in procs.values():
                q.kill()
            return
    print("all three voices up", flush=True)

    jobs = [(oi, rep) for oi in range(len(OPENERS)) for rep in range(REPS)]
    print("%d threads x %d posts = %d completions" % (len(jobs), POSTS_PER_THREAD,
                                                      len(jobs)*(POSTS_PER_THREAD-1)), flush=True)
    threads, nq, tid = [], 0, 0
    for oi, rep in jobs:
        tid += 1
        print("\n[%d/%d] op%d rep%d " % (tid, len(jobs), oi, rep), end="", flush=True)
        t = gen_thread(oi, rep, tid)
        blob = " ".join(p["text"] for p in t["posts"]).lower()
        hits = [h for h in HARM if h in blob]
        if hits:
            nq += 1
            t = quarantine(t, tid, hits)
        threads.append(t)
        with open(OUT, "w") as f:
            json.dump({"version": 7, "update_at": sorted(UPDATE_AT), "cast": {k: v["label"] for k, v in VOICES.items()},
                       "cast_slots": CAST, "config": dict(SAMPLING, **DRY),
                       "posts_per_thread": POSTS_PER_THREAD, "openers": OPENERS,
                       "quarantined": nq, "threads": threads}, f, indent=1)

    for k, p in procs.items():
        p.send_signal(signal.SIGTERM)
        try: p.wait(timeout=25)
        except Exception: p.kill()
    print("\n\ndone: %d threads, %d quarantined" % (len(threads), nq))


if __name__ == "__main__":
    main()

