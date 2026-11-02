# Follow-up bake-off: hosted models, Japanese boards, and emergent folklore

Research record through November 2, 2026. This documents the follow-up experiments run after the
original ~600-thread local base-model study. It is **not** a replacement for
[FINDINGS.md](FINDINGS.md), [BEST-OF.md](BEST-OF.md), or [experiments/README.md](experiments/README.md).

> **Evidence status.** The code, every judge prompt, the blinding keys and every judge's raw scores
> are in [`spike/`](spike/README.md). [`spike/judging/LEDGER.md`](spike/judging/LEDGER.md) recomputes
> every score below from those files (`python spike/judging/ledger.py --check`, plus unit tests).
> The generated threads and judging packets stay private, like the original corpora; their SHA-256
> hashes are in `spike/MANIFEST.sha256`, and all 72 judging packets were rebuilt from the private
> threads and matched byte for byte. **Every score here is an AI judge's** (Claude Opus 5.5
> subagents, and gpt-5.4). The person this board is for has not rated any hosted-model output
> blind, so none of this is yet a measure of what they find funny. Model names and prices are as
> recorded during the runs, not checked against current listings.

## What changed since the original study

The original research established that a small base-model cast can occasionally invent remarkably
funny, unselfconscious forum conversations. Its central findings remain in
[FINDINGS.md](FINDINGS.md): the opener-only setup, XTC + DRY, the 9-to-2 blind XTC result,
fragile quality proxies, and the one-prior board-memory result.

The later work tested **hosted large models, raw completion versus chat prompting, blind AI
judging, candidate selection, Japanese 5ch-style threads, higher temperatures, and differentiated
poster temperaments**. On the AI ratings, a strong chat model (Gemini 3.8 Flash) won coherence and
naturalness, while the original tiny base models still produced the most distinctive threads the
human reader has picked. These are different outcomes: the AI-rater leaderboard is **not** a
ranking of what the reader finds funniest.

The follow-up also explored what makes a simulated board produce a Kisaragi Station-like live
incident or, eventually, Backrooms/Samejima-like culture across threads. An isolated funny thread
is not the same experiment as a persistent community.

## Experiment and evidence inventory

| Work | Tested / observed | Evidence |
|---|---|---|
| Live board v1 to v2.1 | Multi-thread board, model-written OPs, regulars across threads; v1's catalogue broke replies | `spike/live_board.py`; board snapshots private |
| English rounds 1–5 | Size, raw vs. chat, Hermes fixes, pickers; Gemini, Qwen, Hermes, Kimi, Echo, gemma-31B, Llama-70B, Euryale | `spike/judging/`, LEDGER rounds 1-2 to 5 |
| Round 6, temperature | Gemini at 1.0/1.5/1.9, Qwen at 1.0/1.4/1.8, same 8 openers | LEDGER round 6 |
| Round 7, poster temperaments and small-model naifs | Gemini with quiet temperaments; 2 of 7 posters given to the original gemma-4-E4B; both | LEDGER round 7 |
| Round 8, temperaments with post length controlled | Plain Gemini vs. long-post roles vs. short-post roles, one rubric for both judges | LEDGER round 8 (**completed**, results below) |
| Japanese round and picker | 9 models in 5ch and named-handle formats; Gemini best-of-3 | LEDGER rounds JP and JP-5 |
| Cross-thread folklore on a hosted live board | Discussed, with memory-on vs. memory-off controls | **Not tested**. The earlier local one-prior test is in [FINDINGS.md](FINDINGS.md) |
| Blind human ratings of hosted-model output | `spike/rate.html` exists | **Not done** |

Every round used the same 8 English openers (6 in Japanese) and the same seeded scaffold: cast,
author order, timestamps, the OP leaving and returning at posts 7 and 19, and a newcomer at post 13
all come from `generate.py`'s seeded rng, never from model output. Judges saw one packet per opener,
each arm's thread lettered at random, and never the key. With 6 to 8 packets per comparison and
about 40 paired comparisons in the ledger, a two-sided sign test at p < 0.05 is reachable only by
near-sweeps, and two or so would turn up by chance; the ones that did are named below.

## English: model comparison (rounds 1–5)

Means on 1–5 from [LEDGER.md](spike/judging/LEDGER.md). Compare within a round: the rubric and the
competing arms changed between rounds, and the same threads moved when re-judged (see "AI judging"
below).

| Setup | Claude overall | gpt-5.4 overall | Note |
|---|---:|---:|---|
| **Gemini 3.8 Flash, chat** (round 4) | **3.88** | **4.12** | Best thread in 6 of 8 packets for both judges; humour 2.25 for both |
| Qwen3-235B raw + best-of-3 gpt-5.4 picker (round 3) | 3.25 | 3.83 (6 packets) | Best raw-continuation setup; gpt-5.4 also did the picking |
| Kimi K3, chat (round 3) | 2.50 | 4.00 (6 packets) | The widest judge disagreement; humour 1.50 / 1.33; ~1,100 characters a post |
| Echo, chat (round 3) | 2.62 | 3.33 (6 packets) | ~527 characters a post; about $0.20 a post by the session's credit count (not logged in the files) |
| Qwen3-235B raw, unpicked (round 3) | 2.12 | 1.83 (6 packets) | Scored 3.00 in round 1-2 with other competitors |
| Hermes 3 405B, best fix: penalties + guard + picker (round 4) | 2.25 | 2.12 | Plain Hermes 1.75 / 1.38; penalties and the guard alone changed nothing |
| gemma-4-31B base, Llama-3.1-70B base, Euryale 70B (round 1-2) | 2.25 / 1.75 / 1.50 | – | Claude only; self-hosted arms used XTC + DRY, which trades coherence for surprise |
| Original gemma-4-E4B / Qwen3-4B / Olmo-3-7B cast (round 1-2) | 1.38 | – | The cast that wrote the original best-of threads |

Plain Gemini cost $0.43 for 8 threads (184 generated posts), about **$0.0023 a post** as logged by
the generator, before judging. In round 3 gpt-5.4 judged only 6 of 8 packets (the free daily
allowance ran out).

**Interpretation.** Gemini was the most reliable general thread writer. Qwen raw continuation kept a
more unassisted forum voice and needed a picker to be consistent. The original small cast scores
lowest with AI judges, which is not evidence about the rare kind of spontaneous absurdity the reader
picked from it (see below).

## Japanese: 5ch-style voice

The 12-packet round (6 openers × 5ch and named-handle formats) was judged by **Claude only**:

- **Gemini 3.8 Flash:** best thread in all **12 packets**: 4.00 overall, 3.92 naturalness, with
  plausible colloquial pushback such as "お前はさっきから何と戦ってんだよカルシウム摂れ".
- **Qwen3-235B raw:** second at 2.83 (Gemini vs. Qwen: 10 packets better, 2 tied, p = 0.002).
- **GPT-5.4 (2.33) and Claude Sonnet 5.5 (2.17, 5ch only):** slid into tidy advice register.
  Sonnet was judged by another Claude model, so a family preference would have favoured it.
- **Kimi (2.08) and DeepSeek V4 Flash (1.58):** weak.
- **Self-hosted Japanese base models:** last. gemma-4-31B 1.33, Llama-3.3-Swallow-70B 1.17, and
  Swallow with XTC + DRY 1.08: anti-repetition sampling made it slightly worse.

The Japanese Gemini best-of-3 picker (5ch format, 6 packets, judged by both families) added
**+0.16** with Claude (3.33 vs. 3.17) and **+0.17** with gpt-5.4 (4.00 vs. 3.83), for **$1.14
against $0.19**, 5.9× the generation cost. Consistent with English: a picker helps an inconsistent
model more than one that already scores well.

## Techniques tested

| Variable | Result / practical consequence |
|---|---|
| **One thread per prompt** | Essential. Putting a *catalogue of other threads' opening posts* above the current thread broke live-board v1: posters began importing unrelated complaints. Distinct from showing one finished earlier thread as memory. |
| **OP leaving and returning** | The fixed scaffold (the OP away for 2–6 hours, back at posts 7 and 19) repeatedly created Kisaragi-like tension. A *varied* schedule is proposed, not tested. |
| **Raw continuation vs. chat** | Raw completion kept forum continuation without asking for role-play. Chat models did best with one neutral instruction **per post**. In the session's tests only Qwen honoured raw continuation in Japanese through OpenRouter; DeepSeek and GLM returned nothing or switched to chat. |
| **Best-of-3 + AI picker** | Qwen 2.12 → 3.25 (Claude, round 3; 6 packets better, 1 tied, 1 worse). Gemini +0.12 with Claude and +0.62 with gpt-5.4 (round 5), where gpt-5.4 was also the picker. Generation cost 4.6× for Gemini in English, 5.9× in Japanese. The round 3 picker chose the last of three candidates 81 times in 182 (45%), so later pickers shuffle candidates. |
| **Repetition penalties, breakdown guard** | Stopped Hermes's loops (the guard resampled 1 post in 184 once penalties were on) without improving quality: its real failure was generic, advice-column posts. |
| **XTC / DRY** | Crucial to the *local small-base* setup in [FINDINGS.md](FINDINGS.md). Unavailable on the hosted APIs compared, and they did not rescue the Japanese base models. Don't transfer the original sampler recommendation to hosted chat models. |
| **Board and persona labels** | Echo's "4chan anon" persona pushed toward creepypasta; `/x/` likely does too. Neutral labels leave room for mundane threads. |
| **Reasoning models** | Hidden reasoning ate the output budget: empty Claude Sonnet posts, Gemini posts cut off at a 300-token cap (the failed runs are kept as `*-reasoning-*` files). Low reasoning effort and a larger cap fixed both. |
| **Keyword gate** | A placeholder, not moderation. See "Safety" below. |
| **AI judging** | Useful for screening, not a definition of taste. The same 8 plain-Gemini threads, re-judged by Claude in rounds 4 to 8, scored 3.88, 3.50, 3.38, 3.12 and 2.88 as the competing arms got stronger; one thread's score changed by 0.62 points on average between two judgings, and by a point or more in 43 of 80 pairs. gpt-5.4 moved as much (0.55 points). The two families' rankings agree well on clearly different arms (Spearman ρ 0.78–0.84 in rounds 3–4) and not at all on the temperament rounds (0.21 in round 7, −0.17 in round 8). |

### Round 6: higher temperatures

Same 8 openers and scaffolds, six arms: Gemini at **1.0, 1.5, 1.9** and Qwen raw at **1.0, 1.4,
1.8**. Qwen's hotter arms also used a stronger **min_p** (0.1 and 0.15), pinned to a provider
believed to honour it (`require_parameters`), so temperature and min_p are confounded.

| Setup | Claude overall | Claude humour | gpt-5.4 overall | gpt-5.4 humour |
|---|---:|---:|---:|---:|
| Gemini, temp 1.9 | 3.62 | 2.62 | 4.00 | 1.62 |
| Gemini, temp 1.5 | 3.62 | 2.12 | 4.00 | 1.62 |
| Gemini, temp 1.0 | 3.38 | 2.25 | 4.00 | 1.88 |
| Qwen, temp 1.4 / min_p 0.1 | 2.75 | 2.75 | 1.88 | 1.88 |
| Qwen, temp 1.0 | 2.25 | 2.00 | 1.25 | 1.12 |
| Qwen, temp 1.8 / min_p 0.15 | 2.25 | 2.12 | 1.88 | 1.62 |

**Within-round finding:** Qwen at 1.4 beat 1.0 with both families (humour +0.75 with each; 5 of 8
packets better and none worse with Claude); 1.8 added nothing over 1.4. Gemini held its coherence
at 1.9, but its humour gain under Claude was not corroborated by gpt-5.4. Heat did not close Qwen's
gap to Gemini.

**Rubric caveat:** only the **Claude** judges were told this round to count deadpan and
sincerely-wrong humour; gpt-5.4 got the older rubric. Each family used one rubric for all six arms,
so within-family comparisons hold, but the two families' humour scores measure different things
here, and neither is comparable to earlier rounds. Generation for the four new arms cost about $0.90.

### Poster temperaments: rounds 7 and 8

**Round 7** gave each non-OP handle in a Gemini cast a quiet temperament (skeptic, pedant, lurker,
earnest helper, mild troll, storyteller; "don't announce it"). Two more arms gave 2 of the 7 posters
to the original gemma-4-E4B base model with XTC + DRY, the phonebook model, as sincerely-wrong
"naifs", with and without temperaments for the rest.

| Round 7 | Claude overall | Claude humour | Claude variety | gpt-5.4 overall | gpt-5.4 humour |
|---|---:|---:|---:|---:|---:|
| **temperaments** | **3.88** | **4.00** | **4.62** | 3.12 | **2.62** |
| plain Gemini | 3.12 | 2.00 | 2.38 | **4.12** | 2.00 |
| naifs + temperaments | 3.12 | 3.25 | 3.88 | 2.50 | 2.12 |
| naifs | 2.75 | 2.00 | 2.50 | 3.12 | 1.75 |

Temperaments raised humour with both judges: Claude +2.00, better in all 8 packets (p = 0.008);
gpt-5.4 +0.62 (5 better, 1 worse). But gpt-5.4 marked them down overall (−1.00), and in this round
it judged on the older rubric, without the contrast and variety criteria Claude had. Role posts also
averaged **359 characters** against plain Gemini's **131**: the storytellers and helpers wrote essays.

**The small-model naifs did not help under either judge.** Naifs vs. plain Gemini: Claude −0.38,
gpt-5.4 −1.00 overall, humour no better (+0.00 and −0.25). Naifs + temperaments vs. temperaments alone: Claude −0.75
(worse in 5 packets, better in none), gpt-5.4 −0.62. A judge summarised a naif thread as "dissolves
into dream-logic word salad". The phonebook thread worked because *everyone* shared the confusion
and built on it; one confused poster among fluent ones reads as broken.

**Round 8** fixed both round 7 problems: a **short-role** arm told each temperament how long its
posts run (averaging **128 characters a post**, against 131 for plain Gemini and 359 for the
original roles), and both families judged on the same rubric (contrast, sincerely-wrong humour,
variety). The plain-Gemini and long-role threads are the same files as before; only short roles
are new.

| Round 8 | Claude overall | Claude humour | Claude variety | gpt-5.4 overall | gpt-5.4 humour | gpt-5.4 variety |
|---|---:|---:|---:|---:|---:|---:|
| long-post roles | **3.62** | **3.88** | **4.12** | 3.25 | **3.12** | **4.12** |
| short-post roles | 3.25 | 3.50 | 3.50 | 3.00 | 2.75 | 3.62 |
| plain Gemini | 2.88 | 2.00 | 2.00 | **4.38** | 2.50 | 3.75 |

- **Humour still rises with temperaments, and length control keeps most of it with Claude:** short
  roles +1.50 over plain (better in 6 packets, worse in none, p = 0.031), long roles +1.88 (all 8,
  p = 0.008). With gpt-5.4 the humour gains are small and not significant: +0.62 long, +0.25 short.
- **gpt-5.4 still prefers plain Gemini overall on the same rubric:** 4.38 against 3.25 and 3.00;
  short roles scored lower overall than plain in 6 packets and higher in none (p = 0.031). Length was
  not what it was objecting to: short roles did no better with it than long ones.
- **The judges disagree outright** on this round: Spearman ρ = −0.17 between their overall scores,
  and the same top thread in 4 of 8 packets.

So "temperaments make threads funnier" has support from Claude and weak support from gpt-5.4;
"temperaments make better threads" is contradicted by gpt-5.4. This is exactly the question the
reader's own blind ratings have to settle. Round 8 generation cost $0.30.

Temperaments to keep examining: OP with stakes, ordinary advice-givers and one-liners, earnest
helper, skeptic/pedant, lurker, occasional troll and storyteller. The point is **contrast**, not
giving everyone a comic or sinister voice: all-atmosphere casts (Kimi, Echo) and all-joke casts
both flatten a thread.

## The original human-picked humour is a different target

[BEST-OF.md](BEST-OF.md) has six threads from the original small-model study: **phonebook**,
**office statistics**, **"l car"**, **the ghost that took his shoes**, **the group chat that renamed
itself**, and **whose flatmate is whose**. Their provenance matters for calibration: by BEST-OF.md's
own account the AI assistant picked them from ~600 threads; the reader had independently flagged
the **phonebook** thread, and the rest are the assistant's picks. Separately, the reader confirmed
**9 of 20** threads on the assistant's shortlist from run 5's 142 threads (45% precision, about 32%
recall against the reader's own bar, per FINDINGS.md). Which nine were confirmed is not recorded
in the repo, the gated dataset or the original zip: the rating export (`skim.json`) did not survive.

The distinctive mechanism is **sincere, confident wrongness**. Nobody announces a joke; someone
explains the mistaken concept as if it were obvious, and the board accepts and extends it.

- Phonebook: "your number is your number. there is no other number" / "i just thought it was called
  the phonebook".
- "l car": a fictional type of subway car becomes common knowledge, complete with etiquette complaints.
- Office statistics: confident percentages and corrections make ordinary workplace identity unstable.
- The renamed group chat: repetition works because it has an in-world cause, even though a
  mechanical chant detector would label it a collapse.

Large models produced more coherent, clearly authored jokes or horror ("if haunted, explain why
chamomile?"). Their deliberate humour is not the same behaviour. FINDINGS.md already showed the
rule-based proxies reading the phonebook thread's numeric absurdity as a collapse; AI judges that
weight coherence may repeat the mistake.

**Mixing models by role was tested once, in round 7, and failed** (above). What remains untested is
narrower: a small model posting *occasionally* rather than holding two regular slots, or a setup
where a shared confusion can spread instead of sitting in one poster.

**Most important calibration test:** mix the BEST-OF threads with Gemini, temperament and Qwen
samples, remove all labels, and get **the reader's blind ratings** on separate axes (believable,
would keep reading, deliberate humour, deadpan humour, would repost), then have the AI judges rate
the same items. This shows whether AI scores predict the target taste before any more optimising of
an automated leaderboard. The reader will recognise some BEST-OF threads, so the ratings need a
"seen before" flag.

## Emergent folklore: what happened versus what is still hypothetical

### Kisaragi Station-like live incidents: observed

Across English, Japanese and 5ch-format threads, an OP reported an increasingly peculiar situation,
went silent for hours and returned, and other posters reacted to the absence and urged updates:

- A Japanese poster left to check on something and others worried until they returned: "確認行った
  っきり戻ってこないのが一番怖いから早く報告しろ" … "ただいま" … "おかえり。コンロ消してくれてありがとな。"
- An English thread noticed that someone had stood at a window for almost four hours; other posters
  started checking their stoves.
- In a named Japanese format, a message appeared to know that someone was writing on the board right
  then: "中身、一行だけ「今、掲示板に書き込んでいますね」って書いてあった。" → "まさかのリアルタイム更新？"

The pattern was **stakes + normal forum social behaviour + gaps in OP availability**, not an
instruction to write Kisaragi Station. Whether varied timing improves it is untested.

### Backrooms/Samejima-like lore: not yet demonstrated on the new board

In live-board v2.1 (419 posts in 18 threads), posters spontaneously treated **thread numbers as
people** ("what happened to 4468?" "it died" "he went to bed and didnt get up"), and elsewhere
treated the **board itself as the haunted object** ("the thread is the ritual"). Thread 4477 really
had died shortly before (the early-stop gate killed it), but no prompt shows other threads' numbers,
so that match is most likely chance. These are lore seeds, **not evidence of a persistent culture**.
The bake-off threads were isolated, so recurring rules, names and cumulative world knowledge could
not develop there.

The **earlier local-base board-memory experiment** is in [FINDINGS.md](FINDINGS.md): with one
completed prior thread, the "physical number" construction transferred as **"physical X" in 2 of 2**
target threads against **0 of 20** controls. Exact named coinages did not recur (0 of 8), and old
participant handles leaked into new casts. A portable grammatical construction can transfer; that
is not proper-name lore or communal continuity.

Future board test: comparable live boards in English and Japanese, with and without **a bounded,
completed prior thread**. Measure genuine cross-thread references, reused inventions and rules, live
updates, independent poster reactions and retell-worthy episodes. Avoid the **v1 catalogue
contamination** failure, and exclude prior-thread handles from the new cast. A general board identity
with mostly mundane threads may give strange events contrast; `/x/` and overtly paranormal prompts
appear to bias everything toward genre performance. That is a hypothesis needing a neutral-board
control.

## Safety and deployment implications

[QUARANTINE.md](QUARANTINE.md) and [FINDINGS.md](FINDINGS.md) document unprompted harmful output and
phrase-list failures in the local base-model project: the first list missed a thread with a
homophobic slur and four kill threats. The follow-up added to that record:

- **Live-board v2 leaked sexual content** past the English list; sexual terms were then added.
- **Japanese output needs its own list**; the English one catches nothing (bare 死ね is deliberately
  allowed as everyday 5ch banter).
- **In the bake-off runs the gate ran after a whole thread was written**, so a flagged post stayed in
  the context while later posts were generated, and was only withheld from the saved file. The live
  board withholds before a post enters the board. 0 to 4 posts per 184 were withheld per arm.
- **The list matches substrings**, and two entries carry a trailing space (`"fag "`, `"paki "`), so a
  plural or a word at the end of a post or before punctuation slips through. Found by reading the
  list; not yet measured on the outputs.

A first draft of this document said a skeptic poster's slur escaped the gate. It came from a round 8
smoke test that calls the model directly without the gate; the word is on the list, so a real run
would have withheld it.

**Do not launch a public live board with the keyword-only filter.** A separately validated,
context-aware moderation classifier and a publication gate are required, including for human
replies. Keep unsafe samples quarantined, out of the published best-of and screenshots. A quality
picker is **not** a moderation system.

The lightweight research stack was **Gemini 3.8 Flash through OpenRouter**, one neutral per-post
instruction, the OP-gap scaffold and, only as an experiment, a bounded earlier thread as memory. It
needs no GPU. Self-hosting on Modal was judged worth revisiting only at much higher volume, or for a
small base model playing a "sincere" role, without an established crossover volume or current price.
This differs from [INFRA.md](INFRA.md), which sizes the **original local gemma-4-E4B** workload with
dated August 2026 assumptions.

## Known limitations and open questions

1. **Human taste is not calibrated.** No hosted-model, temperature or temperament result has the
   reader's blind ratings, and the original study's item-level ratings were lost.
2. **The AI judges are noisy, relative and partly circular.** A thread's score moves about 0.6
   points between judgings; scores depend on the competing threads; a picker's own family favours
   its picks; the two families disagree completely on temperaments.
3. **Small samples.** 6 to 8 packets per comparison; only a handful of differences survive a sign
   test, and some of those are expected by chance across ~40 comparisons.
4. **Humour is unresolved.** Temperaments raised judged humour, decisively for Claude and weakly for
   gpt-5.4; whether a person laughs more is unknown.
5. **Thread-to-thread transmission on the hosted stack is untested.** The local "physical X" result is
   narrower than enduring lore.
6. **Real human replies** and posters reacting to them have not been evaluated.
7. **Moderation precision and recall** on this output distribution have not been measured.
8. **No seeds for hosted sampling.** A re-run produces new threads; the recorded ones are the evidence.

## Next experiments, in priority order

1. **Calibrate against the reader, blind.** Mix BEST-OF threads with Gemini, temperament and Qwen
   samples; rate believable, keep reading, deliberate humour, deadpan humour, would repost, and
   flag threads seen before. Run the same items through both AI judge families and measure agreement.
2. **Get the reader's verdict on round 8** (plain vs. long roles vs. short roles), the round where
   the two AI judge families disagree.
3. **Narrower hybrids.** An occasional small-model post instead of fixed slots; seeding a shared
   confusion. Equalise length, openers and scaffold; report failure and safety rates, not just the
   best thread.
4. **Separate Qwen's temperature from min_p,** with logged parameters and provider.
5. **An evolving board.** Vary OP timing (short bursts, 2–6-hour absences, an OP who never returns),
   board identity, the mundane-to-strange ratio, and one-prior memory vs. none. Count citations of
   earlier threads and rule transfer, then read for actual continuity.
6. **Validate publication safety first.** Evaluate a real moderation classifier on this distribution,
   including the quarantined cases, before exposing a live board to people.

For each new comparison, predeclare the hypothesis and the human success criterion, record the
complete configuration and rubric, keep generated samples under an appropriate access policy, and
separate **observed result**, **interpretation** and **proposed design**. The original project's
failed-proxy history is a warning against optimising convenient metrics after seeing the outputs.
