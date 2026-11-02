#!/usr/bin/env python3
"""Ablation: find the LOOSEST config that clears a drift gate.

Instrument: Mistral-7B-v0.3 base only -- the arm that half-collapsed, i.e. the
model already sitting at the failure boundary. Tuning on the mandatory gemma
pair would risk fitting the config to the result we want.

Format prior is supplied by a preceding, unrelated, COMPLETE stub thread that is
byte-identical for every arm and every opener. It demonstrates the board's
register -- lowercase, terse, correction, addressing by name -- and carries no
subject and no tone that could reach the thread under test.

The metrics below are FAILURE DETECTORS, not quality measures. Minimising them
converges on the most obedient config, which is the opposite of the goal. So each
has a declared pass threshold, fixed before the run, and the config we pick is
the LOOSEST one that clears every gate -- not the best-scoring one.
"""
import json, os, random, re, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
PORT = 8085
URL = f"http://127.0.0.1:{PORT}"

INSTRUMENT = ("arm4.gguf", "Mistral-7B-v0.3 base")

OPENERS = [
    "does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
    "my roommate has started labelling things in the fridge and i don't know how to bring it up",
    "im on the 11:40 bus and we have passed the same gas station three times, driver isnt answering me",
    "the woman in 4B has had her washing machine running since friday and i can hear it through the floor right now",
    "my landlord says there is no apartment 12 in this building but my lease says 12 and my key works",
    "just got a text from my own number asking if i left the stove on",
]

# constant across every arm, every opener, every config. subject: laptop chargers.
STUB_NAMES = ["erik", "nadia", "teodor"]
STUB = """/x/ — thread 4468

erik 07/30/26(Thu)21:02:11
anyone got the barrel size for the old thinkpad chargers, the yellow tip one

nadia 07/30/26(Thu)21:04:40
7.9 x 5.5 with the centre pin

erik 07/30/26(Thu)21:09:58
mine has no pin

nadia 07/30/26(Thu)21:11:23
then its the newer one, 4.5 x 3.0

teodor 07/30/26(Thu)21:20:05
nadia, thats the ultrabook barrel not the classic

nadia 07/30/26(Thu)21:26:48
no, the classic went square in 2012

erik 07/30/26(Thu)21:31:14
square is the docking one. ill just measure it

"""

CONFIGS = [
    {"tag": "NEW_stems", "dry": 0.0, "stub": False, "min_p": 0.05, "temp": 1.0, "old": False},
    {"tag": "OLD_stems", "dry": 0.0, "stub": False, "min_p": 0.05, "temp": 1.0, "old": True},
]
OLD_STEMS = ["you're", "no,", "post a", "which ", "that's just ", "source", "op is "]

# declared BEFORE the run. a config passes only if every gate passes.
GATES = {
    "wordlike":    (">=", 85),    # % of non-space chars that are inside real words
    "english":     (">=", 80),    # % of posts containing an English function word
    "digits":      ("<=", 8),     # % digit characters
    "code":        ("<=", 5),     # % code-punctuation characters
    "truncated":   ("<=", 25),    # % of completions that hit max_tokens instead of a stop
    "echo4":       ("<=", 15),    # % of a post's 4-grams already seen in earlier posts
    "dups":        ("<=", 1.0),   # mean verbatim duplicate posts per thread
}

FUNCTION_WORDS = set("""the a an and or but if then than that this these those is are was were be been
being have has had do does did not no yes it its i you he she they we me him her them my your his their
of in on at to for from with about into over after before between out up down off just so too very can
will would could should might must dont didnt cant im ive youre thats whats there here when where why
how what who which all any both each few more most other some such only own same as by dont""".split())

CODE_CHARS = set("{};=<>|\\/*#$^~`[]")

SAMPLING = {"top_p": 1.0, "top_k": 0, "repeat_penalty": 1.0, "n_predict": 120}
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

POSTS_PER_THREAD = 16
POOL_SIZE = 7
OP_SHARE = 0.30
STEMS = ["no,", "you're", "wait"]
SEED_AT = {6: "stem", 9: "name", 12: "stem"}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NAMES = [n for n in """marcus ines yusuf brenda kenji priya dmitri oona hakim lucia niall fatima gustav
mei ruth emeka astrid javier noor calvin sanne tomas aisha rosa kwame liesel omar bridget hiro valeria
stefan colm yara piotr greta samir delphine boris mira angus zainab luca hedda tariq paloma finn
sofia""".split() if n not in STUB_NAMES]


def stamp(secs):
    t = 23*3600 + 14*60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (day, DAYS[(3+(day-30)) % 7], t//3600, (t % 3600)//60, t % 60)


def complete(prompt, stops, cfg):
    body = dict(SAMPLING)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True,
                min_p=cfg["min_p"], temperature=cfg["temp"])
    if cfg["dry"]:
        body.update(dry_multiplier=cfg["dry"], dry_base=1.75,
                    dry_allowed_length=4, dry_penalty_last_n=2048)
    req = urllib.request.Request(URL + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
        return d.get("content", ""), d.get("stop_type", "?")
    except Exception:
        return "", "error"


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


def gen_thread(oi, cfg):
    rng = random.Random(90210 + oi)
    pool = rng.sample(NAMES, POOL_SIZE)
    stops = ["\n\n"] + ["\n" + h for h in pool + STUB_NAMES]
    op = pool[0]

    secs = 0
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": OPENERS[oi], "seeded": True, "stop": "-"}]
    doc = (STUB if cfg["stub"] else "") + "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), OPENERS[oi])
    seen = [op]
    author = op

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(40, 12*60)
        if rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])

        seed = ""
        if cfg.get("old"):
            if n % 3 == 0:
                others = [h for h in seen if h != author]
                if others and (n // 3) % 2 == 0:
                    seed = rng.choice(others) + ", "
                else:
                    seed = rng.choice(OLD_STEMS)
        else:
            kind = SEED_AT.get(n)
            if kind == "stem":
                seed = rng.choice(STEMS) + " "
            elif kind == "name":
                others = [h for h in seen if h != author]
                if others:
                    seed = rng.choice(others) + ", "

        prompt = doc + "\n\n%s %s\n%s" % (author, stamp(secs), seed)
        out, why = complete(prompt, stops, cfg)
        posts.append({"n": n, "who": author, "ts": stamp(secs),
                      "text": (seed + out).strip(), "seeded": False, "stop": why})
        if author not in seen:
            seen.append(author)
        doc = prompt + out
        sys.stdout.write("."); sys.stdout.flush()

    return {"opener_index": oi, "participants": pool, "posts": posts}


def measure(th):
    gen = [p for p in th["posts"] if not p["seeded"]]
    texts = [p["text"] for p in gen]
    txt = " ".join(texts)
    body = re.sub(r"\s", "", txt)
    if not body:
        return dict(wordlike=0, english=0, digits=100, code=100, truncated=100, echo4=100, dups=len(gen))

    words = re.findall(r"[A-Za-z']{2,}", txt)
    wordlike = 100 * sum(len(w) for w in words) / len(body)
    digits = 100 * sum(c.isdigit() for c in body) / len(body)
    code = 100 * sum(c in CODE_CHARS for c in body) / len(body)

    hit = sum(1 for t in texts
              if t and FUNCTION_WORDS & set(re.findall(r"[a-z']+", t.lower())))
    english = 100 * hit / len(texts)

    trunc = 100 * sum(1 for p in gen if p["stop"] == "limit") / len(gen)

    seen, echo = set(), []
    for t in texts:
        tk = re.findall(r"[a-z']+", t.lower())
        g = [tuple(tk[i:i+4]) for i in range(max(0, len(tk)-3))]
        if g:
            echo.append(100 * sum(1 for x in g if x in seen) / len(g))
        seen.update(g)
    echo4 = sum(echo)/len(echo) if echo else 0

    norm = [re.sub(r"[^a-z ]", "", t.lower()).strip() for t in texts]
    dups = sum(1 for i, a in enumerate(norm) if a and a in norm[:i])

    return dict(wordlike=wordlike, english=english, digits=digits, code=code,
                truncated=trunc, echo4=echo4, dups=dups)


def passes(m):
    bad = []
    for k, (op, thr) in GATES.items():
        v = m[k]
        if (op == ">=" and v < thr) or (op == "<=" and v > thr):
            bad.append(k)
    return bad


def main():
    path = os.path.join(MODELS, INSTRUMENT[0])
    if not os.path.exists(path):
        print("instrument missing"); return
    print("gates (declared before run):")
    for k, (op, thr) in GATES.items():
        print("   %-10s %s %s" % (k, op, thr))
    proc = start_server(path, PORT)
    if not wait_ready(proc):
        print("failed to load"); return

    out, rows = [], []
    for cfg in CONFIGS:
        print("\n%s " % cfg["tag"], end="", flush=True)
        ms = []
        for oi in range(len(OPENERS)):
            th = gen_thread(oi, cfg)
            th.update(model=INSTRUMENT[1], config=cfg["tag"])
            out.append(th)
            ms.append(measure(th))
            with open(os.path.join(HERE, "ablation3.json"), "w") as f:
                json.dump({"gates": GATES, "threads": out}, f, indent=1)
        avg = {k: sum(m[k] for m in ms)/len(ms) for k in ms[0]}
        rows.append((cfg, avg))

    proc.send_signal(signal.SIGTERM)
    try: proc.wait(timeout=25)
    except Exception: proc.kill()

    hdr = ("config", "wordlike", "english", "digits", "code", "trunc", "echo4", "dups", "verdict")
    print("\n\n%-18s %8s %7s %6s %5s %6s %6s %5s  %s" % hdr)
    winner = None
    for cfg, m in rows:
        bad = passes(m)
        verdict = "PASS" if not bad else "fail: " + ",".join(bad)
        if not bad and winner is None:
            winner = cfg["tag"]
        print("%-18s %7.0f%% %6.0f%% %5.1f%% %4.1f%% %5.0f%% %5.1f%% %5.1f  %s" % (
            cfg["tag"], m["wordlike"], m["english"], m["digits"], m["code"],
            m["truncated"], m["echo4"], m["dups"], verdict))
    print("\nloosest passing config: %s" % (winner or "NONE -- every config failed the gate"))


if __name__ == "__main__":
    main()

