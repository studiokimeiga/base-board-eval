# lore/: does lore spread between threads when the board has memory?

A pre-registered, controlled version of the Backrooms/Samejima question. Twin boards differ only in
whether a new thread is shown one completed earlier thread, crossed with a neutral `/misc/` header
against `/x/`. Read [`PREREGISTRATION.md`](PREREGISTRATION.md) first: it was committed before
anything was generated, and fixes the design, the outcomes and the analysis.

| file | what it is |
|---|---|
| `PREREGISTRATION.md` | design, hypotheses, outcomes, levels from format play to persistent culture, budget |
| `tracker.py`, `test_tracker.py` | the lore tracker: what in a target thread came from one source thread |
| `reference.py` → `reference.json` | what is too common in the project's other 916 English threads to be lore |
| `validate.py` → `VALIDATION.md`, `validation.json` | the tracker checked on v2.1 and the local memory run before it was frozen |
| `board.py`, `test_board.py` | the seeded schedule, the pages, and generation with Gemini 3.8 Flash |
| `schedule.json` | every thread's opener, cast, author order, timestamps and number (no model output) |
| `judge.py`, `test_judge.py` | blind judges: gpt-5.4 and Claude, verdicts in `judging/` |
| `analyze.py`, `test_analyze.py` → `RESULTS.md`, `results.json` | the pre-registered analysis |
| `test_pipeline.py` | the whole pipeline on a fake model that plants an effect, which must be found |
| `MANIFEST.sha256` | SHA-256 of every private file |

## Private files

The generated threads, the judging packets and the judges' raw replies are unfiltered model output.
They stay in `lore/private/` (gitignored), as `spike/remote/` does; `MANIFEST.sha256` lists them by
hash, and the public numbers are computed from them.

## Running it

From the repo root, with Python 3 (on this PC, in WSL: `wsl -e python3`):

```
python -m unittest discover -s lore -p "test_*.py"     # 73 tests, no network
python lore/validate.py --data <private folder>        # rewrites VALIDATION.md
python lore/board.py dry                               # pages and the cost estimate, no calls
LORE_ENV=<path to .env> python lore/board.py smoke     # costs money: the owner approves first
LORE_ENV=<path to .env> python lore/board.py run --design full --cap 20
python lore/board.py manifest
python lore/judge.py packets
LORE_ENV=<path to .env> python lore/judge.py gpt
python lore/judge.py claude-prompt 1                   # ... through 8, one Claude subagent each
python lore/judge.py collect
python lore/analyze.py
```

`<private folder>` holds `spike/remote/` and the original corpora, as for `calibration/build.py`.
