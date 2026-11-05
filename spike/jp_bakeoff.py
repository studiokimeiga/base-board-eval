#!/usr/bin/env python3
"""THROWAWAY SPIKE: Japanese board bake-off (for a learn-Japanese-by-reading board).

Every model writes Japanese natively; nothing is translated. Two page formats:

  5ch     【スレタイ】title, then "N 名前：名無しさん 投稿日：2026/07/30(木) 23:14:02.31 ID:Qm7xKp2a0"
          anonymous posters told apart by ID, as on 5ch
  named   the same thread with persistent handles, "たけし 2026/07/30(木) 23:14:02"

Same scaffold for every model (generate.py's rules, seeded per opener: who posts when,
OP returns after a long gap, late arrivals), same 6 openers, same sampling where the
backend allows it: temperature 1.0, min_p 0.05, no XTC/DRY, no grammar.

Backends:
  raw     the model continues the page itself (OpenRouter /completions, or a local
          llama-server for the Modal-hosted base models)
  chat    one short Japanese instruction per post asking for the next post's body

  py -3.12 spike/jp_bakeoff.py qwen235 5ch
  python spike/jp_bakeoff.py swallow70 named --llama 8300      (on Modal, see modal_board.py)

Writes spike/remote/jp-<arm>-<format>.json (or --out DIR).
"""
import argparse, json, os, random, re, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)

OPENERS = [
    "職場で誰かが俺のマグカップを勝手に洗って、毎回違う棚に戻してくる",
    "自分の番号から「コンロ消した？」ってSMSが来たんだけど",
    "後ろの席の人が、俺が聞かれた質問に勝手に答えるようになった",
    "友達が最近、文の最後に必ず俺の名前をつけてくる",
    "グループLINEの名前が勝手に変わってて、誰も自分がやったって言わない",
    "他人宛ての郵便が一年くらい届き続けてて、最近それを読むようになった",
]
HANDLES = """たけし まゆ こーへい ゆき ぽん太 さくら けんじ みお だいき あや しゅん なな りょう かな
ゆうと めぐ はると ちひろ そうた えみ""".split()

ARMS = {
    # raw continuation
    "qwen235": ("raw", "qwen/qwen3-235b-a22b-2507"),
    "deepseek": ("chat", "deepseek/deepseek-v4-flash"),   # raw /completions came back empty
    "swallow70": ("llama", "Llama-3.3-Swallow-70B-v0.4.Q4_K_M.gguf"),
    # same weights, plus XTC + DRY: the plain run chanted ("俺も来た" x20) as the English one used to
    "swallow70dry": ("llama", "Llama-3.3-Swallow-70B-v0.4.Q4_K_M.gguf"),
    "g31": ("llama", "gemma-4-31B-Q8_0.gguf"),
    # chat, one instruction per post
    "gpt54": ("chat", "openai/gpt-5.4"),
    "gemini": ("chat", "google/gemini-3.8-flash"),
    "geminipick": ("chatpick", "google/gemini-3.8-flash"),   # 3 posts, gpt-5.4 picks
    "sonnet": ("chat", "anthropic/claude-sonnet-5.5"),
    "kimi": ("chat", "moonshotai/kimi-k3"),
}
POSTS = 24
POOL = 7
OP_SHARE = 0.22
RETURN_AT, ARRIVE_AT = {7, 19}, {13}
BIG_GAP = (2 * 3600, 6 * 3600)
DAYS = "月火水木金土日"

# The English harm list doesn't catch Japanese. Self-harm, threats, slurs, explicit sex.
# Bare 死ね is left out on purpose: on 5ch it is everyday banter, and withholding it would
# make the threads less real, which is the point of this board.
JP_GATE = ["死にたい", "自殺", "殺してやる", "殺すぞ", "ぶっ殺", "首吊", "リスカ", "ガイジ", "池沼",
           "チョン", "支那", "土人", "ニガー", "黒んぼ", "レイプ", "強姦", "ちんぽ", "ちんこ", "まんこ",
           "セックス", "中出し", "フェラ", "おっぱい揉"]
G_XTC_DRY = dict(xtc_threshold=0.05, xtc_probability=0.5, dry_multiplier=0.8, dry_base=1.75,
                 dry_allowed_length=2, dry_penalty_last_n=8192)
LOCK = threading.Lock()
SPEND = {"usd": 0.0}
ENV = {}


def stamp(secs, fivech):
    t = time.gmtime(time.mktime((2026, 7, 30, 23, 14, 2, 0, 0, 0)) - time.timezone + secs)
    base = "%04d/%02d/%02d(%s) %02d:%02d:%02d" % (t.tm_year, t.tm_mon, t.tm_mday, DAYS[t.tm_wday],
                                                 t.tm_hour, t.tm_min, t.tm_sec)
    return base + (".%02d" % ((secs * 37) % 100) if fivech else "")


def scaffold(oi, fmt):
    """Who posts when, and under what label. Seeded per opener, identical across models."""
    rng = random.Random(70707 + oi * 1000)
    if fmt == "5ch":
        alnum = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        pool = ["".join(rng.choice(alnum) for _ in range(8)) + "0" for _ in range(POOL)]
    else:
        pool = rng.sample(HANDLES, POOL)
    op, seen, author, secs, plan = pool[0], {pool[0]}, pool[0], 0, []
    for n in range(2, POSTS + 1):
        secs += rng.randint(40, 9 * 60)
        if n in RETURN_AT:
            secs += rng.randint(*BIG_GAP)
            author = op
        elif n in ARRIVE_AT and [h for h in pool if h not in seen]:
            author = rng.choice([h for h in pool if h not in seen])
        elif rng.random() < OP_SHARE and author != op:
            author = op
        else:
            author = rng.choice([h for h in pool if h != author])
        seen.add(author)
        plan.append((n, author, secs))
    return pool, plan


def header(n, who, secs, fmt):
    if fmt == "5ch":
        return "%d 名前：名無しさん 投稿日：%s ID:%s" % (n, stamp(secs, True), who)
    return "%s %s" % (who, stamp(secs, False))


def render(title, posts, fmt):
    return "【スレタイ】%s\n\n" % title + "\n\n".join(
        "%s\n%s" % (header(p["n"], p["who"], p["secs"], fmt), p["text"]) for p in posts if p["text"])


def strip_echo(text, fmt):
    """Drop a copied post header, surrounding quotes, and anything past the post's end."""
    text = text.strip()
    hdr = (r"^>?\d+\s*名前：.*?ID:\S+\s*\n?" if fmt == "5ch"
           else r"^>?\S+ \d{4}/\d\d/\d\d\(.\) \d\d:\d\d:\d\d\s*\n?")
    text = re.sub(hdr, "", text).strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"「":
        text = text[1:-1].strip()
    nxt = (r"\n\d+\s*名前：" if fmt == "5ch" else r"\n\S+ \d{4}/\d\d/\d\d\(.\) \d\d:\d\d")
    text = re.split(nxt, text)[0]
    return text.split("\n\n")[0].strip()


def post_json(url, key, body, timeout=240):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + key} if key else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def retrying(fn, tries=6):
    for attempt in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 402, 403):
                raise RuntimeError("HTTP %d: %s" % (e.code, e.read()[:200]))
            wait = int(e.headers.get("Retry-After") or 0) or 10 * (attempt + 1)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError):
            wait = 5 * (attempt + 1)
        if attempt == tries - 1:
            raise RuntimeError("gave up after %d tries" % tries)
        time.sleep(wait)


def cost(d):
    with LOCK:
        SPEND["usd"] += (d.get("usage") or {}).get("cost", 0) or 0


def writer(arm, fmt, llama_port=None):
    kind, model = ARMS[arm]

    def raw(doc_next):
        if kind == "llama":
            body = {"prompt": doc_next, "n_predict": 200, "temperature": 1.0, "min_p": 0.05,
                    "top_p": 1.0, "top_k": 0, "repeat_penalty": 1.0, "stop": ["\n\n"],
                    "cache_prompt": True}
            if arm.endswith("dry"):     # the English project's settled samplers (generate.py)
                body.update(G_XTC_DRY)
            d = retrying(lambda: post_json("http://127.0.0.1:%d/completion" % llama_port, None,
                                           body, timeout=600))
            return d.get("content", "")
        d = retrying(lambda: post_json("https://openrouter.ai/api/v1/completions",
                                       ENV["OPENROUTER_API_KEY"], {
            "model": model, "prompt": doc_next, "max_tokens": 200, "temperature": 1.0,
            "min_p": 0.05, "top_p": 1.0, "stop": ["\n\n"], "usage": {"include": True}}))
        cost(d)
        return d["choices"][0].get("text") or ""

    def chat(doc, n, who):
        if fmt == "5ch":
            ask = ("以下は5ちゃんねるのスレッドです。\n\n%s\n\n"
                   "次のレス（%d番、ID:%s）の本文だけを書いてください。名前欄・日付・IDは書かないでください。"
                   % (doc, n, who))
        else:
            ask = ("以下はネット掲示板のスレッドです。\n\n%s\n\n"
                   "次の%sの書き込みの本文だけを書いてください。名前や日付は書かないでください。" % (doc, who))
        body = {"model": model, "messages": [{"role": "user", "content": ask}], "max_tokens": 300,
                "temperature": 1.0, "usage": {"include": True}}
        if "kimi" in model or "deepseek" in model:   # reasoning ate deepseek's whole budget
            body["reasoning"] = {"enabled": False}
        elif "gemini" in model or "claude" in model:
            # reasoning can't be disabled for these; at 300 tokens it ate the whole post
            body.update(reasoning={"effort": "low"}, max_tokens=1200)
        d = retrying(lambda: post_json("https://openrouter.ai/api/v1/chat/completions",
                                       ENV["OPENROUTER_API_KEY"], body))
        cost(d)
        return d["choices"][0]["message"].get("content") or ""

    def pick(doc, n, who):
        """Three posts, shuffled, gpt-5.4 picks: the English round 4-5 picker, asked in Japanese
        and told realism comes first, since that's what the Japanese board is for."""
        with ThreadPoolExecutor(3) as ex:
            cands = [strip_echo(c, fmt) for c in ex.map(lambda _: chat(doc, n, who), range(3))]
        options = [c for c in dict.fromkeys(cands) if c] or [""]
        if len(options) == 1:
            return options[0]
        with LOCK:
            PICK_RNG.shuffle(options)
        recent = "\n\n".join(doc.split("\n\n")[-10:])
        listing = "\n\n".join("%d. %s" % (i + 1, c) for i, c in enumerate(options))
        ask = ("以下は掲示板スレッドの直近のレスです。\n\n%s\n\n次のレス（%s）の候補が%d個あります。\n\n%s\n\n"
               "本物の日本のネット掲示板の書き込みとして一番自然で、かつスレを一番面白くする"
               "（笑える・意外・スレの流れを拾って発展させる）候補はどれですか？番号だけで答えてください。"
               % (recent, who, len(options), listing))
        d = retrying(lambda: post_json("https://openrouter.ai/api/v1/chat/completions",
                                       ENV["OPENROUTER_API_KEY"], {
            "model": "openai/gpt-5.4", "max_tokens": 300, "reasoning": {"effort": "low"},
            "usage": {"include": True}, "messages": [{"role": "user", "content": ask}]}))
        cost(d)
        m = re.search(r"\d+", d["choices"][0]["message"].get("content") or "")
        return options[int(m.group()) - 1 if m and 0 < int(m.group()) <= len(options) else 0]

    def write(title, posts, n, who, secs):
        doc = render(title, posts, fmt)
        if kind == "chatpick":
            return pick(doc, n, who)
        if kind == "chat":
            out = chat(doc, n, who)
        else:
            out = raw(doc + "\n\n" + header(n, who, secs, fmt) + "\n")
        return strip_echo(out, fmt)
    return write


PICK_RNG = random.Random(5252)


def thread(i, write, fmt, arm):
    title = OPENERS[i]
    pool, plan = scaffold(i, fmt)
    posts = [{"n": 1, "who": pool[0], "secs": 0, "text": title}]
    t0 = time.time()
    for n, who, secs in plan:
        try:
            text = write(title, posts, n, who, secs)
        except RuntimeError as e:
            print("\n%s/%s thread %d post %d failed: %s" % (arm, fmt, i + 1, n, e), flush=True)
            raise
        p = {"n": n, "who": who, "secs": secs, "text": text}
        if any(g in text for g in JP_GATE):
            p.update(text="[post withheld]", withheld=True)
        posts.append(p)
    for p in posts:
        p["ts"] = stamp(p["secs"], fmt == "5ch")
    return {"opener": title, "op": pool[0], "format": fmt, "arm": arm,
            "secs": round(time.time() - t0), "posts": posts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=sorted(ARMS))
    ap.add_argument("fmt", choices=["5ch", "named"])
    ap.add_argument("--llama", type=int, help="port of a running llama-server (Modal arms)")
    ap.add_argument("--out", default=os.path.join(SPIKE, "remote"))
    a = ap.parse_args()
    if os.path.exists(os.path.join(ROOT, ".env")):
        ENV.update(dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".env"))
                        if "=" in l and not l.lstrip().startswith("#")))
    write = writer(a.arm, a.fmt, a.llama)
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, "jp-%s-%s.json" % (a.arm, a.fmt))
    # Saved after every thread; a rerun keeps finished threads and only writes the missing
    # ones. (The first run saved only at the end and lost every arm that hit a 402.)
    done = {}
    if os.path.exists(out):
        prev = json.load(open(out, encoding="utf-8"))
        done = {OPENERS.index(t["opener"]): t for t in prev["threads"]
                if t["opener"] in OPENERS and not t.get("redo")}
        SPEND["usd"] = prev.get("spend_usd", 0)

    def save():
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"arm": a.arm, "model": ARMS[a.arm][1], "backend": ARMS[a.arm][0],
                       "format": a.fmt, "spend_usd": SPEND["usd"],
                       "threads": [done[k] for k in sorted(done)]}, f, ensure_ascii=False, indent=1)

    for i in range(len(OPENERS)):
        if i in done:
            continue
        if not a.llama:
            used, credits = openrouter_used(both=True)
            if used > credits - SPEND_MARGIN:
                print("%s/%s: stopping, OpenRouter within $%.2f of the balance" % (a.arm, a.fmt, SPEND_MARGIN), flush=True)
                break
        try:
            done[i] = thread(i, write, a.fmt, a.arm)
        except RuntimeError:
            break
        save()
    save()
    print("%s/%s: %d/%d threads in %s  $%.3f" % (a.arm, a.fmt, len(done), len(OPENERS), out,
                                              SPEND["usd"]), flush=True)


SPEND_MARGIN = 0.50      # stop this far short of the account's credit, whatever it's topped up to


def openrouter_used(both=False):
    req = urllib.request.Request("https://openrouter.ai/api/v1/credits",
                                 headers={"Authorization": "Bearer " + ENV["OPENROUTER_API_KEY"]})
    d = json.load(urllib.request.urlopen(req, timeout=30))["data"]
    return (d["total_usage"], d["total_credits"]) if both else d["total_usage"]


if __name__ == "__main__":
    main()
