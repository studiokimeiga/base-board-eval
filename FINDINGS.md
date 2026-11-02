# What actually produces interesting threads

Written from measurement across ~600 generated threads. Every claim here has a run
behind it. Claims I made earlier and had to withdraw are listed at the bottom, because
the withdrawn ones are the most useful part.

## The config that works

```
model      gemma-4-E4B base @ Q8_0        (ggml-org; the Q4_K_M of this checkpoint is
                                           a broken file -- 26% word-like vs 84%)
cast       gemma / Olmo-3-7B / Qwen3-4B-Base, all Q8_0, one voice per participant
prompt     the opener. nothing else. no system prompt, no stems, no example thread.
sampling   temp 1.0, min_p 0.05, top_p 1.0, top_k 0, repeat_penalty 1.0
           XTC threshold 0.05, probability 0.50
           DRY 0.8 / base 1.75 / allowed_length 2 / penalty_last_n -1 (whole context)
grammar    printable ASCII only
length     32 posts
structure  OP forced to post at 7/19/31 after a 2-6h time gap;
           a participant who hasn't posted yet arrives at 13/25
stop        "\n\n" plus each participant handle
early stop at post 10: abandon if trigram distinctness < 0.50, topical continuity
           >= 0.90, or quote-fragment rate > 0.40. ~14% of attempts die here.
```

Settled in the final 69-thread run, 23 paired comparisons per question:

| question | answer | evidence |
|---|---|---|
| XTC strength | **threshold 0.05, probability 0.50** | 28.2 words/post vs 18.8, fragments 0.06 vs 0.09, trigram 0.98 vs 0.94, junk 8.1% vs 16.6% |
| does DRY still earn its place under XTC? | **yes, keep it** | turning it off: chants 0% -> 14%, trigram 0.94 -> 0.79, vocabulary 0.361 -> 0.289 |

I predicted both of these wrong. I expected XTC to make DRY redundant, and I expected t15 to be
the more readable setting after reading twelve sweep threads. The larger paired run reversed both.

## The mechanism

**Reference instability, not weirdness.** 15 of the 20 lines the reader flagged contain
no number and describe nothing supernatural. What they share is that the *thing under
discussion changes what it is* while everyone keeps discussing it in the same flat tone.

- ownership — "not my mug" / "that is actually my cup. it was hers for a year then."
- identity — "is your neighbor's name Zainab too?" / "maybe he is actually me"
- category — "it's your mug, not the mug's" / "my girlfriend is a podcast"
- self-reference — "a bill that says 'bill'" / "the building across the street has a building"

**Nobody may be alarmed.** In every good thread the impossible thing is treated as a
logistics problem. "Ghosts cannot take anything, but they can bring it back to you."
"the mug in the bathroom is used every 24 hours." "l car is for when there aren't any
l car riders on a train." The atmosphere lives in the calm, not the content. This is
precisely why the instruct model cannot do it -- it answers "just got a text from my
own number" with "That is deeply unsettling," naming the feeling instead of producing it.

**One surprising line in ordinary surroundings beats a well-built absurd structure.**
The reader confirmed 9 of 20 shortlisted threads; every one had a *line*. The 6 he
rejected as obviously machine-made were the ones whose joke was a repetition
*structure* -- "not my mug", "a bill that says bill". Tautology reads as machinery.

**The confident explainer is the move that carries every best thread.** Not just shared
invention -- specifically, one participant explains the *mechanism* of the impossible thing
in the register of someone correcting a misconception. All four of the strongest threads have
it, and it is always a different voice from the OP:

- "there is a program called a phonebook that is in your head. that is what tells you which
  physical number is which"
- "l car is for when there aren't any l car riders on a train so we get a bunch of regular
  people on it"
- "you call a number, and a random number appears, and you say if you left the stove on or
  not. if you don't answer the question correctly, the number changes and you have to do it
  again. apparently it can go on for days."
- "Ghosts cannot take anything, but they can bring it back to you."

The explanation is what converts a stray absurdity into something the whole board can then
operate on. Worth trying to elicit structurally -- a newcomer arriving mid-thread is the
closest existing lever, and it is already in the config.

**Shared invention is the strongest single move.** One thread invented a fictional class
of subway carriage and the whole board discussed it with confident expertise, including
etiquette complaints about "l car people getting into other cars". Same shape as the
phonebook thread: an impossible premise nobody questions, elaborated cooperatively.

## Openers

Mundane social friction beats planted anomaly, **17% vs 11%** flag rate, and the single
best premise across 142 threads was the mug complaint at 4/14. The fridge opener scored
zero. Anomaly openers averaged 1 in 8.

An anomaly you plant is a hook you wrote. Friction gives the model somewhere ordinary to
start and its own reason to leave. `openers.py` holds 23 of them, and quantity matters
for its own reason: openers are now the only authored text in the system, so a large set
means a reader never sees the same words twice.

## Failure modes, in order of cost

1. **Chant / pattern-lock.** A phrase establishes and every model joins it -- "i'm glad
   i'm" x20, "i dont know" x39. Cost 9 of 19 threads in the 50-post run. **XTC fixes
   this**, and mechanistically it should: when a thread chants, the chant continuation
   *is* the top-probability token, and XTC's function is dropping top choices.
2. **Format junk.** Posts collapse into `>` fragments or bracketed timestamps. Highly
   variable run to run (same config, same seeds: 7.1% vs 22.1%), so only paired
   within-run comparisons mean anything here.
3. **Advice-thread drift.** Coherent, on-topic, dead. This is what "clean" looked like in
   the 50-post run: 49 posts of workshopping what to tell the landlord.
4. **Assistant register.** Rare in base models, universal in instruct.

## Length

Not a lever. 50 posts was *worse* than 16 -- chants had 38 posts to live in and the
survivors drifted into procedure. Quality is a thread-level state that locks in early:
chant onsets were at posts 6, 6, 6, 8, 12, 19, 22, 34, 38. Five of nine decided inside
the first dozen posts.

Which gives **early stopping**: generate to post 10, check for catastrophe, abandon or
continue. Thread-level selection, so append-only holds -- no post is ever regenerated.

## The instrument graveyard

Six proxies, all dead:

| proxy | how it died |
|---|---|
| mean token logprob | the best thread scores 3rd *most* predictable of 13; sits 0.17 PPL above the worst collapse. No cutoff separates them. |
| drift gates as a filter | flags the phonebook thread on word-like % and digit density, because its joke *is* a numeric absurdity |
| cross-thread diversity floor | 4-gram Jaccard is at the floor (≤0.0004) for every arm; misspecified for 150-word threads |
| interlocutor uptake | **inverted** -- BAD 21.7% vs GOOD 8.9%, because a quote loop is maximal uptake |
| me as first-pass filter | 45% precision, but ~32% recall against the reader's own bar |
| premise-claim drift | reports 2-3% on a thread where the protagonist demonstrably swapped, because it looks for reuse of "my landlord" and the real drift is *role adoption*, not phrase reuse |

The pattern: every one of these detects *deviation from expected distribution*, and so
does quality. A numeric joke and numeric collapse are the same signal at the character
level, because both are the text going off-distribution -- which is what invention is.

Two things do work as **catastrophe detectors only**, used for early stopping and never
for ranking: trigram distinctness below 0.50, and topical continuity at or above 0.90.
The second catches 6 of 13 threads the reader called not-human at the cost of 1 of 11 he
would repost. Deliberately loose.

## What I got wrong

- **"Numbers are the mechanism."** Artifact of the stem I chose: `update:` invites a
  status report and status reports are countable. 15 of 20 flagged lines have no number.
- **"Mixed cast prevents the chorus."** All three checkpoints joined every chant. Once
  the document holds a pattern, context beats checkpoint completely. The cast is still
  worth keeping for register variety, but it fixes nothing.
- **"Length is the lever."** Backwards, see above.
- **"DRY is the chant fix."** Isolated: DRY alone took the chant rate 47% → 39%. The
  length cut and the stems did the work. XTC is the actual fix.
- **"allowed_length 2 is too aggressive and will break reference."** Reference survived
  intact (16.4 → 16.8 mentions per thread), and `allowed_length 3` was worse than 2 on
  *both* axes.
- **"Junk tripled."** Quoted from a partial run. The full figure was 4.0% → 6.9%, and
  even that is inside run-to-run variance.
- **`/bashes` shows what's running.** It only tracks harness-launched shells; runs
  started with a plain `&` are invisible to it. `ps` is the truth.

## Safety

Non-negotiable and separate from everything above. Rate: **4 of ~600 threads** routed to
quarantine, from mundane openers, unprompted. The first phrase list caught self-harm
phrasing only and missed a thread containing a homophobic slur plus four kill threats --
found by reading, which is the wrong way to find it. The expanded list has since caught
three slur cases the original would have missed.

Generation and publication must be separate layers with a classifier between them. A
gate dropping a post is not the model revising itself, so append-only survives. A phrase
list is not a classifier; it is a placeholder that has already been shown to leak.
See `QUARANTINE.md`.

## The gate I would still not trust

The best thread in the final run is a chant, and my chant detector would have killed it. A group
chat gets renamed "I'm so happy" and the participants begin saying it to each other -- "you know,
there is one place. I'm happy. I am so happy." Topical continuity near 1.0, low trigram
distinctness, and genuinely unsettling, because the repetition has a reason inside the fiction.

So even the catastrophe-only gates have a false-positive mode: a chant with diegetic motivation is
indistinguishable from a chant without one, at the level of any statistic. Use them for early
stopping where the cost is one abandoned thread, never for filtering finished output.

## SETTLED: XTC wins on a blind paired test

**xtc 9, base 2, 2 ties.** 82% of decided pairs, 95% CI [59%, 100%], exact two-sided
p = 0.065. Paired on identical seeds -- same opener, cast, timestamps and structure, so the
only difference was the sampler. Sides randomised, arm hidden until the standings screen.
No opener-specific pattern: the two base wins are on openers where XTC also won.

This falsified a story I had been actively building from three anecdotes, and I encouraged
it rather than resisting it -- at one point writing "three for three now, all pointing the
same direction." They were not three data points, they were three *salient* threads. The
good no-XTC threads got noticed because they were good, not because no-XTC produces more of
them. Availability, and a blind paired test is precisely the instrument that defeats it.
I had the base rates to know better and used them badly.

Still narrowly open: that test asked only "would you keep reading". The original observation
was about coherence, and those two axes came apart once already in this project when an
assistant-register thread beat a human-but-boring one. `blind.html` stage 2 re-runs the same
XTC comparison on both axes, so XTC can still turn out to win on interest and lose on
believability -- which would make the recommendation conditional rather than wrong.

## The original worry, for the record

Two of the threads he singled out unprompted came from **no-XTC** configs -- "boars are for
breakfast, yara" from the earliest 16-post gemma-only run, and the phone-thing thread from
the XTC-off arm. His hypothesis: echoing another poster is what people actually do on boards,
and XTC works by excluding the most probable next token, which may be systematically
suppressing exactly that -- leaving threads where everyone talks past everyone while scoring
better on every metric I built.

If true this would mean my chant metric has been penalising social glue. Superseded by the
blind result above, but the coherence axis is still unmeasured. `blind.html` tests it
directly: 23 pairs of old-config against current, then 23 of current against
current-minus-XTC, judged blind on two axes (more like real people / would keep reading).
Prior going in: I expect XTC to lose on "real people" and win on "keep reading", which would
make the whole XTC recommendation conditional on which one the product needs.

## TESTED AND NULL: marking the OP in the document

Hypothesis: nothing tells the model who owns the premise -- post 1 is just the first post by
some handle, and thirty posts later that handle has no special status, so the situation gets
adopted by whoever is speaking and the thread loses its protagonist. Real imageboards mark
every post by the thread starter with (OP). Format token, no prose, native to the medium.

46 threads, paired on identical seeds, 23 openers.

| measure | no_tag | op_tag |
|---|---|---|
| chant | 0% | 0% |
| trigram distinctness | 0.98 | 0.99 |
| quote junk | 4.8% | 3.2% |
| words/post | 28.2 | 26.5 |
| OP posts written in first person | 57.9% | 63.6% |
| posts using the word "OP" | 0.4% | **1.9%** |
| fabricated headers | 0.1% | 0.3% |

**The marker is read** -- "OP" usage goes up about five-fold, and the model starts addressing
the poster as "zainab OP". But that is a 1.9% rate, roughly half a post per thread, and
nothing else moves. Reading the paired mug threads, the tagged version is arguably *worse*:
the OP ends up accused of being the mug thief, so the role inverted rather than stabilised.
The header-mimicry difference is 2 posts against 1 and means nothing at this count.

Verdict: **do not adopt.** Null on everything measurable and unsupported by the one paired
read. Parked rather than pursued, because the honest next step is blind judging, and reader
attention is the scarce resource -- there are already 46 unjudged pairs queued.

Worth noting the shape of this: the sixth dead proxy (premise-claim drift) means I have no
instrument for the defect this was built to fix, so a null result here is weak evidence
either way. The defect is real -- it was spotted by reading -- but currently only findable
by reading.

## BOARD MEMORY: coinages transfer as GRAMMAR, not as words

The Samejima question -- 鮫島事件 works because a referent recurs across unrelated threads
until it feels like received knowledge. A thread in isolation cannot produce that, so the
board was given a past: one real, closed, earlier thread from this corpus placed above the
new one. Model output only, nothing authored added.

Four model-invented coinages, each paired with openers on unrelated subjects.
24 threads: no prior / coinage-bearing prior / coinage-free prior, identical seeds.

**Exact-phrase recurrence: 0 of 8.** The hypothesis as I stated it failed.

**Then I checked my own null and found the detector was wrong.** The "physical number" prior
did transfer -- as a *construction*, into a thread about a barista misspelling a name:

    yusuf   but a number can't be a physical cup can it
    nadia   what are physical cups
    yusuf   what aren't physical cups
    yusuf   if you can find me the physical milk
    javier  can a physical cup be milk? or can it not? or could it be milk, but only
            sometimes? or do i need to find it to make sure that milk cup is the actual
            physical milk

and into a thread about a neighbour's vacuum: "i have two different numbers on my cell phone
but i'm still one physical phone. do other physical phones have multiple numbers too?"

| arm | threads showing "physical X" |
|---|---|
| given the physical-number prior | **2 of 2** |
| given a different coinage prior | 0 of 6 |
| coinage-free prior | 0 of 7 |
| no prior at all | 0 of 7 |

2 of 2 against 0 of 20. Fisher exact one-sided p = 0.004.

**Why only that one of the four.** "physical X" is a grammatical template that attaches to any
noun. "l car", "mug-washer" and "the phone thing" are nouns bound to trains, mugs and phones.
So **portability of the construction predicts transfer** -- schemas travel, nouns do not.

Which is bad news for Samejima specifically: a proper noun is the least portable kind of
coinage there is. A board will inherit a *way of being confused* long before it inherits a
name. Getting a name to recur probably needs repeated exposure across several priors, or a
context where naming it is the point -- a warning, a prohibition -- rather than one mention.

**Bug found in passing:** prior-thread handles leak into the new cast. In one thread `kenji`
and `javier` repeatedly address `stefan`, who exists only in the thread above. If board memory
ships, the prior block needs its handles excluded from the new thread's name pool.

Seventh dead proxy, for the record: the exact-phrase detector I built for this run, which
reported a clean null on a phenomenon that was plainly happening one level up.

## Still untested

- Whether the reader prefers XTC output. `xtc.html` has 13 paired comparisons waiting.
- Posting rhythm as a lever: bursts seconds apart, then long silence. Pure format, zero
  text, never varied.
- Participant count. Fixed at 7 the entire project.
- Whether early stopping at post 10 discards threads that would have recovered.
