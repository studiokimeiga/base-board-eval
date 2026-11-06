#!/usr/bin/env python3
"""Read a generated thread aloud with ElevenLabs (Eleven v4, Text to Dialogue), one voice per poster.

  py -3.12 spike/thread_audio.py [--opener barista] [--file spike/remote/r10/bakeoff-gemini9neutral.json]

The key comes from .env.local (written by `elevenlabs onboard`, gitignored) as ELEVENLABS_API_KEY;
the SDK reads it from the environment. Output: spike/remote/audio/<opener>.mp3 (spike/remote/ is
gitignored, so thread text stays private). Delivery is steered with v4 audio tags per post.
"""
import argparse, json, os, re, sys

from dotenv import load_dotenv

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)
# before the SDK import: it reads ELEVENLABS_API_KEY as it loads
load_dotenv(os.path.join(ROOT, ".env.local"))

from elevenlabs import ElevenLabs
from elevenlabs.types import DialogueInput


# Voice casting: gender as the thread treats each poster, personality from their posts.
# (preferred premade voice names, gender for the fallback)
CAST = {
    "gustav": (["Charlie", "Liam", "Will", "Chris"], "male"),     # the bewildered, defensive OP
    "fatima": (["Laura", "Jessica"], "female"),                  # flat deadpan
    "hedda": (["Alice", "Lily", "Charlotte"], "female"),          # dramatic, conspiratorial
    "rosa": (["Sarah", "Aria"], "female"),                        # curious
    "brenda": (["Jessica", "Matilda"], "female"),                 # brash roaster
    "valeria": (["Matilda", "Aria", "Charlotte"], "female"),      # sardonic
    "sanne": (["River", "Lily", "Sarah"], "female"),              # dry detective
}

# v4 audio tags for the barista thread, by post number: how each line should land.
TAGS = {
    1: "[exasperated]", 2: "[deadpan]", 3: "[indignant]", 4: "[dramatic whisper]", 5: "[curious]",
    6: "[ominous]", 7: "[bewildered]", 8: "[grimly]", 9: "[panicking]", 10: "[laughing]",
    11: "[ashamed]", 12: "[deadpan]", 13: "[mocking]", 14: "[theatrical]", 15: "[flatly]",
    16: "[intense, building]", 17: "[suspicious]", 18: "[realizing]", 19: "[defensive, fast]",
    20: "[disbelieving]", 21: "[conspiratorial]", 22: "[teasing]", 23: "[cackling]",
    24: "[slowly, accusing]",
}


def choose_voices(client, names):
    voices = client.voices.get_all().voices
    by_first = {}
    for v in voices:
        by_first.setdefault(v.name.split()[0], v)
    used, out = set(), {}
    for who in names:
        prefs, gender = CAST.get(who, ([], "female"))
        v = next((by_first[p] for p in prefs if p in by_first and by_first[p].voice_id not in used), None)
        if not v:
            v = next((x for x in voices if (x.labels or {}).get("gender") == gender and x.voice_id not in used), voices[0])
        used.add(v.voice_id)
        out[who] = v
        print("%-8s -> %s" % (who, v.name))
    return out


def speakable(text):
    text = text.replace("’", "'").strip().strip('"')
    return re.sub(r"\s+", " ", text)


def chunks(items, limit=2800):
    """Split the dialogue into requests under the per-request text limit."""
    cur, size = [], 0
    for it in items:
        if cur and size + len(it.text) > limit:
            yield cur
            cur, size = [], 0
        cur.append(it)
        size += len(it.text)
    if cur:
        yield cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(SPIKE, "remote", "r10", "bakeoff-gemini9neutral.json"))
    ap.add_argument("--opener", default="barista")
    a = ap.parse_args()
    client = ElevenLabs()   # reads ELEVENLABS_API_KEY
    with open(a.file, encoding="utf-8") as f:
        thread = next(t for t in json.load(f)["threads"] if a.opener in t["opener"])
    posts = [p for p in thread["posts"] if p.get("text") and not p.get("withheld")]
    voices = choose_voices(client, list(dict.fromkeys(p["who"] for p in posts)))
    lines = [DialogueInput(text=("%s %s" % (TAGS.get(p["n"], ""), speakable(p["text"]))).strip(),
                           voice_id=voices[p["who"]].voice_id) for p in posts]
    out_dir = os.path.join(SPIKE, "remote", "audio")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s.mp3" % a.opener)
    with open(out, "wb") as f:
        for i, part in enumerate(chunks(lines)):
            for b in client.text_to_dialogue.convert(inputs=part, model_id="eleven_v4",
                                                     output_format="mp3_44100_128"):
                f.write(b)
            print("part %d: %d lines" % (i + 1, len(part)), flush=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
