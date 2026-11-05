#!/usr/bin/env python3
"""THROWAWAY SPIKE: bake-off round 3. Same 8 openers and seeded scaffold as rounds 1-2.

  mix       Qwen3-235B + Hermes 405B, one model per poster: Hermes takes generate.py's
            gemma slots (OP + 2), Qwen the other 4. Raw continuation.
  qwenhot   Qwen3-235B raw continuation, hotter: temperature 1.15, min_p 0.05,
            frequency_penalty 0.3 (round 2's qwen235 was 1.0 / 0.05 / none)
  pick      best-of-3: three Qwen3-235B continuations per post, gpt-5.4 picks one. The
            picker sees the last 10 posts and the candidates, nothing else.
  kimi      Kimi K3, chat model, reasoning off: one neutral instruction per post
  echo      Echo (Fulcrum), chat model, persona "Anonymous": same instruction. Runs one
            thread at a time and stops cleanly when credits run out, keeping finished threads.

  py -3.12 spike/round3.py mix          writes spike/remote/bakeoff-mix.json

Rounds 4-8 added arms below. Round 9's five arms (gemini9, rolesshort9, rolesshort9naif,
gemini9neutral, rolesshort9neutral) are pre-registered in spike/PREREGISTRATION-ROUND9.md;
`spike/round3.py plan` prints where the small model posts, without generating anything.

Keys come from the repo's .env (gitignored). gpt-5.4 usage is logged per UTC day in
spike/openai_budget.json and the picker stops before the free daily allowance (250k).
"""
import contextlib, io, json, os, random, re, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)
sys.path.insert(0, ROOT); sys.path.insert(0, SPIKE)
import generate as G
from bakeoff import OPENER_PICKS, POSTS
from live_board import GATE

_ENV_FILE = os.path.join(ROOT, ".env")
ENV = dict(l.strip().split("=", 1) for l in open(_ENV_FILE)
           if "=" in l and not l.lstrip().startswith("#")) if os.path.exists(_ENV_FILE) else dict(os.environ)
LLAMA_COMPLETE = G.complete     # generate.py's own llama-server call (XTC + DRY, ASCII grammar)
QWEN, HERMES = "qwen/qwen3-235b-a22b-2507", "nousresearch/hermes-3-llama-3.1-405b"
ASK = ("Here is an imageboard thread so far:\n\n%s\n\n"
       "Write the next post in the thread, by %s. Reply with only the text of the post.")
HEADER = re.compile(r"\n\n(\S+) (\d\d/\d\d/\d\d\(\w{3}\)\d\d:\d\d:\d\d)\n$")
STAMP = r"\S+ \d\d/\d\d/\d\d\(\w{3}\)\d\d:\d\d:\d\d"
BUDGET = os.path.join(SPIKE, "openai_budget.json")
DAILY_CAP = 230_000            # gpt-5.4 family free allowance is 250k/day; keep headroom
SPEND = {"usd": 0.0, "openai_tokens": 0, "calls": 0}
LOCK = threading.Lock()


class OutOfCredit(Exception):
    pass


def post_json(url, key, body, timeout=240):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def retrying(fn, tries=6):
    for attempt in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):
                raise OutOfCredit("HTTP %d: %s" % (e.code, e.read()[:200]))
            if e.code == 400:      # a bad request won't get better; let the caller decide
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 10 * (attempt + 1)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError):
            wait = 5 * (attempt + 1)
        if attempt == tries - 1:
            raise RuntimeError("gave up after %d tries" % tries)
        time.sleep(wait)


def cut(text, stops):
    """The base arms' stop strings, applied after the fact."""
    for s in stops:
        i = text.find(s)
        if i >= 0:
            text = text[:i]
    return text


def clean_chat(text):
    """Chat models echo the post header and sometimes quote the whole post."""
    text = text.strip()
    text = re.sub(r"^>?" + STAMP + r"\s*\n", "", text).strip()
    if len(text) > 1 and text[0] == text[-1] == '"':
        text = text[1:-1].strip()
    return text


# ---- OpenRouter raw continuation ----
def openrouter_completion(model, prompt, **sampling):
    body = {"model": model, "prompt": prompt, "max_tokens": G.SAMPLING["n_predict"],
            "temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "stop": ["\n\n"],
            "usage": {"include": True}}
    body.update(sampling)
    d = retrying(lambda: post_json("https://openrouter.ai/api/v1/completions",
                                   ENV["OPENROUTER_API_KEY"], body))
    with LOCK:
        SPEND["usd"] += (d.get("usage") or {}).get("cost", 0) or 0
    return d["choices"][0].get("text") or ""


def raw_arm(model_for_port, **sampling):
    def complete(port, prompt, stops):
        return cut(openrouter_completion(model_for_port(port), prompt, **sampling), stops), "eos"
    return complete


# ---- chat arms ----
def chat_arm(kind):
    def complete(port, prompt, stops):
        m = HEADER.search(prompt)
        doc, author = prompt[:m.start()], m.group(1)
        msg = [{"role": "user", "content": ASK % (doc, author)}]
        if kind == "echo":
            body = {"model": "echo", "persona": "Anonymous", "max_tokens": 2000, "messages": msg}
            d = retrying(lambda: post_json("https://echo.fulcrum.inc/api/v1/chat/completions",
                                           ENV["ECHO_API_KEY"], body, timeout=300))
        else:
            body = {"model": "moonshotai/kimi-k3", "messages": msg, "max_tokens": 600,
                    "temperature": 1.0, "reasoning": {"enabled": False}, "usage": {"include": True}}
            d = retrying(lambda: post_json("https://openrouter.ai/api/v1/chat/completions",
                                           ENV["OPENROUTER_API_KEY"], body))
            with LOCK:
                SPEND["usd"] += (d.get("usage") or {}).get("cost", 0) or 0
        with LOCK:
            SPEND["calls"] += 1
        text = clean_chat(d["choices"][0]["message"].get("content") or "")
        return cut(text, stops).strip(), "eos"
    return complete


# ---- best-of-3 with a gpt-5.4 picker ----
def _budget():
    if not os.path.exists(BUDGET):
        return {}
    with open(BUDGET) as f:
        return json.load(f)


def budget_add(tokens):
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with LOCK:
        b = _budget()
        b[day] = b.get(day, 0) + tokens
        with open(BUDGET, "w") as f:     # readers take LOCK too, so none sees it half-written
            json.dump(b, f, indent=1)
        SPEND["openai_tokens"] += tokens
        return b[day]


def budget_left():
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with LOCK:
        b = _budget()
    return DAILY_CAP - b.get(day, 0)


PICK = ("These are the last posts of an imageboard thread:\n\n%s\n\n"
        "Here are %d candidates for the next post, by %s:\n\n%s\n\n"
        "Which candidate would make the thread most worth reading: funny, surprising, or "
        "building on something already in the thread, while still making sense as the next "
        "post? Answer with the candidate's number only.")


def pick_arm():
    def complete(port, prompt, stops):
        m = HEADER.search(prompt)
        author = m.group(1)
        with ThreadPoolExecutor(3) as ex:
            cands = list(ex.map(lambda _: cut(openrouter_completion(QWEN, prompt), stops).strip(),
                                range(3)))
        options = [c for c in dict.fromkeys(cands) if c] or [""]
        if len(options) == 1:
            return options[0], "only one distinct candidate"
        if budget_left() < 5000:
            return options[0], "picker budget exhausted"
        recent = prompt[:m.start()].split("\n\n")[-10:]
        listing = "\n\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(options))
        body = {"model": "gpt-5.4", "reasoning_effort": "none", "max_completion_tokens": 20,
                "messages": [{"role": "user", "content": PICK % ("\n\n".join(recent),
                                                                 len(options), author, listing)}]}
        try:
            d = retrying(lambda: post_json("https://api.openai.com/v1/chat/completions",
                                           ENV["OPENAI_API_KEY"], body))
        except urllib.error.HTTPError:
            body["reasoning_effort"] = "minimal"
            d = retrying(lambda: post_json("https://api.openai.com/v1/chat/completions",
                                           ENV["OPENAI_API_KEY"], body))
        budget_add(d["usage"]["total_tokens"])
        n = re.search(r"\d+", d["choices"][0]["message"]["content"] or "")
        i = int(n.group()) - 1 if n and 0 < int(n.group()) <= len(options) else 0
        return options[i], "picked %d of %d" % (i + 1, len(options))
    return complete


# ---- round 4: keep Hermes's peaks without its breakdowns, and Gemini in English ----
# Round 2 Hermes failed by looping (15 near-identical ~435-char posts in one thread), going
# generic, or printing page furniture. Three remedies, tested separately and together.
HERMES_PENALTIES = dict(repetition_penalty=1.05, frequency_penalty=0.3,
                        provider={"order": ["DeepInfra"]})       # the provider that takes them


def recent_posts(prompt, n=6):
    """Bodies of the last n posts in the document (each block is 'who stamp\\ntext')."""
    blocks = [b.split("\n", 1)[1] for b in prompt.split("\n\n") if "\n" in b][-n:]
    return [b.strip().lower() for b in blocks if b.strip()]


def broken(text, recent):
    """Why this post would count as a breakdown, or None."""
    t = text.strip().lower()
    if not t:
        return "empty"
    if len(t) > 600:
        return "wall of text"
    if re.match(r"^(no\.|>>\d|\d{3,})", t) or re.search(r"\d\d/\d\d/\d\d\(\w{3}\)", t):
        return "page junk"
    words = set(re.findall(r"[a-z']+", t))
    for r in recent:
        rw = set(re.findall(r"[a-z']+", r))
        if t == r or (len(words) > 3 and len(words & rw) / len(words | rw) > 0.7):
            return "repeats a recent post"
    return None


def guarded(model, prompt, stops, tries=4, **sampling):
    """Resample until the post isn't a breakdown; keep the last try if all fail."""
    recent = recent_posts(prompt)
    for k in range(tries):
        text = cut(openrouter_completion(model, prompt, **sampling), stops).strip()
        why = broken(text, recent)
        if not why:
            return text, "ok" if k == 0 else "resampled %d" % k
    return text, "kept after %d tries (%s)" % (tries, why)


def picker_openrouter(prompt, author, options):
    """gpt-5.4 via OpenRouter, same instruction as round 3; candidates arrive shuffled."""
    recent = prompt[:HEADER.search(prompt).start()].split("\n\n")[-10:]
    listing = "\n\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(options))
    body = {"model": "openai/gpt-5.4", "max_tokens": 300, "reasoning": {"effort": "low"},
            "usage": {"include": True},
            "messages": [{"role": "user", "content": PICK % ("\n\n".join(recent), len(options),
                                                             author, listing)}]}
    d = retrying(lambda: post_json("https://openrouter.ai/api/v1/chat/completions",
                                   ENV["OPENROUTER_API_KEY"], body))
    with LOCK:
        SPEND["usd"] += (d.get("usage") or {}).get("cost", 0) or 0
    n = re.search(r"\d+", d["choices"][0]["message"].get("content") or "")
    return int(n.group()) - 1 if n and 0 < int(n.group()) <= len(options) else 0


def hermes_arm(penalties, guard, pick):
    import random as _r
    rng = _r.Random(4242)
    sampling = HERMES_PENALTIES if penalties else {}

    def one(prompt, stops):
        if guard:
            return guarded(HERMES, prompt, stops, **sampling)
        return cut(openrouter_completion(HERMES, prompt, **sampling), stops).strip(), "eos"

    def complete(port, prompt, stops):
        if not pick:
            return one(prompt, stops)
        with ThreadPoolExecutor(3) as ex:
            cands = list(ex.map(lambda _: one(prompt, stops)[0], range(3)))
        options = [c for c in dict.fromkeys(cands) if c] or [""]
        if len(options) == 1:
            return options[0], "only one distinct candidate"
        with LOCK:
            rng.shuffle(options)         # round 3's picker chose slot 3 in 44% of posts
        i = picker_openrouter(prompt, HEADER.search(prompt).group(1), options)
        return options[i], "picked %d of %d" % (i + 1, len(options))
    return complete


def gemini_arm(temperature=1.0, roles=False, short=False, finish=False):
    """finish=True (round 9) logs the API's finish_reason as the post's stop ("length" = cut off
    by max_tokens); earlier rounds logged "eos" for every post."""
    def complete(port, prompt, stops):
        m = HEADER.search(prompt)
        doc, author = prompt[:m.start()], m.group(1)
        ask = ASK % (doc, author)
        if roles:
            role = role_of(author, prompt)
            if role:
                ask += " %s is %s. Don't announce it; just post the way they would." % (author, role)
                if short:
                    ask += " " + ROLE_LENGTH[ROLES.index(role)]
            elif short:
                ask += " Keep it as long as a real post would be: usually a sentence or two."
        body = {"model": "google/gemini-3.8-flash", "max_tokens": 1200, "temperature": temperature,
                "reasoning": {"effort": "low"}, "usage": {"include": True},
                "messages": [{"role": "user", "content": ask}]}
        d = retrying(lambda: post_json("https://openrouter.ai/api/v1/chat/completions",
                                       ENV["OPENROUTER_API_KEY"], body))
        with LOCK:
            SPEND["usd"] += (d.get("usage") or {}).get("cost", 0) or 0
        text = cut(clean_chat(d["choices"][0]["message"].get("content") or ""), stops).strip()
        return text, (d["choices"][0].get("finish_reason") or "?") if finish else "eos"
    return complete


# ---- round 7: a cast of roles instead of one model playing everyone ----
# Temperaments for non-OP posters, assigned per handle so a poster keeps theirs in every thread.
ROLES = ["a skeptic who assumes there's a boring explanation and says so bluntly",
         "a pedant who fixates on one small factual detail",
         "a lurker who rarely says more than a few words",
         "an earnest, slightly naive helper who takes everything at face value",
         "a mild troll who pokes at people for fun",
         "someone who keeps relating it to something from their own life"]
# round 8: round 7's role posts averaged 359 characters (storytellers and helpers wrote essays).
# How long each temperament's posts run, in the same order as ROLES.
ROLE_LENGTH = ["One or two blunt sentences.",
               "One or two sentences.",
               "A few words at most.",
               "One or two short sentences.",
               "One line.",
               "Two or three sentences at most, not a whole story."]
FIRST_POSTER = re.compile(r"\n\n(\S+) \d\d/\d\d/\d\d\(")


def role_of(author, prompt):
    op = FIRST_POSTER.search(prompt)
    if op and op.group(1) == author:
        return None                              # the OP is just the OP
    return ROLES[sum(map(ord, author)) % len(ROLES)]


def naif_arm(roles):
    """generate.py's olmo slots (2 of 7 posters) go to the small gemma-E4B base model with the
    original XTC + DRY sampler: the setup that wrote the phonebook thread. Everyone else is
    Gemini. Needs a llama-server for arm1b.gguf on NAIF_PORT (Modal, see modal_board.py::r7)."""
    naif_port = int(os.environ.get("NAIF_PORT", "8400"))
    G.VOICES["olmo"]["port"] = naif_port
    G.VOICES["gemma"]["port"] = G.VOICES["qwen"]["port"] = 9301
    gemini = gemini_arm(roles=roles)

    def complete(port, prompt, stops):
        if port == naif_port:
            return LLAMA_COMPLETE(naif_port, prompt, stops)
        return gemini(port, prompt, stops)
    return complete


def gemini_pick_arm():
    """Round 5: three Gemini posts, shuffled, gpt-5.4 picks (round 4's Hermes picker setup)."""
    import random as _r
    rng, write = _r.Random(5151), gemini_arm()

    def complete(port, prompt, stops):
        with ThreadPoolExecutor(3) as ex:
            cands = list(ex.map(lambda _: write(port, prompt, stops)[0], range(3)))
        options = [c for c in dict.fromkeys(cands) if c] or [""]
        if len(options) == 1:
            return options[0], "only one distinct candidate"
        with LOCK:
            rng.shuffle(options)
        i = picker_openrouter(prompt, HEADER.search(prompt).group(1), options)
        return options[i], "picked %d of %d" % (i + 1, len(options))
    return complete


# ---- round 9: pre-registered in spike/PREREGISTRATION-ROUND9.md ----
# Five fresh arms with new names, so no earlier file is overwritten. All five gate a post before
# it enters the context, as jp_bakeoff.py and live_board.py do; rounds 3-8 gated only the saved file.
X_HEADER, NEUTRAL_HEADER = G.BOARD_HEADER, "thread 4471"
R9 = {"gemini9": X_HEADER, "rolesshort9": X_HEADER, "rolesshort9naif": X_HEADER,
      "gemini9neutral": NEUTRAL_HEADER, "rolesshort9neutral": NEUTRAL_HEADER}
WITHHELD = "[post withheld]"
GEMINI_LABEL = "google/gemini-3.8-flash"
NAIF_LABEL = G.VOICES["gemma"]["label"] + ", XTC + DRY"
NAIF_SEED = 9090
NAIF_BLOCKS = [(2, 9), (10, 17), (18, 24)]     # one small-model post in each third of the replies
POST_HEADER = re.compile(r"\n\n\S+ \d\d/\d\d/\d\d\(\w{3}\)\d\d:\d\d:\d\d\n")


def post_number(prompt):
    """The number of the post being written: every post has a header, the last one is its own.
    Posts can't contain a blank line (every arm stops at one), so headers can't be faked."""
    return len(POST_HEADER.findall(prompt))


def opener_of(prompt):
    return prompt[POST_HEADER.search(prompt).end():].split("\n\n", 1)[0]


def opener_index(text):
    return [o["t"] for o in G.OPENERS].index(text)


def scaffold():
    """The bake-off's scaffold settings (rounds 1-9): 24 posts, OP back at 7 and 19, a newcomer at 13."""
    G.POSTS_PER_THREAD = POSTS
    G.CHECK_AT = 10**9
    G.RETURN_AT, G.ARRIVE_AT = {7, 19}, {13}


def naif_posts(oi):
    """The posts the small model writes in opener oi's thread: in each third of the replies, one post
    by someone other than the OP, drawn with its own seed. Authors never depend on model output, so
    a dry run with a stub writer gives exactly the scaffold the real run will use."""
    real = G.complete
    G.complete = lambda port, prompt, stops: ("", "dry run")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            posts = G.gen_thread(oi, 0, 0)["posts"]
    finally:
        G.complete = real
    op, rng = posts[0]["who"], random.Random(NAIF_SEED + oi)
    return sorted(rng.choice([p["n"] for p in posts if lo <= p["n"] <= hi and p["who"] != op])
                  for lo, hi in NAIF_BLOCKS)


def occasional_naif_arm():
    """Round 9's narrower hybrid: rolesshort, except that 3 posts per thread (1 in 8 of the 24) come
    from the small gemma-4-E4B base model with generate.py's XTC + DRY sampler, as round 7's naifs
    did. Round 7 gave it 2 of the 7 posters for a whole thread; here it writes single posts by whoever
    the scaffold has posting (never the OP), so no one poster is the confused one. Needs a
    llama-server for arm1b.gguf on NAIF_PORT (Modal, see modal_board.py::r9)."""
    naif_port = int(os.environ.get("NAIF_PORT", "8400"))
    at = {text: set(naif_posts(opener_index(text))) for text in OPENER_PICKS}
    gemini = gemini_arm(roles=True, short=True, finish=True)

    def complete(port, prompt, stops):
        if post_number(prompt) not in at[opener_of(prompt)]:
            return gemini(port, prompt, stops)
        for _ in range(3):
            text, why = LLAMA_COMPLETE(naif_port, prompt, stops)
            if why != "error":          # generate.complete turns any failure into ("", "error")
                return text, why
            time.sleep(5)
        raise RuntimeError("the small-model server failed three times")
    return complete


def gate_first(complete, arm):
    """Withhold a post before it enters the context. The withheld text goes to a private quarantine
    file next to the arm's output, so the gate's false positives can be counted later."""
    path = os.path.join(out_dir(), "quarantine-%s.jsonl" % arm)

    def gated(port, prompt, stops):
        text, why = complete(port, prompt, stops)
        hits = [h for h in GATE if h in text.lower()]
        if not hits:
            return text, why
        with LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"arm": arm, "opener": opener_of(prompt), "n": post_number(prompt),
                                    "who": HEADER.search(prompt).group(1), "matched": hits,
                                    "stop": why, "text": text}, ensure_ascii=False) + "\n")
        return WITHHELD, "withheld, " + why
    return gated


def out_dir():
    return os.environ.get("BAKEOFF_OUT", os.path.join(SPIKE, "remote"))


def build(arm):
    if arm in R9:
        G.BOARD_HEADER = R9[arm]
        if arm == "rolesshort9naif":
            return gate_first(occasional_naif_arm(), arm), 1      # one llama-server slot
        roles = arm.startswith("rolesshort")
        return gate_first(gemini_arm(roles=roles, short=roles, finish=True), arm), 4
    if arm == "geminipick":
        return gemini_pick_arm(), 3
    if arm == "roles":
        return gemini_arm(roles=True), 4
    if arm == "rolesshort":
        return gemini_arm(roles=True, short=True), 4
    if arm in ("naif", "naifroles"):
        return naif_arm(roles=(arm == "naifroles")), 1     # one llama-server slot
    if arm in ("qwent14", "qwent18"):   # round 6: hotter raw Qwen; min_p holds the tail, so pin a provider that honours it
        t, mp = (1.4, 0.1) if arm == "qwent14" else (1.8, 0.15)
        return raw_arm(lambda port: QWEN, temperature=t, min_p=mp, frequency_penalty=0.3,
                       provider={"order": ["DeepInfra"], "require_parameters": True}), 4
    if arm in ("geminit15", "geminit19"):    # round 6: does heat buy humour? (Gemini allows 0-2)
        return gemini_arm(temperature=1.5 if arm == "geminit15" else 1.9), 4
    if arm == "hermespen":
        return hermes_arm(penalties=True, guard=False, pick=False), 4
    if arm == "hermesguard":
        return hermes_arm(penalties=True, guard=True, pick=False), 4
    if arm == "hermespick":
        return hermes_arm(penalties=True, guard=True, pick=True), 3
    if arm == "gemini":
        return gemini_arm(), 4
    if arm == "mix":
        hermes_port = 9001
        G.VOICES["gemma"]["port"] = hermes_port
        G.VOICES["qwen"]["port"] = G.VOICES["olmo"]["port"] = 9002
        return raw_arm(lambda port: HERMES if port == hermes_port else QWEN), 4
    if arm == "qwenhot":
        return raw_arm(lambda port: QWEN, temperature=1.15, frequency_penalty=0.3), 4
    if arm == "pick":
        return pick_arm(), 3
    if arm == "kimi":
        return chat_arm("kimi"), 4
    if arm == "echo":
        return chat_arm("echo"), 1
    raise SystemExit("unknown arm " + arm)


def main():
    arm = sys.argv[1]
    scaffold()
    if arm == "plan":      # round 9: where the small model posts, without generating anything
        for i, text in enumerate(OPENER_PICKS):
            print("opener %d: posts %s" % (i + 1, naif_posts(opener_index(text))))
        return
    complete, workers = build(arm)
    G.complete = complete
    os.makedirs(out_dir(), exist_ok=True)   # before any paid post, so finished threads get saved
    out = os.path.join(out_dir(), "bakeoff-%s.json" % arm)
    naif_at = {t: naif_posts(opener_index(t)) for t in OPENER_PICKS} if arm == "rolesshort9naif" else {}
    done = {}
    if arm in R9 and os.path.exists(out):      # a rerun keeps finished threads, as jp_bakeoff.py does
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
        done = {OPENER_PICKS.index(t["opener"]): t for t in old["threads"]}
        SPEND.update(old["spend"])
        print("%s: resuming, %d threads already written" % (arm, len(done)), flush=True)

    def save():
        threads = [done[k] for k in sorted(done)]
        meta = {"arm": arm, "posts_per_thread": POSTS, "spend": SPEND}
        if arm in R9:
            meta.update(header=G.BOARD_HEADER, gate="before context",
                        saved_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with open(out, "w", encoding="utf-8") as f:
            json.dump(dict(meta, threads=threads), f, ensure_ascii=False, indent=1)

    def one(i_text):
        i, text = i_text
        oi = opener_index(text)
        t0 = time.time()
        t = G.gen_thread(oi, 0, i + 1)
        for p in t["posts"][1:]:
            if any(h in p["text"].lower() for h in GATE):
                p.update(text="[post withheld]", withheld=True)
            if arm in R9:     # gen_thread labels posts by scaffold voice; record who really wrote them
                p.pop("arm")
                p["model"] = NAIF_LABEL if p["n"] in naif_at.get(text, ()) else GEMINI_LABEL
                if p["stop"].startswith("withheld"):
                    p["withheld"] = True
        if arm in R9:
            t["posts"][0]["model"] = "opener"
            if naif_at:
                t["naif_posts"] = naif_at[text]
        t.update(arm=arm, opener=text, secs=round(time.time() - t0))
        with LOCK:
            done[i] = t
            save()
        print("\n%s: thread %d done in %ds" % (arm, i + 1, t["secs"]), flush=True)

    picks = OPENER_PICKS[:int(os.environ.get("BAKEOFF_THREADS", len(OPENER_PICKS)))]   # smoke runs: fewer
    try:
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(one, [(i, t) for i, t in enumerate(picks) if i not in done]))
    except OutOfCredit as e:
        print("\n%s stopped: %s (kept %d finished threads)" % (arm, e, len(done)), flush=True)
    print("\n%s: %d threads  spend $%.3f  openai tokens %d"
          % (arm, len(done), SPEND["usd"], SPEND["openai_tokens"]), flush=True)


if __name__ == "__main__":
    main()
