#!/usr/bin/env python3
"""THROWAWAY SPIKE: bake-off arms served by OpenRouter, as raw text continuation.

Every model here accepts a plain prompt on /completions, so it continues the thread
document exactly like the self-hosted base arms: no instruction, no chat template, same
scaffold (generate.py's seeded author order, timestamps, returns, arrivals), same openers,
same gate. The one difference: OpenRouter has no XTC or DRY, so these arms sample at
temperature 1.0 with min_p 0.05 where the provider supports it.

  py -3.12 spike/openrouter_arm.py hermes405      writes spike/remote/bakeoff-hermes405.json

Reads OPENROUTER_API_KEY from the repo's .env (gitignored).
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)
sys.path.insert(0, ROOT); sys.path.insert(0, SPIKE)
import generate as G
from bakeoff import OPENER_PICKS, POSTS
from live_board import GATE

MODELS = {
    "cydonia24": "thedrummer/cydonia-24b-v4.1",
    "euryale70": "sao10k/l3.1-euryale-70b",
    "hermes405": "nousresearch/hermes-3-llama-3.1-405b",
    "qwen235": "qwen/qwen3-235b-a22b-2507",
}
KEY = next(l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env"))
           if l.startswith("OPENROUTER_API_KEY="))
SPEND = {"prompt": 0, "completion": 0, "cost": 0.0}


def make_complete(model):
    def complete(port, prompt, stops):
        body = {"model": model, "prompt": prompt, "max_tokens": G.SAMPLING["n_predict"],
                "temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "stop": ["\n\n"],
                "usage": {"include": True}}
        for attempt in range(5):
            try:
                req = urllib.request.Request("https://openrouter.ai/api/v1/completions",
                                             data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json",
                                                      "Authorization": "Bearer " + KEY})
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.load(r)
                text = d["choices"][0].get("text") or ""
                u = d.get("usage") or {}
                SPEND["prompt"] += u.get("prompt_tokens", 0)
                SPEND["completion"] += u.get("completion_tokens", 0)
                SPEND["cost"] += u.get("cost", 0) or 0
                break
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError):
                if attempt == 4:
                    return "", "error"
                time.sleep(4 * (attempt + 1))
        # the base arms' per-handle stop strings, applied after the fact (the API caps stops)
        for s in stops:
            i = text.find(s)
            if i >= 0:
                text = text[:i]
        return text, "eos"
    return complete


def main():
    arm = sys.argv[1]
    G.complete = make_complete(MODELS[arm])
    G.POSTS_PER_THREAD = POSTS
    G.CHECK_AT = 10**9
    G.RETURN_AT, G.ARRIVE_AT = {7, 19}, {13}
    out = os.path.join(SPIKE, "remote", "bakeoff-%s.json" % arm)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    def one(i_text):
        i, text = i_text
        oi = [o["t"] for o in G.OPENERS].index(text)
        t0 = time.time()
        t = G.gen_thread(oi, 0, i + 1)
        for p in t["posts"][1:]:
            if any(h in p["text"].lower() for h in GATE):
                p.update(text="[post withheld]", withheld=True)
        t.update(arm=arm, opener=text, secs=round(time.time() - t0))
        return t

    with ThreadPoolExecutor(4) as ex:
        threads = list(ex.map(one, enumerate(OPENER_PICKS)))
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"arm": arm, "model": MODELS[arm], "posts_per_thread": POSTS,
                   "sampling": "temperature 1.0, min_p 0.05 where supported, no XTC/DRY",
                   "spend": SPEND, "threads": threads}, f, ensure_ascii=False, indent=1)
    print("\n%s: wrote %s  tokens in/out %d/%d  cost $%.3f"
          % (arm, out, SPEND["prompt"], SPEND["completion"], SPEND["cost"]), flush=True)


if __name__ == "__main__":
    main()
