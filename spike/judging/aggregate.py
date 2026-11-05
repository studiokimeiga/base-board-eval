"""Unblind the judges' scores (key.json) and average them per model."""
import json, glob, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
key = json.load(open(os.path.join(HERE, "key.json")))
S = {}
for f in glob.glob(os.path.join(HERE, "scores-*.json")):
    S.update(json.load(open(f, encoding="utf-8")))

NAMES = {"cast": "current cast (4-7B)", "g31": "gemma-4-31B base", "l70": "Llama-3.1-70B base",
         "euryale70": "Euryale 70B", "hermes405": "Hermes 3 405B", "qwen235": "Qwen3-235B Instruct"}
DIMS = ["overall", "interest", "humour", "emergence", "coherence"]
agg = collections.defaultdict(lambda: collections.defaultdict(list))
fails, best, wins = collections.defaultdict(list), collections.defaultdict(list), collections.Counter()
for op, threads in sorted(S.items()):
    i = op.split("-")[1]
    top = max(v["overall"] for v in threads.values())
    for letter, v in threads.items():
        arm = key[i][letter]
        for d in DIMS:
            agg[arm][d].append(v[d])
        fails[arm].append(v["main_failure"])
        wins[arm] += v["overall"] == top
        best[arm] += ["%s %s" % (op, b) for b in v["best_lines"]]

rows = sorted(agg, key=lambda a: -sum(agg[a]["overall"]))
print("%-22s %7s %8s %6s %9s %9s %9s" % ("model", "overall", "interest", "humour", "emergence",
                                         "coherence", "best/tied"))
for a in rows:
    m = {d: sum(agg[a][d]) / len(agg[a][d]) for d in DIMS}
    print("%-22s %7.2f %8.2f %6.2f %9.2f %9.2f %9d" % (NAMES[a], m["overall"], m["interest"],
          m["humour"], m["emergence"], m["coherence"], wins[a]))
print()
for a in rows:
    print("%-22s overall by opener %s | %s" % (NAMES[a], agg[a]["overall"],
          collections.Counter(fails[a]).most_common(2)))
json.dump({NAMES[a]: best[a] for a in rows}, open(os.path.join(HERE, "best-lines-by-model.json"), "w",
          encoding="utf-8"), ensure_ascii=False, indent=1)
