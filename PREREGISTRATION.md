# Pre-registration — run 5 (volume / base rate)

## Honest timing

- `experiments/generate5.py` written **14:04:12** — the full design is fixed in that file.
- Run launched, first output at **14:05:40**.
- This document written **14:06**, i.e. *after* launch.
- **No output has been read** at time of writing. 11 of 142 threads existed.

So: the *design* is genuinely pre-registered (it's in a timestamped file, and every
choice below was stated in conversation before the command ran). The *analysis plan*
is written ~2 minutes after generation began. That's weaker than a real
pre-registration and it should be read as such. The thing it still buys: the outcome
measures and the stopping rule are fixed before any thread has been looked at, which
is the failure mode that killed four proxies in this project.

## Question

How often does an unassisted base model, given nothing but an opener, produce a
thread a person would carry out of the room?

Not a model comparison. One arm, one config. The comparison this run *does* make is
seeded vs unseeded openers.

## Fixed before generation

- **Arm**: gemma-4-E4B base @ Q8_0 (`ggml-org`). The Q4_K_M of this checkpoint is a
  confirmed broken file — 26% word-like vs 84% — and is excluded from everything.
- **Injected into the prompt**: the opener, and nothing else. No system prompt, no
  stems, no name seeding, no stub thread, no example thread.
- **Sampling**: temp 1.0, min_p 0.05, top_p 1.0, top_k 0, repeat_penalty 1.0,
  n_predict 120, ASCII-only grammar, stop on `\n\n` + participant handles.
- **DRY**: 0.8 / base 1.75 / allowed_length 4 / **penalty_last_n 256**. Short window
  chosen so local loops die but thread-wide name reuse stays invisible to it;
  validated on the warm-up (1.6 spontaneous name mentions/thread, unseeded).
- **No XTC.** This run is the baseline XTC will be measured against.
- **Volume**: 142 threads, 16 posts each. 9 seeded openers × 8 reps = 72;
  5 unseeded × 14 reps = 70. Strata balanced, openers deliberately not.
- **Append-only**: no thread regenerated, retried, edited, or skipped. Empty
  completions are left as gaps.

## Outcome measures, fixed before reading

1. **plausibly_human** — binary, per thread.
2. **repost** — binary, per thread.
3. Primary quantity: **P(repost | plausibly_human)**, reported with an interval,
   pooled and split by stratum (seeded vs unseeded).
4. For every flagged thread, a required free-text **tell**: the one line that made
   me flag it. Expected to be worth more than the rate.

## Declared in advance

- **Opener 9** ("electricity bill the same to the cent") is a planted numeric probe
  testing whether flat numeric correction is the carrier. Reported **separately**,
  never pooled into the seeded rate.
- **Opener 3** ("no apartment 12") has produced both quarantine events so far, from
  two different models and two configs. A third would make opener-level risk
  concentration a finding rather than coincidence.
- **The triage rule sorts reading order and never filters.** It was fitted in-sample
  on 15 labelled threads and its precision will not be reported as validated. DRY at
  256 is expected to make its `echo4 >= 35%` clause inert.
- **Salted calibration**: 5 known threads (phonebook, bland-instruct, two collapses,
  one middling) shuffled into the reading queue, positions recorded, so rater drift
  shows up as a position effect rather than a feeling.
- **Post 1 hidden by default.** Rating happens on posts 2–16, then post 1 is
  revealed and any change of view is recorded. The delta measures how much the
  openers are carrying rather than the model.

## What this run cannot answer

- **Per-opener rates.** ~4 expected events across 14 openers. The 2×2 structure makes
  the corpus interpretable and is hypothesis-generating only; a 2-vs-1 split across
  cells is not an effect.
- **The opener-clustering hypothesis, non-circularly.** The good-set that generated it
  was selected by reading, and the hypothesis has already been stated to the rater.
  The opener *is* post 1, so blinding is impossible by construction. This needs a
  second rater with no context — which is also the only test that matters for the
  product, since "would a stranger carry this out of the room" was never answerable
  by the person who built it.

## Safety

Quarantine routes at generation time on a crude, recall-oriented phrase list, chosen
asymmetrically: a false positive costs one thread, a miss costs shipping the content.
Rate to date: 2 of 66 threads (3.0%). Expect ~4 here. See `QUARANTINE.md`.
