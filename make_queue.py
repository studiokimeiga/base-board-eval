#!/usr/bin/env python3
"""Build the 30-thread blind rating queue.

  20 shortlisted by me  -> gives PRECISION when validated
  10 drawn at random    -> keeps the mixture unlabelled so the rater's threshold
                           doesn't drift upward knowing every item is a candidate
   5 salted known items -> phonebook / bland-instruct / two collapses / one middling,
                           positions recorded so rater drift shows as a position effect

queue.json     carries thread text ONLY -- no model, no opener index, no flag, no source
queue.key.json carries the mapping, and is never fetched by skim.html

Recall is NOT measured by this design and is not claimed. 10 random threads at a ~2%
base rate contain 0.3 expected events, so an empty random half is the expected outcome
whether the shortlist is excellent or worthless. Rate is reported as
(flagged / 142) x precision, with recall as a stated caveat.

usage: python3 make_queue.py shortlist.json
       shortlist.json = {"phonebook_like": [ids], "striking_other": [ids], "flagged_total": N}
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
N_SHORTLIST, N_RANDOM = 20, 10
SEED = 4471

# salted calibration items, drawn from the already-read 36-thread set
SALT = [
    ("gemma-4-E4B base [Q8_0 diagnostic]", 5, "exemplar_phonebook"),
    ("gemma-4-E4B-it instruct [Q4_K_M]",   5, "known_bland_instruct"),
    ("Olmo-3-1025-7B base [Q4_K_M]",       5, "known_collapse_quoteloop"),
    ("gemma-4-E4B base [Q4_K_M]",          5, "known_collapse_digitsoup"),
    ("Olmo-3-1025-7B base [Q4_K_M]",       2, "known_middling"),
]


def strip(t, qid, opener):
    """Everything the rater may see, and nothing else."""
    return {"qid": qid, "opener": opener,
            "participants": t["participants"],
            "posts": [{"who": p["who"], "ts": p["ts"], "text": p["text"]}
                      for p in t["posts"][1:]]}          # post 1 withheld from the body


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    sl = json.load(open(sys.argv[1]))
    short = list(dict.fromkeys(sl.get("phonebook_like", []) + sl.get("striking_other", [])))

    run = json.load(open(os.path.join(HERE, "threads.run5.json")))
    openers = [o["t"] for o in run["openers"]]
    live = [t for t in run["threads"] if not t.get("quarantined")]
    by_id = {t["id"]: t for t in live}

    rng = random.Random(SEED)
    chosen = short[:N_SHORTLIST]
    pool = [t["id"] for t in live if t["id"] not in set(chosen)]
    rand = rng.sample(pool, min(N_RANDOM, len(pool)))

    old = json.load(open(os.path.join(HERE, "threads.json")))["threads"]
    def find(model, oi):
        return next(t for t in old if t["model"] == model and t["opener_index"] == oi)

    items, key = [], []
    for tid in chosen:
        items.append((by_id[tid], openers[by_id[tid]["opener_index"]], "shortlist", tid))
    for tid in rand:
        items.append((by_id[tid], openers[by_id[tid]["opener_index"]], "random", tid))
    OLD_OPENERS = [
        "does anyone know why the 4 train was sitting at 59th for eleven minutes tonight",
        "my roommate has started labelling things in the fridge and i don't know how to bring it up",
        "im on the 11:40 bus and we have passed the same gas station three times, driver isnt answering me",
        "the woman in 4B has had her washing machine running since friday and i can hear it through the floor right now",
        "my landlord says there is no apartment 12 in this building but my lease says 12 and my key works",
        "just got a text from my own number asking if i left the stove on",
    ]
    for model, oi, label in SALT:
        t = find(model, oi)
        if t.get("quarantined"):
            continue
        items.append((t, OLD_OPENERS[oi], "salt:" + label, "%s/op%d" % (model, oi)))

    rng.shuffle(items)
    out = []
    for i, (t, opener, source, ref) in enumerate(items):
        qid = "q%03d" % (i + 1)
        out.append(strip(t, qid, opener))
        cat = "salt" if source.startswith("salt") else source
        cfg = "run3-36set" if source.startswith("salt") else "run5"
        key.append({"qid": qid, "position": i + 1,
                    "category": cat,          # shortlist | random | salt
                    "config": cfg,            # salts come from the OLD config; never
                                              # mix them into a run5 denominator
                    "source": source, "ref": str(ref),
                    "opener_index": t.get("opener_index"),
                    "seeded": t.get("seeded"), "axis": t.get("axis"),
                    "opener_author": t.get("opener_author")})

    with open(os.path.join(HERE, "queue.json"), "w") as f:
        json.dump({"items": out}, f, indent=1)
    with open(os.path.join(HERE, "queue.key.json"), "w") as f:
        json.dump({"flagged_total": sl.get("flagged_total"),
                   "corpus_size": len(live), "key": key}, f, indent=1)
    os.chmod(os.path.join(HERE, "queue.key.json"), 0o600)

    ns = len(out) - len(chosen) - len(rand)
    print("queue.json: %d items = %d shortlist + %d random + %d salt"
          % (len(out), len(chosen), len(rand), ns))
    print("precision denominator: the %d shortlisted items ONLY" % len(chosen))
    print("excluded from all rate maths: %d salt (known verdicts, old config)" % ns)
    print("queue.key.json written 0600 -- do not open it before rating")


if __name__ == "__main__":
    main()
