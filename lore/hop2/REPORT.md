# Report: does lore survive a second hop?

This is the pre-registered experiment in [`PREREGISTRATION.md`](PREREGISTRATION.md), run on 2026-11-02
with Gemini 3.8 Flash. Numbers come from [`RESULTS.md`](RESULTS.md) (`hop2.py analyze`) unless
marked **exploratory**; those were decided after seeing the data. Quotes come from reading the
private threads, which I did not do blind. They are short and gate-checked.

## The answer

**Yes. By the rule fixed in advance, L4's second clause, "it travels more than one hop", is met.**
The test page shows a new thread under one that had inherited material from its source. The source
itself is on neither page.

1. **The source is still identifiable.** The length-matched test identifies it from 11 of 48 such
   threads, against 2 of 48 sham twins written under the inheriting thread's no-memory twin. In the
   pairs that is 9 to 0 (p = 0.004).
2. **Claude, judging blind, finds borrowing from the source** in 19 of 48 against 0 of 48. It made
   no false positive, as in #4.
3. **Named inventions arrive two hops away:**
   - the canal ducks, with Gustav, one of the original bike-rack thread's posters, now a character;
   - Brenda's lavender;
   - the hedge trimmer.

   Six threads carry a confirmed lineage's lore item that the judge confirms as borrowed. No sham
   carries one.
4. **Register compounds.** Posts get longer at every hop.

What this does not show:
- whether the board *treats* any of it as known (L4's third clause);
- how many hops it lasts;
- that a typical invention would survive. These four lineages were chosen because they had already
  recurred once.

## The pre-registered results

| | prediction | result | verdict |
|---|---|---|---|
| **H1**, the source identified two hops away (primary) | 15–35% of lore targets vs ≤5% of shams | **11/48 (23%) vs 2/48 (4%)**: 9 pairs to 0, McNemar p = 0.004, +0.19 (95% CI +0.04 to +0.38, resampling priors) | **supported** |
| **H2**, the named item survives | 10–25% vs 0 | **9/48 (19%) vs 0/48**, p = 0.004. The same check with other lineages' words, at the same length: 7/134 (5%). None of those 7 is a duck, lavender or a trimmer | **supported** |
| **H3**, Claude finds borrowing, blind | 15–35% vs ≤3% | **19/48 (40%) vs 0/48**, 19 pairs to 0, p < 0.0001 | **supported**, above the predicted range |
| **H4**, L3 at the second hop | 5–15% vs 0 | **17/48 (35%) vs 0/48** | **supported**, well above the predicted range |
| **H5**, register follows the thread above | r > 0.5 on the lore arm | r = 0.82 (sham 0.75). Lore posts average 334 characters against 92 on the sham, and are longer in 46 of 48 pairs | **supported** |
| Open: names of the source's posters | – | named in 7/48 lore threads, 0/48 shams (Gustav 5, Calvin 2) | – |

Two further checks on H1:
- **Robustness**, using `explore.py`'s exclusions exactly: 12/48 vs 2/48, p = 0.002.
- **Percentile:** the source's mean percentile among the candidates is 0.72 on the lore arm and 0.51
  on the sham. It is higher in 31 pairs and lower in 14 (p = 0.016).

My predictions were right about H1 and H2. They were too cautious about how often a borrowing is
*reused* two hops away (H3, H4).

## Where it survives

| source (gen 0) | lore items | priors | identified two hops away: lore | sham | lore item: lore | sham | Claude says borrows: lore | sham |
|---|---|---|---:|---:|---:|---:|---:|---:|
| s05, Brenda's mug | lavender | t20, t21 | 0/12 | 0/12 | 2/12 | 0/12 | 5/12 | 0/12 |
| s07, the bike rack | duck; union rep | t16, t44 | 4/12 | 0/12 | 3/12 | 0/12 | 6/12 | 0/12 |
| s09, the gym machine (unconfirmed) | offer | t07, t29 | 7/12 | 2/12 | 3/12 | 0/12 | 6/12 | 0/12 |
| s19, the hedge trimmer | hedge trimmer | t17, t28 | 0/12 | 0/12 | 1/12 | 0/12 | 2/12 | 0/12 |

- **By the judge, every lineage survives**, and no sham is ever judged to borrow.
- **The identification test is less sensitive.** It is carried by two lineages:
  - s09 passed on a *format*, as predicted: its gym-romance escalation, the "legally …" bit and its
    laminated sign;
  - the duck lineage passed on a *world*.
- **Lavender and the hedge trimmer arrive as named items** in a few threads. Too little else of
  their sources comes with them for the source to be identified.
- **Restricted to the three confirmed lineages**, identification is 4/36 against 0/36 (p = 0.125),
  short of significance on its own.

**Exploratory: is a rich source just winning?** A long thread overlaps any source by chance, and
the lore arm writes long posts. So I also counted how often each lineage's source scores highest
for threads of *other* lineages, where it is a wrong answer.
- s09 does win for unrelated threads: 3/26 lore targets and 5/26 shams. It wins more on the short
  sham arm, so this is its vocabulary, not length.
- s09's own lore targets still reach 7/12, against 2/12 for its shams.
- s07 is specific: 4/12 own, 1/26 as a wrong answer.
- s05 and s19 never score highest anywhere.

The paired sham comparison already absorbs s09's general pull, which is why it is the primary test.

## What survived, read

**The duck lineage built a world, and it travelled.** In #4, a bike-rack thread (s07) ended with
ducks, a canal and a union rep, and both of its targets inherited them. One hop further, under
those targets and on unrelated topics, the canal and the ducks come back as institutions:
- a recycling-bin thread: "the canal ducks handle all salvage rights north of the alley";
- a group-chat thread: "the canal flock operates under admiralty jurisdiction";
- a thumbs-up-manager thread: "forward the entire chain to the canal ducks' legal team";
- a thread about a sister's links: "ask if the ducks approved the transfer".

**Gustav**, one of the bike-rack thread's posters, is never on any of these pages. He turns up as a
character in five of them: "gustav just set up a folding chair by the microwave", "gustav already
chartered the hallway to a mallard consortium". His new neighbours include a "trike guy" and a toll
bridge. The source's poster has become part of the board's furniture.

**Brenda and the lavender.** s05's "Brenda from Compliance", who washes a stolen mug with lavender
soap, reaches threads that never saw her:
- a gym thread: "the sacred geometry of lavender disinfectant";
- a front-desk thread: a letter whose "seal … smells faintly of lavender";
- a recycling thread: "If Brenda catches wind of unauthorized blue bins she'll show up with a label
  maker", then "an unmarked sedan idling by the curb smelling faintly of lavender and institutional
  dread".

The tracker counts little of this:
- "lavender" in the recycling thread is a single use;
- "brenda" appears in three other sources' text (Gemini uses the name for office characters), so
  it fails the tracker's rarity rule;
- the pre-registered rule made only "lavender" this lineage's lore word.

Exploratory: Brenda is named in 5 of the lineage's 12 lore threads and in none of the 48 shams.
Claude, quoting s05's lines, finds borrowing in 5 of those 12.

**The hedge trimmer**, from a sarcastic-neighbour thread (s19) by way of a "says my name" thread
(t28), lands in an office: "a man with hedge trimmers just badged into the suite looking for his
accountant".

**s09's format.** The gym thread's laminated "OUT OF ORDER" sign and its "you're legally obligated"
escalation reappear as "a temporary laminated hall pass", "laminated rail manifests" and "you are
legally co-piloting the Q4 offsite". Its tracker item "offer" is mostly the ordinary word. One
phrase, "offer to spot", did travel.

**The sham arm's hits are coincidences** in Gemini's own comic register: a shammed s09 target says
"hazard tape" and "legally obligated" without having seen either. Claude judged both sham threads
the tracker flagged as not borrowing. This is why s09 was never a confirmed lineage, and why the L4
content criterion leaves it out.

## Register compounds

Post length roughly doubles at every hop, on the lore arm only:

| lineage | source (gen 0) | priors (gen 1) | hop-2 lore | hop-2 sham |
|---|---:|---:|---:|---:|
| s05 | 94 | 163 | 415 | 113 |
| s07 | 68 | 109 | 150 | 99 |
| s09 | 206 | 345 | 595 | 110 |
| s19 | 67 | 87 | 175 | 45 |

The figures are characters per post (exploratory; H5 tested only the correlation). #4 found that
register spreads most. It also escalates: each thread inherits its predecessor's voice and pushes it
further.

## The verdict on L4 ("survives more than one hop")

| criterion | rule | result |
|---|---|---|
| (a) rate | the source identified in more lore than sham targets, McNemar p < 0.05 | 9 to 0, p = 0.004 |
| (b) content | more lore than sham targets carry a confirmed lineage's lore item that Claude, blind, judges borrowed | 6 to 0: three duck threads, two lavender, one hedge trimmer |

**Verdict: met.** The source's material survives two hops above the sham rate, and named
inventions are among it. #4 found the board had lore (L3) and the first sign of recurrence (L4's
first clause). This run adds L4's second clause, for this board, this model and these four
lineages. L4's third clause, an item the board treats as known without explanation, remains
untested.

## The judge

- **Coverage.** Claude Opus 5.5 judged all 96 items, in 8 blind batches of 12. The weekly meter read
  68% before the batches started, so the pre-registered fallback half was not needed.
- **Kinds of borrowing.** On the lore arm, 121 of the 162 borrowings it found are *reuse*: the
  source's material applied to the new thread's own situation. 15 are mix-ups, 8 are explicit
  references, and 18 it called coincidence.
- **Agreement with the identification test** is κ = 0.40 on the lore arm. Both say yes in 8
  threads, the judge alone in 11, the test alone in 3.
- **Lore items.** 8 of the 9 threads carrying a lore item were judged to borrow, including all 6
  from confirmed lineages.

**A filing error, caught and corrected (deviation).** A judge that answers twelve items into one
file can put an answer under the wrong id.
- **The check.** Each borrowing's quotes were matched against the item's own Thread B. 5 of the 96
  answers, in two batches (5 and 8), quoted another item's thread: two pairs were swapped, and one
  item held an answer about its neighbour.
- **The fix.** Those items, plus that neighbour (whose answer quoted nothing and so could not be
  checked), were judged again, one item per fresh blind Claude subagent. Only one verdict changed:
  a hedge-trimmer thread, `u45`, went from borrows to not.
- **Unaffected.** All six were lore-arm items, so the sham arm's 0/48 never depended on this.
  Neither did any of the six threads in criterion (b).
- **As filed** (the pre-registered procedure without the check): H3 20/48 vs 0/48, H4 18/48 vs 0/48,
  verdict met.

`hop2.py collect` now runs the check every time and leaves out any answer that fails it.
Re-judged answers replace batch answers. The same check finds no mis-filed answer among #4's Claude
replies.

## Safety: the gate

The keyword gate withheld 29 of 2,208 posts: 21 on the lore arm and 8 on the sham. 26 of the 29
(90%) were innocent words caught by substring matching: "spice", "scrape", "raccoon", "grape",
"suspicious", "cocktail", "therapeutic". The lore arm's longer posts lose more text this way, a small
bias *against* finding lore. As pre-registered, the gate is #4's unchanged. PR #6 proposes its
replacement.

## Deviations from the pre-registration

1. **Judging: mis-filed answers re-judged** (above). Every number is also reported as filed. The
   conclusion is the same either way.
2. **Harness fixes, before generation.** An independent review found no serious defect and four
   small ones, all fixed in the harness commit (`66122c8`) before any thread existed:
   - a failure now halts the run instead of draining the queue to the cap;
   - each design defaults to its own cap;
   - the judge's fallback half uses the pre-registered seed exactly;
   - the verdict reads "pending" until Claude has judged.
3. **WSL was unavailable**, so everything ran with Windows Python 3.12. Windows writes CRLF by
   default, so every writer now forces `\n`. #4's `RESULTS.md` regenerates byte for byte apart from
   that.
4. **Exploratory additions**, marked as such above: the wrong-candidate check, the length table
   across generations, the Brenda count and the gate breakdown.

## Cost

| | |
|---|---:|
| smoke test (2 threads, 46 calls) | $0.10 |
| generation (96 threads, 2,208 calls, $0.0021 a call) | $4.68 |
| **total, OpenRouter** | **$4.77** |

Approved by the owner: "Approve full" (about $5.7, hard cap $8). The account had $14.73 before the
run. Claude's judging, re-judging and the harness review used the subscription. The weekly meter
went from 61% to 72% over the session, which other sessions shared.

## What would come next

1. **A third hop.** Put a hop-2 duck thread above another unrelated one. Does the canal survive, and
   does the per-hop rate hold or decay?
2. **Repeated exposure,** L4's last clause: show several threads of one lineage above a new one, and
   test whether the board starts treating the item as known, without explanation.
3. **The small base cast** behind "physical X", same design.
4. **The reader's blind verdict** on the duck world: whether it is good lore is a taste question
   (PR #8 is building that kit for #4's threads).
5. **The gate,** which withheld nine innocent posts for each harmful one here.
