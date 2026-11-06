# Round 10: what kind of post comes next

**Written before any round 10 thread was generated or read.**

## Why

The owner's taste probe (calibration/probe) chose plain Gemini under a neutral header as the English
engine. Their main criticism of the plain Gemini thread they liked best ("my dad has started forwarding
me his own emails") was that it was "all gas no brakes". Nearly every reply was a bit topping the one
before, and following hyperbole after hyperbole takes effort. Real funny threads have pauses between
the jokes: a reaction, a plain question, someone answering literally, someone missing the joke.

In plain Gemini, a poster's character comes only from their own earlier posts. Once a thread starts
riffing, each post raises the bar, and nobody plays the straight man.

Round 7–9's per-poster temperaments are not the fix. They locked posters into one move for the whole
thread, and the storyteller temperament filled 9–18% of replies with "this happened to my cousin in
Dublin" anecdotes, which the owner found diluting.

## The arm

`moves10`: plain Gemini 3.8 Flash under the neutral header (`thread 4471`), with the round 9 gate run
before context. It adds one sentence to every non-OP post, telling Gemini what kind of post it is.
The kind is drawn per post, with seed `MOVES_SEED` = 1010, from (opener, post number) only. It never
depends on model output. The OP is left alone.

| move | weight | |
|---|---:|---|
| react | 20 | a few words, no joke of its own |
| ask | 17 | a plain question to the OP or the last poster |
| straight | 17 | a sincere, literal answer or advice |
| doubt | 10 | blunt doubt or a nitpick |
| tangent | 7 | latching onto a minor detail or drifting off topic |
| misread | 5 | skimmed and got the wrong idea, sincerely |
| joke | 18 | one or two lines |
| riff | 6 | a longer bit, a short paragraph at most |

Jokes and riffs together are 24%. The exact wording of each move is in `round3.py` (`MOVES`). Each post's
move is saved on the post as `move`.

**Control:** `gemini9neutral` was run again from the same code, at the same time, into the same folder,
so the owner hasn't seen either side. Same 8 openers and the same scaffold as rounds 1–9.

```
BAKEOFF_OUT=spike/remote/r10 py -3.12 spike/round3.py moves10
BAKEOFF_OUT=spike/remote/r10 py -3.12 spike/round3.py gemini9neutral
```

## What would count

**Owner A/B (the decision).** Eight pairs, one per opener, sides shuffled with a seed. The owner picks
left, right, both good or neither, and the tags include "all gas no brakes" and "too flat / boring".

- moves10 wins at least 5 of the pairs where a side was picked, with at most 1 against: build the board
  with per-post moves. The next round tunes the weights from the tags.
- plain wins on the same terms: drop moves. The owner's complaint was about one thread, not the arm.
- Otherwise it's split. If the tags say "too flat" on the moves side, raise joke/riff. If they say
  "all gas" on the plain side, keep moves but lower their weight.

**Mechanical predictions** (checked before the owner reads, reported whichever way they go):

1. moves10 has more short replies: at least 30% of non-OP posts under 40 characters (plain was 20% in
   the 2026-11-05 rep).
2. moves10 has fewer long replies: under 6% over 250 characters (plain was 9%).
3. Both arms stay near 0% on the "this happened to my cousin" anecdote pattern. The "straight" move
   asks for advice, not stories.
4. The risk to watch: "misread" and "tangent" posts read as broken rather than as people. If more than
   a third of them read broken to Claude, say so before the owner sees the threads.

## Cost

About $0.40 per arm ($0.80 in total), going by the 2026-11-05 gemini9neutral rep.
