#!/usr/bin/env python3
"""The publication gate: whether a post may be shown.

Measured against the old keyword gate and two classifiers in moderation/ (its README.md has the
results, METRICS.md every number). Run it on every post before the post is shown or goes into
any model's prompt, so no model ever replies to a post a reader can't see. A post is held when
either check fires:

  * the keyword list, single English words matched on word boundaries (the word itself or with
    a plain inflection: s, es, d, ed, ing, z), phrases and Japanese terms as substrings, so
    "suspicious" and "grapes" no longer trip "spic" and "rape";
  * OpenAI omni-moderation, pinned to one snapshot, scoring THRESHOLD or more in one of
    CATEGORIES. Its harassment, illicit and violence categories are left out on purpose: on a
    paranormal board they fire on insults and on every described death.

It fails closed: when the classifier can't be reached, the post is held. Gate(terms) without a
key is the keyword list alone, for offline research runs only.

The OpenAI key in .env belongs to a project that shares inputs with OpenAI. That is fine for
model-written board text; a board that takes posts from people needs a project that doesn't.
"""
import json, os, re, time, urllib.error, urllib.request

MODEL = "omni-moderation-2024-09-26"
URL = "https://api.openai.com/v1/moderations"
THRESHOLD = 0.3
# OpenAI's categories that hold a post, and the category each counts as in moderation/LABELLING.md
CATEGORIES = {"self-harm": "self_harm", "self-harm/intent": "self_harm",
              "self-harm/instructions": "self_harm", "harassment/threatening": "violence_threat",
              "illicit/violent": "violence_threat", "hate": "hate_slur",
              "hate/threatening": "hate_slur", "sexual": "sexual", "sexual/minors": "sexual_minors"}
WB_SUFFIX = "(s|es|d|ed|ing|z)?"


def term_patterns(terms):
    """(term, word-boundary regex) for single English words, (term, None) for the rest."""
    return [(t, re.compile(r"\b%s%s\b" % (re.escape(t.strip()), WB_SUFFIX))
             if t.isascii() and " " not in t.strip() else None) for t in terms]


def keyword_hits(text, patterns):
    """The terms a post contains, in list order."""
    low = text.lower()
    return [t for t, rx in patterns if (rx.search(low) if rx else t in low)]


def flagged(scores, threshold=THRESHOLD):
    """The OpenAI categories in CATEGORIES that reach the threshold, sorted."""
    return sorted(k for k in CATEGORIES if scores.get(k, 0.0) >= threshold)


def request(texts):
    return {"model": MODEL, "input": list(texts)}


def openai_key(root):
    """OPENAI_API_KEY from the environment, else from ROOT/.env; None if neither has it."""
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    path = os.path.join(root, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k.strip() == "OPENAI_API_KEY" and v.strip():
                    return v.strip().strip("\"'")
    return None


def openai_scores(texts, key, tries=4):
    """category_scores for each text. Rate limits and server errors are retried; anything else,
    or running out of tries, raises, and the gate holds the post."""
    data = json.dumps(request(texts)).encode("utf-8")
    for attempt in range(tries):
        req = urllib.request.Request(URL, data=data, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            if len(d.get("results") or []) != len(texts):
                raise RuntimeError("moderation returned %d results for %d inputs"
                                   % (len(d.get("results") or []), len(texts)))
            return [x["category_scores"] for x in d["results"]]
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise RuntimeError("moderation HTTP %d" % e.code)
            time.sleep(min(30.0, float(e.headers.get("Retry-After") or 2 ** attempt)))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == tries - 1:
                raise RuntimeError("moderation unreachable: %s" % e)
            time.sleep(2 ** attempt)


class Gate:
    """check(text) -> {"hold", "terms", "categories", "scores", "error"}.

    `before`, the post a reply answers, is for posts from people: the reply is then also scored
    together with it, which catches a reply that is only harmful in context. Model posts never
    need it, because a held post never reaches their prompts."""

    def __init__(self, terms, key=None, threshold=THRESHOLD, moderate=None):
        self.patterns = term_patterns(terms)
        self.threshold = threshold
        self.moderate = moderate or ((lambda texts: openai_scores(texts, key)) if key else None)

    def check(self, text, before=None):
        terms = keyword_hits(text, self.patterns)
        v = {"hold": bool(terms), "terms": terms, "categories": [], "scores": {}, "error": None}
        if self.moderate is None:
            return v
        try:
            results = self.moderate([text] + ([before + "\n\n" + text] if before else []))
        except Exception as e:                     # fail closed
            v.update(hold=True, error=str(e)[:200])
            return v
        v["scores"] = {k: max(s.get(k, 0.0) for s in results) for k in CATEGORIES}
        v["categories"] = flagged(v["scores"], self.threshold)
        v["hold"] = v["hold"] or bool(v["categories"])
        return v


def log_entry(v):
    """What a quarantine log keeps about a verdict, next to the post itself."""
    return {"terms": v["terms"], "categories": v["categories"],
            "scores": {k: round(s, 4) for k, s in v["scores"].items()}, "error": v["error"]}


def reason(v):
    """One short line for the console."""
    return ", ".join(v["terms"] + v["categories"] + ([v["error"]] if v["error"] else []))
