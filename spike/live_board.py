#!/usr/bin/env python3
"""THROWAWAY SPIKE: a live, models-only board.

Everything before this generated one thread at a time, from an opener we wrote, with a
fixed cast that never saw any other thread. This runs a board instead:

  * many threads at once, in bump order; threads that sink past the first page fall off
  * each thread has its own cast of 7 drawn from the board's regulars, mixed across the
    three voices as in generate.py; the OP comes back after time away, late posters arrive
  * real wall-clock time, so a thread left for hours has a gap in it

How threads see each other (v2). v1 put a catalog of every live OP above every prompt;
the models read the page as a list of complaints and added to the list instead of
replying, and model-written OPs drifted into mood pieces. So, only formats with evidence:

  * replies see their own thread and nothing else -- the format of every good thread so far
  * some threads carry ONE earlier thread from this board above them, its first posts only,
    as in generate17's board-memory run, where "physical number" carried over
  * new OPs come from openers.py, or are written by a model with one earlier thread from
    this board above it, never a list. Model OPs that are not one line of prose are dropped

Same sampler, grammar, early-stop gate and harm list as the final config (generate.py).
No text is injected beyond the format.

  py -3.12 spike/live_board.py            then open http://127.0.0.1:8765/
  --cpu       put every model on the CPU (slow, but works while a game holds the GPU)
  --voices    subset of gemma,qwen,olmo
  --hours N   stop after N hours
"""
import argparse, json, math, os, random, signal, sys, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)
sys.path.insert(0, ROOT)
import llama
from llama import start_server
import generate as G                      # final config: sampler, gate, harm list, cast
from openers import ALL as OPENERS

# Overridable so the same script runs on Modal (see modal_board.py)
DATA = os.environ.get("BOARD_DATA_DIR", os.path.join(SPIKE, "remote"))   # private, gitignored
MODELS = os.environ.get("BOARD_MODELS_DIR", os.path.join(ROOT, "models"))
STATE = os.path.join(DATA, "board.json")
QUARANTINE = os.path.join(DATA, "quarantine.jsonl")

BOARD = "/x/"
PAGE = 10              # live threads; anything bumped below this falls off
BUMP_LIMIT = 80        # replies, then the thread is archived
SHOW_LAST = 30         # long threads show OP + "[N posts omitted]" + the last SHOW_LAST
POOL_SIZE = 7          # per-thread cast, slot 0 is OP (generate.py)
OP_SHARE = G.OP_SHARE
OP_RETURN_AFTER = 2*3600   # board time, the low end of generate.py's BIG_GAP
POST_GAP = (15, 120)       # board seconds between posts anywhere on the board
P_ARRIVE = 0.15        # a cast member who hasn't posted yet shows up
P_PRIOR = 0.3          # opener threads that get an earlier thread above them
P_MODEL_OP = 0.4       # new threads whose OP a model writes, once there is a past to write under
PRIOR_POSTS = 10       # generate17
PRIOR_MIN_REPLIES = 10

POPULATION = {"gemma": 14, "qwen": 10, "olmo": 10}

# generate.py's HARM list has no sexual terms; v2 needed them (chan register drifts there fast)
SEXUAL = ["cunt", "cock", "tits", "orgasm", "slut", "fap", "pussy", "blowjob", "jerk off",
          "jerking off", "porn", "boobed", "dick out", "horny", "rape"]
GATE = G.HARM + SEXUAL


def now_stamp(t=None):
    return time.strftime("%m/%d/%y(%a)%H:%M:%S", time.localtime(t or time.time()))


def prose(text):
    """One line of plain prose: not page furniture, quote blocks or a list."""
    t = text.strip()
    return (20 <= len(t) <= 400 and "\n" not in t and not t.startswith((">", "No.", "["))
            and not t[:1].isdigit() and sum(c.isalpha() or c.isspace() for c in t) >= 0.85 * len(t))


class Board:
    def __init__(self, voices, rng):
        self.rng, self.voices = rng, voices
        if os.path.exists(STATE):
            with open(STATE, encoding="utf-8") as f:
                s = json.load(f)
            self.threads, self.next_no, self.regulars = s["threads"], s["next_no"], s["regulars"]
            self.clock = s.get("clock", time.time())
        else:
            self.threads, self.next_no = [], 4471
            self.clock = time.time()   # board time: starts now, runs as fast as the GPU posts
            names = rng.sample(G.NAMES, sum(POPULATION.values()))
            self.regulars, i = {}, 0
            for v, n in POPULATION.items():
                for _ in range(n):
                    self.regulars[names[i]] = v; i += 1
        self.cast_voices = [v if v in voices else voices[0] for v in G.CAST]

    # ---- state ----
    def live(self):
        t = [x for x in self.threads if x["status"] == "live"]
        return sorted(t, key=lambda x: -x["bumped"])

    def save(self, status=""):
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"board": BOARD, "next_no": self.next_no, "regulars": self.regulars,
                       "status": status, "updated": time.time(), "clock": self.clock,
                       "threads": self.threads},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE)

    # ---- documents ----
    @staticmethod
    def render_posts(posts):
        shown = [p for p in posts if not p.get("withheld") and p["text"]]
        if len(shown) > SHOW_LAST + 1:
            omitted = len(shown) - 1 - SHOW_LAST
            parts = [shown[0], {"omitted": omitted}] + shown[-SHOW_LAST:]
        else:
            parts = shown
        return "\n\n".join("[%d posts omitted]" % p["omitted"] if "omitted" in p
                           else "%s %s\n%s" % (p["who"], p["ts"], p["text"]) for p in parts)

    def pick_prior(self, exclude=()):
        """An earlier thread worth remembering: has a conversation, didn't die, and leaves
        enough regulars to cast a new thread without any of its authors."""
        ok = [t for t in self.threads if t["status"] != "died" and t["no"] not in exclude
              and sum(1 for p in t["posts"][1:] if p["text"] and not p.get("withheld"))
              >= PRIOR_MIN_REPLIES and self.castable(self.prior_block(t)[1])]
        return self.rng.choice(ok) if ok else None

    def castable(self, avoid):
        """Whether cast() can fill every slot without anyone in avoid. With --voices qwen,
        all seven slots draw on the ten qwen regulars, so a prior with four or more of them
        among its authors can't be used."""
        need = {v: self.cast_voices.count(v) for v in set(self.cast_voices)}
        return all(sum(1 for h, hv in self.regulars.items() if hv == v and h not in avoid) >= n
                   for v, n in need.items())

    @staticmethod
    def prior_block(t):
        posts = [p for p in t["posts"] if p["text"] and not p.get("withheld")][:PRIOR_POSTS]
        text = "%s — thread %d\n\n%s\n\n" % (BOARD, t["no"], Board.render_posts(posts))
        return text, sorted({p["who"] for p in posts})

    def cast(self, avoid):
        """POOL_SIZE regulars in generate.py's voice order, none of them from the prior."""
        pool = []
        for v in self.cast_voices:
            free = [h for h, hv in self.regulars.items()
                    if hv == v and h not in pool and h not in avoid]
            pool.append(self.rng.choice(free))
        return pool

    def doc(self, t):
        return t.get("prior_text", "") + "%s — thread %d\n\n" % (BOARD, t["no"])

    # ---- actions ----
    def new_thread(self):
        rng, no, ts = self.rng, self.next_no, now_stamp(self.clock)
        prior = self.pick_prior()
        by_model = prior is not None and rng.random() < P_MODEL_OP
        if not by_model and not (prior and rng.random() < P_PRIOR):
            prior = None
        prior_text, prior_who = self.prior_block(prior) if prior else ("", [])
        pool = self.cast(set(prior_who))
        op = pool[0]
        t = {"no": no, "op": op, "pool": pool, "prior": prior["no"] if prior else None,
             "prior_text": prior_text, "prior_who": prior_who}
        if by_model:
            prompt = self.doc(t) + "%s %s\n" % (op, ts)
            text, why = G.complete(G.VOICES[self.regulars[op]]["port"], prompt,
                                   ["\n\n", "\n" + BOARD])
            text = text.strip()
            if not prose(text):
                return None, "op dropped (%r)" % text[:60]
            hits = [h for h in GATE if h in text.lower()]
            if hits:   # never becomes a thread, so it never reaches another prompt
                with open(QUARANTINE, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"thread": None, "matched": hits,
                                        "post": self.post(op, ts, text, why)}) + "\n")
                return None, "op withheld (%d matches)" % len(hits)
        else:
            used = {}
            for x in self.threads:
                if x["origin"] == "opener":
                    used[x["posts"][0]["text"]] = used.get(x["posts"][0]["text"], 0) + 1
            least = min(used.get(o, 0) for o in OPENERS)
            text, why = rng.choice([o for o in OPENERS if used.get(o, 0) == least]), "-"
        self.next_no += 1
        t.update(origin="model" if by_model else "opener", created=self.clock,
                 bumped=self.clock, status="live", posts=[self.post(op, ts, text, why)])
        self.threads.append(t)
        return t, None

    def reply(self, t):
        rng, posts, pool, op = self.rng, t["posts"], t["pool"], t["op"]
        last = posts[-1]["who"]
        seen = {p["who"] for p in posts}
        unseen = [h for h in pool if h not in seen]
        op_last = max(p["t"] for p in posts if p["who"] == op)
        if op != last and self.clock - op_last > OP_RETURN_AFTER and rng.random() < 0.3:
            author, how = op, "returned"
        elif unseen and rng.random() < P_ARRIVE:
            author, how = rng.choice(unseen), "arrived"
        elif op != last and rng.random() < OP_SHARE:
            author, how = op, ""
        else:
            author, how = rng.choice([h for h in pool if h != last]), ""
        ts = now_stamp(self.clock)
        prompt = self.doc(t) + self.render_posts(posts) + "\n\n%s %s\n" % (author, ts)
        stops = ["\n\n", "\n" + BOARD] + ["\n" + h for h in set(pool) | set(t["prior_who"])]
        text, why = G.complete(G.VOICES[self.regulars[author]]["port"], prompt, stops)
        p = self.post(author, ts, text.strip(), why)
        if how:
            p[how] = True
        hits = [h for h in GATE if h in p["text"].lower()]
        if hits:
            with open(QUARANTINE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"thread": t["no"], "matched": hits, "post": p}) + "\n")
            p.update(text="[post withheld]", withheld=True, matched=len(hits))
        posts.append(p)
        if p["text"]:
            t["bumped"] = self.clock
        n = len(posts) - 1
        if n == G.CHECK_AT:
            dead = G.catastrophic([x for x in posts if not x.get("withheld")])
            if dead:
                t.update(status="died", why=dead)
        if n >= BUMP_LIMIT:
            t.update(status="archived", why="bump limit")
        return p

    def post(self, who, ts, text, why):
        return {"who": who, "ts": ts, "t": self.clock, "text": text,
                "voice": self.regulars[who], "stop": why}

    def prune(self):
        for t in self.live()[PAGE:]:
            t.update(status="archived", why="fell off the board")

    def step(self):
        live = self.live()
        self.clock += self.rng.uniform(*POST_GAP)
        # a full page gets a new thread about every 30 posts, so threads get a real run
        p_new = 1.0 if len(live) < 4 else 0.15 if len(live) < 7 else 0.035
        if self.rng.random() < p_new:
            t, err = self.new_thread()
            self.prune()
            if not t:
                return err
            return "new thread %d (%s%s): %s" % (t["no"], t["origin"],
                   ", under %d" % t["prior"] if t["prior"] else "", t["posts"][0]["text"][:80])
        weights = [math.exp(-i / 3.0) * (2.0 if len(t["posts"]) < 4 else 1.0)
                   for i, t in enumerate(live)]
        t = self.rng.choices(live, weights)[0]
        p = self.reply(t)
        return "%d <- %s/%s: %s" % (t["no"], p["who"], p["voice"], p["text"][:80].replace("\n", " / "))


def serve(port, host="127.0.0.1", key=""):
    """Watch page plus board.json. With a key, everything lives under /<key>/ only."""
    prefix = "/%s/" % key if key else "/"

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=SPIKE, **k)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if not path.startswith(prefix):
                return self.send_error(404)
            rest = path[len(prefix):] or "index.html"
            if rest == "board.json":
                if not os.path.exists(STATE):
                    return self.send_error(404)
                with open(STATE, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if rest != "index.html":
                return self.send_error(404)
            self.path = "/index.html"
            return super().do_GET()

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()
    srv = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--voices", default="gemma,qwen,olmo")
    ap.add_argument("--hours", type=float, default=0)
    ap.add_argument("--steps", type=int, default=0)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--seed", type=int, default=int(time.time()))
    a = ap.parse_args()
    voices = [v for v in a.voices.split(",") if v in G.VOICES]
    if a.cpu:
        for v in G.VOICES.values():
            llama.CAST_GPU_LAYERS[v["file"]] = 0

    serve(a.port, os.environ.get("BOARD_HOST", "127.0.0.1"), os.environ.get("BOARD_KEY", ""))
    print("watch: http://127.0.0.1:%d/" % a.port, flush=True)
    board = Board(voices, random.Random(a.seed))
    board.save("loading models")

    procs = {}
    def shutdown(*_):
        for p in procs.values():
            p.kill()
        board.save("stopped")
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    for v in voices:
        path = os.path.join(MODELS, G.VOICES[v]["file"])
        print("loading %s" % v, flush=True)
        procs[v] = start_server(path, G.VOICES[v]["port"], cast=True)
        if not G.wait_ready(G.VOICES[v]["port"], procs[v]):
            print("failed to load %s" % v); shutdown()

    steps, t0 = 0, time.time()
    while True:
        if a.hours and time.time() - t0 > a.hours * 3600:
            break
        if a.steps and steps >= a.steps:
            break
        s0 = time.time()
        msg = board.step()
        steps += 1
        board.save("running")
        print("[%s %5.1fs] %s" % (time.strftime("%H:%M:%S"), time.time() - s0, msg), flush=True)
    shutdown()


if __name__ == "__main__":
    main()
