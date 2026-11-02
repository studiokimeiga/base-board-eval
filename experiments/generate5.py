#!/usr/bin/env python3
"""Volume run: base rate of interesting output from one unassisted base model.

Not a model comparison. One arm, one config, 14 openers, stratified by whether the
opener contains an unexplained detail. The question is how often something worth
reposting appears at all -- which no metric can answer, only reading.

Config, all validated on the 30-thread warm-up:
  gemma-4-E4B base @ Q8_0   (Q4_K_M of this checkpoint is a broken file)
  no stems, no name seeding, no stub thread -- nothing injected but the opener
  DRY 0.8 / base 1.75 / allowed_length 4 / penalty_last_n 256
      short window: kills local loops, leaves thread-wide name reuse visible,
      so addressing-by-name survives (1.6 mentions/thread unseeded in warm-up)
  ASCII grammar, min_p .05, temp 1.0, 120 max tokens, stop on "\n\n" + handles

Replicates are unequal ON PURPOSE. 9 seeded openers x 8 and 5 unseeded x 14
balances the two STRATA (72 vs 70) rather than the openers. Per-opener rates are
not resolvable at this volume regardless, so equal per-opener n buys nothing.

Quarantine routes at generation time. Crude, recall-oriented, deliberately
asymmetric: a false positive costs one thread, a miss costs shipping the content.
"""
import json, os, random, re, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
PORT = 8088
URL = f"http://127.0.0.1:{PORT}"
OUT = os.path.join(HERE, "threads.run5.json")

ARM = ("arm1b.gguf", "gemma-4-E4B base [Q8_0]")

# seeded  = contains an unexplained detail (a boring explanation is still available)
# author  = who wrote it. kept in the data because it is a real variable.
OPENERS = [
    # ---- seeded (9) x 8 replicates ----
    dict(t="does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
         seeded=True,  axis="institutional", author="assistant", note="original"),
    dict(t="im on the 11:40 bus and we have passed the same gas station three times, driver isnt answering me",
         seeded=True,  axis="institutional", author="assistant"),
    dict(t="the woman in 4B has had her washing machine running since friday and i can hear it through the floor right now",
         seeded=True,  axis="domestic",      author="assistant"),
    dict(t="my landlord says there is no apartment 12 in this building but my lease says 12 and my key works",
         seeded=True,  axis="institutional", author="assistant", note="both quarantine events to date"),
    dict(t="just got a text from my own number asking if i left the stove on",
         seeded=True,  axis="domestic",      author="assistant", note="produced the phonebook thread"),
    dict(t="hr has me down as starting in 2019 and i started in 2021 and they've corrected it twice now",
         seeded=True,  axis="institutional", author="haki"),
    dict(t="there are two suite 300s on the building directory and the mail gets split between them",
         seeded=True,  axis="institutional", author="haki"),
    dict(t="the previous tenant still gets a magazine here and i've been forwarding it for two years",
         seeded=True,  axis="domestic",      author="haki"),
    dict(t="my electricity bill has been the same to the cent for five months",
         seeded=True,  axis="domestic",      author="haki", note="numeric probe - track separately"),
    # ---- unseeded (5) x 14 replicates ----
    dict(t="my roommate has started labelling things in the fridge and i don't know how to bring it up",
         seeded=False, axis="domestic",      author="assistant", note="original"),
    dict(t="the guy who sits behind me has started answering questions that people asked me",
         seeded=False, axis="institutional", author="assistant"),
    dict(t="someone at work keeps taking my mug, washing it, and putting it back in a different cupboard",
         seeded=False, axis="institutional", author="assistant"),
    dict(t="my neighbour has started saying good morning in a way i'm fairly sure is sarcastic",
         seeded=False, axis="domestic",      author="assistant"),
    dict(t="i've been pretending to like a podcast my girlfriend recommended since february",
         seeded=False, axis="domestic",      author="assistant"),
]

REPS_SEEDED, REPS_UNSEEDED = 8, 14

HARM = ["kill myself", "killing myself", "kill me", "want to die", "wanna die",
        "end my life", "end it all", "should die", "better off dead", "suicide",
        "hang myself", "hurt myself", "cut myself", "rather die"]

SAMPLING = {"temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "top_k": 0,
            "repeat_penalty": 1.0, "n_predict": 120}
DRY = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=4, dry_penalty_last_n=256)
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

POSTS_PER_THREAD = 16
POOL_SIZE = 7
OP_SHARE = 0.30
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


def complete(prompt, stops):
    body = dict(SAMPLING)
    body.update(DRY)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True)
    req = urllib.request.Request(URL + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        return d.get("content", ""), d.get("stop_type", "?")
    except Exception:
        return "", "error"


def wait_ready(proc, limit=300):
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


def gen_thread(oi, rep, tid):
    """Append-only. Nothing regenerated, retried, edited or skipped."""
    rng = random.Random(90210 + oi*1000 + rep)
    pool = rng.sample(NAMES, POOL_SIZE)
    stops = ["\n\n"] + ["\n" + h for h in pool]
    op = pool[0]
    text = OPENERS[oi]["t"]

    secs, author = 0, op
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": text, "stop": "-"}]
    doc = "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), text)

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(40, 12*60)
        if rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])
        prompt = doc + "\n\n%s %s\n" % (author, stamp(secs))
        out, why = complete(prompt, stops)
        posts.append({"n": n, "who": author, "ts": stamp(secs),
                      "text": out.strip(), "stop": why})
        doc = prompt + out
        sys.stdout.write("."); sys.stdout.flush()

    o = OPENERS[oi]
    return {"id": tid, "opener_index": oi, "rep": rep, "seeded": o["seeded"],
            "axis": o["axis"], "opener_author": o["author"],
            "participants": pool, "posts": posts}


def quarantine(t, tid):
    qd = os.path.join(HERE, "quarantine")
    os.makedirs(qd, exist_ok=True); os.chmod(qd, 0o700)
    qp = os.path.join(qd, "run5-thread-%d-op%d-rep%d.json" % (tid, t["opener_index"], t["rep"]))
    with open(qp, "w") as f:
        json.dump({"note": "auto-quarantined at generation time", "thread": t}, f, indent=1)
    os.chmod(qp, 0o600)
    w = len(t["posts"]) - 1
    stub = {k: t[k] for k in ("id", "opener_index", "rep", "seeded", "axis",
                              "opener_author", "participants")}
    stub.update(quarantined=True, posts=[t["posts"][0],
        {"n": 2, "who": t["posts"][1]["who"], "ts": t["posts"][1]["ts"],
         "text": "[%d posts withheld - auto-quarantined]" % w}])
    return stub


def main():
    path = os.path.join(MODELS, ARM[0])
    if not os.path.exists(path):
        print("missing %s" % ARM[0]); return
    jobs = [(oi, rep) for oi, o in enumerate(OPENERS)
            for rep in range(REPS_SEEDED if o["seeded"] else REPS_UNSEEDED)]
    ns = sum(1 for oi, _ in jobs if OPENERS[oi]["seeded"])
    print("%d threads: %d seeded / %d unseeded, %d openers, ~%d posts"
          % (len(jobs), ns, len(jobs)-ns, len(OPENERS), len(jobs)*(POSTS_PER_THREAD-1)),
          flush=True)

    proc = start_server(path, PORT)
    if not wait_ready(proc):
        print("failed to load"); return

    threads, nq, tid = [], 0, 0
    for oi, rep in jobs:
        tid += 1
        t = gen_thread(oi, rep, tid)
        t["model"] = ARM[1]
        blob = " ".join(p["text"] for p in t["posts"]).lower()
        if any(h in blob for h in HARM):
            nq += 1
            t = quarantine(t, tid)
            t["model"] = ARM[1]
        threads.append(t)
        with open(OUT, "w") as f:
            json.dump({"version": 5, "model": ARM[1], "config": dict(SAMPLING, **DRY),
                       "openers": OPENERS, "quarantined": nq, "threads": threads}, f, indent=1)
        if tid % 10 == 0:
            print(" [%d/%d, %d quarantined]" % (tid, len(jobs), nq), flush=True)

    proc.send_signal(signal.SIGTERM)
    try: proc.wait(timeout=25)
    except Exception: proc.kill()
    print("\ndone: %d threads, %d quarantined (%.1f%%)"
          % (len(threads), nq, 100*nq/len(threads)))


if __name__ == "__main__":
    main()
