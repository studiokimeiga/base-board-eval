# Blind calibration: does an AI judge share the reader's taste?

Every hosted-model result in [BAKEOFF.md](../BAKEOFF.md) is an AI judge's score, and the two judge
families disagree on the question that matters most (round 8: Spearman −0.17). The project's best
threads came from a 4B model, and the mechanism that makes them good, sincere confident wrongness,
is the kind of thing a coherence-minded judge could miss. This kit puts the same 30 threads in front
of the reader and the AI judges, blind, on the same scales, so their preferences can be measured
separately and compared.

**This file was committed before any item was rated or judged.** The hypotheses below are fixed;
the analysis in `analyze.py` computes exactly them.

## The items

`build.py` picks 30 threads, six from each source, with seed 20261102:

| source | what | where from |
|---|---|---|
| `bestof` | the six [BEST-OF.md](../BEST-OF.md) threads, whole (the office statistics thread has 32 posts; BEST-OF.md shows 20) | original corpora |
| `smallrand` | six unselected threads from the recommended config (run 14) | `threads.final.json` |
| `gemini` | plain Gemini 3.8 Flash | bake-off rounds 4–8 |
| `rolesshort` | Gemini with quiet per-poster temperaments and post lengths | round 8 |
| `qwenpick` | Qwen3-235B raw continuation, best-of-3 with a gpt-5.4 picker | round 3 |

Each bake-off arm uses six of the eight bake-off openers, rotated so each opener appears two or three
times. Any thread with a withheld post, a term on the board's gate list, or a word on a stricter
exclusion list (`build.py`) is skipped in favour of the next one; two `rolesshort` threads were
skipped for withheld posts. Every thread is shown the same way: numbered posts, handles, the
starter marked OP, no timestamps or model names, in a random order per rater.

`key.json` (public) maps item ids to sources and records a SHA-256 of each rendered thread.
`items.json` holds the thread text and stays private like the rest of the generated output; rebuild
it with `python calibration/build.py --data <folder with the corpora and spike/remote>`.

## The scales

Identical for the reader and the judges (`rubric.json`): **believable**, **interest**, **deliberate
humour**, **deadpan humour**, **overall** (1–5 each), and **would repost** (yes/no). The reader also
marks threads they have **seen before** (they will recognise some BEST-OF threads), threads they
**would not publish**, and lines they like.

## Hypotheses

- **H1, agreement.** Spearman ρ between the reader's overall ratings and each AI judge's, over the
  30 items. ρ ≥ 0.6: the judge is usable as a first screen; 0.3–0.6: weak; below 0.3: not usable.
  The ceiling to compare against is the agreement between two independent Claude passes.
- **H2, the deadpan blind spot.** The reader's gap between `bestof` and the hosted threads (mean of
  `gemini`, `rolesshort`, `qwenpick`) on deadpan humour is larger than each AI judge's gap.
  Predicted: yes.
- **H3, temperaments.** The reader rates `rolesshort` above `gemini` on deliberate humour (as Claude
  did in round 8), and not lower overall. Predicted: humour yes; overall unknown.
- **H4, the phonebook thread** (the reader's own earlier pick) lands in the reader's top 7 of 30 on
  overall, and each AI judge ranks it lower than the reader does. Predicted: yes.
- **Open, no prediction:** which source the reader finds most believable, and whether the judges agree.

Predicted for the AI judges before running them: both families put `gemini` or `rolesshort` first
on overall, `bestof` below both, and `smallrand` last.

Every comparison is also reported without the items the reader marked as seen before. Intervals
are bootstrap 95% intervals over items (2,000 resamples, seeded).

## Running it

Rate (the reader):

```
python -m http.server 8000        # from the repo root, with calibration/items.json built
```

then open http://localhost:8000/calibration/rate.html. Ratings stay in the browser until you press
**Export**, which downloads a JSON file; put it in `calibration/ratings/`.

Judge (the AI side):

```
python calibration/judge.py packets            # one text file per item, for the Claude judges
python calibration/judge.py claude-prompt A 1  # the exact prompt for Claude pass A, batch 1 of 3
python calibration/judge.py gpt                # gpt-5.4, one call per item, free daily allowance
```

Analyse, at any point: `python calibration/analyze.py` writes `RESULTS.md` from `key.json`, the
judges' `scores-*.json` and whatever is in `ratings/`. `python -m unittest discover -s calibration`
runs the tests.
