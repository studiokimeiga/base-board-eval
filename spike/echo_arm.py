#!/usr/bin/env python3
"""THROWAWAY SPIKE: the bake-off's Echo arm (Fulcrum's persona chat model, via its API).

Echo is a chat model, so it can't just continue the document like the base arms. Each post
is one request: the thread so far plus a single neutral instruction to write the next post
by the scheduled author. Everything else is the bake-off scaffold: generate.py's seeded
author order, timestamps, OP returns and late arrivals, the same 8 openers, the same gate.

Reads ECHO_API_KEY from the repo's .env (gitignored). Writes spike/remote/bakeoff-echo.json.
"""
import json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)
sys.path.insert(0, ROOT); sys.path.insert(0, SPIKE)
import generate as G
from bakeoff import OPENER_PICKS, POSTS
from live_board import GATE

PERSONA = "4chan anon"
ASK = ("Here is an imageboard thread so far:\n\n%s\n\n"
       "Write the next post in the thread, by %s. Reply with only the text of the post.")
KEY = next(l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env"))
           if l.startswith("ECHO_API_KEY="))
HEADER = re.compile(r"\n\n(\S+) (\d\d/\d\d/\d\d\(\w{3}\)\d\d:\d\d:\d\d)\n$")


def echo(port, prompt, stops):
    """Drop-in for generate.complete: the prompt ends with the next post's header line."""
    m = HEADER.search(prompt)
    doc, author = prompt[:m.start()], m.group(1)
    # max_tokens: the default 20k budget is reserved against credits per request; a post
    # (reasoning included) takes ~550
    body = {"model": "echo", "persona": PERSONA, "max_tokens": 2000,
            "messages": [{"role": "user", "content": ASK % (doc, author)}]}
    for attempt in range(7):
        try:
            req = urllib.request.Request("https://echo.fulcrum.inc/api/v1/chat/completions",
                                         data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as r:
                text = json.load(r)["choices"][0]["message"].get("content") or ""
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):   # no retry fixes billing or auth; never save blanks
                raise SystemExit("Echo HTTP %d: %s" % (e.code, e.read()[:200]))
            if attempt == 6:
                raise SystemExit("Echo HTTP %d after retries" % e.code)
            time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, KeyError):
            if attempt == 6:
                raise SystemExit("Echo unreachable after retries")
            time.sleep(5 * (attempt + 1))
    # same cut as the base arms' stop strings, applied after the fact
    text = text.strip()
    # it sometimes copies a post header ("fatima 07/30/26(Thu)23:14:02") onto its first line
    text = re.sub(r"^>?\S+ \d\d/\d\d/\d\d\(\w{3}\)\d\d:\d\d:\d\d\n", "", text).strip()
    for s in stops:
        i = text.find(s)
        if i > 0:
            text = text[:i]
    if text.lower().startswith(author.lower() + ":"):
        text = text[len(author) + 1:]
    return text.strip(), "eos"


def main():
    G.complete = echo
    G.POSTS_PER_THREAD = POSTS
    G.CHECK_AT = 10**9
    G.RETURN_AT, G.ARRIVE_AT = {7, 19}, {13}
    out = os.path.join(SPIKE, "remote", "bakeoff-echo.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    def one(i_text):
        i, text = i_text
        oi = [o["t"] for o in G.OPENERS].index(text)
        t0 = time.time()
        t = G.gen_thread(oi, 0, i + 1)
        for p in t["posts"][1:]:
            if any(h in p["text"].lower() for h in GATE):
                p.update(text="[post withheld]", withheld=True)
        t.update(arm="echo", opener=text, secs=round(time.time() - t0))
        print("\nthread %d done in %ds" % (i + 1, t["secs"]), flush=True)
        return t

    with ThreadPoolExecutor(2) as ex:   # 4 at once hit Echo's rate limit
        threads = list(ex.map(one, enumerate(OPENER_PICKS)))
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"arm": "echo", "persona": PERSONA, "posts_per_thread": POSTS,
                   "threads": threads}, f, ensure_ascii=False, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
