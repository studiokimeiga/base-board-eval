#!/usr/bin/env python3
"""Round 3 blind judging.

  packets  write judging/r3/opener-N.txt (threads lettered at random) and r3/key.json
  gpt      score every packet with gpt-5.4 (free-tier project key), r3/scores-gpt.json
  report   unblind r3/scores-claude-*.json and r3/scores-gpt.json, average per model

The rubric text is identical for both judges.

Round 9 (spike/PREREGISTRATION-ROUND9.md) adds:

  packets r9          opener-N-vK.txt: every packet in 5 letter orders (a Latin square per opener),
                      plus tag-N-L.txt, one thread per file for the drift tagger, and scaffold.json
  gpt r9 --paid       40 packet readings; replies are checked, retried, and their usage logged
  tag_gpt r9          gpt-5.4 labels the horror-register posts in each tag file, tags-gpt.json
  blind r9 DIR        copy the packets and tag files to DIR, alone, and write the Claude prompts
                      (prompts/r9_claude_judge-*.txt, r9_claude_tag-*.txt) pointing there
  collect r9 DIR      check the Claude judges' and taggers' JSON in DIR and copy it into r9/
"""
import glob, json, os, random, re, shutil, sys, threading, time, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor

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
        "r8": ["gemini", "roles", "rolesshort"],
        # round 9: an occasional small-model post; the /x/ label against a neutral header
        "r9": ["gemini9", "rolesshort9", "rolesshort9naif", "gemini9neutral", "rolesshort9neutral"]}[ROUND]
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
         "rolesshort": "Gemini, temperaments + per-role post length",
         "gemini9": "Gemini 3.8 Flash (chat), /x/ header",
         "rolesshort9": "Gemini, short temperaments, /x/ header",
         "rolesshort9naif": "short temperaments + 1 post in 8 by gemma-4-E4B base, /x/ header",
         "gemini9neutral": "Gemini 3.8 Flash (chat), neutral header",
         "rolesshort9neutral": "Gemini, short temperaments, neutral header"}
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


def packet_text(i, op, letters, data):
    """One opener's threads in letter order, the format every judge has read since round 3."""
    out = ["OPENER %d: %s\n" % (i + 1, op)]
    for L, a in letters.items():
        t = next(t for t in data[a]["threads"] if t["opener"] == op)
        out.append("=" * 20 + "\nTHREAD %s\n" % L + "=" * 20)
        op_who = t["posts"][0]["who"]
        for n, p in enumerate(t["posts"]):
            out.append("%d. %s%s: %s" % (n + 1, p["who"], " (OP)" if p["who"] == op_who else "",
                                        p["text"] or "(empty)"))
        out.append("")
    return "\n".join(out)


def write(path, text):
    """LF line endings everywhere (rounds 1-8 were written in Windows text mode, so CRLF)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def dump(obj, path):
    write(path, json.dumps(obj, ensure_ascii=False, indent=1))


def read_json(path, default=None):
    if default is not None and not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def packets():
    os.makedirs(R3, exist_ok=True)
    data = {a: load(a) for a in ARMS}
    data = {a: d for a, d in data.items() if d}
    openers = [t["opener"] for t in data[ARMS[0]]["threads"]]
    if ROUND == "r9":
        return latin_packets(data, openers)
    rng, key = random.Random({"r3": 31337, "r4": 4747}.get(ROUND, 5353)), {}
    for i, op in enumerate(openers):
        arms = [a for a in data if any(t["opener"] == op for t in data[a]["threads"])]
        rng.shuffle(arms)
        letters = "ABCDEFGH"[:len(arms)]
        key[i + 1] = dict(zip(letters, arms))
        open(os.path.join(R3, "opener-%d.txt" % (i + 1)), "w", encoding="utf-8").write(
            packet_text(i, op, key[i + 1], data))
    json.dump(key, open(os.path.join(R3, "key.json"), "w"), indent=1)
    print("packets:", {k: len(v) for k, v in key.items()})


LATIN_SEED = 9393


def latin_packets(data, openers):
    """Round 9: each opener's packet in five versions, lettered by the five rotations of one random
    order, so every arm is read in every position exactly once per opener and each judge family
    reads every thread five times. Also one file per thread for the drift tagger (named by the
    thread's letter in version 1), and the scaffold's authors, which hold no model text."""
    for a in ARMS:
        if a not in data or [t["opener"] for t in data[a]["threads"]] != openers:
            raise SystemExit("%s: need all %d threads, in opener order" % (a, len(openers)))
    rng, key, scaffold = random.Random(LATIN_SEED), {}, {}
    for i, op in enumerate(openers):
        order = list(ARMS)
        rng.shuffle(order)
        for v in range(len(order)):
            name = "%d-v%d" % (i + 1, v + 1)
            key[name] = dict(zip("ABCDE", order[v:] + order[:v]))
            write(os.path.join(R3, "opener-%s.txt" % name), packet_text(i, op, key[name], data))
        for L, a in key["%d-v1" % (i + 1)].items():
            write(os.path.join(R3, "tag-%d-%s.txt" % (i + 1, L)), packet_text(i, op, {L: a}, data))
        authors = {a: [p["who"] for p in data[a]["threads"][i]["posts"]] for a in ARMS}
        if len({tuple(w) for w in authors.values()}) != 1:
            raise SystemExit("opener %d: the arms' scaffolds differ" % (i + 1))
        scaffold[i + 1] = authors[ARMS[0]]
    dump(key, os.path.join(R3, "key.json"))
    dump(scaffold, os.path.join(R3, "scaffold.json"))
    print("packets: %d readings of %d openers, %d tag files" % (len(key), len(openers), len(ARMS) * len(openers)))


# ---- asking gpt-5.4 ----
GPT_INTRO = ("You are a blind judge for an experiment on AI-generated imageboard threads. "
             "Below is one opener and several threads (lettered) that continue it, each written "
             "by a different, unnamed model.\n\n")
GPT_REPLY = ('\n\nReply with ONLY a JSON object: {"A": {"interest":n,"humour":n,"emergence":n,'
             '"coherence":n,"variety":n,"overall":n,"best_lines":["#7: ..."],"main_failure":"..."}, "B": {...}, ...}')


def rubric():
    return RUBRIC_V2 if int(ROUND[1:]) >= 8 else RUBRIC     # from round 8 on, Claude's rubric too


def read_env():
    with open(os.path.join(ROOT, ".env")) as f:
        return dict(l.strip().split("=", 1) for l in f if "=" in l and not l.lstrip().startswith("#"))


def checked_scores(s, letters):
    """One packet's scores: every letter scored, every score an integer from 1 to 5."""
    dims = ["interest", "humour", "emergence", "coherence", "overall"]
    dims += ["variety"] if rubric() is RUBRIC_V2 else []
    if sorted(s) != sorted(letters):
        raise ValueError("scored %s, the packet has %s" % (sorted(s), sorted(letters)))
    for L, v in s.items():
        for d in dims:
            if not (type(v.get(d)) is int and 1 <= v[d] <= 5):
                raise ValueError("%s %s = %r" % (L, d, v.get(d)))
        if not isinstance(v.get("main_failure"), str):
            raise ValueError("%s has no main_failure" % L)
    return s


def checked_tags(s):
    """One thread's labels: the numbers of its HORROR posts, from 2 to 24."""
    h = s.get("horror")
    if not (isinstance(h, list) and all(type(n) is int and 2 <= n <= 24 for n in h)):
        raise ValueError("bad labels %r" % (s,))
    return {"horror": sorted(set(h))}


def ask_json(prompt, paid, env, check):
    """One gpt-5.4 call (OpenRouter with --paid, else the free OpenAI allowance). A reply that isn't
    JSON or fails `check` is a technical failure, not a verdict: it is asked again, at most twice."""
    sys.path.insert(0, SPIKE)
    from round3 import post_json, retrying
    if paid:
        url, key = "https://openrouter.ai/api/v1/chat/completions", env["OPENROUTER_API_KEY"]
        body = {"model": "openai/gpt-5.4", "reasoning": {"effort": "low"}, "usage": {"include": True},
                "messages": [{"role": "user", "content": prompt}]}
    else:
        url, key = "https://api.openai.com/v1/chat/completions", env["OPENAI_API_KEY"]
        body = {"model": "gpt-5.4", "reasoning_effort": "low",
                "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(3):
        d = retrying(lambda: post_json(url, key, body, timeout=600))
        raw = d["choices"][0]["message"].get("content") or ""
        try:
            return check(json.loads(raw[raw.index("{"):raw.rindex("}") + 1])), dict(d["usage"], tries=attempt + 1)
        except ValueError as e:          # no "{", bad JSON, or a failed check
            err = e
    raise RuntimeError("no valid reply in 3 tries: %s" % err)


def ask_all(files, out_name, prompt_of, check, paid, workers):
    """Ask gpt-5.4 about each file once, resuming from out_name; usage goes to usage-<out_name>."""
    env = read_env()
    sys.path.insert(0, SPIKE)
    from round3 import budget_add, budget_left
    out_path, usage_path = os.path.join(R3, out_name), os.path.join(R3, "usage-" + out_name)
    done, usage = read_json(out_path, {}), read_json(usage_path, {})
    lock = threading.Lock()

    def one(f):
        name = os.path.basename(f)[:-4]
        if not paid and budget_left() < 25000:
            print("skipping %s: free daily budget nearly used (rerun with --paid)" % name)
            return
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        s, u = ask_json(prompt_of(text), paid, env, lambda s: check(s, text))
        if not paid:
            budget_add(u["total_tokens"])
        with lock:
            done[name], usage[name] = s, u
            dump(done, out_path)
            dump(usage, usage_path)
        print(name, "done,", u["total_tokens"], "tokens, $%s" % u.get("cost", "?"), flush=True)

    todo = [f for f in files if os.path.basename(f)[:-4] not in done]
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, todo))
    print("%d of %d done; logged cost $%.3f" % (len(done), len(files),
                                                sum(u.get("cost", 0) or 0 for u in usage.values())))


def gpt():
    paid = "--paid" in sys.argv      # same model either way; --paid routes through OpenRouter
    ask_all(sorted(glob.glob(os.path.join(R3, "opener-*.txt"))), "scores-gpt.json",
            lambda text: GPT_INTRO + rubric() + GPT_REPLY + "\n\n" + text,
            lambda s, text: checked_scores(s, re.findall(r"^THREAD ([A-H])$", text, re.M)),
            paid, 4 if paid else 1)


# ---- round 9: drift tagging, and the Claude prompts ----
TAG_DEFINITION = """A post is HORROR when it is written in the register of horror fiction or creepypasta: it treats what is happening as sinister or supernatural, gives ominous warnings or instructions ("don't open it", "get out of the house tonight"), speaks of an unnamed presence ("whatever it is", "it knows you're there"), or describes dread, curses, rituals, hauntings or body horror. A post that raises such an idea only to doubt or mock it is not HORROR, and neither is a post that is merely odd, absurd or funny. Posts marked "[post withheld]" are not HORROR.

Label every post from 2 onward; post 1 is the opener. This is not a judgement of quality."""
TAG_GPT = ("You are labelling one AI-generated imageboard thread for a single property.\n\n" + TAG_DEFINITION +
           '\n\nReply with ONLY a JSON object listing the HORROR posts by number: {"horror": [3, 8, 9]}, '
           'or {"horror": []} if there are none.\n\n')


def tag_gpt():
    ask_all(sorted(glob.glob(os.path.join(R3, "tag-*.txt"))), "tags-gpt.json",
            lambda text: TAG_GPT + text, lambda s, text: checked_tags(s), True, 4)


CLAUDE_JUDGE = """You are a blind judge for an experiment on AI-generated imageboard threads. Each file below has one opener and five threads (A–E) continuing it, each written by a different, unnamed setup. Do not try to find out which wrote which. Open ONLY the four files named below; open nothing else on this computer.

Files:
%s

%s

Reply with ONLY a JSON object (no prose), one entry per file, keyed by the file's name without .txt:
{%s}

Before replying, save exactly that JSON, and nothing else, to %s with the Write tool."""
CLAUDE_TAG = """You are labelling AI-generated imageboard threads for a single property. Each file below holds one thread. Open ONLY the eight files named below; open nothing else on this computer. Label each file on its own, without comparing threads.

Files:
%s

%s

Reply with ONLY a JSON object (no prose), one entry per file, keyed by the file's name without .txt:
{%s}

Before replying, save exactly that JSON, and nothing else, to %s with the Write tool."""
SCORE_TEMPLATE = ('{"A": {"interest":n,"humour":n,"emergence":n,"coherence":n,"variety":n,"overall":n,'
                  '"best_lines":["#7: ..."],"main_failure":"..."}, "B": {...}, "C": {...}, "D": {...}, "E": {...}}')


def judge_assignment(versions=5):
    """Ten Claude judges, four packets each: judges 1-5 read openers 1-4 and judges 6-10 openers 5-8,
    judge s reading version ((s - 1) + (opener - 1)) mod 5 + 1 of each. So each opener's five
    versions go to five different judges, and no judge reads an opener twice."""
    return [(s, ["opener-%d-v%d" % (p, (s - 1 + p - 1) % versions + 1)
                 for p in (range(1, 5) if s <= versions else range(5, 9))])
            for s in range(1, 2 * versions + 1)]


def tag_assignment():
    """Five Claude taggers: tagger k labels, for every opener, the thread lettered k in version 1,
    so each reads all eight openers once, a different mix of arms each."""
    return [(k + 1, ["tag-%d-%s" % (p, "ABCDE"[k]) for p in range(1, 9)]) for k in range(5)]


def blind():
    """Copy the packets and tag files to an otherwise empty folder and write the Claude prompts that
    point there, so no judge can stumble on key.json or the raw threads next to them."""
    dest = os.path.abspath(sys.argv[3])
    if os.path.isdir(dest) and os.listdir(dest):
        raise SystemExit(dest + " is not empty")
    os.makedirs(dest, exist_ok=True)
    for f in glob.glob(os.path.join(R3, "opener-*.txt")) + glob.glob(os.path.join(R3, "tag-*.txt")):
        shutil.copy2(f, dest)
    prompts = os.path.join(HERE, "prompts")
    for s, names in judge_assignment():
        files = "\n".join("- " + os.path.join(dest, n + ".txt") for n in names)
        entries = ", ".join('"%s": %s' % (n, SCORE_TEMPLATE if i == 0 else "{...}") for i, n in enumerate(names))
        write(os.path.join(prompts, "r9_claude_judge-%d.txt" % s),
              CLAUDE_JUDGE % (files, RUBRIC_V2, entries, os.path.join(dest, "scores-claude-%d.json" % s)))
    for k, names in tag_assignment():
        files = "\n".join("- " + os.path.join(dest, n + ".txt") for n in names)
        entries = ", ".join('"%s": {"horror": %s}' % (n, "[3, 8, 9]" if i == 0 else "[...]")
                            for i, n in enumerate(names))
        write(os.path.join(prompts, "r9_claude_tag-%d.txt" % k),
              CLAUDE_TAG % (files, TAG_DEFINITION, entries, os.path.join(dest, "tags-claude-%d.json" % k)))
    print("copied the packets and tag files to %s; prompts in %s" % (dest, prompts))


def collect():
    """Check every Claude judge's and tagger's JSON in the blind folder and copy it into r9/ as is."""
    src = os.path.abspath(sys.argv[3])
    key = read_json(os.path.join(R3, "key.json"))
    for s, names in judge_assignment():
        f = os.path.join(src, "scores-claude-%d.json" % s)
        got = read_json(f)
        if sorted(got) != sorted(names):
            raise SystemExit("%s covers %s, expected %s" % (f, sorted(got), sorted(names)))
        for n in names:
            checked_scores(got[n], list(key[n.split("-", 1)[1]]))
        shutil.copy2(f, R3)
    for k, names in tag_assignment():
        f = os.path.join(src, "tags-claude-%d.json" % k)
        got = read_json(f)
        if sorted(got) != sorted(names):
            raise SystemExit("%s covers %s, expected %s" % (f, sorted(got), sorted(names)))
        for n in names:
            checked_tags(got[n])
        shutil.copy2(f, R3)
    print("copied %d judge files and %d tag files into %s" % (len(judge_assignment()), len(tag_assignment()), R3))


def report():
    key = json.load(open(os.path.join(R3, "key.json")))
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
            i = op.split("-", 1)[1]          # "opener-3" -> "3"; round 9's "opener-3-v2" -> "3-v2"
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
    {"packets": packets, "gpt": gpt, "report": report, "tag_gpt": tag_gpt, "blind": blind,
     "collect": collect}[sys.argv[1]]()
