# Run by the bake-off session at 2026-11-02T05:36:30.569Z (Bash tool, from the repo root on Windows).
# Recovered verbatim from the session transcript.
PYTHONIOENCODING=utf-8 py -3.12 - <<'EOF' 2>&1 | grep -v platform
# gpt-5.4 second opinion on the Japanese picker packets, via OpenRouter (free tokens are spent)
import sys, json, glob, os, urllib.request
sys.argv = ["jp_judge.py", "x", "r5"]; sys.path.insert(0, "spike/judging")
import jp_judge as J
env = dict(l.strip().split("=",1) for l in open(".env") if "=" in l and not l.lstrip().startswith("#"))
path = os.path.join(J.JP, "scores-gpt.json")
scores = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
for f in sorted(glob.glob(os.path.join(J.JP, "*-opener-*.txt"))):
    name = os.path.basename(f)[:-4]
    if name in scores: continue
    prompt = ("You are a blind judge, fluent in Japanese and Japanese internet culture. Below is one opener and several threads (lettered) continuing it, each written by a different, unnamed model.\n\n" + J.RUBRIC +
              '\n\nReply with ONLY a JSON object: {"A": {"naturalness":n,"interest":n,"humour":n,"emergence":n,"coherence":n,"overall":n,"best_lines":["#7: ..."],"main_failure":"..."}, "B": {...}, ...}\n\n' + open(f, encoding="utf-8").read())
    body = {"model": "openai/gpt-5.4", "reasoning": {"effort": "low"}, "messages": [{"role": "user", "content": prompt}]}
    d = json.load(urllib.request.urlopen(urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer " + env["OPENROUTER_API_KEY"]}), timeout=600))
    raw = d["choices"][0]["message"]["content"]
    scores[name] = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    json.dump(scores, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(name, "scored", flush=True)
EOF
