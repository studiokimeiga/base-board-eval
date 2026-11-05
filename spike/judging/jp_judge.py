#!/usr/bin/env python3
"""Japanese bake-off blind judging.

  packets  write judging/jp/<fmt>-opener-N.txt (threads lettered at random) and jp/key.json
  gpt      score packets with gpt-5.4 on the free-tier project key, jp/scores-gpt.json
  report   unblind jp/scores-claude-*.json and jp/scores-gpt.json, average per model and format
"""
import glob, json, os, random, sys, urllib.request, collections
import packet_record as PR          # binds scores-*.json to the packets they were made against

HERE = os.path.dirname(os.path.abspath(__file__))
SPIKE = os.path.dirname(HERE)
ROOT = os.path.dirname(SPIKE)
# `jp_judge.py packets r5` judges the Gemini picker follow-up (5ch only) in its own folder
ROUND = sys.argv[2] if len(sys.argv) > 2 else ""
JP = os.path.join(HERE, "jp" + ("-" + ROUND if ROUND else ""))
ARMS = (["geminipick", "gemini", "qwen235", "gpt54"] if ROUND == "r5" else
        ["qwen235", "swallow70", "swallow70dry", "g31", "deepseek", "gpt54", "gemini", "sonnet", "kimi"])
FORMATS = ("5ch",) if ROUND == "r5" else ("5ch", "named")
NAMES = {"qwen235": "Qwen3-235B (raw)", "swallow70": "Llama-3.3-Swallow-70B base (raw)",
         "swallow70dry": "Swallow-70B base + XTC/DRY (raw)",
         "g31": "gemma-4-31B base (raw)", "deepseek": "DeepSeek V4 Flash (chat)",
         "gpt54": "GPT-5.4 (chat)", "gemini": "Gemini 3.8 Flash (chat)",
         "sonnet": "Claude Sonnet 5.5 (chat)", "kimi": "Kimi K3 (chat)",
         "geminipick": "Gemini 3.8 Flash best-of-3, gpt-5.4 picker"}
DIMS = ["overall", "naturalness", "interest", "humour", "emergence", "coherence"]
RUBRIC = """These threads are for a Japanese board that a learner will read to absorb real, native internet Japanese. Realism matters more than anything: the learner has dictionary tools, so difficulty is NOT a problem. Slang, abbreviations, ｗ/草, net memes and casual grammar are good if they are what real posters would write. Posts marked "[post withheld]" were filtered for safety, so ignore them.

Score every thread from 1 to 5 on each of these:
- naturalness: does it read like real Japanese netizens on a board like this (1 = translated-sounding, textbook, or an AI assistant giving tidy advice; 5 = indistinguishable from real posters)
- interest: would a reader want to keep reading or reply? (1 = would close it, 5 = would screenshot it)
- humour: real laughs, deadpan, absurdity that lands (1 = none, 5 = several real laughs)
- emergence: something nobody planted in the opener appears and other posters pick it up and develop it, like a coinage, a running joke, a shifting reference or an escalating shared premise (1 = none, 5 = a genuine shared bit that grows)
- coherence: posters respond to each other and the thread is followable (1 = incoherent, 5 = fully followable)
Also give an overall 1-5, weighting naturalness and interest most.

Then:
- best_lines: up to 3 of the best lines, quoted exactly in Japanese, with the post number.
- main_failure: one short English phrase, such as "assistant tone", "translationese", "advice column", "repetition loop", "derails into nonsense", "page junk", "role confusion", or "none".

Be calibrated and harsh. A 5 should be rare. Compare within the packet so your scale is consistent."""


def load(arm, fmt):
    p = os.path.join(SPIKE, "remote", "jp-%s-%s.json" % (arm, fmt))
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def packets():
    os.makedirs(JP, exist_ok=True)
    rng, key, texts = random.Random(8848), {}, {}
    for fmt in FORMATS:
        data = {a: load(a, fmt) for a in ARMS}
        data = {a: d for a, d in data.items() if d}
        openers = [t["opener"] for t in next(iter(data.values()))["threads"]]
        for i, op in enumerate(openers):
            arms = [a for a in data if any(t["opener"] == op for t in data[a]["threads"])]
            rng.shuffle(arms)
            letters = "ABCDEFGHI"[:len(arms)]
            name = "%s-opener-%d" % (fmt, i + 1)
            key[name] = dict(zip(letters, arms))
            out = ["OPENER (%s format): %s\n" % (fmt, op)]
            for L, a in zip(letters, arms):
                t = next(t for t in data[a]["threads"] if t["opener"] == op)
                out.append("=" * 20 + "\nTHREAD %s\n" % L + "=" * 20)
                for p in t["posts"]:
                    who = ("ID:" + p["who"]) if fmt == "5ch" else p["who"]
                    out.append("%d %s%s: %s" % (p["n"], who, " (OP)" if p["who"] == t["op"] else "",
                                                p["text"] or "(empty)"))
                out.append("")
            texts[name] = "\n".join(out)
    # refuses, writing nothing, if a packet some judge already scored would change
    PR.write(JP, texts, key)
    json.dump(key, open(os.path.join(JP, "key.json"), "w"), indent=1)
    print("packets:", {k: len(v) for k, v in key.items()})


def gpt():
    PR.check(JP, json.load(open(os.path.join(JP, "key.json"))).get)
    record = PR.load(JP)
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".env"))
               if "=" in l and not l.lstrip().startswith("#"))
    sys.path.insert(0, SPIKE)
    from round3 import budget_add, budget_left
    path = os.path.join(JP, "scores-gpt.json")
    scores = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for f in sorted(glob.glob(os.path.join(JP, "*-opener-*.txt"))):
        name = os.path.basename(f)[:-4]
        if name in scores:
            continue
        if not PR.packet_matches(JP, name, record):
            raise SystemExit("%s isn't the packet recorded in %s; rerun `packets`" % (name, PR.RECORD))
        if budget_left() < 30000:
            print("stopping: free daily budget nearly used"); break
        prompt = ("You are a blind judge, fluent in Japanese and Japanese internet culture. Below is one "
                  "opener and several threads (lettered) continuing it, each written by a different, "
                  "unnamed model.\n\n" + RUBRIC +
                  '\n\nReply with ONLY a JSON object: {"A": {"naturalness":n,"interest":n,"humour":n,'
                  '"emergence":n,"coherence":n,"overall":n,"best_lines":["#7: ..."],"main_failure":"..."},'
                  ' "B": {...}, ...}\n\n' + open(f, encoding="utf-8").read())
        body = {"model": "gpt-5.4", "reasoning_effort": "low",
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + env["OPENAI_API_KEY"]})
        d = json.load(urllib.request.urlopen(req, timeout=600))
        budget_add(d["usage"]["total_tokens"])
        raw = d["choices"][0]["message"]["content"]
        scores[name] = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        json.dump(scores, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(name, "scored,", d["usage"]["total_tokens"], "tokens", flush=True)


def report():
    key = json.load(open(os.path.join(JP, "key.json")))
    PR.check(JP, key.get)
    judges = {"claude": {}, "gpt": {}}
    for f in glob.glob(os.path.join(JP, "scores-claude-*.json")):
        judges["claude"].update(json.load(open(f, encoding="utf-8")))
    if os.path.exists(os.path.join(JP, "scores-gpt.json")):
        judges["gpt"] = json.load(open(os.path.join(JP, "scores-gpt.json"), encoding="utf-8"))
    by_thread = {}
    for j, S in judges.items():
        if not S:
            continue
        for fmt in ("5ch", "named", "both"):
            agg = collections.defaultdict(lambda: collections.defaultdict(list))
            for name, threads in S.items():
                if fmt != "both" and not name.startswith(fmt):
                    continue
                for L, v in threads.items():
                    arm = key[name][L]
                    for d in DIMS:
                        agg[arm][d].append(v.get(d, 0))
                    by_thread.setdefault(name, {}).setdefault(arm, {})[j] = v
            print("\n== judge: %s | format: %s ==" % (j, fmt))
            print("%-36s %s %4s" % ("model", " ".join("%11s" % d for d in DIMS), "n"))
            for a in sorted(agg, key=lambda a: -sum(agg[a]["overall"]) / len(agg[a]["overall"])):
                print("%-36s %s %4d" % (NAMES[a], " ".join("%11.2f" % (sum(agg[a][d]) / len(agg[a][d]))
                                                          for d in DIMS), len(agg[a]["overall"])))
    json.dump(by_thread, open(os.path.join(JP, "by-thread.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    {"packets": packets, "gpt": gpt, "report": report}[sys.argv[1]]()
