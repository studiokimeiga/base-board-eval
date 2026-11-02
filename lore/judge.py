#!/usr/bin/env python3
"""Blind judges for the lore boards: what in a later thread seems to come from an earlier one?

  python lore/judge.py packets                  one private text file per item, and the key
  python lore/judge.py claude-prompt N          the exact prompt for Claude batch N (of BATCHES)
  python lore/judge.py gpt [--via openrouter|openai]
  python lore/judge.py collect                  public verdicts from the judges' private replies

An item is a target thread with its source thread above it as "Thread A (earlier)", whether or not
the target's page showed it. Item ids are shuffled with a fixed seed so nothing in a packet tells
the arm; key.json maps them back. A judge that finds borrowing in a no-memory item is wrong by
construction, which is what the analysis uses to measure the judges.

Replies, which quote the threads, stay in lore/private/judging/. lore/judging/scores-*.json keep
per-item verdicts only: borrows, confidence and how many borrowings of each kind.
"""
import argparse, glob, json, os, random, re, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "spike"))
import board as B

SEED = 20261102
BATCHES = 8
PRIVATE = os.path.join(B.PRIVATE, "judging")
PUBLIC = os.path.join(HERE, "judging")
KINDS = ("reference", "mixup", "reuse", "coincidence")
GPT = "openai/gpt-5.4"

PROMPT = """Two threads from the same imageboard follow. Thread A was posted first. Thread B was posted later, on the same board.

Some of the people writing Thread B may have read Thread A. Or none of them did, and any resemblance is coincidence. Both threads were written by AI models.

Find anything in Thread B that came from Thread A rather than from B's own opening post: a distinctive word or phrase, an invented term or a way of talking, a rule or an explanation, a named person, object or event, or a mention of another thread. Ignore ordinary words, and anything B's opening post explains on its own.

For each borrowing, give a short quote from B, the line in A it seems to come from, and one kind:
- "reference": B points at an earlier thread, or at something in A, explicitly
- "mixup": B treats A's situation as if it were B's own (the two threads are confused)
- "reuse": B takes something from A and applies it to B's own situation
- "coincidence": similar, but probably independent

Then say whether B borrows from A at all (true or false), and how sure you are, from 1 (guessing) to 5 (certain).

Answer with JSON only, in this form:
{"borrowings": [{"b": "...", "a": "...", "kind": "reuse"}], "borrows": true, "confidence": 3}

=== Thread A (earlier) ===
%s

=== Thread B (later) ===
%s
"""


def render(t):
    shown = [p for p in t["posts"] if p.get("text") and not p.get("withheld")]
    return "%s — thread %d\n\n%s" % (t["board"], t["no"],
                                      "\n\n".join("%s\n%s" % (p["who"], p["text"]) for p in shown))


def load_run(root=None):
    """{(board key, thread id, arm or None): thread} for every thread the run wrote."""
    root = root or os.path.join(B.PRIVATE, "run")
    out = {}
    for b in B.BOARDS:
        for path in glob.glob(os.path.join(root, b, "*.json")):
            name = os.path.basename(path)[:-5]
            tid, _, arm = name.partition("-")
            with open(path, encoding="utf-8") as f:
                out[(b, tid, arm or None)] = json.load(f)
    return out


def items(run):
    """Every target in both arms, with its source; ids shuffled with SEED."""
    keys = sorted(k for k in run if k[2])
    rng = random.Random(SEED)
    ids = ["i%03d" % i for i in range(len(keys))]
    rng.shuffle(ids)
    out = []
    for item_id, (b, tid, arm) in zip(ids, keys):
        t = run[(b, tid, arm)]
        s = run[(b, t["source"], None)]
        out.append({"item": item_id, "board": b, "target": tid, "arm": arm,
                    "text": PROMPT % (render(s), render(t))})
    return sorted(out, key=lambda x: x["item"])


def batches(item_ids, n=BATCHES):
    ids = sorted(item_ids)
    return [ids[i::n] for i in range(n)]


def half(item_ids):
    """The random half Claude judges if usage limits do not allow every item (pre-registered)."""
    ids = sorted(item_ids)
    random.Random(SEED).shuffle(ids)
    return sorted(ids[:len(ids) // 2])


def parse(reply):
    """The judge's JSON, from a reply that may wrap it in prose or a code fence."""
    m = re.search(r"\{.*\}", reply or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    bs = [x for x in d.get("borrowings") or [] if isinstance(x, dict)]
    kinds = {k: sum(1 for x in bs if x.get("kind") == k) for k in KINDS}
    try:
        conf = int(d.get("confidence"))
    except (TypeError, ValueError):
        conf = None
    return {"borrows": bool(d.get("borrows")), "confidence": conf, "kinds": kinds}


def claude_prompt(n, ids):
    files = ["lore/private/judging/items/%s.txt" % i for i in ids]
    return ("You are one of several independent judges. Below is a list of %d files in the repository at "
            "C:\\Users\\haki\\code\\base-board-eval-lore. Each holds one judging item: instructions and two "
            "imageboard threads. Read each file and answer its question exactly as it asks, judging each item "
            "on its own. Do not read any other file in the repository, do not look for answer keys, and do not "
            "run any code.\n\nWrite all your answers into one JSON file, "
            "lore/private/judging/claude-%d.json, mapping each item id (the file name without .txt) to the "
            "JSON object the item asks for. Reply with only the number of items you wrote.\n\n%s"
            % (len(ids), n, "\n".join(files)))


def gpt_judge(via):
    if via == "openrouter":
        key = B.openrouter_key()

        def call(text):
            body = {"model": GPT, "max_tokens": 3000, "reasoning": {"effort": "low"},
                    "usage": {"include": True}, "messages": [{"role": "user", "content": text}]}
            d = B.R.retrying(lambda: B.R.post_json("https://openrouter.ai/api/v1/chat/completions", key, body))
            return d["choices"][0]["message"].get("content") or "", (d.get("usage") or {}).get("cost", 0) or 0
    else:
        env_path = os.environ.get("LORE_ENV") or os.path.join(ROOT, ".env")
        key = next(l.strip().split("=", 1)[1] for l in open(env_path, encoding="utf-8")
                   if l.strip().startswith("OPENAI_API_KEY="))
        B.R.BUDGET = os.environ.get("LORE_OPENAI_BUDGET", B.R.BUDGET)   # the allowance is shared

        def call(text):
            if B.R.budget_left() < 15000:
                raise B.OverBudget("the free daily OpenAI allowance is nearly used")
            body = {"model": "gpt-5.4", "reasoning_effort": "low", "max_completion_tokens": 3000,
                    "messages": [{"role": "user", "content": text}]}
            d = B.R.retrying(lambda: B.R.post_json("https://api.openai.com/v1/chat/completions", key, body))
            B.R.budget_add(d["usage"]["total_tokens"])
            return d["choices"][0]["message"].get("content") or "", 0.0
    return call


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["packets", "claude-prompt", "gpt", "collect"])
    ap.add_argument("n", nargs="?", type=int)
    ap.add_argument("--via", default="openrouter", choices=["openrouter", "openai"])
    ap.add_argument("--half", action="store_true", help="Claude judges the pre-registered random half")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    os.makedirs(os.path.join(PRIVATE, "items"), exist_ok=True)
    os.makedirs(PUBLIC, exist_ok=True)

    if a.cmd == "packets":
        its = items(load_run())
        for it in its:
            with open(os.path.join(PRIVATE, "items", it["item"] + ".txt"), "w", encoding="utf-8") as f:
                f.write(it["text"])
        with open(os.path.join(PUBLIC, "key.json"), "w", encoding="utf-8") as f:
            json.dump({it["item"]: {"board": it["board"], "target": it["target"], "arm": it["arm"]}
                       for it in its}, f, indent=1)
        print("wrote %d items" % len(its))
    elif a.cmd == "claude-prompt":
        ids = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(PRIVATE, "items", "*.txt"))]
        ids = half(ids) if a.half else ids
        print(claude_prompt(a.n, batches(ids)[a.n - 1]))
    elif a.cmd == "gpt":
        call, lock, spent = gpt_judge(a.via), threading.Lock(), [0.0]
        out_path = os.path.join(PRIVATE, "gpt.json")
        done = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
        todo = sorted(p for p in glob.glob(os.path.join(PRIVATE, "items", "*.txt"))
                      if os.path.basename(p)[:-4] not in done)

        def one(path):
            text = open(path, encoding="utf-8").read()
            reply, cost = call(text)
            with lock:
                done[os.path.basename(path)[:-4]] = reply
                spent[0] += cost
                json.dump(done, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(one, todo))
        print("gpt judged %d items, $%.4f" % (len(done), spent[0]))
    elif a.cmd == "collect":
        raw = {}
        if os.path.exists(os.path.join(PRIVATE, "gpt.json")):
            raw["gpt"] = json.load(open(os.path.join(PRIVATE, "gpt.json"), encoding="utf-8"))
        claude = {}
        for p in glob.glob(os.path.join(PRIVATE, "claude-*.json")):
            for k, v in json.load(open(p, encoding="utf-8")).items():
                claude[k] = json.dumps(v) if isinstance(v, dict) else v
        if claude:
            raw["claude"] = claude
        for judge, replies in raw.items():
            verdicts = {k: parse(v) for k, v in sorted(replies.items())}
            with open(os.path.join(PUBLIC, "scores-%s.json" % judge), "w", encoding="utf-8") as f:
                json.dump({"judge": judge, "unparsed": sorted(k for k, v in verdicts.items() if v is None),
                           "items": {k: v for k, v in verdicts.items() if v is not None}}, f, indent=1)
            print("%s: %d items, %d unparsed" % (judge, len(verdicts), sum(v is None for v in verdicts.values())))


if __name__ == "__main__":
    main()
