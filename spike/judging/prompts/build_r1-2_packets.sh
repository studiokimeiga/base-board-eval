# Run by the bake-off session at 2026-11-02T03:14:00.353Z (Bash tool, from the repo root on Windows).
# Recovered verbatim from the session transcript.
mkdir -p judging && py -3.12 - <<'EOF' 2>&1 | grep -v platform
import json, random
ARMS=["cast","g31","l70","euryale70","hermes405","qwen235"]
data={a: json.load(open("remote/bakeoff-%s.json"%a,encoding="utf-8")) for a in ARMS}
openers=[t["opener"] for t in data["cast"]["threads"]]
rng=random.Random(9271); key={}
for i,op in enumerate(openers):
    arms=ARMS[:]; rng.shuffle(arms); letters="ABCDEF"
    key[i+1]={letters[k]:a for k,a in enumerate(arms)}
    out=["OPENER %d: %s\n" % (i+1, op)]
    for k,a in enumerate(arms):
        t=next(t for t in data[a]["threads"] if t["opener"]==op)
        out.append("=" * 20 + "\nTHREAD %s\n" % letters[k] + "=" * 20)
        for n,p in enumerate(t["posts"]):
            tag = " (OP)" if p["who"]==t["posts"][0]["who"] else ""
            out.append("%d. %s%s: %s" % (n+1, p["who"], tag, p["text"] if p["text"] else "(empty)"))
        out.append("")
    open("judging/opener-%d.txt"%(i+1),"w",encoding="utf-8").write("\n".join(out))
json.dump(key, open("judging/key.json","w"), indent=1)
import os; print([ (f, os.path.getsize("judging/"+f)) for f in sorted(os.listdir("judging"))])
EOF
