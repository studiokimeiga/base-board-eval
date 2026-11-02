#!/usr/bin/env python3
"""Ablation: what actually stops distribution drift at 4-7B?

Four configs, on the two most drift-prone arms, measured automatically.
No human reading required -- drift and repetition are machine-detectable.

  A  baseline            min_p .05, no DRY, 1-post scaffold   (reproduces run 3)
  B  + DRY               min_p .05, DRY,    1-post scaffold
  C  + thick scaffold    min_p .05, DRY,    4-post scaffold
  D  + tighter min_p     min_p .10, DRY,    4-post scaffold

Everything else is held fixed. Seed posts are authored by me and are therefore
a variable, not a neutral improvement -- that is the point of isolating C.
"""
import json, os, random, re, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
PORT = 8083
URL = f"http://127.0.0.1:{PORT}"

ARMS = [
    ("arm1b.gguf", "gemma-4-E4B base [Q8_0]"),
    ("arm4.gguf",  "Mistral-7B-v0.3 base"),
]

OPENERS = [
    "does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
    "my roommate has started labelling things in the fridge and i don't know how to bring it up",
    "im on the 11:40 bus and we have passed the same gas station three times, driver isnt answering me",
    "the woman in 4B has had her washing machine running since friday and i can hear it through the floor right now",
    "my landlord says there is no apartment 12 in this building but my lease says 12 and my key works",
    "just got a text from my own number asking if i left the stove on",
]

# 3 seed replies per opener, used only in the thick-scaffold configs.
# Deliberately flat and practical: no genre words, no tonal lean, no narrative beats.
# Slot 0 -> pool[1], slot 1 -> pool[2], slot 2 -> OP (pool[0]).
SEEDS = [
    ["signal problems at 59th all week", "it does that northbound too", "tracker said it was moving the whole time"],
    ["how long has he been doing it", "does he label your stuff or just his", "just his so far. started maybe a week ago"],
    ["is it the express, that one loops back past the depot", "screenshot the tracker",
     "tracker says on schedule. we just went past it again"],
    ["thin floors or is it loud loud", "could be the drum bearing, they run for hours like that",
     "loud enough that i can hear it stop and start"],
    ["check the lease against the deed, unit numbering gets redone", "is it 12 or 12A on the mailbox",
     "mailbox has no number at all. lease says 12"],
    ["thats spoofing, they do it with local numbers too", "did you leave the stove on though",
     "no. and my number isnt local, its an old area code"],
]

CONFIGS = [
    {"tag": "A_baseline",   "dry": 0.0, "thick": False, "min_p": 0.05},
    {"tag": "B_dry",        "dry": 0.8, "thick": False, "min_p": 0.05},
    {"tag": "C_scaffold",   "dry": 0.8, "thick": True,  "min_p": 0.05},
    {"tag": "D_minp",       "dry": 0.8, "thick": True,  "min_p": 0.10},
]

BASE_SAMPLING = {"temperature": 1.0, "top_p": 1.0, "top_k": 0,
                 "repeat_penalty": 1.0, "n_predict": 120}
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

POSTS_PER_THREAD = 16
POOL_SIZE = 7
OP_SHARE = 0.30
STEMS = ["no,", "you're", "wait"]
SEED_AT = {6: "stem", 9: "name", 12: "stem"}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NAMES = ["marcus","ines","yusuf","brenda","kenji","priya","dmitri","oona","hakim","lucia",
         "niall","fatima","gustav","mei","teodor","ruth","emeka","astrid","javier","noor",
         "calvin","sanne","tomas","aisha","erik","rosa","kwame","liesel","omar","bridget",
         "hiro","valeria","stefan","nadia","colm","yara","piotr","greta","samir","delphine",
         "boris","mira","angus","zainab","luca","hedda","tariq","paloma","finn","sofia"]


def stamp(secs):
    t = 23*3600 + 14*60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (day, DAYS[(3+(day-30))%7], t//3600, (t%3600)//60, t%60)


def complete(prompt, stops, cfg):
    body = dict(BASE_SAMPLING)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True,
                min_p=cfg["min_p"])
    if cfg["dry"]:
        body.update(dry_multiplier=cfg["dry"], dry_base=1.75,
                    dry_allowed_length=4, dry_penalty_last_n=2048)
    req = urllib.request.Request(URL + "/completion", data=json.dumps(body).encode(),
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


def gen_thread(oi, cfg):
    rng = random.Random(90210 + oi)
    pool = rng.sample(NAMES, POOL_SIZE)
    stops = ["\n\n"] + ["\n" + h for h in pool]
    op = pool[0]

    secs = 0
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": OPENERS[oi], "seeded": True}]
    doc = "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), OPENERS[oi])
    seen = [op]
    author = op

    # authored scaffold posts, if this config uses them
    if cfg["thick"]:
        for j, txt in enumerate(SEEDS[oi]):
            secs += rng.randint(40, 12*60)
            who = [pool[1], pool[2], op][j]
            posts.append({"n": len(posts)+1, "who": who, "ts": stamp(secs), "text": txt, "seeded": True})
            doc += "\n\n%s %s\n%s" % (who, stamp(secs), txt)
            if who not in seen:
                seen.append(who)
            author = who

    for n in range(len(posts)+1, POSTS_PER_THREAD+1):
        secs += rng.randint(40, 12*60)
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
        out = complete(prompt, stops, cfg)
        posts.append({"n": n, "who": author, "ts": stamp(secs),
                      "text": (seed + out).strip(), "seeded": False})
        if author not in seen:
            seen.append(author)
        doc = prompt + out
        sys.stdout.write("."); sys.stdout.flush()

    return {"opener_index": oi, "participants": pool, "posts": posts}


def metrics(th):
    gen = [p["text"] for p in th["posts"] if not p["seeded"]]
    txt = " ".join(gen)
    if not txt.strip():
        return {"wordlike": 0, "trigram_distinct": 0, "dup_posts": len(gen)}
    words = re.findall(r"[A-Za-z']{2,}", txt)
    alpha = sum(len(w) for w in words)
    total = len(re.sub(r"\s", "", txt)) or 1
    toks = re.findall(r"[a-z']+", txt.lower())
    tri = [tuple(toks[i:i+3]) for i in range(max(0, len(toks)-2))]
    distinct = len(set(tri)) / len(tri) if tri else 0
    norm = [re.sub(r"[^a-z ]", "", p.lower()).strip() for p in gen]
    dup = sum(1 for i, a in enumerate(norm) if a and a in norm[:i])
    return {"wordlike": round(100*alpha/total), "trigram_distinct": round(distinct, 3),
            "dup_posts": dup}


def main():
    out = []
    for fname, model in ARMS:
        path = os.path.join(MODELS, fname)
        if not os.path.exists(path):
            print("missing %s" % fname); continue
        print("\n=== loading %s ===" % fname, flush=True)
        proc = start_server(path, PORT)
        if not wait_ready(proc):
            print("failed to load %s" % fname)
            try: proc.kill()
            except Exception: pass
            continue
        for cfg in CONFIGS:
            print("\n  %s %s " % (model, cfg["tag"]), end="", flush=True)
            for oi in range(len(OPENERS)):
                th = gen_thread(oi, cfg)
                th.update(model=model, config=cfg["tag"], **{"cfg_" + k: v for k, v in cfg.items() if k != "tag"})
                out.append(th)
                with open(os.path.join(HERE, "ablation.json"), "w") as f:
                    json.dump({"threads": out}, f, indent=1)
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=25)
        except Exception: proc.kill()

    print("\n\n%-26s %-12s %9s %9s %9s" % ("model", "config", "wordlike", "tri-dist", "dup"))
    agg = {}
    for th in out:
        m = metrics(th)
        k = (th["model"], th["config"])
        agg.setdefault(k, []).append(m)
    for (model, cfg), ms in agg.items():
        n = len(ms)
        print("%-26s %-12s %8d%% %9.3f %9.1f" % (
            model, cfg,
            sum(x["wordlike"] for x in ms)/n,
            sum(x["trigram_distinct"] for x in ms)/n,
            sum(x["dup_posts"] for x in ms)/n))


if __name__ == "__main__":
    main()
