#!/usr/bin/env python3
"""Blind base-model board comparison, v3.

Changes from v2:
  - 6 openers x 6 threads per arm (was 2), so per-model means aren't n=2 noise
  - steering cut from 5 seeds per thread to 3, and the derailing stems are gone
    ("which ", "post a", "op is", "source", "that's just" all forced the same
     clarifying-question shape into every arm)
  - openers are live, first-person, present-tense, each with one unexplained
    detail that also has a boring explanation available
  - OP is weighted to post more often, and timestamp gaps are shorter, so the
    document reads as an in-progress thread rather than a slow Q&A
  - arm1b: same base checkpoint as arm1 at Q8_0 from a different quantizer,
    to test whether arm1's collapse is the model or the file
"""
import json, os, random, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
PORT = 8087
URL = f"http://127.0.0.1:{PORT}"

ARMS = [("arm1b.gguf", "gemma-4-E4B base [Q8_0]")]
REPLICATES = 5           # threads per opener
OUT = os.path.join(HERE, "threads.warmup.json")

# crude, recall-oriented, transparent. routes to quarantine/ at generation time.
# a false positive costs one thread; a miss costs shipping the content.
HARM = ["kill myself", "killing myself", "kill me", "want to die", "wanna die",
        "end my life", "end it all", "should die", "better off dead", "suicide",
        "hang myself", "hurt myself", "cut myself"]

# 0-1 are the v1/v2 controls, kept so this run is comparable to the last.
# 2-5 are new: mundane register, one unexplained detail, boring explanation available.
OPENERS = [
    "does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
    "my roommate has started labelling things in the fridge and i don't know how to bring it up",
    "im on the 11:40 bus and we have passed the same gas station three times, driver isnt answering me",
    "the woman in 4B has had her washing machine running since friday and i can hear it through the floor right now",
    "my landlord says there is no apartment 12 in this building but my lease says 12 and my key works",
    "just got a text from my own number asking if i left the stove on",
]

# only sentence openings, and only three per thread
STEMS = ["no,", "you're", "wait"]
SEED_AT = {}

SAMPLING = {
    "temperature": 1.0,
    "min_p": 0.05,
    "top_p": 1.0,
    "top_k": 0,
    "repeat_penalty": 1.0,
    "n_predict": 120,
}

GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

POSTS_PER_THREAD = 16
POOL_SIZE = 7
OP_SHARE = 0.30
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

NAMES = [
    "marcus", "ines", "yusuf", "brenda", "kenji", "priya", "dmitri", "oona", "hakim",
    "lucia", "niall", "fatima", "gustav", "mei", "teodor", "ruth", "emeka", "astrid",
    "javier", "noor", "calvin", "sanne", "tomas", "aisha", "erik", "rosa", "kwame",
    "liesel", "omar", "bridget", "hiro", "valeria", "stefan", "nadia", "colm", "yara",
    "piotr", "greta", "samir", "delphine", "boris", "mira", "angus", "zainab", "luca",
    "hedda", "tariq", "paloma", "finn", "sofia",
]


def stamp(secs):
    t = 23 * 3600 + 14 * 60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (
        day, DAYS[(3 + (day - 30)) % 7], t // 3600, (t % 3600) // 60, t % 60)


def complete(prompt, stops):
    body = dict(SAMPLING)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True,
                dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=4,
                dry_penalty_last_n=256)
    req = urllib.request.Request(
        URL + "/completion", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r).get("content", "")
    except Exception:
        return ""


def wait_ready(proc, limit=240):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(URL + "/health", timeout=2) as r:
                if json.load(r).get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def gen_thread(opener_index, tid, rep=0):
    """Append-only. Nothing is regenerated, retried, edited, or skipped."""
    rng = random.Random(90210 + opener_index * 1000 + rep)
    pool = rng.sample(NAMES, POOL_SIZE)
    stops = ["\n\n"] + ["\n" + h for h in pool]

    op = pool[0]
    secs = 0
    author = op
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": OPENERS[opener_index]}]
    seen = [op]
    doc = "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), OPENERS[opener_index])

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(40, 12 * 60)
        if rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])

        seed = ""
        kind = SEED_AT.get(n)
        if kind == "stem":
            seed = rng.choice(STEMS) + " "
        elif kind == "name":
            others = [h for h in seen if h != author]
            if others:
                seed = rng.choice(others) + ", "

        prompt = doc + "\n\n%s %s\n%s" % (author, stamp(secs), seed)
        out = complete(prompt, stops)
        posts.append({"n": n, "who": author, "ts": stamp(secs), "text": (seed + out).strip()})
        if author not in seen:
            seen.append(author)
        doc = prompt + out
        sys.stdout.write("."); sys.stdout.flush()

    return {"id": tid, "opener_index": opener_index, "rep": rep,
            "participants": pool, "posts": posts}


def main():
    out_path = os.path.join(HERE, OUT)
    threads = []
    tid = 0
    for i, (fname, model) in enumerate(ARMS, 1):
        path = os.path.join(MODELS, fname)
        if not os.path.exists(path):
            print("[arm %d] %s missing, cut" % (i, fname), flush=True)
            continue
        print("\n[arm %d/%d] loading" % (i, len(ARMS)), flush=True)
        proc = start_server(path, PORT)
        if not wait_ready(proc):
            print("[arm %d] failed to load, skipping" % i, flush=True)
            try: proc.kill()
            except Exception: pass
            continue
        nq = 0
        for oi in range(len(OPENERS)):
            for rep in range(REPLICATES):
                tid += 1
                t = gen_thread(oi, tid, rep)
                t["model"] = model
                blob = " ".join(p["text"] for p in t["posts"]).lower()
                if any(h in blob for h in HARM):
                    nq += 1
                    qd = os.path.join(HERE, "quarantine")
                    os.makedirs(qd, exist_ok=True); os.chmod(qd, 0o700)
                    qp = os.path.join(qd, "warmup-thread-%d-op%d.json" % (tid, oi))
                    with open(qp, "w") as f:
                        json.dump({"note": "auto-quarantined at generation", "thread": t}, f, indent=1)
                    os.chmod(qp, 0o600)
                    w = len(t["posts"]) - 1
                    t = {"id": t["id"], "model": model, "opener_index": oi, "rep": rep,
                         "participants": t["participants"], "quarantined": True,
                         "posts": [t["posts"][0],
                                   {"n": 2, "who": t["posts"][1]["who"], "ts": t["posts"][1]["ts"],
                                    "text": "[%d posts withheld - auto-quarantined]" % w}]}
                threads.append(t)
                with open(out_path, "w") as f:
                    json.dump({"version": 4, "quarantined": nq, "threads": threads}, f, indent=1)
        print("\n  quarantined %d of %d" % (nq, len(threads)), flush=True)
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=25)
        except Exception: proc.kill()
        print("\n[arm %d/%d] done (%d threads)" % (i, len(ARMS), len(threads)), flush=True)

    print("\nthreads written: %d" % len(threads))


if __name__ == "__main__":
    main()

