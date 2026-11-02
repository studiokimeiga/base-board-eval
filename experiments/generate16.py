#!/usr/bin/env python3
"""Blind three-arm comparison: is the older, chantier config actually more coherent?

The reader's observation, which cuts against everything I've been optimising: the early
16-post gemma-only threads FEEL more coherent despite containing more repetition --

    yara   boars are for breakfast.
    nadia  boars are for breakfast, yara

-- and he's right that echoing is what people do on boards. Repeating someone's line
back at them is social glue. XTC works by excluding the most probable next token, so it
may be suppressing precisely that move, leaving a thread where everyone talks past
everyone while scoring better on every metric I built.

Three arms, same 23 openers, no injected text anywhere:

  A_old    solo gemma-4-E4B @ Q8_0, 16 posts, DRY(4, 256 window), NO XTC.
           The early configuration, minus the stems (those are retired).
  B_new    mixed cast, 32 posts, XTC t05/p50, DRY(2, whole context), forced OP returns
           and newcomer arrivals. The current recommendation.
  C_noxtc  exactly B with XTC switched off. Isolates XTC from everything else in B.

A vs B answers the reader's question about whole configurations. B vs C attributes any
difference to XTC specifically. Judged blind and paired on identical openers.
"""
import json, os, random, re, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server
from openers import ALL as OPENER_TEXTS, OPENERS as UNSEEDED

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
OUT = os.path.join(HERE, "threads.optag.json")

VOICES = {
    "gemma": dict(file="arm1b.gguf",  port=8171, label="gemma-4-E4B base [Q8_0]"),
    "olmo":  dict(file="olmo-q8.gguf", port=8172, label="Olmo-3-1025-7B [Q8_0]"),
    "qwen":  dict(file="qwen-q8.gguf", port=8173, label="Qwen3-4B-Base [Q8_0]"),
}
MIXED = ["gemma", "qwen", "olmo", "gemma", "olmo", "qwen", "gemma"]
SOLO  = ["gemma"] * 7

DRY_OLD = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=4, dry_penalty_last_n=256)
DRY_NEW = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=2, dry_penalty_last_n=8192)
XTC     = dict(xtc_threshold=0.05, xtc_probability=0.5)

# Does marking the OP in the document stop the protagonist drifting?
#
# Nothing currently tells the model who owns the premise. Post 1 is just the first post by
# some handle; thirty posts later that handle has no special status, and the situation gets
# adopted by whoever happens to be speaking. The thread loses the person you were meant to
# worry about, which is the difference between a Kisaragi-shaped thread and a muddle.
#
# Real imageboards mark it -- every post by the thread starter carries (OP). That is a
# format token, not injected prose, and it is native to the medium. Zero words added.
ARMS = [
    dict(name="no_tag", cast=MIXED, posts=32, extra=dict(DRY_NEW, **XTC), structure=True, optag=False),
    dict(name="op_tag", cast=MIXED, posts=32, extra=dict(DRY_NEW, **XTC), structure=True, optag=True),
]

OPENERS = [dict(t=x, seeded=(x not in UNSEEDED)) for x in OPENER_TEXTS]
POOL_SIZE = 7
OP_SHARE = 0.22
RETURN_AT = {7, 19, 31}
ARRIVE_AT = {13, 25}
BIG_GAP = (2 * 3600, 6 * 3600)

SAMPLING = {"temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "top_k": 0,
            "repeat_penalty": 1.0, "n_predict": 120}
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


def stamp(secs):
    t = 23 * 3600 + 14 * 60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (day, DAYS[(3 + (day - 30)) % 7],
                                             t // 3600, (t % 3600) // 60, t % 60)


def complete(port, prompt, stops, extra):
    body = dict(SAMPLING)
    body.update(extra)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True)
    req = urllib.request.Request("http://127.0.0.1:%d/completion" % port,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return json.load(r).get("content", "")
    except Exception:
        return ""


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


def gen(arm, oi, tid):
    """Append-only: no post regenerated, retried, edited or skipped."""
    rng = random.Random(31337 + oi)          # same scaffold for every arm
    pool = rng.sample(NAMES, POOL_SIZE)
    voice_of = {n: arm["cast"][i] for i, n in enumerate(pool)}
    stops = ["\n\n"] + ["\n" + h for h in pool]
    op = pool[0]
    text = OPENERS[oi]["t"]

    secs, author, seen = 0, op, {op}
    def hdr(who, secs):
        tag = " (OP)" if arm.get("optag") and who == op else ""
        return "%s%s %s" % (who, tag, stamp(secs))

    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": text, "voice": voice_of[op]}]
    doc = "/x/ — thread 4471\n\n%s\n%s" % (hdr(op, 0), text)

    for n in range(2, arm["posts"] + 1):
        secs += rng.randint(40, 9 * 60)
        if arm["structure"] and n in RETURN_AT:
            secs += rng.randint(*BIG_GAP)
            author = op
        elif arm["structure"] and n in ARRIVE_AT:
            unseen = [h for h in pool if h not in seen]
            author = rng.choice(unseen) if unseen else rng.choice([h for h in pool if h != author])
        elif rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])
        v = voice_of[author]
        prompt = doc + "\n\n%s\n" % hdr(author, secs)
        out = complete(VOICES[v]["port"], prompt, stops, arm["extra"])
        posts.append({"n": n, "who": author, "ts": stamp(secs), "text": out.strip(), "voice": v})
        seen.add(author)
        doc = prompt + out
        sys.stdout.write("." if n % 10 else str(n // 10)); sys.stdout.flush()

    return {"id": tid, "arm": arm["name"], "opener_index": oi,
            "seeded": OPENERS[oi]["seeded"], "participants": pool,
            "cast": voice_of, "posts": posts}


def main():
    procs = {}
    for k, v in VOICES.items():
        p = os.path.join(MODELS, v["file"])
        if not os.path.exists(p):
            print("missing %s" % v["file"]); return
        procs[k] = start_server(p, v["port"], cast=True)
        if not wait_ready(v["port"], procs[k]):
            print("failed to load %s" % k)
            for q in procs.values():
                q.kill()
            return
    print("three voices up. %d arms x %d openers" % (len(ARMS), len(OPENERS)), flush=True)

    threads, nq, tid = [], 0, 0
    for arm in ARMS:
        for oi in range(len(OPENERS)):
            tid += 1
            print("\n[%d/%d] %-8s op%-2d " % (tid, len(ARMS) * len(OPENERS), arm["name"], oi),
                  end="", flush=True)
            t = gen(arm, oi, tid)
            blob = " ".join(p["text"] for p in t["posts"]).lower()
            hits = [h for h in HARM if h in blob]
            if hits:
                nq += 1
                qd = os.path.join(HERE, "quarantine")
                os.makedirs(qd, exist_ok=True); os.chmod(qd, 0o700)
                qp = os.path.join(qd, "blind-%d-%s-op%d.json" % (tid, arm["name"], oi))
                with open(qp, "w") as f:
                    json.dump({"matched": hits, "thread": t}, f, indent=1)
                os.chmod(qp, 0o600)
                w = len(t["posts"]) - 1
                t = {k: t[k] for k in ("id", "arm", "opener_index", "seeded", "participants")}
                t.update(quarantined=True, posts=[{"n": 1, "who": "?", "ts": "-",
                                                   "text": "[%d posts withheld]" % w}])
                sys.stdout.write("[quarantined]")
            threads.append(t)
            with open(OUT, "w") as f:
                json.dump({"version": 16, "injected_text": "none", "isolates": "(OP) marker in the document",
                           "arms": {a["name"]: dict(posts=a["posts"], extra=a["extra"],
                                                    optag=a.get("optag", False)) for a in ARMS},
                           "openers": [o["t"] for o in OPENERS],
                           "quarantined": nq, "threads": threads}, f, indent=1)

    for p in procs.values():
        p.send_signal(signal.SIGTERM)
        try: p.wait(timeout=25)
        except Exception: p.kill()
    print("\n\ndone: %d threads, %d quarantined" % (len(threads), nq))


if __name__ == "__main__":
    main()

