"""Round 11 (spike/TIDY.md): two fixes to plain Gemini that leave its prompt alone.

  strip_vocative   drop a name a reply only uses to address someone ("stefan, check the log" ->
                   "check the log"); the caller passes the poster right above and the OP. A name
                   that points at someone ("stefan is right", "ask stefan") stays.
  overused         the pet insult a poster would be using for the third time in a thread, so the
                   caller can re-roll that one post.

Pure functions on text; round3.py wires them in (tidy_arm).
"""
import re

POST = re.compile(r"\n\n(\S+) \d\d/\d\d/\d\d\(\w{3}\)\d\d:\d\d:\d\d\n")

# After a leading name, a word that makes the name a form of address rather than the subject:
# "calvin do not…", "marcus how do you…", "omar you're asleep…". Verbs that make the name the
# subject ("marcus did it", "stefan is right") are deliberately absent.
ADDRESS_NEXT = ("you|your|you're|youre|ur|u|do|don't|dont|stop|what|why|how|where|who|when|get|go|"
                "run|check|tell|calm|please|pls|listen|look|leave|open|close|turn|answer|wake|lmao|lol|"
                "bro|dude|man|wtf|holy|honestly|seriously|literally|no|yes|yeah|ok|okay|wait|relax|"
                "chill|shut|read|unlock|take|grab|put|walk|drive|reply|send|delete|"
                "throw|stay|keep|hold|never|i|i'm|im|we|this|that|wash|offer|whenever|need|"
                # a pronoun straight after a name makes it address: "ines he has you on an algorithm"
                "he|she|they|it|there|someone|everyone|nobody")
# Before a trailing name without a comma, a word that makes the name an object ("i blame marcus",
# "ask stefan"), so it stays.
OBJECT_BEFORE = {"to", "with", "at", "for", "from", "blame", "ask", "asked", "tell", "told", "like",
                 "than", "and", "or", "about", "is", "was", "said", "says", "named", "called", "by",
                 "of", "on", "trust", "believe", "listen", "agree", "not", "sorry", "thank", "thanks",
                 "unlike", "as", "but", "even", "only", "also", "just", "me", "off", "up", "out", "in",
                 "into", "onto", "over", "after", "behind", "near", "kick", "ban", "block", "ping",
                 "tag", "invite", "add", "see", "saw", "hear", "heard", "help", "find", "found", "kill"}

INSULTS = re.compile(r"\b(dumbass(?:es)?|idiots?|morons?|retards?|dipshits?|jackass(?:es)?|clowns?|"
                     r"losers?|apes?|nerds?|freaks?|psychos?|schizos?|weirdos?|dumb ?fucks?|"
                     r"absolute (?:fool|idiot|moron|clown)s?)\b", re.I)


def posts_in(prompt):
    """[(who, text)] for every finished post in a raw thread prompt (the last header is the post
    being written)."""
    heads = list(POST.finditer(prompt))
    out = []
    for a, b in zip(heads, heads[1:]):
        out.append((a.group(1), prompt[a.end():b.start()]))
    return out


def _cap_like(original, text):
    return text[:1].upper() + text[1:] if original[:1].isupper() and text else text


def strip_vocative(text, name):
    """text without `name` where it's only addressing them, or text unchanged."""
    n = re.escape(name)
    stripped = text.strip()
    new = re.sub(r"^%s\s*,\s*" % n, "", stripped, flags=re.I)
    if new == stripped:
        new = re.sub(r"^%s\s+(?=(?:%s)\b)" % (n, ADDRESS_NEXT), "", stripped, flags=re.I)
    if new == stripped:
        new = re.sub(r"\s*,\s*%s([.!?]*)$" % n, r"\1", stripped, flags=re.I)
    if new == stripped:
        m = re.search(r"(\S+)\s+%s([.!?]*)$" % n, stripped, flags=re.I)
        titled = m and m.group(1)[:1].isupper() and not re.search(r"[.!?]$", m.group(1))  # "Senior Ines"
        if m and not titled and m.group(1).lower().strip(".,!?") not in OBJECT_BEFORE and len(stripped.split()) >= 3:
            new = stripped[:m.start()] + m.group(1) + m.group(2)
    if new == stripped or len(new.split()) < 1 or not re.search(r"\w", new):
        return text
    return _cap_like(stripped, new)


def overused(text, author, earlier, limit=2):
    """The insult in `text` that `author` already used `limit` times in `earlier` posts, or None."""
    mine = " ".join(t for who, t in earlier if who == author).lower()
    for m in INSULTS.finditer(text):
        word = m.group(1).lower().rstrip("s") if not m.group(1).lower().endswith("ss") else m.group(1).lower()
        stem = re.escape(word.replace(" ", " ?"))
        if len(re.findall(r"\b%s" % stem, mine)) >= limit:
            return m.group(1).lower()
    return None
