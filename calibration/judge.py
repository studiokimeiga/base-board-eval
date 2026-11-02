#!/usr/bin/env python3
"""AI judges for the blind calibration set, on the reader's own scales (rubric.json).

  packets                 write packets/<id>.txt, one thread per file, for the Claude judges
  claude-prompt PASS N    print the exact prompt for Claude pass PASS (A or B), batch N of 3
  gpt [--paid]            score every item with gpt-5.4, one call per item; scores-gpt.json

Add --set r9 to any of them for the round 9 set: items-r9.json, packets-r9/, scores-r9-gpt.json,
and its Claude replies saved as scores-r9-claude-<PASS><N>.json.

Claude judges run as subagents (as in the bake-off): each reads a third of the packets (10 of
the calibration set's, 6 of the round 9 set's), rates every thread on its own, and its JSON reply
is saved as scores-claude-<PASS><N>.json. Two passes split and order the items differently, so
their agreement shows how stable the judge is. gpt-5.4 uses the free daily OpenAI allowance
tracked in spike/openai_budget.json and stops before it runs out; --paid sends the same request
through OpenRouter instead.
"""
import json, os, random, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEEDS = {"A": 101, "B": 202}
BATCHES = 3
# Every thread in the round 9 set is Gemini's, so its judges aren't told this
MIXED = " Some threads were written by small base models and some by large chat models; nothing says which."


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def paths(s=""):
    """A set's items, packet folder and gpt-5.4 scores: the calibration set's, or with -<s> added."""
    x = "-" + s if s else ""
    return (os.path.join(HERE, "items%s.json" % x), os.path.join(HERE, "packets" + x),
            os.path.join(HERE, "scores%s-gpt.json" % x))


def items(s=""):
    return read_json(paths(s)[0])["items"]


def thread_text(item):
    return "\n".join("%d. %s%s: %s" % (p["n"], p["who"], " (OP)" if p["op"] else "", p["text"] or "(empty)")
                     for p in item["posts"])


def scales_text(s=""):
    r = read_json(os.path.join(HERE, "rubric.json"))
    lines = ["- %s: %s (1 = %s, 5 = %s)" % (c["id"], c["ask"], c["low"], c["high"]) for c in r["scales"]]
    lines.append("- repost: true or false. %s" % r["repost"])
    return r["intro"].replace(MIXED, "") if s == "r9" else r["intro"], "\n".join(lines)


SHAPE = ('{"believable":n,"interest":n,"joke":n,"deadpan":n,"overall":n,"repost":true,'
         '"best_lines":["#7: ..."],"main_failure":"..."}')


def gpt_prompt(item, s=""):
    intro, scales = scales_text(s)
    return ("You are rating one thread from an experiment on AI-generated imageboard threads. "
            + intro + "\n\nScales:\n" + scales +
            '\n\nThen best_lines: up to 3 of the thread\'s best lines, quoted exactly, with the post '
            'number like "#7: ..."; and main_failure: one short phrase.\n\nReply with ONLY a JSON '
            "object: " + SHAPE + "\n\nTHREAD\n" + thread_text(item))


def batches(pass_name, s=""):
    ids = sorted(i["id"] for i in items(s))
    random.Random(SEEDS[pass_name]).shuffle(ids)
    return [ids[k::BATCHES] for k in range(BATCHES)]


def claude_prompt(pass_name, n, s=""):
    intro, scales = scales_text(s)
    ids = batches(pass_name, s)[n - 1]
    files = "\n".join("- " + os.path.join(paths(s)[1], i + ".txt") for i in ids)
    return ("You are a blind judge for an experiment on AI-generated imageboard threads. Each file "
            "below holds one thread. Open ONLY these files, in this order, and nothing else in that "
            "folder or its parents:\n\n" + files + "\n\n" + intro + " Rate each thread on its own, "
            "as if it were the only one you had read; don't rank them against each other.\n\nScales:\n"
            + scales + '\n\nThen best_lines: up to 3 of the thread\'s best lines, quoted exactly, with '
            'the post number like "#7: ..."; and main_failure: one short phrase.\n\nReply with ONLY a '
            'JSON object keyed by the file name without .txt, in the order above (no prose): {"%s": %s, ...}'
            % (ids[0], SHAPE))


def packets(s=""):
    folder = paths(s)[1]
    os.makedirs(folder, exist_ok=True)
    for item in items(s):
        with open(os.path.join(folder, item["id"] + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(thread_text(item) + "\n")
    print("wrote", len(items(s)), "packets to", folder)


def gpt(s=""):
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "spike"))
    from round3 import ENV, budget_add, budget_left
    paid = "--paid" in sys.argv
    out = paths(s)[2]
    scores = read_json(out) if os.path.exists(out) else {}
    for item in items(s):
        if item["id"] in scores:
            continue
        if not paid and budget_left() < 15000:
            print("stopping: free daily allowance nearly used (rerun tomorrow, or with --paid)")
            break
        msg = [{"role": "user", "content": gpt_prompt(item, s)}]
        if paid:
            url, key = "https://openrouter.ai/api/v1/chat/completions", ENV["OPENROUTER_API_KEY"]
            body = {"model": "openai/gpt-5.4", "reasoning": {"effort": "low"}, "messages": msg}
        else:
            url, key = "https://api.openai.com/v1/chat/completions", ENV["OPENAI_API_KEY"]
            body = {"model": "gpt-5.4", "reasoning_effort": "low", "messages": msg}
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.load(r)
        if not paid:
            budget_add(d["usage"]["total_tokens"])
        raw = d["choices"][0]["message"]["content"]
        scores[item["id"]] = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(scores, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(item["id"], "scored,", d["usage"]["total_tokens"], "tokens", flush=True)


if __name__ == "__main__":
    args, s = sys.argv[1:], ""
    if "--set" in args:
        k = args.index("--set")
        s = {"calibration": "", "r9": "r9"}.get(args[k + 1] if k + 1 < len(args) else "", "?")
        del args[k:k + 2]
    cmd = args[0] if args and s != "?" else ""
    if cmd == "packets":
        packets(s)
    elif cmd == "claude-prompt":
        print(claude_prompt(args[1], int(args[2]), s))
    elif cmd == "gpt":
        gpt(s)
    else:
        print(__doc__)
