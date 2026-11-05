# Taste probe: 14 pairs instead of 48 ratings

The blind calibration sets ([../README.md](../README.md)) ask the owner to rate 48 whole threads on
five scales. That is the measurement, and it stays as it is. This probe is a faster, rougher
instrument for a different job: **choosing which way to build next.** Each pair holds the opener
fixed and changes one thing, and the owner just picks the one they'd rather have on the board.

**Written before the owner answered any pair.** The pairs, and what each outcome changes, are fixed
below and in `analyze_probe.py`.

## What the owner said they want

The English board for fun: Backrooms, Kisaragi Station and Samejima-style lore; genuine humour,
including dumb humour like the phonebook thread, as long as it doesn't become incomprehensible.
Incoherence is fine when it reads as posters being facetious, sarcastic, playing dumb or playing
along. The Japanese board is for language learning, with kiokun integration, and has to be fun to read.

## The decisions

| decision | pairs | what's compared (same opener in each pair) | why it's open |
|---|---|---|---|
| **engine** | 3 | the original small base-model cast (round 1–2 bake-off, XTC + DRY) vs. plain Gemini 3.8 Flash under the neutral header | Every thread the owner has picked came from the small cast; both AI judges put it last. The biggest fork: local GPU vs. hosted API. |
| **qwen** | 1 | Qwen3-235B raw continuation, unpicked, vs. plain Gemini, both under `/x/` | A middle path: base-model forum voice with a big model's coherence. Judges rate it low. |
| **register** | 2 | `/x/` header vs. neutral header (plain Gemini once, short temperaments once) | Round 9: the label causes most of the creepypasta. The owner likes paranormal lore *and* plain dumb humour. |
| **roles** | 1 | short temperaments vs. plain Gemini, both neutral | Under the neutral header both judges preferred plain. |
| **naif** | 1 | short temperaments with one post in eight by the small model vs. without, `/x/` | Claude read the small model's posts as glitches; the owner said playing dumb can work. |
| **chaos** | 2 | small cast at the recommended sampler (t 0.5 + DRY) vs. t 1.5 without DRY | Where the owner's line for "too incomprehensible" sits. |
| **jp-engine** | 2 | Japanese 5ch: Gemini vs. Qwen raw | Claude put Gemini first in every packet; no human has read either. |
| **jp-tidy** | 1 | Japanese 5ch: Gemini vs. GPT-5.4 | GPT-5.4 writes a tidier, advice-column register: less natural, maybe easier to learn from. |
| **jp-format** | 1 | Japanese: anonymous 5ch IDs vs. named handles (both Gemini) | Named handles may be easier to follow for a learner. |

Pairs are shown engine first, with decisions interleaved, so stopping early still covers the
biggest ones. Which thread is on the left is seeded random.

## What each outcome changes

A side wins a decision when it takes every pair the owner picked a side on (or all but one, with
three or more). Otherwise the decision is **split**. "Both good" and "neither" count as no preference.

- **engine** → small cast: the English board runs the small local cast, and the next work is
  coherence (picker, early stop) and hosting it. Gemini: the board runs hosted Gemini, neutral
  header, and the small model's role is at most a seasoning. Split: test a hybrid that seeds a
  *shared* confusion.
- **qwen** → Qwen: run a raw-continuation round with a picker under the neutral header. Gemini: drop it.
- **register** → `/x/`: keep a paranormal board identity. Neutral: a general board where strange
  threads are contrast. Split: a board with both kinds, set per thread.
- **roles** → temperaments: keep them. Plain: drop them.
- **naif** → with: keep a confused poster, then test seeding a shared confusion. Without: drop it.
- **chaos** → hotter: loosen the small cast's sampler. Recommended: keep it.
- **jp-engine / jp-tidy / jp-format** → the Japanese board's model, register and format, in that order.

The tags (funny, deadpan, creepy, builds lore, too random, too polished, …) and starred lines say
*why*, and feed the next round's prompt and picker design rather than a verdict.

## Limits

One pair is one thread against one thread, and in the bake-off thread-to-thread variation is about as
large as the differences between arms. Two or three pairs a decision give a direction to test, not a
measurement. Excerpts show the first 12 posts; the rest is a click away, and an OP who leaves and
comes back (posts 7 and 19) may need it. None of the probe's threads is in either blind calibration
set (`build_probe.py` checks), so answering the probe doesn't spoil those.

**A fresh rep for the neutral Gemini arm.** Every round 9 `gemini9neutral` thread that isn't in the
round 9 blind set had a withheld post, so `round3.py gemini9neutral` was run once more on 2026-11-05
(same code, header and gate; $0.39, no post withheld), writing to `calibration/probe/private/`. Its threads stay
private; `key-probe.json` records their hashes.

## Running it

```
python calibration/probe/build_probe.py --data <repo root> --data <folder with spike/remote> --data <folder with threads.final.json>
python -m http.server 8801        # from the repo root
```

Open http://localhost:8801/calibration/probe/probe.html, answer, press **Export**, put the file in
`calibration/probe/answers/`, then `python calibration/probe/analyze_probe.py` writes `RESULTS.md`.
