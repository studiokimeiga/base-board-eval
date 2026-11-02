#!/usr/bin/env python3
"""AI judges for the blind calibration set, on the reader's own scales (rubric.json).

  packets                 write packets/<id>.txt, one thread per file, for the Claude judges
  claude-prompt PASS N    print the exact prompt for Claude pass PASS (A or B), batch N of 3
  gpt [--paid]            score every item with gpt-5.4, one call per item; scores-gpt.json

Claude judges run as subagents (as in the bake-off): each reads 10 packets, rates every
thread on its own, and its JSON reply is saved as scores-claude-<PASS><N>.json. Two passes
split and order the items differently, so their agreement shows how stable the judge is.
gpt-5.4 uses the free daily OpenAI allowance tracked in spike/openai_budget.json and stops
before it runs out; --paid sends the same request through OpenRouter instead.
"""
import json, os, random, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACKETS = os.path.join(HERE, "packets")
SEEDS = {"A": 101, "B": 202}
BATCHES = 3


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def items():
    return read_json(os.path.join(HERE, "items.json"))["items"]


def thread_text(item):
    return "\n".join("%d. %s%s: %s" % (p["n"], p["who"], " (OP)" if p["op"] else "", p["text"] or "(empty)")
                     for p in item["posts"])


def scales_text():
    r = read_json(os.path.join(HERE, "rubric.json"))
    lines = ["- %s: %s (1 = %s, 5 = %s)" % (s["id"], s["ask"], s["low"], s["high"]) for s in r["scales"]]
    lines.append("- repost: true or false. %s" % r["repost"])
    return r["intro"], "\n".join(lines)


SHAPE = ('{"believable":n,"interest":n,"joke":n,"deadpan":n,"overall":n,"repost":true,'
         '"best_lines":["#7: ..."],"main_failure":"..."}')


def gpt_prompt(item):
    intro, scales = scales_text()
    return ("You are rating one thread from an experiment on AI-generated imageboard threads. "
            + intro + "\n\nScales:\n" + scales +
            '\n\nThen best_lines: up to 3 of the thread\'s best lines, quoted exactly, with the post '
            'number like "#7: ..."; and main_failure: one short phrase.\n\nReply with ONLY a JSON '
            "object: " + SHAPE + "\n\nTHREAD\n" + thread_text(item))


def batches(pass_name):
    ids = sorted(i["id"] for i in items())
    random.Random(SEEDS[pass_name]).shuffle(ids)
    return [ids[k::BATCHES] for k in range(BATCHES)]


def claude_prompt(pass_name, n):
    intro, scales = scales_text()
    ids = batches(pass_name)[n - 1]
    files = "\n".join("- " + os.path.join(PACKETS, i + ".txt") for i in ids)
    return ("You are a blind judge for an experiment on AI-generated imageboard threads. Each file "
            "below holds one thread. Open ONLY these files, in this order, and nothing else in that "
            "folder or its parents:\n\n" + files + "\n\n" + intro + " Rate each thread on its own, "
            "as if it were the only one you had read; don't rank them against each other.\n\nScales:\n"
            + scales + '\n\nThen best_lines: up to 3 of the thread\'s best lines, quoted exactly, with '
            'the post number like "#7: ..."; and main_failure: one short phrase.\n\nReply with ONLY a '
            'JSON object keyed by the file name without .txt, in the order above (no prose): {"%s": %s, ...}'
            % (ids[0], SHAPE))


def packets():
    os.makedirs(PACKETS, exist_ok=True)
    for item in items():
        with open(os.path.join(PACKETS, item["id"] + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(thread_text(item) + "\n")
    print("wrote", len(items()), "packets to", PACKETS)


def gpt():
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "spike"))
    from round3 import ENV, budget_add, budget_left
    paid = "--paid" in sys.argv
    out = os.path.join(HERE, "scores-gpt.json")
    scores = read_json(out) if os.path.exists(out) else {}
    for item in items():
        if item["id"] in scores:
            continue
        if not paid and budget_left() < 15000:
            print("stopping: free daily allowance nearly used (rerun tomorrow, or with --paid)")
            break
        msg = [{"role": "user", "content": gpt_prompt(item)}]
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "packets":
        packets()
    elif cmd == "claude-prompt":
        print(claude_prompt(sys.argv[2], int(sys.argv[3])))
    elif cmd == "gpt":
        gpt()
    else:
        print(__doc__)
