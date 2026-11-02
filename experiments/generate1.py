#!/usr/bin/env python3
"""Blind base-model board comparison. One model at a time, append-only generation."""
import json, os, random, signal, subprocess, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama import start_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
MODELS = os.path.join(HERE, "models")
PORT = 8081
URL = f"http://127.0.0.1:{PORT}"

# arm file -> real model id (never printed to the terminal)
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
    "stop": ["\n\n", "\n\n1 Anonymous"],
}

POSTS_PER_THREAD = 16
BASE_NO = 44710001
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def stamp(secs):
    """07/30/26(Thu)23:14:02 advanced by `secs` from a fixed start."""
    t = 23 * 3600 + 14 * 60 + 2 + secs
    day = 30 + t // 86400
    t %= 86400
    return "07/%02d/26(%s)%02d:%02d:%02d" % (day, DAYS[(3 + (day - 30)) % 7], t // 3600, (t % 3600) // 60, t % 60)


def header(n, secs, no):
    return "%d Anonymous %s No.%d" % (n, stamp(secs), no)


def complete(prompt):
    body = dict(SAMPLING)
    body["prompt"] = prompt
    body["cache_prompt"] = True
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


def gen_thread(rng, opener_index, tid):
    """Append-only. Nothing is ever regenerated, retried, or skipped."""
    opener = OPENERS[opener_index]
    secs = 0
    no = BASE_NO
    posts = [{"n": 1, "ts": stamp(0), "no": no, "text": opener}]
    doc = "/x/ — thread 4471\n\n%s\n%s" % (header(1, 0, no), opener)

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(30, 40 * 60)
        no += rng.randint(3, 400)
        h = header(n, secs, no)
        seed = rng.choice(STEMS) if n % 3 == 0 else ""
        prompt = doc + "\n\n" + h + "\n" + seed
        out = complete(prompt)
        text = (seed + out).strip()
        posts.append({"n": n, "ts": stamp(secs), "no": no, "text": text})
        doc = prompt + out
        sys.stdout.write("."); sys.stdout.flush()

    return {"id": tid, "opener_index": opener_index, "posts": posts}


def main():
    log = os.path.join(HERE, "dl.log")
    deadline = time.time() + float(os.environ.get("DL_DEADLINE_S", 420))

    def ready(fname):
        """Block until this arm's download is confirmed complete, or the budget expires."""
        while time.time() < deadline:
            try:
                txt = open(log).read()
            except OSError:
                txt = ""
            if "DONE " + fname in txt:
                return True
            if "FAIL " + fname in txt:
                return False
            time.sleep(2)
        return "DONE " + fname in open(log).read()

    available = ARMS
    threads = []
    tid = 0
    for i, (fname, model) in enumerate(available, 1):
        if not ready(fname):
            print("[arm %d] not downloaded in budget, cut" % i, flush=True)
            continue
        print("\n[arm %d/%d] loading" % (i, len(available)), flush=True)
        proc = start_server(os.path.join(MODELS, fname), PORT)
        if not wait_ready(proc):
            print("[arm %d] failed to load, skipping" % i, flush=True)
            try:
                proc.kill()
            except Exception:
                pass
            continue
        for oi in range(len(OPENERS)):
            tid += 1
            rng = random.Random(1000 * i + oi)  # deterministic per arm/opener
            t = gen_thread(rng, oi, tid)
            t["model"] = model
            threads.append(t)
            with open(os.path.join(HERE, "threads.json"), "w") as f:
                json.dump(threads, f, indent=1)
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        print("\n[arm %d/%d] done" % (i, len(available)), flush=True)

    print("\nthreads written: %d" % len(threads))


if __name__ == "__main__":
    main()
