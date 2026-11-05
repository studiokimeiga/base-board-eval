# Pre-registration: bake-off round 9

Written on 2026-11-02, before any round 9 thread existed, and pushed together with everything that
runs the round: the arms (`spike/round3.py`), the Modal runner (`spike/modal_board.py::r9`),
packets, judging and tagging (`spike/judging/round3_judge.py`), the analysis
(`spike/judging/ledger.py`), and offline tests for all of it (`spike/test_round3.py`,
`spike/judging/test_ledger.py`). Generation starts only after those commits are on GitHub, whose
push time is the timestamp, and after the repo owner has approved the spend (estimate below).

Before this was written, the only model output read was from rounds 1 to 8: one round 8 thread from
each of plain Gemini and short roles, the judges' notes from rounds 7 and 8, a word-list count over
earlier files, and the tagger check on round 8 described under "Drift".

## Questions

1. **A narrower hybrid.** Round 7 gave 2 of the 7 posters to the small gemma-4-E4B base model (XTC +
   DRY) for whole threads, and both judge families marked it down: one confused poster among fluent
   ones reads as broken. Does an *occasional* small-model post, 1 in 8, spread across posters, help
   short-temperament Gemini threads instead?
2. **The board label.** Every English prompt so far began with `generate.py`'s `/x/ — thread 4471`,
   the paranormal board. Plain Gemini's threads drift into creepypasta, and both families named "the
   same ominous voice" as its main failure in rounds 7 and 8. With everything else fixed, does a
   neutral header reduce that drift, for plain Gemini and for short temperaments?
3. **Replication.** In round 8 Claude rated short temperaments funnier than plain Gemini (+1.50
   humour), while gpt-5.4 preferred plain Gemini overall (4.38 against 3.00). Does that disagreement
   hold on fresh threads?

## Arms

Five new arms, written together in one Modal container (all five at once; only one needs the GPU).
New names, so no earlier file is touched.

| arm | header | posts written by | answers |
|---|---|---|---|
| `gemini9` | `/x/ — thread 4471` | Gemini 3.8 Flash, one neutral instruction per post (round 4's `gemini`) | 2, 3 |
| `rolesshort9` | `/x/ — thread 4471` | Gemini with short temperaments (round 8's `rolesshort`) | 1, 2, 3 |
| `rolesshort9naif` | `/x/ — thread 4471` | as `rolesshort9`, except 3 posts per thread by gemma-4-E4B base, XTC + DRY | 1 |
| `gemini9neutral` | `thread 4471` | as `gemini9` | 2 |
| `rolesshort9neutral` | `thread 4471` | as `rolesshort9` | 2 |

**Held fixed, as in rounds 3 to 8:** the 8 openers (`bakeoff.py`'s `OPENER_PICKS`); the seeded
scaffold from `generate.py` (7 handles per thread, author order, timestamps, the OP away and back at
posts 7 and 19, a newcomer at 13), which never depends on model output; 24 posts per thread;
`google/gemini-3.8-flash` through OpenRouter at temperature 1.0, reasoning effort low, max_tokens
1200; the per-post instruction (`ASK`); the six temperaments and their lengths (`ROLES`,
`ROLE_LENGTH`), assigned by a hash of the handle; and the gate list (`GATE`, the harm list plus the
sexual-term list).

**Changed for every arm, relative to round 8:**

- **The gate runs before a post enters the context**, as the Japanese runs and the live board did.
  A post that matches is replaced by `[post withheld]` in the thread the next poster sees, and its
  text goes to a private quarantine file (`spike/remote/quarantine-<arm>.jsonl`), so the gate's false
  positives can be counted. Nothing is regenerated.
- Each post records who actually wrote it (`model`) and Gemini's `finish_reason`, so posts cut off by
  max_tokens can be counted. (Earlier files label every post with its scaffold voice and log "eos".)

**The neutral header is `thread 4471`:** the label is removed rather than replaced. Every other board
name carries its own genre (`/b/` shock, `/adv/` advice, off-topic banter), and the question is
whether `/x/` causes the drift. The test in `spike/test_round3.py` checks that the two headers'
prompts differ in nothing else.

**The small model's posts** (`rolesshort9naif`, `python spike/round3.py plan`): in each third of the
replies (posts 2–9, 10–17, 18–24), one post by someone other than the OP, drawn with
`random.Random(9090 + opener index)`. That is 3 of 24 posts, and they are written by whoever the
scaffold has posting, so no single poster is the confused one. The small model sees the raw thread,
as round 7's naifs did, and can't be given a temperament; the OP is always Gemini.

| opener | posts by the small model (handle) |
|---|---|
| 1 mug washed and moved | 6 kenji, 11 kwame, 22 yara |
| 2 text from my own number | 3 astrid, 15 astrid, 20 finn |
| 3 the guy behind me answers my questions | 2 priya, 16 gustav, 23 yara |
| 4 my name at the end of every sentence | 3 dmitri, 13 rosa (the newcomer), 20 dmitri |
| 5 the group chat renamed itself | 9 paloma, 13 boris (the newcomer), 20 omar |
| 6 a different name on my cup | 8 hedda, 10 brenda, 18 sanne |
| 7 someone else's post for a year | 2 tomas, 15 javier, 20 tomas |
| 8 dad forwards his own emails | 9 niall, 11 niall, 18 mei |

**A smoke run first:** one thread per arm (`modal_board.py::r9 --out r9-smoke --threads 1`), written
to its own folder, checked only for plumbing (the header, who wrote which post, non-empty
small-model posts, the gate's files) and then set aside. It is never judged.

**Append-only.** No thread is regenerated, edited or dropped. If an API failure stops an arm, a rerun
resumes its file and writes only the missing threads; that would be reported.

## Judging

Every packet holds one opener and all five arms' threads, lettered A–E. Each opener's packet is
written in **five versions whose letter orders are the five rotations of one random order**
(`random.Random(9393)`), so every arm is read in every position exactly once per opener: a Latin
square per opener, 40 readings per judge family. The ledger shows a first-position bonus in rounds
1–8 (+0.20 Claude, +0.44 gpt-5.4 above the packet mean); this cancels it within every comparison,
and averaging five readings per thread cuts the judges' own noise (a thread's score moved about 0.6
points between judgings in earlier rounds).

- **Both families judge on `RUBRIC_V2`, verbatim**, the rubric both used in round 8.
- **gpt-5.4:** `round3_judge.py gpt r9 --paid`: OpenRouter, reasoning effort low, one call per
  reading, the round 8 prompt with the packet appended. A reply that isn't valid JSON, or doesn't
  score every letter 1–5, is a technical failure and is asked again (at most twice); the number of
  tries and the usage are logged.
- **Claude:** ten Claude Opus 5.5 subagents with default settings, as in rounds 1–8. Judges 1–5 read
  openers 1–4 and judges 6–10 openers 5–8, judge *s* reading version ((*s* − 1) + (opener − 1)) mod 5
  + 1, so each opener's five versions go to five different judges and no judge reads an opener
  twice. `round3_judge.py blind` copies the packets to a folder with nothing else in it and writes
  the prompts (`prompts/r9_claude_judge-*.txt`); each judge saves its JSON there, and `collect`
  checks it before copying it into `judging/r9/`.
- A thread's score, per family, is the mean of its five readings; every comparison is per opener.

## Drift: the measures

- **Primary: HORROR posts.** A blind tagger labels each post from 2 to 24 HORROR or not, by
  `TAG_DEFINITION` in `round3_judge.py`:

  > A post is HORROR when it is written in the register of horror fiction or creepypasta: it treats
  > what is happening as sinister or supernatural, gives ominous warnings or instructions ("don't
  > open it", "get out of the house tonight"), speaks of an unnamed presence ("whatever it is", "it
  > knows you're there"), or describes dread, curses, rituals, hauntings or body horror. A post that
  > raises such an idea only to doubt or mock it is not HORROR, and neither is a post that is merely
  > odd, absurd or funny. Posts marked "[post withheld]" are not HORROR.

  Each thread is labelled alone (one thread per file), once by gpt-5.4 (`tag_gpt`, one call per
  thread) and once by a Claude subagent (five taggers, eight threads each: every opener once, arms
  mixed, `prompts/r9_claude_tag-*.txt`). Neither is told the arm. A thread's measure is the share of
  its 23 replies labelled HORROR, averaged over the two taggers.
- **Secondary:** the share of non-OP posters with at least one HORROR post (each tagger); the share of
  the judges' readings whose `main_failure` names the horror register (`HORROR_NOTE` in `ledger.py`),
  and the share that also says the posters sound alike (`SAME_NOTE`: the "single ominous voice");
  and the taggers' agreement (Cohen's κ over the 920 post labels).
- Reference values from round 8, by the same patterns (`test_ledger.py` pins them): Claude named the
  horror register in 6 of 8 plain-Gemini notes and 0 of 8 short-role notes, gpt-5.4 in 5 and 1; the
  "same ominous voice" pattern matched 3 and 2 plain-Gemini notes, no short-role note.
- **Tried and dropped: a word list.** A list of explicit supernatural words (ghost, haunted, entity,
  demonic, ritual, "whatever it is" and so on) matched 1.6% of plain Gemini's round 8 posts and 2.2%
  of short roles' (0–3% across earlier English arms), so it doesn't see the drift both judges
  described: Gemini's creepypasta is ominous instructions and an unnamed "it", not vocabulary.
- **Tagger check on round 8**, before this commit: two Claude subagents tagged round 8's plain-Gemini
  and short-roles threads blind, with the prompt above (each saw every opener once, 4 threads of each
  arm). Plain Gemini: 74% of replies HORROR, and 81% of non-OP posters wrote at least one; short
  roles: 42% and 33%. Plain Gemini was higher in 6 of 8 openers; one of the other two, opener 5, is
  the only plain-Gemini thread whose notes from neither family named horror (tagged 17%). Most of
  short roles' HORROR posts are the OP's own reports, which is why the posters measure separates the
  arms more than the post share. Each tagger opened only its eight files (checked in the subagent
  transcripts). The check ran once, and the definition was not changed after it.

## Hypotheses and how each will be read

All tests are exact two-sided sign tests over openers with ties dropped (the ledger's convention);
with 8 openers, p < 0.05 needs no losses and at least 6 wins, and with the 16 pooled pairs of H2,
13 wins to 3 losses when none is tied. The tests named here are the confirmatory ones; everything
else in the ledger is exploratory. There is no correction for multiple tests; there are three
named hypotheses.

- **H1, the narrower hybrid** (`rolesshort9naif` vs `rolesshort9`). Prediction: no gain; round 7's
  naifs lowered overall with both families. Reading: *promising* if both families score it higher on
  humour and not lower overall; *harmful* if both score it lower overall; otherwise *mixed*.
  Reported alongside: the small model's posts withheld, and the share of readings whose
  `main_failure` calls the thread nonsense (`NONSENSE_NOTE` in `ledger.py`; in round 7 it matched 2
  of 8 Claude notes and 3 of 8 gpt-5.4 notes for the naif arm, 0 and 1 for plain Gemini).
- **H2, the board label** (`gemini9neutral` vs `gemini9`, `rolesshort9neutral` vs `rolesshort9`).
  Prediction: the neutral header lowers the HORROR share in both pairs, and the judges' horror notes
  for plain Gemini. Confirmatory test: the 16 per-opener differences in HORROR share (both pairs
  pooled). *Supported* if the pooled difference is negative with p < 0.05 and each tagger family's
  pooled difference is negative; *not supported* if it is zero or positive; otherwise *weak*. Effects
  on the judges' scores are reported without a prediction.
- **H3, replication of round 8** (`rolesshort9` vs `gemini9`). Prediction: Claude's humour higher for
  short roles, and gpt-5.4's overall higher for plain Gemini. *Replicates* if both directions hold;
  p-values reported.
- **Exploratory:** short roles vs plain Gemini under the neutral header; position within thread (the
  Latin square makes it measurable thread by thread); how far a thread's five readings spread.

## What none of this decides

Every score here is an AI judge's. The reader's own blind ratings outrank all of them, and are still
pending for round 8. The human criterion for both changes is the reader's: blind, would they keep
reading and laugh more at an arm's threads than at `rolesshort9`'s? This round decides only which
arms are worth putting in front of the reader.

## Cost estimate, for approval before any spending

| item | estimate |
|---|---|
| Gemini generation, 5 arms (OpenRouter list price $0.825/M input, $4.125/M output; earlier Gemini arms cost $0.30–0.47 each) | $1.50–2.40 |
| Smoke run (1 thread per arm) | about $0.10 |
| Modal: one L4 ($0.80/h) or A10G for 20–40 minutes, smoke run included | $0.30–0.80 |
| gpt-5.4 judging, 40 readings (≈ 6k tokens in, ≈ 2–3k out each, at $2.50/M and $15/M) | $2–3 |
| gpt-5.4 tagging, 40 threads | $0.50–1 |
| Claude judges and taggers: 15 Opus 5.5 subagents | no API cost (plan usage) |
| **total** | **about $5–7; approval asked for up to $10** |

The OpenRouter key had $82.48 of its $100 limit left when this was written.

## Where everything goes

- Private (ignored by git, hashed in `spike/MANIFEST.sha256`): the threads
  (`spike/remote/bakeoff-<arm>.json`), the quarantine files (`spike/remote/quarantine-<arm>.jsonl`),
  the smoke run (`spike/remote/r9-smoke/`), the packets (`spike/judging/r9/opener-N-vK.txt`) and the
  tag files (`spike/judging/r9/tag-N-L.txt`).
- Public: `spike/judging/r9/key.json`, `scaffold.json` (handles only), every score, tag and usage
  file, the prompts in `spike/judging/prompts/`, `raw-stats.json`, `LEDGER.md`, and a short section
  in `BAKEOFF.md`.

## Events after registration

Added during the run. Nothing above this heading changed after the pre-registration was pushed
(`f468fe4`, 16:02Z on 2026-11-02).

- **16:05Z, approval.** The owner approved up to $10.
- **Smoke run.** The first attempt crashed on this side before anything ran remotely (the Modal
  CLI printed a "✓" into a Windows console encoding that can't hold it). The rerun wrote one thread
  per arm and passed every plumbing check: the headers, the small model's posts 6, 11 and 22, and
  a withheld post's quarantine record. Gemini cost $0.19. The threads are set aside, unjudged.
- **Accounting fix (`6e68377`).** The gpt-5.4 usage log now counts every paid try of a call that
  was asked again. What is asked and how replies are checked did not change.
- **16:12–16:18Z, the full run stopped on HTTP 402.** The OpenRouter account had $1.05 of its $20
  credit left. The "$82.48 of its $100 limit" in the cost section was the key's own cap, not the
  account's balance, and OpenRouter reserves worst-case credit for each request in flight (about
  $0.27 per Gemini call, $1.92 per gpt-5.4 call with no max_tokens). One thread was finished and
  kept (`rolesshort9`, opener 1). The other arms' threads in progress were lost ($0.21 of Gemini
  logged); one of them had a withheld post, whose quarantine record is kept privately in
  `spike/remote/r9-stopped-run/` and is not counted. Spend so far, Modal included: about $0.57.
- **16:22–16:40Z, the resumed run.** After the owner added credit (balance checked directly: $21.04),
  the rerun kept the saved `rolesshort9` thread and wrote the other 39. Every arm then had 8 full
  threads, and the checks against this design in `spike/test_round3.py` passed: the same scaffold as
  a dry run, the small model's posts exactly as planned and nowhere else, and no stored post with a
  gate term.
- **Judging, as registered.** Each family read all 40 packet versions. gpt-5.4's replies were all
  valid at the first try ($0.87), and so were the tagger's ($0.24). The 15 Claude subagents' prompts
  are byte-identical to `prompts/r9_claude_*.txt` (checked against their transcripts), and each
  opened only its own packet or tag files: two also searched their own packets for curly quotes, and
  one re-read its own packets to check its quotes.
- **The gate** withheld 9 posts in the judged threads: 2 real matches, and 7 innocent substrings
  ("hospice" four times in one thread, "scrape" or "scraped" three times).
- **Spend.** Gemini $2.03 logged, gpt-5.4 $1.11, and Modal about 30 GPU-minutes: about $3.60 of the
  $10 approved.
