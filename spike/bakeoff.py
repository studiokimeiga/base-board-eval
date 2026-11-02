#!/usr/bin/env python3
"""THROWAWAY SPIKE: paired model bake-off for the board.

Same 8 openers, same scaffold (cast slots, author sequence, timestamps, OP returns and
late arrivals all come from generate.py's seeded rng, never from model output), same
sampler. Only the weights differ:

  cast     gemma-4-E4B / Qwen3-4B / Olmo-3-7B, mixed as in generate.py  (current board)
  g31      gemma-4-31B base Q8_0 for every voice
  l70      Llama-3.1-70B base Q4_K_M for every voice

Early stopping is off so every arm writes every thread in full. Posts that hit the
harm or sexual-content list are withheld afterwards, before anyone reads them.

  python spike/bakeoff.py --arm g31 --models /models --out /data   (run by modal_board.py)
"""
import argparse, json, os, signal, sys, time

SPIKE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SPIKE))
sys.path.insert(0, SPIKE)
import generate as G
from llama import start_server
from live_board import GATE

OPENER_PICKS = [
    "someone at work keeps taking my mug, washing it, and putting it back in a different cupboard",
    "just got a text from my own number asking if i left the stove on",
    "the guy who sits behind me has started answering questions that people asked me",
    "my friend has started saying my name at the end of every sentence",
    "our group chat renamed itself and nobody will say who did it",
    "the barista has written a different name on my cup three times this week",
    "i've been getting someone else's post for a year and i've started reading it",
    "my dad has started forwarding me his own emails",
]
ARMS = {
    "cast": {"gemma": "arm1b.gguf", "qwen": "qwen-q8.gguf", "olmo": "olmo-q8.gguf"},
    "g31": {"all": "gemma-4-31B-Q8_0.gguf"},
    "l70": {"all": "Meta-Llama-3.1-70B.Q4_K_M.gguf"},
}
POSTS = 24


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--models", default=os.path.join(os.path.dirname(SPIKE), "models"))
    ap.add_argument("--out", default=SPIKE)
    a = ap.parse_args()

    G.POSTS_PER_THREAD = POSTS
    G.CHECK_AT = 10**9                      # no early stopping: every arm writes every thread
    G.RETURN_AT, G.ARRIVE_AT = {7, 19}, {13}
    files = ARMS[a.arm]
    procs, port = {}, 8200
    for key, f in files.items():
        print("loading", f, flush=True)
        procs[key] = start_server(os.path.join(a.models, f), port, cast=(a.arm == "cast"))
        if not G.wait_ready(port, procs[key], limit=900):
            print("failed to load", f); [p.kill() for p in procs.values()]; sys.exit(1)
        for v in G.VOICES:
            if key in (v, "all"):
                G.VOICES[v]["port"] = port
        port += 1

    threads = []
    for i, text in enumerate(OPENER_PICKS):
        oi = [o["t"] for o in G.OPENERS].index(text)
        t0 = time.time()
        t = G.gen_thread(oi, 0, i + 1)
        for p in t["posts"][1:]:
            hits = [h for h in GATE if h in p["text"].lower()]
            if hits:
                p.update(text="[post withheld]", withheld=True)
        t.update(arm=a.arm, opener=text, secs=round(time.time() - t0))
        threads.append(t)
        print("\nthread %d/%d done in %ds" % (i + 1, len(OPENER_PICKS), t["secs"]), flush=True)
        with open(os.path.join(a.out, "bakeoff-%s.json" % a.arm), "w", encoding="utf-8") as f:
            json.dump({"arm": a.arm, "files": files, "posts_per_thread": POSTS,
                       "threads": threads}, f, ensure_ascii=False, indent=1)
    for p in procs.values():
        p.send_signal(signal.SIGTERM)
        try: p.wait(timeout=30)
        except Exception: p.kill()


if __name__ == "__main__":
    main()
