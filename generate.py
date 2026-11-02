#!/usr/bin/env python3
"""Long threads, mixed cast. Product prototype + natural experiment.

WHY MIXED: the paraphrase chorus -- six posters restating one idea in different
words -- is the tell that survived DRY, because the n-grams genuinely differ.
No sampler can fix it; every post conditions on the same short context and no
participant has persistent state. Different checkpoints DO have different
register, so the cast is the fix.

CAST (per participant, fixed for the whole thread)
  gemma-4-E4B base @ Q8_0  -- OP + 2 others. highest ceiling, carries a thread.
  Olmo-3-1025-7B @ Q8_0    -- 2 posters. never breaks, never surprises; makes the
                              board feel populated and gives the weird something
                              ordinary to be weird against.
  Qwen3-4B-Base @ Q8_0     -- 2 posters. the only arm that produced real hostility
                              and flat contradiction. the ones who pick fights.

WHY 50 POSTS: the phonebook thread sustained its premise for ~10 posts, which is
most of a 16-post thread. That was the format ceiling, not the model's limit.
Cache reuse means each post prefills ~24 new tokens, so 50 posts costs ~3x 16, not 10x.

WHY THESE 4 OPENERS: the only ones where the reader and I independently agreed a
thread was worth reposting.

THREE SERVERS AT ONCE, deliberately breaking the earlier one-at-a-time rule: a
mixed cast would otherwise need a model reload per post. ~20GB of weights on 64GB.
All three at Q8_0 so no voice is handicapped by quantisation -- the Q4_K_M of the
gemma base checkpoint was a confirmed broken file.

Per-post model attribution is stored. Which checkpoint produced the lines that get
flagged is the experiment hiding inside the prototype.
"""
import json, os, random, re, signal, subprocess, sys, time, urllib.request
from llama import start_server
from openers import ALL as OPENER_TEXTS, OPENERS as UNSEEDED

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
OUT = os.path.join(HERE, "threads.final.json")

VOICES = {
    "gemma": dict(file="arm1b.gguf",  port=8151, label="gemma-4-E4B base [Q8_0]"),
    "olmo":  dict(file="olmo-q8.gguf", port=8152, label="Olmo-3-1025-7B [Q8_0]"),
    "qwen":  dict(file="qwen-q8.gguf", port=8153, label="Qwen3-4B-Base [Q8_0]"),
}
# slot 0 is OP
CAST = ["gemma", "qwen", "olmo", "gemma", "olmo", "qwen", "gemma"]

OPENERS = [dict(t=x, seeded=(x not in UNSEEDED)) for x in OPENER_TEXTS]

POSTS_PER_THREAD = 32

# EARLY STOPPING. Chant onsets in the 50-post run were at posts 6,6,6,8,12,19,22,34,38 --
# five of nine decided inside the first dozen. So a thread's fate is largely set by
# post ~10 and generating the other 22 is spending compute on threads already lost.
#
# This is thread-level selection, not post-level: no post is ever regenerated, so
# append-only holds. Killing a whole thread and starting a fresh one is the funnel.
#
# Both gates are catastrophe-only, validated against the reader's own labels:
#   trigram distinctness < 0.50   -- chant. worst labelled chant was 0.17, best thread 0.93.
#   topical continuity  >= 0.90   -- tautology lock. caught 6 of 13 threads he called
#                                    not-human, at the cost of 1 of 11 he would repost.
#   quote-fragment rate  > 0.40   -- the model has left prose for quote blocks.
# Deliberately loose. A quality ranker is not attempted; four of those have already died.
CHECK_AT      = 10
MIN_TRIGRAM   = 0.50
MAX_CONTINUITY = 0.90
MAX_QUOTE     = 0.40

STOP_WORDS = set("""the a an and or but if then than that this these those is are was were be been being
have has had do does did not no yes it its i you he she they we me him her them my your his their of in on
at to for from with about into over after before between out up down off just so too very can will would
could should might must dont didnt cant im ive youre thats whats there here when where why how what who
which all any both each few more most other some such only own same as by like get got know think really
one two also even still back way something anything nothing someone thing things time""".split())


def _content(s):
    return {w for w in re.findall(r"[a-z']{4,}", s.lower()) if w not in STOP_WORDS}


def catastrophic(posts):
    """True if this thread has already locked into a failure and should be abandoned."""
    g = [p["text"] for p in posts[1:] if p["text"]]
    if len(g) < 5:
        return "empty"
    toks = re.findall(r"[a-z']+", " ".join(g).lower())
    tri = [tuple(toks[i:i+3]) for i in range(max(0, len(toks)-2))]
    dist = len(set(tri))/len(tri) if tri else 0
    if dist < MIN_TRIGRAM:
        return "chant tri=%.2f" % dist
    hits = sum(1 for i, x in enumerate(g[1:], 1)
               if _content(x) & set().union(*[_content(y) for y in g[max(0, i-3):i]]))
    cont = hits / max(1, len(g)-1)
    if cont >= MAX_CONTINUITY:
        return "tautology cont=%.2f" % cont
    if sum(1 for x in g if x.lstrip().startswith(">")) / len(g) > MAX_QUOTE:
        return "quote-blocks"
    return None
REPS = 1
POOL_SIZE = 7
OP_SHARE = 0.22

# The only new injection in this run, and the smallest one that can work. At these
# positions the OP is forced to post and its turn is seeded with one or two words.
# Nothing about WHAT develops is specified -- only that the poster is reporting rather
# than restating. The 50-post run showed the real problem was that no new information
# ever entered the document: the OP had one fact and every later post was commentary
# on it. Static at 16 posts is tolerable; at 50 it either loops or drifts into procedure.
# "update: " invited a status report, status reports are countable, and 15 of the 20
# lines the reader flagged contain no number at all. So the numeric drift was an
# artefact of the stem, not a property of good threads. Broadened here.
#
# And OP-only was an implementation choice, not a finding: several of the best beats
# came from bystanders bringing news ("the woman in 4b is my sister", "I'm the
# culprit!", "maybe he is actually me"). A second witness is a stronger turn than the
# OP reporting again, so half the slots now go to non-OP posters.
# NOTHING is injected into any post. No stems, no seeded words, no template text.
# The reader was seeing "update:" three times a thread in every thread -- my template,
# not a board. So the disclosure mechanism moves entirely into the format:
#
#   RETURN_AT   the OP posts again after a LARGE time gap (2-6h). A person coming back
#               hours later, with no prompt text at all, implies something happened.
#               The thread then spans ~20h and crosses midnight, which the timestamp
#               format already displays.
#   ARRIVE_AT   a participant who has NOT posted yet posts for the first time. A new
#               voice arriving late is the structural version of the witness stem --
#               selecting an unseen author is a choice about WHO, never about WHAT.
#
# Whether a base model reads a four-hour gap as "time passed, report something new" is
# exactly the open question. It is a far weaker signal than a seeded word, and it may
# simply not work.
RETURN_AT = {7, 19, 31}
ARRIVE_AT = {13, 25}
BIG_GAP   = (2*3600, 6*3600)

SAMPLING = {"temperature": 1.0, "min_p": 0.05, "top_p": 1.0, "top_k": 0,
            "repeat_penalty": 1.0, "n_predict": 120}
# allowed_length 2. Reverted from 3 after measurement: Jumping straight to 2 tripled the >quote-fragment rate
# allowed_length 3 was WORSE than 2 on both axes -- chant 27% vs 4%, >quote 11.7% vs
# 7.0% -- which falsifies the theory that DRY aggressiveness was driving the junk.
# The junk rate is high-variance run to run; the only robust signal is that widening
# the window from 256 to whole context raises it (4.0% -> ~7%). Cost accepted.
# Original note kept for the record: allowed_length 4 -> 2 and window 256 -> whole context. "i'm glad" is three tokens and
# slid through free before; 9 of 19 long threads collapsed into a chant. This will also
# suppress name-addressing, which is the price -- chants ruined half the corpus, names
# improved a handful of posts.
DRY = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=2, dry_penalty_last_n=8192)
GRAMMAR = 'root ::= ( [\\t -~] | "\\n" )*'

# expanded after thread 29 slipped through: the run5 list covered self-harm phrasing
# only and had no coverage for slurs or violence toward others.
HARM = [
    "kill myself", "killing myself", "kill me", "want to die", "wanna die", "end my life",
    "end it all", "should die", "better off dead", "suicide", "hang myself", "hurt myself",
    "cut myself", "rather die",
    # violence toward others
    "kill you", "kill them", "kill him", "kill her", "kill everyone", "kill you all",
    "going to kill", "gonna kill", "murder you", "shoot you", "shoot up", "beat you to death",
    "get killed", "you will die", "i'll end you",
    # slurs
    "faggot", "fag ", "nigger", "nigga", "tranny", "kike", "spic", "chink", "retard",
    "wetback", "towelhead", "paki ", "dyke", "coon",
]

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


# paired A/B on identical seeds: same pool, timestamps, author sequence, stems and
# opener; the two threads diverge from post 2 onward ONLY because of the sampler.
# Both arms run against the same loaded servers, arm A fully then arm B, so the
# prefix cache is never thrashed between two different documents.
# XTC strength sweep. XTC removes every token above `threshold` except the least
# probable of them, with probability `xtc_probability`. So LOWER threshold = more
# tokens eligible for removal = more aggressive; HIGHER probability = removed more
# often. This is the dial that trades novelty against readability, which is the
# tradeoff that actually matters here.
# Winner of the sweep: threshold 0.05 / probability 0.5. Best on every mechanical axis
# (trigram 0.98, quote junk 0.3%, 24.7 words per post, low fragment rate) and the reads
# hold up -- one thread invented a fictional "l car" class of subway carriage and the
# whole board discussed it with confident expertise. p70 drifted into greentext and a
# bereavement thread for a mug; p30 derailed into generic advice.
XTC = dict(xtc_threshold=0.05, xtc_probability=0.5)

# The remaining open question, folded in here as a paired arm rather than run separately
# so it gets 46 pairs instead of 8: does DRY still earn its place now that XTC handles
# the chants? DRY penalises repeated bigrams, which means it penalises CALLBACKS -- and
# "is your neighbor's name Zainab too?" is a callback. If XTC alone holds the line, then
# dropping DRY returns the mechanism the best lines run on.
# Two open questions, one run, 23 paired comparisons each.
#
# XTC STRENGTH. t05_p50 won the sweep on every mechanical axis and has the higher
# ceiling -- it invented the "l car". But its floor is worse: one thread ended "no im
# sorry that this isnt something youre doing because it isnt, youre not doing it, it
# isnt youre doing", which is closer to bewildering than asked for. t15_p50 reads more
# coherently and still produces the mechanism ("a big train can fit a small train on
# it" / "it cant" / "there are two trains, a big train and a small train"). The brief
# was funny and readable, not maximally strange, so this settles which ships.
#
# DRY. It penalises repeated bigrams, so it penalises CALLBACKS, and callbacks are where
# the best lines live. If XTC alone holds the chants, DRY is pure cost.
_DRY = dict(dry_multiplier=0.8, dry_base=1.75, dry_allowed_length=2, dry_penalty_last_n=8192)
ARMS = [("t05_dry",  dict(xtc_threshold=0.05, xtc_probability=0.5, **_DRY)),
        ("t15_dry",  dict(xtc_threshold=0.15, xtc_probability=0.5, **_DRY)),
        ("t15_nodry", dict(xtc_threshold=0.15, xtc_probability=0.5))]
ARM = ARMS[0]


def complete(port, prompt, stops):
    body = dict(SAMPLING); body.update(ARM[1])   # DRY now lives in the arm
    body.update(prompt=prompt, stop=stops, grammar=GRAMMAR, cache_prompt=True)
    req = urllib.request.Request("http://127.0.0.1:%d/completion" % port,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.load(r)
        return d.get("content", ""), d.get("stop_type", "?")
    except Exception as e:
        return "", "error"


def wait_ready(port, proc, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=2) as r:
                if json.load(r).get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def gen_thread(oi, rep, tid):
    """Append-only. Nothing regenerated, retried, edited or skipped."""
    rng = random.Random(70707 + oi*1000 + rep)
    pool = rng.sample(NAMES, POOL_SIZE)
    voice_of = {name: CAST[i] for i, name in enumerate(pool)}
    stops = ["\n\n"] + ["\n" + h for h in pool]
    op = pool[0]
    seen = {op}
    text = OPENERS[oi]["t"]

    secs, author = 0, op
    posts = [{"n": 1, "who": op, "ts": stamp(0), "text": text,
              "voice": voice_of[op], "model": VOICES[voice_of[op]]["label"], "stop": "-"}]
    doc = "/x/ — thread 4471\n\n%s %s\n%s" % (op, stamp(0), text)

    for n in range(2, POSTS_PER_THREAD + 1):
        secs += rng.randint(40, 9*60)
        if n in RETURN_AT:
            secs += rng.randint(*BIG_GAP) - rng.randint(40, 9*60)   # replace the normal gap
            author = op
        elif n in ARRIVE_AT:
            unseen = [h for h in pool if h not in seen]
            author = rng.choice(unseen) if unseen else rng.choice([h for h in pool if h != author])
        elif rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])
        v = voice_of[author]
        prompt = doc + "\n\n%s %s\n" % (author, stamp(secs))
        out, why = complete(VOICES[v]["port"], prompt, stops)
        posts.append({"n": n, "who": author, "ts": stamp(secs), "text": out.strip(),
                      "voice": v, "model": VOICES[v]["label"], "stop": why,
                      "returned": n in RETURN_AT, "arrived": n in ARRIVE_AT, "arm": ARM[0]})
        seen.add(author)
        doc = prompt + out
        if n % 10 == 0:
            sys.stdout.write(str(n//10)); sys.stdout.flush()
        else:
            sys.stdout.write("."); sys.stdout.flush()

        if n == CHECK_AT:
            why_stop = catastrophic(posts)
            if why_stop:
                sys.stdout.write("[killed: %s]" % why_stop); sys.stdout.flush()
                return {"id": tid, "opener_index": oi, "rep": rep,
                        "seeded": OPENERS[oi]["seeded"], "participants": pool,
                        "cast": voice_of, "abandoned": why_stop, "posts": posts}

    return {"id": tid, "opener_index": oi, "rep": rep, "seeded": OPENERS[oi]["seeded"],
            "participants": pool, "cast": voice_of, "posts": posts}


def quarantine(t, tid, hits):
    qd = os.path.join(HERE, "quarantine")
    os.makedirs(qd, exist_ok=True); os.chmod(qd, 0o700)
    qp = os.path.join(qd, "long-thread-%d-op%d-rep%d.json" % (tid, t["opener_index"], t["rep"]))
    with open(qp, "w") as f:
        json.dump({"note": "auto-quarantined at generation", "matched": hits, "thread": t}, f, indent=1)
    os.chmod(qp, 0o600)
    w = len(t["posts"]) - 1
    stub = {k: t[k] for k in ("id", "opener_index", "rep", "seeded", "participants", "cast")}
    stub.update(quarantined=True, matched=hits, posts=[t["posts"][0],
        {"n": 2, "who": t["posts"][1]["who"], "ts": t["posts"][1]["ts"],
         "text": "[%d posts withheld - auto-quarantined]" % w}])
    return stub


def main():
    procs = {}
    for k, v in VOICES.items():
        p = os.path.join(MODELS, v["file"])
        if not os.path.exists(p):
            print("missing %s" % v["file"]); return
        print("loading %-6s %s" % (k, v["file"]), flush=True)
        procs[k] = start_server(p, v["port"], cast=True)
        if not wait_ready(v["port"], procs[k]):
            print("failed to load %s" % k)
            for q in procs.values():
                q.kill()
            return
    print("all three voices up", flush=True)

    jobs = [(arm, oi, rep) for arm in ARMS
            for oi in range(len(OPENERS)) for rep in range(REPS)]
    print("%d threads x %d posts = %d completions" % (len(jobs), POSTS_PER_THREAD,
                                                      len(jobs)*(POSTS_PER_THREAD-1)), flush=True)
    threads, nq, tid = [], 0, 0
    global ARM
    for arm, oi, rep in jobs:
        ARM = arm
        tid += 1
        print("\n[%d/%d] %-4s op%d rep%d " % (tid, len(jobs), arm[0], oi, rep), end="", flush=True)
        t = gen_thread(oi, rep, tid)
        t["arm"] = arm[0]
        blob = " ".join(p["text"] for p in t["posts"]).lower()
        hits = [h for h in HARM if h in blob]
        if hits:
            nq += 1
            t = quarantine(t, tid, hits)
        threads.append(t)
        with open(OUT, "w") as f:
            json.dump({"version": 14, "injected_text": "none", "early_stopping": {"at": CHECK_AT, "min_trigram": MIN_TRIGRAM, "max_continuity": MAX_CONTINUITY}, "arms": {a[0]: a[1] for a in ARMS}, "return_at": sorted(RETURN_AT), "arrive_at": sorted(ARRIVE_AT), "cast": {k: v["label"] for k, v in VOICES.items()},
                       "cast_slots": CAST, "config": dict(SAMPLING, **DRY),
                       "posts_per_thread": POSTS_PER_THREAD, "openers": OPENERS,
                       "quarantined": nq, "threads": threads}, f, indent=1)

    for k, p in procs.items():
        p.send_signal(signal.SIGTERM)
        try: p.wait(timeout=25)
        except Exception: p.kill()
    print("\n\ndone: %d threads, %d quarantined" % (len(threads), nq))


if __name__ == "__main__":
    main()







