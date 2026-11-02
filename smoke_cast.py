#!/usr/bin/env python3
"""Load the three-voice cast the way generate*.py does and time one post from each.

Usage: python smoke_cast.py
Prints, per voice, generation speed with the shipping sampler config (XTC + DRY + grammar).
"""
import json, os, subprocess, sys, time, urllib.request
from llama import start_server

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
VOICES = {
    "gemma": dict(file="arm1b.gguf",  port=8191),
    "qwen":  dict(file="qwen-q8.gguf", port=8192),
    "olmo":  dict(file="olmo-q8.gguf", port=8193),
}
PROMPT = "/x/ — thread 4471\n\nmarcus 07/30/26(Thu)23:14:02\nmy flatmate has started buying the exact brand of yoghurt i buy\n\nines 07/30/26(Thu)23:16:40\n"
BODY = {"temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "top_k": 0, "repeat_penalty": 1.0,
        "n_predict": 120, "dry_multiplier": 0.8, "dry_base": 1.75, "dry_allowed_length": 2,
        "dry_penalty_last_n": 8192, "xtc_threshold": 0.05, "xtc_probability": 0.5,
        "grammar": 'root ::= ( [\\t -~] | "\\n" )*', "stop": ["\n\n"]}


def get(port, path):
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=5) as r:
        return json.load(r)


def wait_ready(port, proc, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            return False
        try:
            if get(port, "/health").get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def vram_used():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else -1


def main():
    procs = {}
    try:
        for k, v in VOICES.items():
            before = vram_used()
            t0 = time.time()
            procs[k] = start_server(os.path.join(MODELS, v["file"]), v["port"], cast=True)
            if not wait_ready(v["port"], procs[k]):
                print("%-6s FAILED to load" % k); return 1
            print("%-6s loaded in %4.1fs, +%5d MiB VRAM (now %d MiB used)"
                  % (k, time.time() - t0, vram_used() - before, vram_used()), flush=True)
        print()
        for k, v in VOICES.items():
            body = dict(BODY, prompt=PROMPT)
            req = urllib.request.Request("http://127.0.0.1:%d/completion" % v["port"],
                                         data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=240) as r:
                out = json.load(r)
            t = out.get("timings", {})
            print("%-6s %5.1f tok/s  (%d tokens)  %r"
                  % (k, t.get("predicted_per_second", 0), t.get("predicted_n", 0),
                     out.get("content", "").strip()[:70]), flush=True)
        return 0
    finally:
        for p in procs.values():
            p.kill()


if __name__ == "__main__":
    sys.exit(main())
