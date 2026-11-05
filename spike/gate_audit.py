#!/usr/bin/env python3
"""Does the keyword gate's substring match miss variants of its own slur entries?

  python spike/gate_audit.py [REPO_ROOT]

Scans every stored post that wasn't withheld, in spike/remote/ and the original corpora
(threads*.json, from the gated dataset), and reports posts where a word-boundary match on the
gate's slur stems (any ending: plurals, end of post, before punctuation) finds something the
gate's substring match did not. Two entries carry a trailing space ("fag ", "paki "), which is
where such misses would come from. Prints counts and locations only, never post text.
"""
import glob, json, os, re, sys

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "spike"))
from live_board import GATE                 # noqa: E402

STEMS = re.compile(r"\b(fag|faggot|paki|nigger|nigga|tranny|kike|spic|chink|retard|wetback|towelhead|dyke|coon)"
                   r"(s|es|ed|ing|z)?\b", re.I)


def posts_of(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    for ti, t in enumerate((d.get("threads") if isinstance(d, dict) else d) or []):
        for pi, p in enumerate(t.get("posts") or []):
            yield ti, pi, p.get("text") or "", p.get("withheld")


def main():
    total = gated = 0
    misses = []
    for f in sorted(glob.glob(os.path.join(ROOT, "spike", "remote", "*.json")) +
                    glob.glob(os.path.join(ROOT, "threads*.json"))):
        for ti, pi, text, withheld in posts_of(f):
            if withheld or text.startswith("["):
                continue
            total += 1
            if any(h in text.lower() for h in GATE):
                gated += 1                   # left in a quarantined thread of the original corpora
                continue
            m = STEMS.search(text)
            if m:
                misses.append((os.path.relpath(f, ROOT), ti, pi, m.group(0).lower()))
    print("posts scanned (not withheld): %d; containing a gate term: %d" % (total, gated))
    print("slur variants the substring gate misses: %d" % len(misses))
    for row in misses:
        print("  %s thread %d post %d: %s" % row)


if __name__ == "__main__":
    main()
