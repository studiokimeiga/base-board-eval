# Round 12: how hard Gemini thinks before each post

Written before any thread was generated.

## Why

Round 6 (BAKEOFF.md 5c) found temperature barely matters for Gemini: it plans a post before writing
it, so heat mostly changes wording. If the plan is where the humour comes from, the setting that
controls the plan should matter more. The live board uses `low` (chosen for cost, never compared).

## Arms

All three are the live board's setup: the plain prompt under the neutral header, with round 11's
tidy fixes (spike/TIDY.md). Same 8 openers and scaffold as every round. Only the thinking level
differs (OpenRouter `reasoning.effort`, which maps to Gemini's `thinkingLevel`):

- `think12min`: minimal
- `think12low`: low (generated fresh today, so it isn't compared against an older run)
- `think12high`: high

    BAKEOFF_OUT=spike/remote/r12 py -3.12 spike/round3.py think12min   (and low, high)

## The owner's A/B

probe.html?set=think: per opener, minimal vs low and high vs low, sides shuffled, 16 pairs, the arms
hidden. Picks are A, B, both good or neither.

Rule, per comparison (8 pairs): an arm wins if it's picked in at least 5 and loses at most 1;
otherwise it's a split. The live board changes only if `minimal` or `high` wins against `low`.

## Predictions

1. `minimal` writes shorter, flatter replies, more one-liners and fewer built-up bits; the owner
   prefers `low` to it.
2. `high` reads much like `low` (the plan saturates early) and is a split, while costing clearly
   more per post in thinking tokens.
3. Thinking tokens per post: minimal < low < high, with high at least twice low.

## Results

(filled in after the owner's picks)
