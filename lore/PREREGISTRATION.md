# Pre-registration: does lore spread between threads when the board has memory?

**Committed before any thread for this experiment was generated.** The tracker, its tests, its
validation, the generation harness and the judge prompt follow in later commits, all before
generation. Anything changed after this commit is listed under "Deviations" in `RESULTS.md`,
with the pre-registered version reported alongside.

Written 2026-11-02, branched from `evidence/bakeoff-recovery` at `5347524`.

## Why

The Backrooms/Samejima question: board folklore needs a referent that turns up again in unrelated
threads until it reads as something everyone already knows. One thread on its own can't produce that,
so the board needs memory. What the repo has so far:

- **The local board-memory run** ([FINDINGS.md](../FINDINGS.md), `experiments/generate17.py`):
  with one completed earlier thread above a new one, the "physical number" construction came back
  as "physical X" in **2 of 2** target threads against **0 of 20** others. Exact coinages recurred
  0 of 8 times; an exact-phrase detector reported a false null. The run had 24 threads, coinages
  picked by reading, and the small local cast.
- **Live board v2.1** ([BAKEOFF.md](../BAKEOFF.md)) put one earlier thread above 5 of 18 threads.
  Posters asked "what happened to 4468?", but every prompt shows thread numbers, and that thread
  had no earlier thread above it. That is format play. Nobody measured what carried over.
- **The hosted stack** (Gemini 3.8 Flash through OpenRouter, the bake-off's best AI-judged writer)
  has never been given memory.
- **Every English prompt so far began with `/x/ — thread 4471`**, the paranormal board.

## Hypotheses

**H1 (primary).** A new thread shown one completed earlier thread from its board carries material
from that earlier thread more often than the same new thread written without it.

Secondary:

- **H2, form.** Most of what transfers is an explicit reference or a mix-up (the new thread
  discussing the old thread's situation as if it were its own). *Lore-level* reuse (below) is rare.
- **H3, format play.** Mentions of thread numbers other than the earlier thread's own number occur
  in both arms at similar rates. They come from the page furniture and are not memory.
- **H4, header.** Under `/x/`, threads use more paranormal-genre vocabulary than under a neutral
  `/misc/` header.
- **H5, recurrence.** Each earlier thread has two later targets. The same item reaches both of
  them more often with memory than without.
- **Open, no prediction:** whether the header changes how much transfers.

**My predictions, made before any data.** Transfer (tracker, primary outcome): 30–60% of memory
targets against at most 10% of their no-memory twins. Lore-level reuse in at most 10% of memory
targets. Recurrence (H5) in at most 3 of 46 sources. More genre vocabulary under `/x/`.

## Design

### Generator

Gemini 3.8 Flash through OpenRouter (`google/gemini-3.8-flash`), with the bake-off's plain-Gemini
call (`spike/round3.py::gemini_arm`): temperature 1.0, reasoning effort low, max 1200 tokens,
everything else at defaults. The OpenRouter listing checked on 2026-11-02 gives $0.825/M input tokens
and $4.125/M output and reasoning tokens. The bake-off logged $0.0023 a post for this call. Each call
also carries a `seed` derived from (header, thread, post), the same in both arms. That is best effort
only; nothing assumes determinism. The smoke test records whether a repeated call reproduces.

### Boards and threads

There are four boards: {`/x/`, `/misc/`} × {memory, none}. Each board has 23 source threads and
46 target threads.

- **Sources (generation 0).** One per opener in `openers.ALL`: 22 mundane openers plus the
  own-number text. Each runs to 24 posts with nothing above it. The memory and no-memory boards
  under a header **share** their sources. They are one board's past with two different futures, so
  the boards differ only in the factor under test.
- **Targets (generation 1).** Each source gets **two** targets, with different openers that share
  no topic tag with it (work, home, kitchen, neighbour, names, messaging, identity, family/friends,
  public, phone). Each opener is a target twice. The pairing comes from a seeded random search, and
  the schedule file records it before generation. Each target is written **twice**, with the same
  opener, cast, author order, timestamps and thread number:
  - **memory:** the complete source thread is above it on the page;
  - **none:** nothing is above it.
- That makes 46 sources + 184 targets = **230 threads, 5,290 generated posts**.

### Factor 1: memory (primary)

On the memory board the page is `<source header>\n\n<source posts>\n\n<target header>\n\n<target
posts so far>`. On the no-memory board it is `<target header>\n\n<target posts so far>`. Posts are
rendered `handle timestamp\ntext`, as in `spike/live_board.py`. The source is shown **whole and
complete**, all 24 posts, never a catalogue of openers. That is the v1 failure. Withheld posts are
never shown.

### Factor 2: header

`/x/ — thread N` against `/misc/ — thread N`. The neutral board changes only the board code. All
of a board's threads, sources and targets, carry its header.

### Fixed across boards: the same scaffold for the same thread

- **Openers:** `openers.ALL`, mostly mundane, as above.
- **Cast:** 7 handles from `generate.NAMES`. A target's cast **excludes its source's 7 handles**,
  in both arms.
- **OP timing.** Each thread draws one pattern, balanced 8/8/7 within sources and 16/15/15
  within targets:
  - *away*: the thread goes quiet for 2–6 hours before each of the OP's two returns, at a post
    from 6–9 and one from 16–20. Otherwise the OP posts at `generate.py`'s rate, 0.22.
  - *burst*: the OP posts only in two bursts of 2–3 posts, 5–40 seconds apart, one starting at
    posts 3–6 and one at posts 11–16.
  - *gone*: the OP never posts again after the opener.
- **Newcomer:** a cast member who hasn't posted yet posts 13. Other gaps run 40–540 seconds, and
  other authors are chosen uniformly from the cast except the last poster, as in `generate.py`.
- **Thread numbers:** sources 4471–4493, targets from 4494 in a seeded order. Every target keeps
  the same number in both arms.
- **Timestamps:** sources from Mon 10/26/26, targets from Thu 10/29/26, staggered, in
  `live_board.py`'s format.
- **Gate:** `live_board.GATE` (harm list plus sexual terms) is checked before a post enters the
  page. A withheld post is never shown again and goes to a private quarantine log.
- **No early stopping.** Every thread runs to 24 posts, so the arms can't lose threads at
  different rates.
- **Stops:** `\n\n`, the board header, and a newline followed by any handle of the cast or the
  source. The stop list is identical in both arms.

### Instruction, identical in both arms

```
Here is a page from an imageboard:

<page>

Write the next post in the last thread on the page, by <handle>. Reply with only the text of the post.
```

The bake-off's wording, "Here is an imageboard thread so far … the next post in the thread",
misdescribes a page that holds two threads. That could push the model to treat them as one thread
and inflate mix-ups in the memory arm. This wording is accurate in both arms. As in the bake-off,
the page doesn't show the new post's own header.

### Order of generation

All sources come first. Then memory and no-memory targets go out interleaved, so any drift in the
model or the provider hits both arms equally. The provider OpenRouter routes each call to is logged.

### Smoke test

This happens only after the owner approves the budget. One `/x/` source and both arms of one of
its targets, three threads in all, check the harness end to end and measure cost per post. One
repeated call checks the seed. The smoke threads are **excluded**, hashed separately, and
regenerated in the real run. Only harness errors may change anything. The smoke threads' content
may not.

## Measurement 1: the lore tracker (built, tested and frozen before generation)

The tracker scores a target thread T against a source thread S, **whether or not T was shown S**.
Every no-memory target is scored against the same source text as its memory twin, a text it never
saw. Every hit there is chance: shared vocabulary, the model's habits, format play. The memory
effect is the difference within pairs. That keeps the tracker honest. It also means the thread
numbers every page shows can't fake an effect, because they are equally present in both arms.

What it reports (exact rules in `tracker.py`, committed and frozen before generation):

1. **Transferred items.** Material distinctive of S that shows up in T's generated posts. An item is
   a word or a 2–3 word phrase from S that is rare on the board, appearing in at most 5% of the
   background threads. The background is the other sources, never targets, so it doesn't depend
   on the arm. To count, the item must also be absent from T's opener and from the *topic twin*
   (the generation-0 source written from T's opener, which shows what T's topic produces anyway).
   It counts as transferred if:
   - it is a word used **at least twice** in T, counting reuse with a new partner word
     ("physical number" → "physical milk") as a *construction*;
   - or it is a phrase used once;
   - or it is two distinctive words from one S post appearing together in one T post (a reused
     rule or invention).
2. **Grounded references.** S's thread number, a handle that posts only in S, or an
   earlier-thread phrase ("the other thread", "last thread") in a post that also carries an
   S item.
3. **Format play, counted and never treated as memory:** T's own number, numbers near it or near
   S's, post numbers (`>>123456`, `No. 995808`), the board's name, and "this thread"/"OP" talk.

**Primary outcome (binary, per target):** *transfer* means at least one transferred item or at
least one grounded reference.

**Validation acceptance criteria.** The tracker must pass all four on existing data before it is
frozen. Its thresholds may be tuned on this validation data only, and any tuning is recorded.

- **A1, known positive (construction).** In the local memory run (`threads.memory.json`, priors
  rebuilt by `generate17.py`'s selectors), both targets shown the "physical number" prior
  (ids 11 and 15) are flagged, with "physical" among their items. This is the false null an
  exact-phrase detector produced.
- **A2, known positive (mix-up).** In v2.1, thread 4483 (under 4475) is flagged, with 4475's
  material among its items. See the labels below.
- **A3, format play.** v2.1 thread 4481's numbers (4468, 4477, 4452, 4488, 4516) are format play,
  not references. In no thread does a number count as a reference unless that thread's page showed
  it.
- **A4, false positives.** On *sham pairs*, threads scored against an earlier thread they never
  saw, the transfer flag fires on at most 15% of pairs in each dataset. For v2.1 that means every
  thread against every earlier thread it wasn't shown. For the memory run, every target against
  every prior it wasn't shown.

**Hand labels for v2.1, written from reading the board before the tracker existed:**

| target ← source | label | where |
|---|---|---|
| 4479 ← 4475 | none | "the better friend and person" echoes 4475's "better person": coincidence. "on this board" talk is format |
| 4480 ← 4473 | none | the model-written OP's "a place like /x/" is format |
| 4483 ← 4475 | **transfer (mix-up)** | posts 20–23: "She thinks her boss is very petty", "And you think she's petty", a manager who expects coffee. 4475's situation is pinned on 4483's OP |
| 4484 ← 4472 | none | |
| 4488 ← 4473 | none | only 2 replies |
| the 13 threads with no prior | none, by construction | format play in 4481 (thread numbers), 4477 and 4486 (post numbers), 4473, 4478 and 4485 (thread/board talk) |

## Measurement 2: blind judges

- **Items:** each of the 184 targets with its source, as "Thread A (earlier)" and "Thread B
  (later)". The arm is hidden and the order is shuffled.
- **Question:** what in B seems to come from A? Each borrowing is classified *reference*, *mix-up*
  (A's situation treated as B's own), *reuse* (something from A applied to B's own situation) or
  *coincidence*. Then B borrows from A yes/no, with a confidence of 1–5. The prompt is committed
  verbatim before judging.
- **Two families:** gpt-5.4 (through OpenRouter, or the free OpenAI allowance), and Claude Opus 5.5
  subagents in batches. If usage limits don't allow Claude to judge every item, it judges a
  random half, chosen with seed 20261102 before any judging.
- Any "yes" on a no-memory item is a false positive by construction.

## Levels: what counts as persistent culture, and what is format play

| level | name | definition |
|---|---|---|
| L0 | **format play** | Anything the page furniture explains: the thread's own number and numbers near it, post numbers, the board name, talk of "this thread", OP, the board or posting. It is on every page in both arms, so it is never evidence of memory. |
| L1 | **reference** | A pointer that only the earlier thread can explain: its number, a handle that posts only there, or an earlier-thread phrase that carries its material. |
| L2 | **transfer** | Material distinctive of the earlier thread reappears (the tracker's rule). Mix-ups count. |
| L3 | **lore** | Transfer that is *reused*, applied to the new thread's own situation (a blind judge's *reuse*, not *mix-up* or *coincidence*), and used by **at least two** of the new thread's posters. "physical milk" in a barista thread is the model case. |
| L4 | **persistent culture** | The same item recurs in two unrelated threads that each saw it once (H5); or it travels more than one hop; or the board treats it as known. This design tests only the first. |

Claims are graded by the highest level reached above its no-memory rate. "The board has lore"
needs L3 cases on memory boards, with no-memory boards at or near zero. "Persistent culture" needs
L4, which one hop can only begin to test.

## Analysis (`analyze.py`, committed before judging)

- **Per board** (header × arm): counts k/n with Wilson 95% intervals for transfer, grounded
  references, L3 lore, number play and recurrence. Also withheld and empty posts.
- **Memory effect (H1),** pooled over headers and then per header. 92 pairs (target, memory vs
  none), McNemar exact, two-sided. The difference in proportions gets a 95% bootstrap interval
  that resamples sources, because a source's two targets aren't independent (2,000 resamples,
  seed 20261102). As a robustness check, a sign test on the per-source difference.
- **Items per target:** a sign test on the paired differences.
- **Judges:** the same tests. Agreement with the tracker (Cohen's κ) for each family, and between
  the families.
- **H2:** the share of memory-arm transfers that the judges classify reference, mix-up or reuse.
- **H3:** number play in each arm, paired by target, with a sign test.
- **H4:** the share of generated posts with a genre term (list below), per thread. Sources and
  no-memory targets are paired by role and opener across headers, giving 69 pairs, with a sign
  test. Memory targets are left out because their sources differ.
- **H5:** sources whose two memory targets share a transferred item, against the same count for
  no-memory targets.
- **Exclusions: none.** Failed calls stay as empty posts, append-only, and are reported.
- **Read examples:** I read every memory-arm transfer and every no-memory false positive. Both are
  reported with short quotes, gate-checked. This reading is **not blind** and is labelled as such.
  The blind numbers are the judges'.

**Genre terms for H4** (lowercase, whole words): ghost, ghosts, ghostly, haunt, haunted, haunting,
demon, demons, demonic, entity, entities, paranormal, supernatural, occult, ritual, rituals,
cursed, curse, possessed, possession, apparition, poltergeist, exorcism, seance, ouija, omen,
phantom, specter, spectre, wraith, doppelganger, skinwalker, cryptid, eldritch, liminal,
backrooms, otherworldly, uncanny, eerie, creepy, sinister, ominous, unholy, "shadow people",
"shadow person", "the void", "not human", "another dimension", "glitch in the matrix".

## Budget, and the owner's approval

Nothing is generated until the owner approves a budget. The estimate uses OpenRouter's listed
prices and the bake-off's logged $0.0023 a post. A memory post costs about $0.0008 more, because
it adds about 1,000 input tokens.

| design | threads | generation | gpt-5.4 judge | total, about | hard cap in code |
|---|---:|---:|---:|---:|---:|
| **full** (as above) | 230 | $14.0 | $2.6 | **$17** | $20 |
| one target per source | 138 | $8.2 | $1.3 | $9.5 | $12 |
| `/x/` only, two targets per source | 115 | $7.0 | $1.3 | $8.5 | $10 |

If the free OpenAI allowance covers gpt-5.4, its share costs nothing. Claude judging uses the
subscription, not money. The smoke test is about $0.20 of the generation figure. If a reduced design
is approved, the analysis is the same minus what it drops: H5 needs two targets per source, and H4
needs both headers.

## What this cannot show

One hop only. One model with one instruction, so chat-model behaviour may not carry over to the
small base cast that produced "physical X". AI judges, not the reader, whose taste is uncalibrated
(see the calibration kit). Two targets per source is the least that can show recurrence (L4), not
community memory. The reader, not this design, decides whether an L3 case is *good* lore.
