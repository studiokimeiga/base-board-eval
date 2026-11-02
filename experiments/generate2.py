#!/usr/bin/env python3
"""Blind base-model board comparison, v2.

Changes from v1:
  - named participants (random handles) instead of "Anonymous" + No. ids
  - ASCII-only GBNF grammar so output stays in English
  - stop strings per participant handle, so a model can't write the next header
  - RNG seeded by opener only => every arm sees byte-identical prompts
"""
import json, os, random, signal, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
PORT = 8081
URL = f"http://127.0.0.1:{PORT}"

ARMS = [
    ("arm1.gguf", "gemma-4-E4B (base)"),
    ("arm2.gguf", "gemma-4-E4B-it (instruct)"),
    ("arm3.gguf", "Qwen3-4B-Base"),
    ("arm4.gguf", "Mistral-7B-v0.3 (base)"),
    ("arm5.gguf", "Olmo-3-1025-7B (base)"),
]

OPENERS = [
    "does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
    "my roommate has started labelling things in the fridge and i don't know how to bring it up",
]

STEMS = ["you're", "no,", "post a", "which ", "that's just ", "source", "op is "]

SAMPLING = {
    "temperature": 1.0,
    "min_p": 0.05,
    "top_p": 1.0,
    "top_k": 0,
    "repeat_penalty": 1.0,
    "n_predict": 120,
}

# printable ASCII plus newline; nothing else can be sampled
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

POSTS_PER_THREAD = 16
POOL_SIZE = 7
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

NAMES = [
    "marcus", "ines", "yusuf", "brenda", "kenji", "priya", "dmitri", "oona", "hakim",
    "lucia", "niall", "fatima", "gustav", "mei", "teodor", "ruth", "emeka", "astrid",
    "javier", "noor", "calvin", "sanne", "tomas", "aisha", "erik", "rosa", "kwame",
    "liesel", "omar", "bridget", "hiro", "valeria", "stefan", "nadia", "colm", "yara",
    "piotr", "greta", "samir", "delphine", "boris", "mira", "angus", "zainab", "luca",
    "hedda", "tariq", "paloma", "finn", "sofia",
]


def make_pool(rng):
    return rng.sample(NAMES, POOL_SIZE)


def stamp(secs):
    t = 23 * 3600 + 14 * 60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (
        day, DAYS[(3 + (day - 30)) % 7], t // 3600, (t % 3600) // 60, t % 60)


def complete(prompt, stops):
    body = dict(SAMPLING)
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True)
    req = urllib.request.Request(
        URL + "/completion", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r).get("content", "")
    except Exception:
        return ""


def wait_ready(proc, limit=180):
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


def gen_thread(opener_index, tid):
    """Append-only. Nothing is regenerated, retried, edited, or skipped."""
    rng = random.Random(90210 + opener_index)   # identical scaffold for every arm
    pool = make_pool(rng)
    stops = ["\n\n"] + ["\n" + h for h in pool]

    secs = 0
    author = pool[0]
    posts = [{"n": 1, "who": author, "ts": stamp(0), "text": OPENERS[opener_index]}]
    seen = [author]
    doc = "/x/ — thread 4471\n\n%s %s\n%s" % (author, stamp(0), OPENERS[opener_index])

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(30, 40 * 60)
        author = rng.choice([h for h in pool if h != author])

        seed = ""
        if n % 3 == 0:
            others = [h for h in seen if h != author]
            if others and (n // 3) % 2 == 0:
                seed = rng.choice(others) + ", "
            else:
                seed = rng.choice(STEMS)

        prompt = doc + "\n\n%s %s\n%s" % (author, stamp(secs), seed)
        out = complete(prompt, stops)
        text = (seed + out).strip()
        posts.append({"n": n, "who": author, "ts": stamp(secs), "text": text})
        if author not in seen:
            seen.append(author)
        doc = prompt + out
        sys.stdout.write("."); sys.stdout.flush()

    return {"id": tid, "opener_index": opener_index, "participants": pool, "posts": posts}


def main():
    out_path = os.path.join(HERE, "threads.json")
    threads = []
    tid = 0
    for i, (fname, model) in enumerate(ARMS, 1):
        path = os.path.join(MODELS, fname)
        if not os.path.exists(path):
            print("[arm %d] missing, cut" % i, flush=True)
            continue
        print("\n[arm %d/%d] loading" % (i, len(ARMS)), flush=True)
        proc = start_server(path, PORT)
        if not wait_ready(proc):
            print("[arm %d] failed to load, skipping" % i, flush=True)
            try: proc.kill()
            except Exception: pass
            continue
        for oi in range(len(OPENERS)):
            tid += 1
            t = gen_thread(oi, tid)
            t["model"] = model
            threads.append(t)
            with open(out_path, "w") as f:
                json.dump({"version": 2, "threads": threads}, f, indent=1)
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=20)
        except Exception: proc.kill()
        print("\n[arm %d/%d] done" % (i, len(ARMS)), flush=True)

    print("\nthreads written: %d" % len(threads))


if __name__ == "__main__":
    main()
