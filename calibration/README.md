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

## The round 9 set (added after registration)

Added on 2026-11-02, after both AI judge families had scored the 30 items above and before the reader
had rated anything; no text above this section changed. Round 9
([`spike/PREREGISTRATION-ROUND9.md`](../spike/PREREGISTRATION-ROUND9.md)) found that the `/x/` board
header drives plain Gemini's creepypasta, and without it both judge families rated plain Gemini the
round's funniest arm. Its pre-registration left the verdict to the reader: blind, would they keep
reading and laugh more? This set asks them. The questions below, and `analyze.py`'s code for them,
were committed before the reader rated any of its threads.

**What changed for both sets.** `analyze.py` now reads the reader's exports thread by thread: each
thread takes its latest complete rating across all exports, a reader with no ratings in a set is left
out of that set's report, and an undefined ρ reads "not enough ratings" instead of stopping the
script. None of this changes a result computed from one complete export.

**The items.** `build.py` takes six threads from each of three round 9 arms, with the same screen as
above, and `key-r9.json` (public) gives them the ids `c31`–`c48`, so they never share an id with the
first set:

| source | what | thread file (`spike/remote/`) |
|---|---|---|
| `gemini9neutral` | plain Gemini 3.8 Flash under the neutral header `thread 4471` | `bakeoff-gemini9neutral.json` |
| `gemini9` | the same under `/x/ — thread 4471` | `bakeoff-gemini9.json` |
| `rolesshort9` | Gemini with short temperaments, under `/x/` | `bakeoff-rolesshort9.json` |

The openers are matched rather than rotated as in the first set, because these arms are compared with
each other, and round 9 compared arms opener by opener: `gemini9neutral` takes the first six of its
threads that pass the screen, and the other arms try the same openers first. Four threads were skipped
for withheld posts, two in each plain-Gemini arm, so `rolesshort9` has exactly `gemini9neutral`'s six
openers (R3 is fully paired) while `gemini9` shares four of its six with each (R1 and R2). The owner
chose matching over the rotation before anything was rated. `items-r9.json` stays private.

**Rated on its own.** The reader rates these 18 threads apart from the 30, on the same page, scales
and flags (`rate.html?set=r9`), in their own order and with their own saved ratings. Mixing them into
the 30 would have changed what the reader sees in the registered set.

**Questions.** R1 to R3 compare two arms. Each scale's difference of means comes with an exact
two-sided permutation p, over all 924 ways to split the 12 threads six and six, and with the
difference over the openers both arms share. **Humour** is the mean of the reader's deliberate and
deadpan humour, as round 9's judges scored laughs of either kind on one scale. For the reader only
the primary readings get a verdict: **higher** or **lower** when p < 0.05, otherwise **no clear
difference**, once every thread of both arms is rated. That makes four primary readings, uncorrected,
as round 9 named its three; every other scale is descriptive. Each is also given without the threads
the reader marked as seen before. No prediction for the reader.

- **R1, the label:** `gemini9neutral` − `gemini9`; primary: humour. Round 9's judges: humour +2.35
  (Claude) and +1.73 (gpt-5.4) over all eight openers.
- **R2, temperaments under `/x/`:** `rolesshort9` − `gemini9`, the split that replicated in round 9
  (Claude found short roles funnier, gpt-5.4 preferred plain Gemini overall); primary: humour.
- **R3, round 9's question:** `gemini9neutral` − `rolesshort9`: does the reader keep reading and laugh
  more at neutral plain Gemini than at short roles? Primary: interest and humour; round 9's criterion
  is met when both read **higher**.
- **R4, the judges:** Spearman ρ between the reader and each round 9 judge family over the 18 threads,
  on overall (read with H1's thresholds once all 18 are rated), on interest, and with each of the
  reader's humour scales against the judges' one humour score. It uses round 9's own scores, each
  thread's mean over its five readings, so it needs no new judging; the two families' ρ with each
  other is given for reference.

**Limits.** Blind means unlabelled, not unrecognisable: the `/x/` threads' horror register is easy to
spot, and the reader may have read round 9's results. Round 9's judges read the threads side by side
on rubric v2, the reader one at a time on this rubric, so R4 mixes taste with method. With six threads
an arm, only large differences reach p < 0.05. R1 and R2 compare arms that share only four openers,
and in round 9's scores the openers differ about as much as the threads do, so for them the
same-opener figure is the one that holds the opener fixed. For the same reasons, round 9's judges
score these 18 threads a little differently from the whole round (`RESULTS.md` against the figures
above).

**AI judges on this rubric.** `judge.py ... --set r9` writes the packets (`packets-r9/`), the Claude
prompts and the gpt-5.4 calls for this set; its judges aren't told that some threads come from small
base models, since all 18 are Gemini's. Their `scores-r9-*.json` would join R1 to R4 automatically.
Not run: gpt-5.4 needs the owner's OK to spend.

**Running it.**

```
python calibration/build.py --data <folder with the corpora> --data <folder with round 9's spike/remote>
python -m http.server 8000        # from the repo root
```

then open http://localhost:8000/calibration/rate.html?set=r9. **Export** names the file
`ratings-r9-<name>-<date>.json`; put it in `calibration/ratings/` beside the other set's, and
`python calibration/analyze.py` fills in the round 9 section of `RESULTS.md`. Export as often as you
like: each thread counts its latest rating. `build.py` reads each file from the first `--data` folder
that has it and builds every set whose files it finds, naming any it leaves out (`--set r9` makes a
set required); `CALIBRATION_DATA` takes the same folders, joined like `PATH`, for the tests.
