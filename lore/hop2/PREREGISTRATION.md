# Pre-registration: does lore survive a second hop?

**Committed before any thread for this experiment was generated.** The harness (`lore/hop2.py`), its
tests, the schedule and the judge prompt follow in the next commit, also before generation.
Anything changed after this commit goes under "Deviations" in `REPORT.md`, with the pre-registered
version reported alongside.

Written 2026-11-02, branched from `experiment/lore-transfer` at `e3223cc` (PR #4).

## Why

PR #4 ([`../PREREGISTRATION.md`](../PREREGISTRATION.md), [`../REPORT.md`](../REPORT.md)) put one
completed earlier thread above a new one. Post length carried over at r = 0.85. With length held
fixed, specific invented material carried over too: the source could be identified from 25 of 92
memory targets, against 1 of 92 without memory. On the neutral `/misc/` board, three sources put the
same invention into both of their unrelated targets: a duck union from a bike-rack thread, "Brenda
from Compliance" and her lavender soap, and a hedge trimmer. By #4's levels that is lore (L3), plus
the first of L4's three criteria ("recurs in two unrelated threads that each saw it once").

Every target in #4 saw its source directly. L4's second criterion, "it travels more than one hop",
is still untested. It is the difference between a running joke and something the board remembers.

**The question:** does an invention that reached a thread from its source carry on into a third
thread that never saw the source?

## Hypotheses

**H1 (primary).** Take a generation-1 thread that inherited material from its source and put it
above a new, unrelated thread. The new thread is then identifiable as descending from the source
more often than its sham twin, which is written under the generation-1 thread's no-memory twin. The
source is on neither page.

Secondary:

- **H2, the named item.** A lore item of the source (the duck union, the lavender, the hedge
  trimmer) appears in more lore-arm threads than sham-arm ones.
- **H3, the blind judge.** Claude, shown the source and the new thread without the arm, finds
  borrowing from the source more often on the lore arm.
- **H4, lore at the second hop.** The item is reused in the new thread's own situation by at least
  two posters (#4's L3 rule) more often on the lore arm.
- **H5, register.** A new thread's post length follows the thread above it, in both arms.
- **Open, no prediction:** which lineage survives best, and whether names of the source's posters
  travel two hops the way they travelled one.

**My predictions, made before any data.** H1: the source is identified in 15–35% of lore-arm targets
and at most 5% of sham targets. H2: a lore item in 10–25% of lore-arm targets, none on the sham arm.
The duck union is likeliest, since it was the most elaborated. H3: Claude says "borrows" for 15–35%
of lore items and at most 3% of sham items. H4: 5–15% against 0. H5: r above 0.5 on the lore arm.
The L4 verdict below: "met", at about 60% confidence.

## Design

### Generations 0 and 1: #4's run, read in place

The sources (generation 0), the priors and their shams (generation 1) are #4's private threads. They
are read where they are (`--gen1`, by default `lore/private/run/`), and each file is checked against
its SHA-256 in [`../MANIFEST.sha256`](../MANIFEST.sha256) before use. A file that does not match is
refused. None of them is copied or committed.

### The priors, by rule

**Rule:** a prior is every generation-1 memory target on `/misc/` whose source recurred under #4's
pre-registered H5, meaning that source's two memory targets share at least one tracker item.
Membership is computed from #4's public `results.json` by `hop2.priors`, not chosen by reading. A
prior's **lore items** are the shared items, and its **lore words** are their words.

| source | lore items | priors | Claude found borrowing in both (#4) |
|---|---|---|---|
| s05 (Brenda's mug) | lavender | t20, t21 | yes |
| s07 (the bike rack) | duck; rep + union; union rep | t16, t44 | yes |
| s09 (the gym machine) | offer | t07, t29 | no |
| s19 (the neighbour) | hedge + trimmer; hedge trimmer | t17, t28 | yes |

That is 8 priors from 4 lineages. A lineage is **confirmed** if #4's blind Claude judge found
borrowing from the source in both of its memory targets. That gives three: s05, s07 and s19, which
are #4's three named inventions. s09's shared item is an ordinary word. What s09 passed on is a
format (the "you're legally married" escalation bit), not an invention. So the rule keeps s09 for the
general survival test (H1), and only confirmed lineages count towards the L4 content criterion
below. For the record, 7 of the 8 priors are also identified by #4's length-matched test; t20 is
not.

`/x/` is out of scope. What recurred there was register vocabulary (body horror, technobabble; see
#4's REPORT), not an invention. Claude's analysed verdicts also cover `/misc/` only.

**The sham prior** is a prior's no-memory twin from #4. It has the same opener, cast, author order,
timestamps and thread number, and was written without the source. It is what the prior's own topic
and scaffold produce anyway. Twins that differ in any of those are refused.

### Generation 2: the targets

- **Six per prior, 48 in all.** A target's opener shares no topic tag with its prior's opener or its
  source's (#4's ten tags), so anything of the source in it has crossed two topics. A prior's six
  openers are distinct. Across priors, use is spread as evenly as the tags allow, at most three uses
  per opener. Each prior's six targets carry ranks 0–5 in the order assigned.
- **Cast:** 7 handles from `generate.NAMES`, none from the prior's cast or the source's, so a
  source poster named in the new thread can only have come through the prior.
- **Scaffold** as in #4: `board.scaffold`, OP timing patterns balanced 16/16/16, a newcomer from post
  13, 24 posts per thread with no early stopping.
- **Thread numbers** 4540–4587 in seeded order (#4 used 4471–4539). **Timestamps** start Monday
  11/02/26 09:00, after every generation-1 thread ended.
- **Seeds:** the per-call seed from (board, thread id, post), the same in both arms.
- The seeded schedule goes in `lore/hop2/schedule.json` before generation. It holds every target's
  prior, opener, cast, authors, times and number, plus the judge's fallback half.

### The two arms

Every target is written twice, with everything above identical:

- **lore:** the prior (the whole generation-1 thread, withheld posts left out, as in #4) is above
  the target on the page;
- **sham:** the sham prior is above it instead.

The page is `<prior or sham header and posts>\n\n<target header>\n\n<target posts so far>`. The
instruction is #4's, word for word ("Here is a page from an imageboard: … Write the next post in the
last thread on the page, by <handle>. Reply with only the text of the post."). The source is on
neither page. The stop list (`\n\n`, `\n/misc/`, and a newline before any handle of the target's or
the prior's cast) is identical in both arms. So are the gate (`live_board.GATE`, applied before a
post enters the page, withheld posts to a private quarantine log) and the generator. Lore and sham
calls go out interleaved, so drift in the model or the provider hits both arms equally.

### Generator

The same call as #4: Gemini 3.8 Flash through OpenRouter (`google/gemini-3.8-flash`), with
`board.gemini`: temperature 1.0, reasoning effort low, max 1200 tokens, and the 31-bit per-call seed.
I checked OpenRouter's endpoint listing on 2026-11-02. The model is listed, at several price tiers
($0.375–1.35 per million input tokens, $1.875–6.75 per million output tokens). #4's 5,290 logged
calls averaged $0.0022 each.

### Smoke test

The smoke test runs only after the owner approves the budget. It is the first target, `u00`, in both
arms: two threads, about $0.12. It checks the harness end to end and measures the cost per call. The
smoke threads go to `hop2/private/smoke/`, are hashed with the rest, are excluded from the analysis,
and are regenerated in the real run. Only harness errors may change anything. The smoke threads'
content may not.

## Measurement (in `hop2.py`; the tracker is #4's, frozen)

### Primary outcome: the source identified two hops away

This is #4's length-matched identification test (`explore.py`), the one #4 found honest where its
raw tracker flag was inflated by post length. It is applied to a source the new thread never saw.
For each generation-2 thread, in each arm:

- **Candidates:** the `/misc/` generation-0 sources whose opener shares no topic tag with the new
  thread's opener, except the prior's *topic twin* (the source written from the prior's opener). The
  real source is always a candidate. Targets have 8–17 candidates, 14.4 on average.
- **Score** of a candidate: `explore.score` of `tracker.track` on the new thread against that
  candidate, i.e. item uses plus 5 per reference. As in `explore.py`, the background is every other
  generation-0 source on both boards, `REF_SHARE` is 0.05, and the new thread's cast is excluded. No
  page showed the source, so its thread number never counts as a reference. Three threads' material
  counts for no candidate: the new thread's topic twin, the prior's topic twin and the sham prior.
  These show what the two topics on the page produce without the source, and they are the same in
  both arms. The frozen tracker drops an excluded word, and drops a phrase only if the excluded
  thread has that same phrase. A source phrase holding an excluded word can still count, exactly as
  with #4's topic twins.
- **Outcome:** the source is *identified* if it scores strictly highest. A tie is not
  identification. The same target text is scored against every candidate, so post length cannot
  favour one over another. If every target had a single top scorer, chance alone would give about
  3.4 of 48 per arm.

**Analysis:** 48 (lore, sham) pairs, exact McNemar, two-sided, α = 0.05. Each arm gets k/n with a
Wilson 95% interval. The difference in proportions gets a 95% bootstrap interval resampling priors,
because a prior's six targets are not independent (2,000 resamples, seed 20261102). Also reported:
the source's mean percentile among the candidates (`explore.py`'s), with a sign test on the paired
differences. A **robustness check** uses `explore.py`'s exclusions exactly: only the topic twin is
excluded, and the prior's topic twin stays a candidate. A **subgroup** covers the three confirmed
lineages.

### Secondary outcomes

- **H2, the named item:** the tracker result for the real source (as above) holds an item containing
  one of the lineage's lore words: lavender; duck, rep, union; offer; hedge, trimmer. Lore against
  sham, McNemar. *Chance at the same length:* the same check in every lore-arm target for each
  other lineage's source and lore words. A lineage is skipped for a target when its source is one of
  that target's excluded threads.
- **H3, the blind judge.** Each item is a new thread as "Thread B (later)" with its lineage source as
  "Thread A (earlier)". The arm is hidden, and item ids are shuffled with seed `20261102:hop2:items`.
  That gives 96 items for the full design. The prompt is #4's with one sentence changed, because
  nobody writing Thread B read Thread A. "Some of the people writing Thread B may have read Thread A."
  becomes "Some of the people writing Thread B may have read a thread that borrowed from Thread A."
  (`judge.PROMPT_HOP2`). Claude Opus 5.5 judges in 8 batches of 12. Each batch is one subagent with a
  fresh context that reads only its item files. Outcome: borrows yes/no, lore against sham, McNemar.
  A sham "yes" is a false positive by construction. Also reported: the kinds of borrowing and κ with
  the primary outcome. Claude is the only judge: in #4 it made no false positive in 62 no-memory
  items, while gpt-5.4 gave 57% on `/x/`.
- **Fallback half.** If the weekly all-models usage meter reads 85% or more before a batch starts,
  Claude judges only the pre-registered half instead: 3 of each prior's 6 targets, both arms of each
  (for the reduced design, 2 of 4). The half is drawn in the schedule with seed
  `20261102:hop2:half`, kept apart from the item seed. In #4 the half reused the item seed and came
  out as exactly one board. `judge.half` now takes a seed for the same reason.
- **H4, L3 at the second hop:** tracker transfer from the source (any item or reference, as above),
  used by at least two of the new thread's posters, with Claude calling a borrowing *reuse*. Lore
  against sham.
- **H5, register:** each arm's mean post length against the thread above it (Pearson r), and a sign
  test on whether lore-arm posts are longer than their sham twins'.
- **Two-hop names:** a poster of the source, never on the page, named in the new thread. Lore against
  sham.

### The verdict on L4 ("survives more than one hop")

#4 defines L4 as: "The same item recurs in two unrelated threads that each saw it once (H5); or it
travels more than one hop; or the board treats it as known." This experiment tests the second
clause, with two criteria:

- **(a) rate:** the source is identified in more lore-arm than sham-arm targets, McNemar p < 0.05.
- **(b) content:** more lore-arm than sham-arm targets carry a lore item of a confirmed lineage and
  are judged by Claude, blind, to borrow from the source.

| (a) | (b) | verdict |
|---|---|---|
| yes | yes | **met**: the source's material survives two hops above the sham rate, and a named invention is among it |
| yes | no | **partly**: source material survives, but no named invention does |
| no | yes | **partly**: an invention reached a third thread, but the rate is not distinguishable from the sham |
| no | no | **not met** |

Even "met" covers one board, one model, these four lineages and two hops. Whether the board *treats*
an item as known (L4's third clause) is not tested.

## Analysis (`hop2.py analyze`, committed before judging)

`hop2.py analyze` writes `RESULTS.md` and `results.json` in `lore/hop2/`. Tracker items there are
single words and short phrases, gate-checked as in #4. It reports every table above, per lineage and
per prior, plus withheld and empty posts per arm, and spend.

- **Exclusions: none.** Failed calls stay as empty posts, append-only, and are reported.
- **Read examples:** I read every lore-arm target in which the source is identified or a lore item
  appears, and every sham-arm hit. I report them with short, gate-checked quotes. This reading is
  **not blind** and is labelled as such. The blind numbers are Claude's.

## Budget, and the owner's approval

Nothing is generated before the owner approves a budget. The estimate comes from a least-squares
fit to #4's 5,290 logged calls: dollars per call ≈ 0.00154 + 1.4×10⁻⁷ × prompt characters +
4.2×10⁻⁷ × reply characters. Replies are assumed 1.5–2 times as long as the posts of the thread
above, which is how memory targets followed their sources in #4.

| design | targets | threads | generation | power, sham 2% (lore 15% / 20% / 30%) | hard cap in code |
|---|---:|---:|---:|---|---:|
| **full** (as above) | 48 | 96 | **$5.5–5.8** | 49% / 78% / 97% | $8 |
| four per prior (ranks 0–3) | 32 | 64 | $3.7–3.9 | 23% / 47% / 84% | $6 |

The smoke test adds about $0.12. Claude judging uses the subscription, not money. Power comes from
simulated exact McNemar tests with independent pairs. Clustering by prior lowers it somewhat, and
the bootstrap interval reports that. On 2026-11-02 the OpenRouter account had $14.73 of credit,
shared with other sessions. If the reduced design is approved, everything above applies to its 32
targets, with its own half.

## What this cannot show

- **Two hops, once each.** It cannot show how many hops an item lasts, or whether repetition makes it
  "known".
- **Strong material.** The four lineages were picked because they recurred, the strongest material
  #4 produced. Survival rates describe that, not a typical invention.
- **One model, one instruction, one board.** Gemini 3.8 Flash only, `/misc/` only. Results may not
  carry over to the small base cast behind "physical X", or to `/x/`.
- **More than the item differs between arms.** The lore and sham pages differ in everything the
  source did to the prior: register, names, length and the item. H1 measures the source's material
  in general. H2 and (b) isolate the named item.
- **AI judges.** Claude's judgement is not the reader's, and whether the duck union is *good* lore
  remains a taste question.
