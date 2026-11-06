#!/usr/bin/env python3
"""Read a generated thread aloud with ElevenLabs (Eleven v4), one voice per poster.

  py -3.12 spike/thread_audio.py mug [--file spike/remote/r10/bakeoff-gemini9neutral.json]

Each post is its own request (Text to Dialogue, one speaker, with the lines around it as context),
so every line can be levelled to the same loudness before they're joined: one dialogue request
for the whole thread came back with some voices much louder than others. Lines are joined with
short, slightly random pauses and written as MP3.

The key comes from .env.local (from `elevenlabs onboard`, gitignored). Output goes to
spike/remote/audio/<script>.mp3 (spike/remote/ is gitignored: thread text stays private).
"""
import argparse, io, json, os, random, re, subprocess, sys, wave

import numpy as np
from dotenv import load_dotenv

SPIKE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SPIKE)
# before the SDK import: it reads ELEVENLABS_API_KEY as it loads
load_dotenv(os.path.join(ROOT, ".env.local"))

from elevenlabs import ElevenLabs
from elevenlabs.types import DialogueInput

RATE = 24000
TARGET_DBFS = -20.0   # loudness of speech, measured over voiced frames only
PEAK_DBFS = -1.0

# Per thread: which opener, a voice per poster (premade voice names), an audio tag per post
# (how the line should land), and text edits (names only there to address someone, dropped).
SCRIPTS = {
    "barista": {
        "opener": "barista",
        "cast": {"gustav": "Charlie", "fatima": "Laura", "hedda": "Alice", "rosa": "Sarah",
                 "brenda": "Jessica", "valeria": "Matilda", "sanne": "River"},
        "tags": {1: "[exasperated]", 2: "[deadpan]", 3: "[indignant]", 4: "[dramatic whisper]", 5: "[curious]",
                 6: "[ominous]", 7: "[bewildered]", 8: "[grimly]", 9: "[panicking]", 10: "[laughing]",
                 11: "[ashamed]", 12: "[deadpan]", 13: "[mocking]", 14: "[theatrical]", 15: "[flatly]",
                 16: "[intense, building]", 17: "[suspicious]", 18: "[realizing]", 19: "[defensive, fast]",
                 20: "[disbelieving]", 21: "[conspiratorial]", 22: "[teasing]", 23: "[cackling]",
                 24: "[slowly, accusing]"},
        "edits": {},
    },
    "mug": {
        "opener": "taking my mug",
        "cast": {"javier": "Liam", "omar": "Callum", "kenji": "Will", "erik": "Daniel",
                          "kwame": "George", "yara": "Lily", "sofia": "Jessica"},
        "tags": {1: "[annoyed]", 2: "[deadpan]", 3: "[scheming]", 4: "[ominous]", 5: "[defeated sigh]",
                 6: "[deadpan]", 7: "[frustrated]", 8: "[deadpan]", 9: "[smug]", 10: "[exasperated]",
                 11: "[thoughtfully]", 12: "[calmly]", 13: "[giggling]", 14: "[resigned, then excited]",
                 15: "[earnest]", 16: "[gently, like a pet expert]", 17: "[completely serious]",
                 18: "[deadpan]", 19: "[firmly]", 20: "[whispering urgently]", 21: "[panicked]",
                 22: "[soothing]", 23: "[horrified]", 24: "[calmly, sinister]"},
        "edits": {19: "i am not biting the mugs. but if i come in on monday and find a chipped saucer in "
                      "the breakroom i'm holding you personally responsible"},
    },
    "post": {
        "opener": "someone else's post",
        "cast": {"kenji": "Chris", "tomas": "Callum", "mira": "Sarah", "javier": "Liam",
                 "hiro": "Eric", "emeka": "Adam", "bridget": "Laura"},
        "tags": {1: "[sheepish]", 2: "[snorts]", 3: "[eager]", 4: "[mock-serious]", 5: "[quietly]",
                 6: "[scheming]", 7: "[uneasy]", 8: "[practical]", 9: "[guilty]", 10: "[softly, moved]",
                 11: "[shaken]", 12: "[urgent]", 13: "[sarcastic]", 14: "[slowly, realizing]",
                 15: "[urgent, piecing it together]", 17: "[stunned whisper]", 18: "[urgent]",
                 19: "[quietly]", 20: "[darkly amused]", 21: "[focused]", 22: "[alarmed]",
                 23: "[determined]", 24: "[dry]"},
        "edits": {4: "U.S.P.I.S. does not play games anon. you're gonna get raided by guys in windbreakers "
                     "over bed bath and beyond coupons"},
    },
}


def speakable(text):
    # board quote links (>>4471) aren't spoken
    text = "\n".join(l for l in text.split("\n") if not l.strip().startswith(">>"))
    text = text.replace("’", "'").strip().strip('"')
    return re.sub(r"\s+", " ", text)


def pcm(client, text, voice_id, prev, nxt):
    kw = {}
    if prev:
        kw["previous_text"] = prev[-100:]   # the API takes at most 100 characters of context
    if nxt:
        kw["future_text"] = nxt[:100]
    raw = b"".join(client.text_to_dialogue.convert(
        inputs=[DialogueInput(text=text, voice_id=voice_id)], model_id="eleven_v4",
        output_format="pcm_24000", **kw))
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def level(x):
    """Scale so voiced speech sits at TARGET_DBFS, with peaks kept under PEAK_DBFS."""
    if not len(x):
        return x
    frame = RATE // 50                                   # 20 ms
    n = len(x) // frame
    rms = np.sqrt(np.mean(x[:n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    voiced = rms[rms > rms.max() * 0.1]                  # ignore pauses and breaths
    loud = np.sqrt(np.mean(voiced ** 2)) if len(voiced) else rms.mean()
    gain = 10 ** (TARGET_DBFS / 20) / max(loud, 1e-6)
    peak = np.abs(x).max() * gain
    if peak > 10 ** (PEAK_DBFS / 20):
        gain *= 10 ** (PEAK_DBFS / 20) / peak
    return x * gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", choices=sorted(SCRIPTS))
    ap.add_argument("--file", default=os.path.join(SPIKE, "remote", "r10", "bakeoff-gemini9neutral.json"))
    a = ap.parse_args()
    cfg = SCRIPTS[a.script]
    client = ElevenLabs()   # reads ELEVENLABS_API_KEY
    with open(a.file, encoding="utf-8") as f:
        thread = next(t for t in json.load(f)["threads"] if cfg["opener"] in t["opener"])
    posts = [p for p in thread["posts"] if p.get("text") and not p.get("withheld") and speakable(p["text"])]

    # premade voices only: the free plan can't use library voices through the API
    voices = {v.name.split(" - ")[0]: v.voice_id for v in client.voices.get_all().voices if v.category == "premade"}
    missing = sorted({cfg["cast"][p["who"]] for p in posts} - set(voices))
    if missing:
        raise SystemExit("voices not in this account: %s" % ", ".join(missing))

    lines = [speakable(cfg["edits"].get(p["n"], p["text"])) for p in posts]
    rng = random.Random(7)
    out = []
    for i, p in enumerate(posts):
        text = ("%s %s" % (cfg["tags"].get(p["n"], ""), lines[i])).strip()
        x = level(pcm(client, text, voices[cfg["cast"][p["who"]]],
                      lines[i - 1] if i else None, lines[i + 1] if i + 1 < len(lines) else None))
        if out:
            # a beat between posts; a longer one when the OP comes back
            gap = rng.uniform(0.35, 0.7) + (0.35 if p["who"] == posts[0]["who"] else 0)
            out.append(np.zeros(int(gap * RATE), dtype=np.float32))
        out.append(x)
        print("#%d %-7s %-9s %.1fs" % (p["n"], p["who"], cfg["cast"][p["who"]], len(x) / RATE), flush=True)

    audio = np.clip(np.concatenate(out), -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    out_dir = os.path.join(SPIKE, "remote", "audio")
    os.makedirs(out_dir, exist_ok=True)
    mp3 = os.path.join(out_dir, "%s.mp3" % a.script)
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "wav", "-i", "pipe:0",
                    "-codec:a", "libmp3lame", "-b:a", "160k", mp3], input=buf.getvalue(), check=True)
    print("wrote %s (%.0fs)" % (mp3, len(audio) / RATE))


if __name__ == "__main__":
    main()
