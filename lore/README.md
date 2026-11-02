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
| `explore.py` → `exploratory.json` | **not pre-registered**: the length-matched identification test, register, genre by arm, the gate |
| `REPORT.md` | what it all means: the answer, the correction, read examples, deviations, cost |
| `judging/` | the blinding key and each judge family's per-item verdicts (no quotes) |
| `test_pipeline.py` | the whole pipeline on a fake model that plants an effect, which must be found |
| `MANIFEST.sha256` | SHA-256 of every private file |
| `hop2/PREREGISTRATION.md` | **the second hop**: does an invention survive into a thread that never saw its source? |
| `hop2.py`, `test_hop2.py` | the second hop's prior rule, schedule, generation, blind judge and analysis |
| `hop2/schedule.json` | every generation-2 thread's prior, opener, cast, author order, timestamps and number |
| `hop2/RESULTS.md`, `hop2/results.json` | the second hop's pre-registered analysis (`hop2.py analyze`) |
| `hop2/REPORT.md` | **the second hop's answer**: L4 "survives more than one hop" is met; read examples, deviations, cost |
| `hop2/judging/` | the blinding key and Claude's per-item verdicts (no quotes), with the mis-filed answers it re-judged |
| `hop2/MANIFEST.sha256` | SHA-256 of every hop-2 private file |

## Private files

The generated threads, the judging packets and the judges' raw replies are unfiltered model output.
They stay in `lore/private/` (gitignored), as `spike/remote/` does; `MANIFEST.sha256` lists them by
hash, and the public numbers are computed from them.

## Running it

From the repo root, with Python 3 (on this PC, in WSL: `wsl -e python3`):

```
python -m unittest discover -s lore -p "test_*.py"     # 117 tests, no network
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

The second hop reads the run above in place (`--gen1`, default `lore/private/run`) and checks every
file against `MANIFEST.sha256`; its own private files go to `lore/hop2/private/`:

```
python lore/hop2.py schedule                                # lore/hop2/schedule.json, no calls
python lore/hop2.py dry --gen1 <run folder>                 # pages and the cost estimate, no calls
LORE_ENV=<path to .env> python lore/hop2.py smoke --gen1 <run folder>    # costs money: approve first
LORE_ENV=<path to .env> python lore/hop2.py run --gen1 <run folder> --design full --cap 8
python lore/hop2.py manifest
python lore/hop2.py packets --gen1 <run folder>
python lore/hop2.py claude-prompt 1                         # ... through 8, one Claude subagent each
python lore/hop2.py collect                                 # flags any answer filed under the wrong item
python lore/hop2.py claude-prompt --item <id>               # judge a flagged item again, on its own
python lore/hop2.py collect
python lore/hop2.py analyze --gen1 <run folder>
```
