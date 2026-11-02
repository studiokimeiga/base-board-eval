# lore/reader/: does memory make threads better? A blind reader test

**This file was committed and pushed before anyone rated.** The hypotheses, the exact set (fixed
by `build.py` and its seed, with every thread's hash in `key.json`) and the analysis
(`analyze.py`) are fixed here. Any later change is reported as a deviation next to these.

The lore run ([`../REPORT.md`](../REPORT.md)) showed that one completed earlier thread above a new
one changes what it says: its register, and in about a quarter of threads specific invented
material, such as the duck union. Every judgement of whether that makes threads *better* has come
from AI judges. This kit asks the reader, blind.

## What the reader sees

Each **set** is three threads from the lore boards:

1. **An earlier thread on this board**, the source.
2. **Two follow-ups**, A and B, that began with the same opening post, cast, timing and thread
   number. One was written with the earlier thread above it on the page (memory); the other
   without (no memory). Nothing says which.

The reader knows that one of the two saw the earlier thread, but not which. The page reveals it
only after export.

**Per follow-up.** The calibration kit's five scales, verbatim from `calibration/rubric.json` v1:
believable, interest, deliberate humour, deadpan humour, overall, each 1–5. Then *would repost*
(yes/no), *does it pick up anything from the earlier thread?* (yes/no), and *I've seen lines from
this thread before*. That last one matters: `../REPORT.md` quotes some of these threads.

**Per set.** Which follow-up would you rather read (A/B), and optional notes.

## The set: 8 triples, and why not 12

The request was "about 12 triples, 30–40 minutes". The data says 12 would take about an hour. The
median triple runs 6,400 characters on `/misc/` and 8,600 on `/x/`: source plus both follow-ups,
read and rated, comes to about 5 minutes on `/misc/` and 6 on `/x/`. **8 triples** (64,700
characters in all) fit roughly 40–50 minutes. The page saves progress, so it can be done in two
sittings.

`build.py` (seed 4471) draws them:

- **Screened** as in `calibration/build.py`: the source and both follow-ups must have no withheld
  post, no gate term, and nothing from its stricter word list. 32 of 46 `/misc/` triples and 23 of
  46 `/x/` triples pass.
- **Stratified by whether transfer happened.** The length-matched identification test of
  `../explore.py` says whether the memory follow-up's text points to its own source. A random 6 of
  32 could easily contain no transfer at all, so the draw takes, on `/misc/`, **3 triples where the
  source was identified and 3 where it wasn't**. On `/x/` it takes 1 and 1.
- **One triple per source**, so no earlier thread is read twice.
- **Memory is follow-up A in exactly half** of each board's triples, at random, so reading order
  cannot favour either arm.
- **Set order** is random per reader, saved in the browser, as in the calibration kit.

| set | board | source identified? | characters |
|---|---|---|---:|
| r01 | /misc/ | yes | 18,636 |
| r02 | /misc/ | no | 7,084 |
| r03 | /misc/ | yes | 7,531 |
| r04 | /misc/ | no | 4,392 |
| r05 | /x/ | no | 7,163 |
| r06 | /x/ | yes | 8,552 |
| r07 | /misc/ | yes | 4,578 |
| r08 | /misc/ | no | 6,769 |

`key.json` records each set's board, target, source, stratum, the SHA-256 of every rendered
thread, and **which side was memory**. **Don't open `key.json` before rating.**

**A known skew on `/x/`.** The keyword gate withheld innocent posts mostly in `/x/` memory threads
("scraped", "draped"; `../REPORT.md`), and the screen drops any triple with a withheld post. So the
`/x/` memory follow-ups that reach the reader are the less heavily horror-laden ones. The `/x/`
contrast is weaker than the board's.

## Hypotheses and predictions, fixed before rating

- **R1 (primary): on `/misc/`, the reader prefers the memory follow-up in more than half of the
  triples.** Prediction: 4 or more of 6.
- **R1b: the preference is stronger where the source was identified.** Prediction: 3 of 3
  identified triples, against about half of the rest.
- **R2: on `/x/`, no preference for memory.** Memory `/x/` threads run longer and heavier.
  Prediction: at most 1 of 2.
- **R3: the reader says a follow-up picks up the earlier thread more often for memory follow-ups.**
  Prediction: at least 3 of the 4 memory follow-ups in the identified sets, and at most 1 of the 8
  no-memory follow-ups.
- **R4, scales (memory minus no memory, per triple).** Prediction: on `/misc/`, interest and
  deliberate humour higher; believability no higher. No prediction for deadpan or overall.
- **R5, the instruments.** The reader's pick-up answers are compared with the tracker's flag and
  with the judges' blind verdicts on the same follow-ups (from `../results.json` and
  `../judging/`): agreement and κ. Claude judged only the `/misc/` items. No prediction.

## Analysis (`analyze.py`)

- **Complete sets only:** both follow-ups rated on every scale, repost and pick-up answered, and a
  preference given. Memory and no memory are mapped back from A and B through `key.json`.
- **Statistics:** counts with Wilson 95% intervals; the exact two-sided sign test for R1; paired
  differences per scale. With 6 `/misc/` triples, R1 can only reach p < 0.05 at 6 of 6, so these
  are measurements of direction and size, not significance tests. A second reader, or a second set
  built the same way, would add power.
- **Seen before:** every result is reported with and without sets where either follow-up was
  marked seen before.
- **Raters:** each reader's export is reported separately; nothing is pooled across raters.

## How to rate

1. **Build the set** (once), with the lore run's private threads:
   `python lore/reader/build.py --run <experiment/lore-transfer checkout>/lore/private/run`.
   It writes `items.json`, which is gitignored. Then serve the repo root:
   `python -m http.server 8000 --bind 127.0.0.1`.
2. **Rate** at http://127.0.0.1:8000/lore/reader/rate.html. When done, press **Export**, put the
   file in `lore/reader/ratings/`, and run `python lore/reader/analyze.py`, which writes
   `RESULTS.md`.

`python -m unittest discover -s lore/reader -p "test_*.py"` runs the tests (19, no network).
