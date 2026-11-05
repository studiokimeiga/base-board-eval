#!/usr/bin/env python3
"""Round 3 blind judging.

  packets  write judging/r3/opener-N.txt (threads lettered at random) and r3/key.json
  gpt      score every packet with gpt-5.4 (free-tier project key), r3/scores-gpt.json
  report   unblind r3/scores-claude-*.json and r3/scores-gpt.json, average per model

The rubric text is identical for both judges.
"""
import glob, json, os, random, re, sys, time, urllib.request, collections
import packet_record as PR          # binds scores-*.json to the packets they were made against

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
ROOT = os.path.dirname(SPIKE)
# `round3_judge.py packets r4` judges round 4 instead (its own folder, arms and key)
ROUND = sys.argv[2] if len(sys.argv) > 2 else "r3"
R3 = os.path.join(HERE, ROUND)
ARMS = {"r3": ["qwen235", "hermes405", "mix", "qwenhot", "pick", "kimi", "echo"],
        # round 4: the Hermes fixes, Gemini in English, and three references from rounds 2-3
        "r4": ["hermes405", "hermespen", "hermesguard", "hermespick", "gemini", "pick", "kimi"],
        # round 5: does a picker lift Gemini the way it lifted Qwen?
        "r5": ["geminipick", "gemini", "pick", "kimi"],
        # round 6: does temperature buy Gemini humour? same threads at 1.0, 1.5, 1.9
        "r6": ["gemini", "geminit15", "geminit19", "qwen235", "qwent14", "qwent18"],
        # round 7: a cast of roles instead of one model playing everyone
        "r7": ["gemini", "roles", "naif", "naifroles"],
        # round 8: roles with post length controlled; gpt-5.4 gets the same rubric as Claude
        "r8": ["gemini", "roles", "rolesshort"]}[ROUND]
NAMES = {"qwen235": "Qwen3-235B (round 2)", "hermes405": "Hermes 3 405B (round 2)",
         "mix": "Qwen + Hermes mixed cast", "qwenhot": "Qwen3-235B, hotter sampling",
         "pick": "Qwen3-235B best-of-3, gpt-5.4 picker", "kimi": "Kimi K3 (chat)",
         "echo": "Echo (chat)", "hermespen": "Hermes 405B + repetition penalties",
         "hermesguard": "Hermes 405B + penalties + breakdown guard",
         "hermespick": "Hermes 405B + penalties + guard + best-of-3 picker",
         "gemini": "Gemini 3.8 Flash (chat)", "geminipick": "Gemini 3.8 Flash best-of-3, gpt-5.4 picker",
         "geminit15": "Gemini 3.8 Flash, temperature 1.5", "geminit19": "Gemini 3.8 Flash, temperature 1.9",
         "qwent14": "Qwen3-235B raw, temperature 1.4 / min_p 0.1", "qwent18": "Qwen3-235B raw, temperature 1.8 / min_p 0.15",
         "roles": "Gemini, posters given temperaments", "naif": "Gemini + 2 small-model naif posters",
         "naifroles": "Gemini + naifs + temperaments",
         "rolesshort": "Gemini, temperaments + per-role post length"}
RUBRIC_V2 = """The goal of the project: a board of AI posters that a person would genuinely enjoy reading and want to jump into. That means flashes of brilliance and humour, ideas that emerge and develop between posters, AND enough coherence to follow. It does not need to be paranormal, and an advice column is boring. A good board also has contrast: not every poster should be performing; ordinary, skeptical, sincere or confused posters make the strange or funny parts land. Posts marked "[post withheld]" were filtered for safety, so ignore them. Note "walls of text" in main_failure if length hurts.

Count humour when a line is genuinely funny, including deadpan, absurd, or sincerely-wrong posters who don't know they're funny, not only deliberate jokes.

Score every thread from 1 to 5 on each of these:
- interest: would a reader want to keep reading or reply? (1 = would close it, 5 = would screenshot it)
- humour: real laughs (1 = none, 5 = several real laughs)
- emergence: something nobody planted in the opener appears and other posters pick it up and develop it (1 = none, 5 = a genuine shared bit that grows)
- coherence: posters respond to each other and the thread is followable (1 = word salad, 5 = fully followable)
- variety: do the posters feel like different people with different voices and attitudes? (1 = everyone sounds the same, 5 = a real mix of people)
Also give an overall 1-5.

Then:
- best_lines: up to 3 of the thread's best lines, quoted exactly, with the post number.
- main_failure: one short phrase.

Be calibrated and harsh. A 5 should be rare. Compare within the opener so your scale is consistent."""
RUBRIC = """The goal of the project: a board of AI posters that a person would genuinely enjoy reading and want to jump into. That means flashes of brilliance and humour, ideas that emerge and develop between posters, AND enough coherence to follow. It does not need to be paranormal, and an advice column is boring. Posts marked "[post withheld]" were filtered for safety, so ignore them and don't penalise them.

Score every thread from 1 to 5 on each of these:
- interest: would a reader want to keep reading or reply? (1 = would close it, 5 = would screenshot it and send it to a friend)
- humour: actually funny lines, deadpan, absurdity that lands (1 = none or unintentionally bad, 5 = several real laughs)
- emergence: something nobody planted in the opener appears and gets picked up and developed by other posters, like a coinage, a shifting reference, a running joke or an escalating shared premise (1 = none, 5 = a genuine shared bit that grows)
- coherence: posters respond to each other and the thread is followable (1 = word salad or everyone talking past each other, 5 = fully followable)
Also give each thread an overall 1-5.

Then:
- best_lines: up to 3 of the thread's best lines, quoted exactly, with the post number.
- main_failure: one short phrase, such as "repetition loop", "advice column", "derails into nonsense", "generic", "chant", "page junk", "creepypasta cliche", or "none".

Be calibrated and harsh. A 5 should be rare. Judge each thread on its own merits, but compare within the same opener so your scale is consistent."""


def load(arm):
    p = os.path.join(SPIKE, "remote", "bakeoff-%s.json" % arm)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def packets():
    os.makedirs(R3, exist_ok=True)
    data = {a: load(a) for a in ARMS}
    data = {a: d for a, d in data.items() if d}
    openers = [t["opener"] for t in data[ARMS[0]]["threads"]]
    rng, key, texts = random.Random({"r3": 31337, "r4": 4747}.get(ROUND, 5353)), {}, {}
    for i, op in enumerate(openers):
        arms = [a for a in data if any(t["opener"] == op for t in data[a]["threads"])]
        rng.shuffle(arms)
        letters = "ABCDEFGH"[:len(arms)]
        key[str(i + 1)] = dict(zip(letters, arms))
        out = ["OPENER %d: %s\n" % (i + 1, op)]
        for L, a in zip(letters, arms):
            t = next(t for t in data[a]["threads"] if t["opener"] == op)
            out.append("=" * 20 + "\nTHREAD %s\n" % L + "=" * 20)
            op_who = t["posts"][0]["who"]
            for n, p in enumerate(t["posts"]):
                out.append("%d. %s%s: %s" % (n + 1, p["who"], " (OP)" if p["who"] == op_who else "",
                                            p["text"] or "(empty)"))
            out.append("")
        texts["opener-%d" % (i + 1)] = "\n".join(out)
    # refuses, writing nothing, if a packet some judge already scored would change
    PR.write(R3, texts, {"opener-" + i: letters for i, letters in key.items()})
    json.dump(key, open(os.path.join(R3, "key.json"), "w"), indent=1)
    print("packets:", {k: len(v) for k, v in key.items()})


def key_of(key):
    return lambda name: key.get(name.split("-")[1])


def gpt():
    PR.check(R3, key_of(json.load(open(os.path.join(R3, "key.json")))))
    record = PR.load(R3)
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".env"))
               if "=" in l and not l.lstrip().startswith("#"))
    sys.path.insert(0, SPIKE)
    from round3 import budget_add, budget_left
    out_path = os.path.join(R3, "scores-gpt.json")
    scores = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    for f in sorted(glob.glob(os.path.join(R3, "opener-*.txt"))):
        name = os.path.basename(f)[:-4]
        if name in scores:
            continue
        if not PR.packet_matches(R3, name, record):
            raise SystemExit("%s isn't the packet recorded in %s; rerun `packets`" % (name, PR.RECORD))
        # same model either way; --paid routes through OpenRouter once the free day is used up
        paid = "--paid" in sys.argv
        if not paid and budget_left() < 25000:
            print("stopping: free daily budget nearly used (rerun with --paid)"); break
        text = open(f, encoding="utf-8").read()
        prompt = ("You are a blind judge for an experiment on AI-generated imageboard threads. "
                  "Below is one opener and several threads (lettered) that continue it, each written "
                  "by a different, unnamed model.\n\n" + (RUBRIC_V2 if ROUND >= "r8" else RUBRIC) +
                  '\n\nReply with ONLY a JSON object: {"A": {"interest":n,"humour":n,"emergence":n,'
                  '"coherence":n,"variety":n,"overall":n,"best_lines":["#7: ..."],"main_failure":"..."}, "B": {...}, ...}'
                  "\n\n" + text)
        if paid:
            url, key = "https://openrouter.ai/api/v1/chat/completions", env["OPENROUTER_API_KEY"]
            body = {"model": "openai/gpt-5.4", "reasoning": {"effort": "low"},
                    "messages": [{"role": "user", "content": prompt}]}
        else:
            url, key = "https://api.openai.com/v1/chat/completions", env["OPENAI_API_KEY"]
            body = {"model": "gpt-5.4", "reasoning_effort": "low",
                    "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        d = json.load(urllib.request.urlopen(req, timeout=600))
        if not paid:
            budget_add(d["usage"]["total_tokens"])
        raw = d["choices"][0]["message"]["content"]
        scores[name] = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        json.dump(scores, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(name, "scored,", d["usage"]["total_tokens"], "tokens", flush=True)


def report():
    key = json.load(open(os.path.join(R3, "key.json")))
    PR.check(R3, key_of(key))
    judges = {"claude": {}, "gpt": {}}
    for f in glob.glob(os.path.join(R3, "scores-claude-*.json")):
        judges["claude"].update(json.load(open(f, encoding="utf-8")))
    if os.path.exists(os.path.join(R3, "scores-gpt.json")):
        judges["gpt"] = json.load(open(os.path.join(R3, "scores-gpt.json"), encoding="utf-8"))
    dims = ["overall", "interest", "humour", "emergence", "coherence"]
    by_thread = {}
    for j, S in judges.items():
        agg = collections.defaultdict(lambda: collections.defaultdict(list))
        for op, threads in S.items():
            i = op.split("-")[1]
            for L, v in threads.items():
                arm = key[i][L]
                for d in dims:
                    agg[arm][d].append(v[d])
                by_thread.setdefault(i, {}).setdefault(arm, {})[j] = v
        if not agg:
            continue
        print("\n== judge: %s ==" % j)
        print("%-38s %7s %8s %6s %9s %9s %4s" % ("model", *dims, "n"))
        for a in sorted(agg, key=lambda a: -sum(agg[a]["overall"]) / len(agg[a]["overall"])):
            m = [sum(agg[a][d]) / len(agg[a][d]) for d in dims]
            print("%-38s %7.2f %8.2f %6.2f %9.2f %9.2f %4d" % (NAMES[a], *m, len(agg[a]["overall"])))
    json.dump(by_thread, open(os.path.join(R3, "by-thread.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    {"packets": packets, "gpt": gpt, "report": report}[sys.argv[1]]()
