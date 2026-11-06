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

## First run, discarded before anyone rated it

The first run used the bake-off's old budget (max_tokens 1200), and thinking comes out of that
budget. `high` thought about 1,140 tokens a post, so 60 of its 184 posts were cut off mid-sentence,
and a few leaked the model's own notes. `low` had 13 cut, `minimal` 7. The keyword gate also withheld
two posts for "retardant" and "scraper" (it matched inside words), which dropped two high/low pairs.
Kept in spike/remote/r12-budget1200/.

The rerun uses the live board's settings, which got the same fix the same morning: max_tokens 3000,
and a post that is still cut off is written once more (`gemini_arm(live=True)`). The gate now
matches single words as whole words (`gate_hits`), as the live gate does. Arms, pairs, rule and
predictions are unchanged.

## Fourth arm, added before the rerun finished and before any rating

- `think12mix`: a third of each thread's posters (2 of 6, never the OP) think at high in every post,
  everyone else at low; about 23% of posts. Chosen by a fixed per-name ranking, so the same names
  tend to be the sharp ones across threads (`mix_high`). The idea: one or two people building bits
  while the rest react, closer to a real thread than everyone planning, and cheaper than all-high.

The page gets 8 more pairs, mix vs low (24 in all, fewer if any are screened out). Same rule.

Prediction 4: if `high` beats `low`, `mix` beats `low` at least as clearly (the bits come from the one
or two who build them; the rest reacting gives the "brakes" plain Gemini lacks). If `high` splits,
`mix` splits too.

## The rerun, as generated (before rating)

| arm | thinking tokens/post | $/post | median chars | under 40 | over 250 | cut retries | still cut |
|---|---|---|---|---|---|---|---|
| minimal | 430 | 0.0022 | 110 | 14% | 2% | 0 | 0 |
| low | 577 | 0.0027 | 61 | 26% | 2% | 0 | 0 |
| high | 2,923 | 0.0116 | 52 | 40% | 5% | 19 | 7 |
| mix | 1,110 | 0.0048 | 82 | 29% | 11% | 7 | 4 |

(Thinking tokens count every call, retries included.) `high` thinks about 5x `low` and costs
about 4.3x; even 3000 tokens wasn't always enough, so 7 of its posts (4%) are still cut off on
the page, and 4 of mix's. On the live board those would be dropped, not shown.

The page builder's own screen (calibration/build.py) also matched gate terms inside words and
dropped three threads ("scraped", "raccoon", "suspicious"); it now matches whole words, as the
spike and live gates do. All 24 pairs are on the page. The answer store is `probe-answers-think-v2`,
so nothing from the discarded first build carries over.

## Results

(filled in after the owner's picks)
