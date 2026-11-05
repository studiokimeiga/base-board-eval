#!/usr/bin/env python3
"""Build lore/reference.json: what is too common in this project's board English to be lore.

  python lore/reference.py --data <folder with the original corpora and spike/remote/>

A word or phrase that turns up in many of the project's other threads is ordinary vocabulary, not
something one thread could have handed to another, however rare it is on one small board. This
counts, over every English thread the project generated before this experiment, how many threads
use each word and phrase (tracker.py's own tokens), and keeps those in more than 1% of threads,
with their counts, so tracker.load_reference can apply any cut above that.

Left out: the two validation boards (threads.memory.json, spike/remote/board-*.json), the
Japanese files, quarantined threads and withheld posts. Identical threads are counted once. The
output lists words and phrases only, never thread text; gate-list terms are dropped from it
(posts that contain them are withheld before they reach a page anyway).
"""
import argparse, glob, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import tracker as T
from generate import HARM

MIN_SHARE = 0.01
LEFT_OUT = ("threads.memory.json",)
GATE = HARM + ["cunt", "cock", "tits", "orgasm", "slut", "fap", "pussy", "blowjob", "porn", "rape"]


def corpus_files(data):
    top = [f for f in glob.glob(os.path.join(data, "*.json"))
           if os.path.basename(f).startswith(("threads", "ablation"))
           and os.path.basename(f) not in LEFT_OUT]
    bake = glob.glob(os.path.join(data, "spike", "remote", "bakeoff-*.json"))
    return sorted(top) + sorted(bake)


def threads_of(path):
    d = json.load(open(path, encoding="utf-8"))
    ts = d["threads"] if isinstance(d, dict) else d
    for t in ts:
        if isinstance(t, dict) and t.get("posts") and not t.get("quarantined"):
            yield [p for p in t["posts"] if isinstance(p, dict)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    seen, sources, words, phrases = set(), [], {}, {}
    for path in corpus_files(a.data):
        n = 0
        for posts in threads_of(path):
            key = tuple(p.get("text", "") for p in posts if not p.get("withheld"))
            if key in seen:
                continue
            seen.add(key)
            n += 1
            w, ph = T._thread_sets(posts)
            for x in w:
                words[x] = words.get(x, 0) + 1
            for x in ph:
                phrases[x] = phrases.get(x, 0) + 1
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        sources.append({"file": os.path.relpath(path, a.data).replace(os.sep, "/"),
                        "sha256": digest, "threads": n})
    total = len(seen)

    def common(counts):
        return {x: k for x, k in sorted(counts.items())
                if k / total > MIN_SHARE and not any(g.strip() in x for g in GATE)}

    out = {"note": "Words and phrases in more than %d%% of the project's other English threads, "
                   "with the number of threads that use each; built by lore/reference.py."
                   % (MIN_SHARE * 100),
           "threads": total, "min_share": MIN_SHARE, "built_from": sources,
           "words": common(words), "phrases": common(phrases)}
    with open(os.path.join(HERE, "reference.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    print("%d threads from %d files: %d common words, %d common phrases"
          % (total, len(sources), len(out["words"]), len(out["phrases"])))


if __name__ == "__main__":
    main()
