# spike/: the hosted-model bake-off and the live board

The code and judging records from the 2026-11-01/02 session written up in
[`../BAKEOFF.md`](../BAKEOFF.md). It ran from an untracked `spike/` folder on a local branch,
`spike/live-board`, that never had a commit of its own; this is that folder, minus the private
files described below. The scripts are kept as they were last run, throwaway style included,
so the write-up can be traced back to them.

## What's here

| file | what it did |
|---|---|
| `live_board.py`, `index.html` | The live multi-thread board, versions 1 to 2.1 (`index.html` watches it) |
| `modal_board.py` | Runs the board and the self-hosted arms on Modal GPUs (gemma-4-31B, Llama-3.1-70B, the original cast, the round 7 naifs) |
| `bakeoff.py` | Round 1-2 self-hosted arms (`cast`, `g31`, `l70`): same 8 openers and seeded scaffold as `generate.py`, XTC + DRY |
| `openrouter_arm.py` | Round 1-2 OpenRouter raw-continuation arms (`qwen235`, `hermes405`, `euryale70`, `cydonia24`) |
| `echo_arm.py` | The Echo arm (`bakeoff-echo-failed.json` is its first, persona-broken run) |
| `round3.py` | Every English arm from round 3 on: `python spike/round3.py <arm>`, arm names as in `judging/LEDGER.md` |
| `jp_bakeoff.py` | The Japanese round, 5ch and named-handle formats |
| `browse.html`, `rate.html` | Side-by-side thread viewer with scores, and a blind rating page for a person (`rate.html?round=8` was added afterwards, for the reader's verdict on round 8) |
| `judging/round3_judge.py`, `judging/jp_judge.py`, `judging/aggregate.py` | Packet builders, the gpt-5.4 judge, and the per-round reports used in the session |
| `judging/prompts/` | Every Claude judge prompt, verbatim, and which rubric each judge got |
| `judging/*/key.json`, `judging/*/scores-*.json` | The blinding keys and every judge's raw scores, best lines and failure notes |
| `judging/ledger.py` → `judging/LEDGER.md` | Recomputes every number in `BAKEOFF.md` from the score files, with paired tests |
| `judging/raw-stats.json` | Post lengths, withheld posts, logged spend and hashes, computed from the private files |
| `MANIFEST.sha256` | SHA-256 of every private file, so the public numbers point at exact private outputs |

## What's not here, and why

The generated threads themselves (`remote/`), the judging packets (which contain the full threads),
the board snapshots, the board's quarantine log and the run logs stay out of the repo, for the same
reason as the original corpora (see the main README): they are unfiltered model output, and the
keyword gate is known to leak. `.gitignore` here keeps them out; `MANIFEST.sha256` lists all 140
by hash. A private snapshot exists outside the repo; ask the repo owner.

## Checking the numbers

From the repo root, with nothing but Python 3:

```
python spike/judging/ledger.py --check
python -m unittest discover -s spike/judging -p "test_*.py"
```

With the private files in place, `python spike/judging/ledger.py rawstats` re-hashes them, rebuilds
every judging packet from `key.json` and the raw threads, and compares the result with the packet
the judges read, byte for byte. All 74 packets match, so the private files are exactly what was
judged. `cd spike && sha256sum -c MANIFEST.sha256` checks the rest. `python spike/gate_audit.py`
looks for slur variants the keyword gate's substring match would miss (none in 26,388 posts).

## Things to know before reusing it

- **Every English prompt starts with `/x/ — thread 4471`.** That is `generate.py`'s document
  header, and `live_board.py` uses the same board name: every English thread here was written for
  the paranormal board. The Japanese prompts have no board label.
- **The gate ran after generation in English.** `round3.py` and `bakeoff.py` write a whole thread
  and only then replace posts that hit the keyword list with `[post withheld]`, so flagged posts were
  in the context while later posts were written. `jp_bakeoff.py` and `live_board.py` withhold a post
  before it enters the context.
- **Packets were written on Windows.** A post containing its own `\r\n` (Euryale's output does)
  reads back with an extra blank line. `ledger.py rawstats` allows for exactly this when it compares.
- **Re-running needs keys and money.** `.env` (gitignored) needs `OPENROUTER_API_KEY`; the free-tier
  gpt-5.4 picker and judge use `OPENAI_API_KEY` and stop before the daily allowance; Echo needs
  `ECHO_API_KEY`. The self-hosted arms need Modal and the GGUFs. The session spent about $16 on
  OpenRouter, $30 of Echo credit and a few dollars of Modal.
- **Hosted models change.** Model ids and providers are in the code; there are no seeds for hosted
  sampling, so a re-run gives new threads, not these ones.
