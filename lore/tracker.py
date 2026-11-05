"""Lore tracker: what in a later thread came from one earlier thread.

`track(target, source, background)` scores a target thread against a source thread whether or not
the target's page showed the source. On a no-memory board every hit is chance (shared vocabulary,
the model's habits, the page's own numbers), and that is what lets the memory board's hits mean
something: the memory effect is the difference within pairs (PREREGISTRATION.md).

A thread is a list of posts, {"who": handle, "text": ...}; post 0 is the opener. Withheld and empty
posts are skipped everywhere, and only the target's replies are scored: its opener is authored.

What counts, in order of how much it says:

  reference   a pointer only the source explains: its thread number when the page showed it, a
              handle that posted only there, or an earlier-thread phrase ("the other thread") in a
              post that also carries source material
  item        material distinctive of the source, i.e. in at most DF_SHARE of the background
              threads, and absent from the target's opener and from its topic twin (a thread written
              from the target's opener without the source):
                word    used at least twice; a new partner word makes it a construction
                        ("physical number" -> "physical milk")
                phrase  2-3 words, used once if one of its words is itself rare, else twice
                pair    two distinctive words of one source post together in one target post
  format play the page's furniture: the thread's own number and numbers near the ones the page
              shows, post numbers, the board's name, "this thread"/"OP" talk. Counted, never memory.

The exact-phrase detector this replaces reported a false null on "physical X" (FINDINGS.md).
"""
import json, os, re
from functools import lru_cache

DF_SHARE = 0.05     # rare = in at most 5% of background threads, and at least 1 is always allowed
REF_SHARE = 0.05    # ...and in at most 5% of the project's other threads (validate.py picks it by rule)
NEAR = 200          # a thread-like number this close to a number on the page is format play
REFERENCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference.json")

STOP = {w.replace("'", "") for w in """
a about above after again against all also am an and any anyway anyways are aren't as at basically
be because been before being below between both but by can can't cannot could couldn't did didn't
do does doesn't doing don't down during each else even ever every few for from further get gets
getting go goes going gone gonna got gotta guess had hadn't has hasn't have haven't having he he'd
he'll he's her here here's hers herself him himself his honestly how how's i i'd i'll i'm i've idk
if imo in into is isn't it it's its itself just kinda know let let's like liked likes literally lmao
lol lot lots maybe me mean means might more most much must mustn't my myself no nor not now of off
oh ok okay on once one ones only or other others ought our ours ourselves out over own pretty
probably quite rather really said same say says she she'd she'll she's should shouldn't so some
sorta still such tbh than that that's the their theirs them themselves then there there's these
they they'd they'll they're they've think thinking thought this those though through thru to too u
um under until up ur us very want wanted wants was wasn't way we we'd we'll we're we've well were
weren't what what's whatever when when's where where's whether which while who who's whom why
why's will with won't would wouldn't yeah yep yes yet you you'd you'll you're you've your yours
yourself yourselves
""".split()}
FORMAT_WORDS = {"thread", "board", "post", "op", "anon", "reply", "bump"}

SEGMENT = re.compile(r"[.!?;:,()\[\]\"\n]+")
TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)*")
NUMBER = re.compile(r"(>>\s*|\bno\.?\s*)?\b(\d{3,})\b", re.I)
DEIXIS = re.compile(r"\b(?:other|another|last|previous|earlier|older|old|original|prior|that|those)"
                    r" threads?\b")
SELF = re.compile(r"\b(?:this|the|our|ur) (?:thread|board)\b|\bop\b")


def norm(tok):
    """Lowercase token -> the form plurals and possessives share."""
    if tok.endswith("'s"):
        tok = tok[:-2]
    tok = tok.replace("'", "")
    if not tok.isalpha():
        return tok
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith(("ches", "shes", "sses", "xes", "zes")):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def _stop(tok):
    return tok.replace("'", "") in STOP or norm(tok) in STOP


def _segments(text):
    """Runs of (normalised token, is_stop) between punctuation, so n-grams never cross a sentence."""
    t = text.lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"[-/_]", " ", t)
    for seg in SEGMENT.split(t):
        toks = TOKEN.findall(seg)
        if toks:
            yield [(norm(x), _stop(x)) for x in toks]


def _big_number(w):
    return w.isdigit() and len(w) >= 3


@lru_cache(maxsize=None)
def _items(text):
    """(words, phrases, word occurrences, partners) of one post. Words are content words; phrases
    are 2-3 tokens with non-stop ends and at least two non-stop tokens. partners maps a word to the
    non-stop tokens right before and after it."""
    words, phrases, occ, partners = set(), set(), [], {}
    for seg in _segments(text):
        for i, (w, stop) in enumerate(seg):
            if stop or len(w) < 3 or w.isdigit():
                continue
            words.add(w)
            occ.append(w)
            near = partners.setdefault(w, set())
            for j in (i - 1, i + 1):
                if 0 <= j < len(seg) and not seg[j][1] and not _big_number(seg[j][0]):
                    near.add(seg[j][0])
        for n in (2, 3):
            for i in range(len(seg) - n + 1):
                g = seg[i:i + n]
                if g[0][1] or g[-1][1] or sum(not s for _, s in g) < 2:
                    continue
                if any(_big_number(w) for w, _ in g):
                    continue
                phrases.add(" ".join(w for w, _ in g))
    return frozenset(words), frozenset(phrases), tuple(occ), {k: frozenset(v) for k, v in partners.items()}


def load_reference(max_share, path=REFERENCE):
    """The words and phrases of reference.json used in more than `max_share` of its threads."""
    with open(path, encoding="utf-8") as f:
        ref = json.load(f)
    if max_share < ref["min_share"]:
        raise ValueError("reference.json only keeps items above %s" % ref["min_share"])
    n = ref["threads"]
    return {"words": frozenset(w for w, k in ref["words"].items() if k / n > max_share),
            "phrases": frozenset(p for p, k in ref["phrases"].items() if k / n > max_share)}


def _live(posts):
    return [(i, p) for i, p in enumerate(posts) if p.get("text") and not p.get("withheld")]


def _thread_sets(posts):
    words, phrases = set(), set()
    for _, p in _live(posts):
        w, ph, _, _ = _items(p["text"])
        words |= w
        phrases |= ph
    return words, phrases


def track(target, source, background, target_no=None, source_no=None, source_shown=False,
          topic_twin=None, board="/x/", target_cast=(), common=None):
    """Score `target` against `source`. `background` is a list of threads that are neither of them
    (for an experiment: the other sources). `source_shown` says whether the target's page showed the
    source; only then can the source's number be a reference. `common` ({"words", "phrases"}, see
    load_reference) lists what is too common in board English to be anyone's lore."""
    common_w = common["words"] if common else frozenset()
    common_p = common["phrases"] if common else frozenset()
    bg = [_thread_sets(t) for t in background]
    df_max = max(1, int(DF_SHARE * len(bg)))

    def rare(x, k):
        return sum(1 for s in bg if x in s[k]) <= df_max

    live_target = _live(target)
    replies = [(i, p) for i, p in live_target if i > 0]
    cast = {p["who"] for p in target if p.get("who")} | set(target_cast)
    source_who = {p["who"] for _, p in _live(source) if p.get("who")}
    only_source = sorted(source_who - cast)
    board_tokens = {w for seg in _segments(board) for w, _ in seg}
    # words are normalised ("ines" -> "ine"), so the handles they are checked against must be too;
    # the raw handles stay in `cast` and `source_who` for reference matching
    handle_tokens = {w for h in cast | source_who for seg in _segments(h) for w, _ in seg}
    banned = cast | source_who | handle_tokens | board_tokens | FORMAT_WORDS

    opener = [p for i, p in live_target if i == 0]
    excluded_w, excluded_p = _thread_sets(opener + list(topic_twin or []))

    def keep_word(w):
        return w not in excluded_w and w not in banned and w not in common_w and rare(w, 0)

    def keep_phrase(ph):
        return (ph not in excluded_p and not set(ph.split()) & banned and ph not in common_p
                and rare(ph, 1))

    source_posts = _live(source)
    s_words, s_phrases, s_partners, s_post_words = {}, {}, {}, []
    for i, p in source_posts:
        w, ph, _, partners = _items(p["text"])
        dw = {x for x in w if keep_word(x)}
        s_post_words.append((i, dw))
        for x in dw:
            s_words.setdefault(x, "premise" if i == 0 else "reply")
            s_partners.setdefault(x, set()).update(partners.get(x, ()))
        for x in ph:
            if keep_phrase(x):
                s_phrases.setdefault(x, "premise" if i == 0 else "reply")

    found = {}

    def add(key, kind, i, who, origin, **extra):
        it = found.setdefault(key, {"item": key, "kind": kind, "uses": 0, "posts": set(),
                                    "authors": set(), "construction": False, "fillers": set(),
                                    "origin": origin})
        it["uses"] += 1
        it["posts"].add(i)
        it["authors"].add(who)
        for k, v in extra.items():
            it[k] |= v

    material = {}            # post -> source words/phrases present, used to ground deixis
    for i, p in replies:
        w, ph, occ, partners = _items(p["text"])
        material[i] = (w & set(s_words)) | (ph & set(s_phrases))
        for x in occ:
            if x in s_words:
                add(x, "word", i, p["who"], s_words[x],
                    fillers=set(partners.get(x, ())) - s_partners.get(x, set()))
        for x in ph & set(s_phrases):
            add(x, "phrase", i, p["who"], s_phrases[x])
        # one use per pair per target post, however many source posts carry it; the first
        # (earliest) source post carrying it gives its origin
        pairs = {}
        for j, dw in s_post_words:
            shared = sorted(dw & w)
            if len(shared) >= 2:
                pairs.setdefault(" + ".join(shared), "premise" if j == 0 else "reply")
        for key, origin in pairs.items():
            add(key, "pair", i, p["who"], origin)

    def rare_word(w):
        return (len(w) >= 3 and not w.isdigit() and w not in STOP and w not in banned
                and w not in common_w and rare(w, 0))

    items = []
    for it in found.values():
        if it["kind"] == "word":
            if it["uses"] < 2:
                continue
            it["construction"] = bool(it["fillers"])
        # a phrase of ordinary words is a collocation, not a coinage, unless the thread reuses it
        if it["kind"] == "phrase" and it["uses"] < 2 and not any(map(rare_word, it["item"].split())):
            continue
        items.append(dict(it, posts=sorted(it["posts"]), authors=sorted(it["authors"]),
                          fillers=sorted(it["fillers"])))
    order = {"word": 0, "phrase": 1, "pair": 2}
    items.sort(key=lambda it: (order[it["kind"]], -it["uses"], it["item"]))

    refs, fmt = [], {"own_number": 0, "near_number": 0, "post_number": 0, "board_name": 0,
                     "self_ref": 0}
    for i, p in replies:
        text = p["text"].lower()
        fmt["board_name"] += text.count(board.lower()) if board else 0
        fmt["self_ref"] += len(SELF.findall(text))
        for h in only_source:
            if re.search(r"\b%s\b" % re.escape(h.lower()), text):
                refs.append({"kind": "handle", "post": i, "match": h})
        for m in NUMBER.finditer(text):
            x = int(m.group(2))
            if m.group(1):
                fmt["post_number"] += 1
            elif x == target_no:
                fmt["own_number"] += 1
            elif source_shown and x == source_no:
                refs.append({"kind": "number", "post": i, "match": m.group(2)})
            elif any(len(str(n)) == len(m.group(2)) and abs(x - n) <= NEAR
                     for n in (target_no, source_no) if n is not None):
                fmt["near_number"] += 1
        grounded = (material.get(i) or any(r["post"] == i for r in refs))
        for m in DEIXIS.finditer(text):
            if grounded:
                refs.append({"kind": "deixis", "post": i, "match": m.group(0)})
            else:
                fmt["self_ref"] += 1

    # uptake: the most posters sharing any one item (L3 needs one item used by two posters);
    # posters: everyone who used any item, which is what `uptake` meant before 2026-11-05
    posters = {a for it in items for a in it["authors"]}
    return {"transfer": bool(items or refs), "items": items, "references": refs,
            "format_play": fmt, "uptake": max((len(it["authors"]) for it in items), default=0),
            "posters": len(posters)}
