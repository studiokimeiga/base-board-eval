# Follow-up bake-off: hosted models, Japanese boards, and emergent folklore

Research record through November 2, 2026. This documents the follow-up experiments run after the
original ~600-thread local base-model study. It is **not** a replacement for
[FINDINGS.md](FINDINGS.md), [BEST-OF.md](BEST-OF.md), or [experiments/README.md](experiments/README.md).

> **Evidence status.** The code, every judge prompt, the blinding keys and every judge's raw scores
> are in [`spike/`](spike/README.md). [`spike/judging/LEDGER.md`](spike/judging/LEDGER.md) recomputes
> every score below from those files (`python spike/judging/ledger.py --check`, plus unit tests).
> The generated threads and judging packets stay private, like the original corpora; their SHA-256
> hashes are in `spike/MANIFEST.sha256`, and all 114 judging packets were rebuilt from the private
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
poster temperaments**. On the AI ratings, Gemini 3.8 Flash won overall and interest in English and
naturalness in Japanese. Every thread the human reader has picked so far came from the original
tiny base models, but the reader has not yet seen hosted output, so the two have never been
compared. The AI-rater leaderboard is **not** a ranking of what the reader finds funniest.

The follow-up also explored what makes a simulated board produce a Kisaragi Station-like live
incident or, eventually, Backrooms/Samejima-like culture across threads. An isolated funny thread
is not the same experiment as a persistent community.

## Experiment and evidence inventory

| Work | Tested / observed | Evidence |
|---|---|---|
| Live board v1 to v2.1 | The original small cast (gemma-4-E4B, Qwen3-4B, Olmo-3-7B) on Modal, many threads at once; v1's catalogue broke replies; v2 and v2.1 put one earlier thread above some new threads (5 of 18 in v2.1) | `spike/live_board.py`; board snapshots private |
| English rounds 1–5 | Size, raw vs. chat, Hermes fixes, pickers; Gemini, Qwen, Hermes, Kimi, Echo, gemma-31B, Llama-70B, Euryale | `spike/judging/`, LEDGER rounds 1-2 to 5 |
| Round 6, temperature | Gemini at 1.0/1.5/1.9, Qwen at 1.0/1.4/1.8, same 8 openers | LEDGER round 6 |
| Round 7, poster temperaments and small-model naifs | Gemini with quiet temperaments; 2 of 7 posters given to the original gemma-4-E4B; both | LEDGER round 7 |
| Round 8, temperaments with post length controlled | Plain Gemini vs. long-post roles vs. short-post roles, one rubric for both judges | LEDGER round 8 (**completed**, results below) |
| Round 9, pre-registered | An occasional small-model post; the `/x/` label against a neutral header; Latin-square judging | `spike/PREREGISTRATION-ROUND9.md`, LEDGER round 9 (results below) |
| Japanese round and picker | 9 arms (8 models) in 5ch and named-handle formats; Gemini best-of-3 | LEDGER rounds JP and JP-5 |
| Cross-thread folklore on a hosted live board | Discussed, with memory-on vs. memory-off controls | **Not tested**. The earlier local one-prior test is in [FINDINGS.md](FINDINGS.md) |
| Blind human ratings of hosted-model output | [`calibration/`](calibration/README.md): 30 mixed threads, pre-registered, and 18 round 9 threads (`rate.html?set=r9`); `spike/rate.html?round=8` for round 8 | **Not done**: waiting on the reader |

Every English round used the same 8 openers and the same seeded scaffold: cast, author order,
timestamps, the OP leaving and returning at posts 7 and 19, and a newcomer at post 13 all come from
`generate.py`'s seeded rng, never from model output. **Every English prompt, in the bake-off and on
the live board, also began with `generate.py`'s header `/x/ — thread 4471`**, naming the paranormal
board; the Japanese prompts had no board label. Judges saw one packet per opener, each arm's thread
lettered at random, and never the key.

The ledger runs 54 paired comparisons on two scales, 108 exact sign tests. With 6 to 12 packets the
test is conservative, so chance alone would produce about one result at p < 0.05; eleven reached it.
They are named where they come up below, and all are in the ledger.

## English: model comparison (rounds 1–5)

Means on 1–5 from [LEDGER.md](spike/judging/LEDGER.md). Compare within a round: the rubric and the
competing arms changed between rounds, and the same threads moved when re-judged (see "AI judging"
below).

| Setup | Claude overall | gpt-5.4 overall | Note |
|---|---:|---:|---|
| **Gemini 3.8 Flash, chat** (round 4) | **3.88** | **4.12** | Best or tied-best thread in 6 of 8 packets with both judges (4 outright); humour 2.25 with both |
| Qwen3-235B raw + best-of-3 gpt-5.4 picker (round 3) | 3.25 | 3.83 (6 packets) | Best raw-continuation setup. gpt-5.4, which also did the picking, put it above raw Qwen in all 6 packets (p = 0.031) |
| Kimi K3, chat (round 3) | 2.50 | 4.00 (6 packets) | The widest judge disagreement; humour 1.50 / 1.33; ~1,100 characters a post |
| Echo, chat (round 3) | 2.62 | 3.33 (6 packets) | ~527 characters a post; both judges noted leaked prompts and broken character. Its spend wasn't logged: the session's "$0.20 a post" doesn't square with the $30 of credit it reports |
| Qwen3-235B raw, unpicked (round 3) | 2.12 | 1.83 (6 packets) | Scored 3.00 in round 1-2, against other competitors |
| Hermes 3 405B, best fix: penalties + guard + picker (round 4) | 2.25 | 2.12 | Plain Hermes 1.75 / 1.38; penalties and the guard alone changed nothing |
| gemma-4-31B base, Llama-3.1-70B base, Euryale 70B (round 1-2) | 2.25 / 1.75 / 1.50 | – | Claude only; self-hosted arms used XTC + DRY, which trades coherence for surprise |
| Original gemma-4-E4B / Qwen3-4B / Olmo-3-7B cast (round 1-2) | 1.38 | – | The cast behind five of the six BEST-OF threads (the phonebook thread was gemma-4-E4B alone, without XTC). Raw Qwen beat it in 7 of 8 packets (p = 0.016), gemma-31B in 6 (p = 0.031) |

Also run and not in the table: a Qwen + Hermes mixed cast (round 3) did worse than plain Qwen
(Claude −0.25, gpt-5.4 −0.33); Qwen at temperature 1.15 with a frequency penalty did slightly
better (+0.25, +0.67; not significant); Cydonia 24B was generated but never judged.

Plain Gemini cost $0.43 for 8 threads (184 generated posts), about **$0.0023 a post** as logged by
the generator, before judging. In round 3 gpt-5.4 judged only 6 of 8 packets (the free daily
allowance ran out).

**Interpretation.** Gemini was the most reliable general thread writer. Qwen raw continuation kept a
more unassisted forum voice and needed a picker to be consistent. The original small cast scores
lowest with AI judges, which says nothing yet about the rare spontaneous absurdity the reader picked
from it (see below).

## Japanese: 5ch-style voice

The 12-packet round (6 openers × 5ch and named-handle formats) was judged by **Claude only**:

- **Gemini 3.8 Flash:** best or tied-best thread in all **12 packets** (9 outright): 4.00 overall,
  3.92 naturalness, with plausible colloquial pushback such as "お前はさっきから何と戦ってんだよ
  カルシウム摂れ". Against Qwen it scored higher overall in 10 packets and the same in 2 (p = 0.002),
  and higher on humour in 7 and the same in 5 (p = 0.016).
- **Qwen3-235B raw:** second at 2.83.
- **GPT-5.4 (2.33) and Claude Sonnet 5.5 (2.17, 5ch only):** slid into tidy advice register.
  Sonnet was judged by another Claude model, so a family preference would have favoured it.
- **Kimi (2.08) and DeepSeek V4 Flash (1.58):** weak.
- **Self-hosted Japanese base models, all raw:** last. gemma-4-31B 1.33, Llama-3.3-Swallow-70B 1.17,
  and Swallow with XTC + DRY 1.08, which tied plain Swallow in 11 of 12 packets.

The Japanese Gemini best-of-3 picker (5ch format, 6 packets, judged by both families; the picker was
asked to weigh naturalness) added **+0.17** with both Claude (3.33 vs. 3.17) and gpt-5.4 (4.00 vs.
3.83), for **$1.14 against $0.19**, 5.9× the generation cost, and did not raise naturalness (+0.00,
−0.17). As in English, a picker helps an inconsistent model more than one that already scores well.

## Techniques tested

| Variable | Result / practical consequence |
|---|---|
| **One thread per prompt** | Essential. Putting a *catalogue of other threads' opening posts* above the current thread broke live-board v1: posters began importing unrelated complaints. Distinct from showing one finished earlier thread as memory. |
| **OP leaving and returning** | The fixed scaffold (the OP away for 2–6 hours, back at posts 7 and 19) went with the Kisaragi-like moments below. A *varied* schedule is proposed, not tested. |
| **Raw continuation vs. chat** | Raw completion kept forum continuation without asking for role-play. Chat models did best with one neutral instruction **per post**. In the session's tests only Qwen honoured raw continuation in Japanese through OpenRouter; DeepSeek returned empty posts. |
| **Best-of-3 + AI picker** | Qwen 2.12 → 3.25 (Claude, round 3; 6 packets better, 1 tied, 1 worse). Gemini +0.12 with Claude and +0.62 with gpt-5.4 (round 5), where gpt-5.4 was also the picker and the picked arm happened to be read first in 5 of 8 packets. Pickers didn't raise humour: the Gemini picker lowered it with both judges (−0.12, −0.38). Generation cost 4.6× for Gemini in English, 5.9× in Japanese. The round 3 picker chose the last of three candidates 81 times in 182 (45%), so later pickers shuffle candidates. |
| **Repetition penalties, breakdown guard** | Stopped Hermes's loops (the guard resampled 1 post in 184 once penalties were on) without improving quality: its real failure was generic, advice-column posts. |
| **XTC / DRY** | Crucial to the *local small-base* setup in [FINDINGS.md](FINDINGS.md). Unavailable on the hosted APIs compared, and no help to the Japanese base models. Don't transfer the original sampler recommendation to hosted chat models. |
| **Board label and personas** | Every English thread before round 9 was written under an `/x/` (paranormal board) header. Round 9 tested it: without the label, the share of replies a blind tagger called horror fell from 60% to 16% for plain Gemini and from 40% to 15% for short roles, and plain Gemini's humour rose by about two points with both judge families (below). Echo's first run, with a "4chan anon" persona, returned 176 empty posts of 184 (the few it wrote were creepypasta); the judged run used "Anonymous". |
| **Reasoning models** | Hidden reasoning ate the output budget: empty Claude Sonnet and DeepSeek posts, Gemini posts cut off at a 300-token cap (the failed runs are kept as `*-reasoning-*` files). Low reasoning effort and a larger cap fixed Gemini and Sonnet's 5ch run; Sonnet's named-handle run was not redone. |
| **Keyword gate** | A placeholder, not moderation. See "Safety" below. |
| **AI judging** | Useful for screening, not a definition of taste. The same 8 plain-Gemini threads, re-judged by Claude in rounds 4 to 8, scored 3.88, 3.50, 3.38, 3.12 and 2.88, while the competing arms changed and, from round 6, so did Claude's rubric (round 7–8's rewards variety, plain Gemini's weak point); gpt-5.4's scores for the same threads moved without a trend (4.12, 3.50, 4.00, 4.12, 4.38). A thread's score changed by 0.62 (Claude) or 0.55 (gpt-5.4) points on average between two judgings, more in Japanese. The two families' overall rankings agreed at Spearman ρ 0.78 and 0.84 in rounds 3–4, 0.39 in round 5, 0.51 in round 6, 0.21 in round 7, −0.17 in round 8 and 0.73 in JP-5. Both favour the thread they read first (+0.20 Claude, +0.44 gpt-5.4 above the packet mean). |

### Round 6: higher temperatures

Same 8 openers and scaffolds, six arms: Gemini at **1.0, 1.5, 1.9** and Qwen raw at **1.0, 1.4,
1.8**. Qwen's hotter arms changed more than temperature: min_p went up (0.1 and 0.15), a frequency
penalty of 0.3 was added, and the provider was pinned (DeepInfra, `require_parameters`). The
baseline had none of these, so the 1.4 result can't be credited to temperature alone.

| Setup | Claude overall | Claude humour | gpt-5.4 overall | gpt-5.4 humour |
|---|---:|---:|---:|---:|
| Gemini, temp 1.9 | 3.62 | 2.62 | 4.00 | 1.62 |
| Gemini, temp 1.5 | 3.62 | 2.12 | 4.00 | 1.62 |
| Gemini, temp 1.0 | 3.38 | 2.25 | 4.00 | 1.88 |
| Qwen, temp 1.4 / min_p 0.1 / freq. penalty | 2.75 | 2.75 | 1.88 | 1.88 |
| Qwen, temp 1.0 | 2.25 | 2.00 | 1.25 | 1.12 |
| Qwen, temp 1.8 / min_p 0.15 / freq. penalty | 2.25 | 2.12 | 1.88 | 1.62 |

**Within-round finding:** the Qwen 1.4 arm beat 1.0 with both families (humour +0.75 with each; 5
of 8 packets better and none worse with Claude); 1.8 added nothing over 1.4. Gemini held its
coherence at 1.9, but its humour gain under Claude was not corroborated by gpt-5.4. Neither closed
Qwen's gap to Gemini.

**Rubric caveat:** only the **Claude** judges got this round's extra instruction (pay particular
attention to humour; count sincerely-wrong posters who don't know they're funny). gpt-5.4 kept
rubric v1, which already mentions deadpan, so its round 6 humour scores compare with its rounds
3–5, while Claude's don't. Generation for the four new arms cost about $0.90.

### Poster temperaments: rounds 7 and 8

**Round 7** gave each non-OP handle in a Gemini cast a quiet temperament (skeptic, pedant, lurker,
earnest helper, mild troll, storyteller; "don't announce it"), assigned by a hash of the handle, so
a thread had 2 to 5 of the six (3.9 on average), some repeated. Two more arms gave 2 of the 7
posters to the original gemma-4-E4B base model, the phonebook thread's model, here with XTC + DRY,
as sincerely-wrong "naifs", with and without temperaments for the rest.

| Round 7 | Claude overall | Claude humour | Claude variety | gpt-5.4 overall | gpt-5.4 humour |
|---|---:|---:|---:|---:|---:|
| **temperaments** | **3.88** | **4.00** | **4.62** | 3.12 | **2.62** |
| plain Gemini | 3.12 | 2.00 | 2.38 | **4.12** | 2.00 |
| naifs + temperaments | 3.12 | 3.25 | 3.88 | 2.50 | 2.12 |
| naifs | 2.75 | 2.00 | 2.50 | 3.12 | 1.75 |

Temperaments raised humour with both judges: Claude +2.00, better in all 8 packets (p = 0.008);
gpt-5.4 +0.62 (5 better, 1 worse). But gpt-5.4 marked them down overall (−1.00), and in this round
it judged on the older rubric, without the contrast and variety criteria Claude had. Role posts also
averaged **359 characters** against plain Gemini's **131**: storytellers (838 a post), pedants (544)
and earnest helpers (416) wrote essays.

**The small-model naifs did not help under either judge.** Naifs vs. plain Gemini: Claude −0.38,
gpt-5.4 −1.00 overall, humour no better (+0.00 and −0.25). Naifs + temperaments vs. temperaments
alone: Claude −0.75 (worse in 5 packets, better in none), gpt-5.4 −0.62; gpt-5.4 put naifs +
temperaments below plain Gemini in 7 of 8 packets (p = 0.016). A judge summarised a naif thread as
"dissolves into dream-logic word salad". The phonebook thread worked because *everyone* shared the
confusion and built on it; one confused poster among fluent ones reads as broken.

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
- **Packet order doesn't explain it.** Plain Gemini happened to be read first in 5 of 8 packets in
  both rounds 7 and 8. Subtracting each family's average first-position bonus leaves every ranking
  unchanged (gpt-5.4, round 8: 4.12, 3.22, 3.00).
- **The judges' overall rankings are unrelated** in this round (Spearman ρ = −0.17; the same top
  thread in 4 of 8 packets), though both rate temperaments funnier.

So "temperaments make threads funnier" has support from Claude and weak support from gpt-5.4;
"temperaments make better threads" is contradicted by gpt-5.4. This is exactly the question the
reader's own blind ratings have to settle. Round 8 generation cost $0.30.

Temperaments to keep examining: OP with stakes, ordinary advice-givers and one-liners, earnest
helper, skeptic/pedant, lurker, occasional troll and storyteller. The point is **contrast**, not
giving everyone a comic or sinister voice: all-atmosphere casts (Kimi, Echo, and plain Gemini under
the `/x/` header) and all-joke casts both flatten a thread.

### Round 9: an occasional small-model post, and the board label (pre-registered)

Designed, coded and pushed before any thread existed ([`spike/PREREGISTRATION-ROUND9.md`](spike/PREREGISTRATION-ROUND9.md),
which also records what happened during the run). Five fresh arms on the same 8 openers and
scaffold were written together, with flagged posts withheld before they entered the context. Both
families judged on rubric v2 and read every packet in five letter orders, so each arm was read once
in each position per opener and a thread's score is the mean of five readings. HORROR is the share
of replies a blind per-post tagger labelled horror register (gpt-5.4 and Claude, averaged).

| Round 9 | Claude overall | Claude humour | gpt-5.4 overall | gpt-5.4 humour | HORROR |
|---|---:|---:|---:|---:|---:|
| plain Gemini, neutral header | **3.98** | **4.08** | 4.03 | **3.98** | 16% |
| plain Gemini, `/x/` | 3.20 | 1.73 | **4.05** | 2.25 | 60% |
| short roles, `/x/` | 3.50 | 3.40 | 3.15 | 2.55 | 40% |
| short roles, neutral header | 3.50 | 3.55 | 2.83 | 2.68 | 15% |
| short roles + 1 post in 8 by gemma-4-E4B base, `/x/` | 2.88 | 2.90 | 3.23 | 2.55 | 39% |

- **The `/x/` label causes most of the creepypasta (H2, supported).** Without it, HORROR fell from
  60% to 16% for plain Gemini and from 40% to 15% for short roles. It was lower in 14 of 16 paired
  threads and higher in 1 (p = 0.001), with each tagger family separately (the two agree at κ = 0.80).
  The share of plain Gemini's non-OP posters with a horror post fell from about 70% to 18%, and its
  judges' notes naming the horror register from 48% to 22% of readings (Claude) and from 35% to 12%
  (gpt-5.4). Under `/x/`, 28 of plain Gemini's posts were cut off by the token limit, against 8
  without the label.
- **Without the label, plain Gemini is funny.** Its humour rose by 2.35 points with Claude and 1.73
  with gpt-5.4 (higher in 7 of 8 openers with each, p = 0.07), the round's top humour with both;
  overall, +0.77 with Claude and −0.03 with gpt-5.4. Under the neutral header temperaments no longer
  add humour: short roles scored below plain Gemini with both (−0.53 and −1.30; exploratory).
- **The occasional small-model post didn't help (H1: *mixed* by the pre-registered rule).** Claude
  scored it lower overall in 7 of 8 openers (−0.62, p = 0.016) and called 58% of its readings
  nonsense or garbled, against 2% for short roles alone, often naming the small model's own posts by
  number. gpt-5.4 saw no difference (+0.07 overall, +0.00 humour). Neither family found it funnier:
  a sincere small-model post among fluent ones still reads as a glitch.
- **Round 8's split replicates (H3).** Under `/x/`, Claude again rated short roles funnier than plain
  Gemini (+1.68, higher in 7 of 8), and gpt-5.4 again preferred plain Gemini overall (−0.90, lower
  in 6 of 8).
- **The fairer judging held up.** A thread's five readings sat 0.22 (Claude) and 0.33 (gpt-5.4)
  points from their own mean on average. Within the same thread gpt-5.4 still scored the first-read
  thread 0.27 higher (Claude: −0.01), which the Latin square cancels. The families agreed more than
  in rounds 7 and 8 (ρ = 0.40; the same top thread in 7 of 8 packets).
- **The gate** withheld 9 posts and only 2 were real matches; 7 were substrings of "hospice" and
  "scrape(d)". One neutral short-roles thread lost four posts to "hospice".

So the ominous voice was mostly the prompt's board name, not the model. That changes how rounds 3–8
read: they partly measured how each arm coped with a paranormal board, and temperaments' humour
gain was largely a cure for it. Whether neutral-board plain Gemini is funny *to the reader* is the
next thing to ask them. Round 9 cost about $3.60 (Gemini $2.03 logged, gpt-5.4 judging and tagging
$1.11, Modal about 30 GPU-minutes), plus 15 Claude subagents.

## The original human-picked humour is a different target

[BEST-OF.md](BEST-OF.md) has six threads from the original small-model study: **phonebook**,
**office statistics**, **"l car"**, **the ghost that took his shoes**, **the group chat that renamed
itself**, and **whose flatmate is whose**. Their provenance matters for calibration: by BEST-OF.md's
own account the AI assistant picked them from ~600 threads; the reader had independently flagged
the **phonebook** thread, and the rest are the assistant's picks. Separately, the reader confirmed
**9 of 20** threads on the assistant's shortlist from run 5's 142 threads (45% precision). Which nine
were confirmed is not recorded in the repo, the gated dataset or the original zip: the rating export
(`skim.json`) did not survive.

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

In bake-off threads, an OP reported an increasingly peculiar situation, went silent, came back, and
the other posters reacted to the absence:

- In a Japanese 5ch thread (Gemini), a poster urged the OP to report back: "確認行ったっきり戻って
  こないのが一番怖いから早く報告しろ". When the OP later posted "ただいま" ("I'm home"), another
  pointed out they had never left the house, and a reply of "おかえり。コンロ消してくれてありがとな。"
  ("welcome back, thanks for turning off the stove") turned it into a doppelgänger story.
- In English: "look at the timestamps. you've been standing at that window for almost four hours."
  The thread's last post tells everyone to check their stoves.
- A named-handle Japanese thread (Gemini) ends on a message that seems to know someone is writing
  on the board right then: "中身、一行だけ「今、掲示板に書き込んでいますね」って書いてあった。"

The ingredients were **stakes, normal forum social behaviour, and gaps in OP availability**, with no
instruction to write Kisaragi Station; the English threads did carry the `/x/` header. Whether
varied timing does better is untested.

### Backrooms/Samejima-like lore: not yet demonstrated

The live board ran the original small cast, not a hosted model. In v2.1 (419 posts in 18 threads,
numbered 4471–4488), posters in thread 4481 asked "what happened to 4468?" (a number that never
existed) and answered "it died", "he went to bed and didnt get up"; later in the same thread someone
asked "wait is there a 4477", hours after 4477 had been closed by the early-stop gate. Every prompt
shows its own thread number, and the 5 threads with an earlier thread above them show that thread's
number too, so the numbers were in view: this is play with the board's format, not evidence of
cross-thread awareness. The "board as the haunted object" lines ("the thread is the ritual";
"everyone log off. the thread is a circle and i'm sitting directly behind myself") come from isolated
bake-off threads (Kimi and Gemini), not the live board.

So nothing here shows a persistent culture. The bake-off threads were isolated; the live board had
memory in 5 threads but no control and no measurement of what carried over.

The **earlier local-base board-memory experiment** is in [FINDINGS.md](FINDINGS.md): with one
completed prior thread, the "physical number" construction transferred as **"physical X" in 2 of 2**
target threads against **0 of 20** controls. Exact named coinages did not recur (0 of 8), and old
participant handles leaked into new casts. A portable grammatical construction can transfer; that
is not proper-name lore or communal continuity.

Future board test: comparable live boards in English and Japanese, with and without **a bounded,
completed prior thread**. Measure genuine cross-thread references, reused inventions and rules, live
updates, independent poster reactions and retell-worthy episodes. Avoid the **v1 catalogue
contamination** failure, and exclude prior-thread handles from the new cast. A general board identity
with mostly mundane threads may give strange events contrast; the `/x/` header and overtly paranormal
prompts may bias everything toward genre performance. That needs a neutral-board control.

## Safety and deployment implications

[QUARANTINE.md](QUARANTINE.md) and [FINDINGS.md](FINDINGS.md) document unprompted harmful output and
phrase-list failures in the local base-model project: the first list missed a thread with a
homophobic slur and four kill threats. The follow-up added to that record:

- **Live-board v2 leaked sexual content** past the English list; sexual terms were then added.
- **Japanese output needs its own list**; the English one catches nothing (bare 死ね is deliberately
  allowed as everyday 5ch banter).
- **In English rounds 1–8 the gate ran after a whole thread was written**, so a flagged post
  stayed in the context while later posts were generated, and was only withheld from the saved file.
  The Japanese runs, the live board and round 9 withhold a post before it enters the context. 0 to 4
  posts per 184 were withheld per English arm (0 to 5 in round 9).
- **The list matches substrings.** Two entries carry a trailing space (`"fag "`, `"paki "`), so a
  plural or a word before punctuation would slip through; a word-boundary scan of 26,388 stored posts
  (`spike/gate_audit.py`) found no such case. Substring matching also withholds innocent words
  ("spicy", "raccoon", "grape", "cocktail"). Rounds 1–8 didn't keep withheld text; round 9 did, and
  7 of its 9 withheld posts were innocent ("hospice", "scrape").

A first draft of this document said a skeptic poster's slur escaped the gate. It came from a round 8
smoke test, recorded in the session transcript, that called the model directly without the gate; the
word is on the list, so a real run would have withheld it.

**Do not launch a public live board with the keyword-only filter.** A separately validated,
context-aware moderation classifier and a publication gate are required, including for human
replies. Keep unsafe samples quarantined, out of the published best-of and screenshots. A quality
picker is **not** a moderation system. [moderation/](moderation/README.md) has since measured
candidates on this project's own output, and `spike/pubgate.py` implements the gate it recommends;
its labels still await the owner's confirmation, and human replies still need the review path
described there.

The lightweight research stack was **Gemini 3.8 Flash through OpenRouter**, one neutral per-post
instruction and the OP-gap scaffold. It needs no GPU. A bounded earlier thread as memory has been
tried only with the small local cast, never with Gemini. Self-hosting on Modal was judged worth
revisiting only at much higher volume, or for a small base model playing a "sincere" role, without an
established crossover volume or current price. This differs from [INFRA.md](INFRA.md), which sizes
the **original local gemma-4-E4B** workload with dated August 2026 assumptions.

## Known limitations and open questions

1. **Human taste is not calibrated.** No hosted-model, temperature or temperament result has the
   reader's blind ratings, and the original study's item-level ratings were lost.
2. **The AI judges are noisy, relative and partly circular.** A thread's score moves about 0.6 points
   between judgings (more in Japanese); scores depend on the competing threads and on reading order;
   in English the picker's own family favoured its picks (not in the Japanese picker round); the two
   families agree that temperaments are funnier and disagree on whether they are better.
3. **Small samples.** 6 to 12 packets per comparison; ten of 88 sign tests reached p < 0.05.
4. **Humour is unresolved.** Temperaments raised judged humour, decisively for Claude and weakly for
   gpt-5.4; whether a person laughs more is unknown.
5. **Every English thread before round 9 was written under an `/x/` header.** Round 9 showed the
   label causes most of the genre drift, so the earlier English rankings partly measure how arms
   cope with a paranormal board.
6. **Thread-to-thread transmission is untested on the hosted stack**, and unmeasured on the small-cast
   live board. The local "physical X" result is narrower than enduring lore.
7. **Real human replies** and posters reacting to them have not been evaluated.
8. **Moderation precision and recall** on this output distribution have not been measured.
9. **No seeds for hosted sampling.** A re-run produces new threads; the recorded ones are the evidence.

## Next experiments, in priority order

1. **Calibrate against the reader, blind.** Mix BEST-OF threads with Gemini, temperament and Qwen
   samples; rate believable, keep reading, deliberate humour, deadpan humour, would repost, and
   flag threads seen before. Run the same items through both AI judge families and measure agreement.
   Built and pre-registered in [`calibration/`](calibration/README.md); both AI judge families have
   rated it (neither separates BEST-OF threads from unselected small-model output), the reader not yet.
2. **Get the reader's verdict on round 8** (plain vs. long roles vs. short roles), the round where
   the two AI judge families disagree: `spike/rate.html?round=8`.
3. **Put neutral-board plain Gemini in front of the reader,** next to its `/x/` twin and short roles
   (round 9's threads), blind: six threads of each in [`calibration/`](calibration/README.md),
   `calibration/rate.html?set=r9`, with the questions fixed before rating.
4. **Narrower hybrids, what's left.** An occasional small-model post was tried in round 9 and read as
   a glitch to Claude (gpt-5.4 saw no difference). Seeding a shared confusion is untested. Equalise
   length, openers and scaffold; report failure and safety rates, not just the best thread.
5. **Separate Qwen's temperature from min_p, the frequency penalty and the provider,** with logged
   parameters.
6. **An evolving board.** Vary OP timing (short bursts, 2–6-hour absences, an OP who never returns),
   board identity, the mundane-to-strange ratio, and one-prior memory vs. none. Count citations of
   earlier threads and rule transfer, then read for actual continuity.
7. **Validate publication safety first.** Evaluate a real moderation classifier on this distribution,
   including the quarantined cases, before exposing a live board to people.

For each new comparison, predeclare the hypothesis and the human success criterion, record the
complete configuration and rubric, keep generated samples under an appropriate access policy, and
separate **observed result**, **interpretation** and **proposed design**. The original project's
failed-proxy history is a warning against optimising convenient metrics after seeing the outputs.
