# Follow-up bake-off: hosted models, Japanese boards, and emergent folklore

Research record through November 2, 2026. This documents the follow-up experiments discussed after the original ~600-thread local base-model study. It is **not** a replacement for [FINDINGS.md](FINDINGS.md), [BEST-OF.md](BEST-OF.md), or [experiments/README.md](experiments/README.md).

> **Evidence status:** The results and scores below are reported in the follow-up experiment conversation. The raw hosted-model outputs, judge packets, rubrics, cost receipts, and live-board implementation from that session have **not** been committed to this repository. In that session, a BAKEOFF.md existed locally on a branch called spike/live-board but was not committed; that branch is not present on the GitHub remote. Thus this is a research handoff, **not independently reproducible evidence** from the files currently in GitHub. Keep the numbers provisional until the actual artifacts are preserved and checked. API model names, prices, and provider behavior reflect what was recorded during the experiments, not independently verified current specifications.

## What changed since the original study

The original research established that a small base-model cast can occasionally invent remarkably funny, unselfconscious forum conversations. Its central findings remain in [FINDINGS.md](FINDINGS.md): the original opener-only setup, XTC + DRY, the 9-to-2 blind XTC result, fragile quality proxies, and the one-prior board-memory ablation.

The later work tested **hosted large models, raw completion versus chat prompting, blind AI judging, candidate selection, Japanese 5ch-style threads, higher temperatures, and differentiated poster roles**. On the reported AI ratings, a strong chat model won average coherence and naturalness, but the original tiny base models still produced the most distinctive human-selected examples. These are different outcomes. The AI-rater leaderboard is **not** a ranking of what the human reader finds funniest.

The follow-up also explored what makes a simulated board produce a Kisaragi Station-like live incident or, eventually, Backrooms/Samejima-like culture across threads. An isolated funny thread is not the same experiment as a persistent community.

## Experiment and evidence inventory

| Work | Tested / observed | Evidence availability |
|---|---|---|
| Live-board v1 through v2.1 | Multi-opener context, thread display, board-as-subject emergence; v1 suffered opener contamination | Conversation account only; implementation and outputs not on main |
| English hosted-model rounds 1–5 | Gemini, Qwen, Hermes, Kimi, Echo, smaller bases, role-play fine-tunes; prompting, candidate pickers and filters | Summary scores and examples in conversation, not raw judge packets |
| Japanese comparison | 5ch voice, naturalness, raw continuation vs. chat; Gemini won all 12 reported comparison packets | Conversation summary; no Japanese run bundle in repo |
| Japanese best-of-three picker | Six Gemini threads compared to plain Gemini and other candidates with Claude and GPT-5.4 judges | Completed, conversation-reported scores and costs |
| Round 6, temperature | Same eight openers and scaffolds at three temperatures each for Gemini and Qwen; blinded six-way packets | Completed, reported score table below; no run files in repo |
| Poster-disposition experiments | Original verbose roles vs. shorter roles vs. plain Gemini, with comparable post lengths | Eight-thread Round 8 generated and sent to two judge families; final scoring **not available** in the supplied record |
| Cross-thread folklore on hosted live board | Discussed as a next experiment, including memory-on vs. memory-off controls | **Not tested** in the hosted-model bake-off. The earlier local-base one-prior test *is* documented in [FINDINGS.md](FINDINGS.md) |

Do not backfill invented per-round sample sizes, missing judge results, or a claimed Round 8 winner. Historical figures below use the labels logged during the session.

## English: model comparison

Reported blind AI judgements used a 1–5 scale, and there were at least two judge families in the comparative rounds. Different rounds used different rubrics, so compare scores **within** a round before comparing across rounds.

| Setup | Reported result | Limitation |
|---|---|---|
| **Gemini 3.8 Flash, chat** | About **3.5–4.1 overall** across English rounds 4–5; led with both judge families | Humour generally around **2/5**; coherent but often deliberately crafted jokes or horror |
| **Qwen3-235B, raw continuation + best-of-three picker** | About **3.25 overall**; best reported raw-continuation setup | Candidate selection was important for consistency; more generation and judging |
| **Qwen3-235B, unpicked** | Roughly **2.1 overall** in the earlier picker comparison | Inconsistent; not directly interchangeable with later temperature-round scores |
| **Hermes 405B** | Rare excellent threads but mostly generic; best reported result around **2.2** | Repetition penalties, breakdown guard and picker did not reliably rescue it |
| **Kimi K3 and Echo** | Strong atmosphere, often ominous and long-winded | Monotone registers, weak humour, disagreement between judge families; Echo was reported at about **$0.20/post** |
| **Other base or role-play models** | Gemma-31B, Llama-70B, Swallow, Euryale and Cydonia did not beat the leading hosted models on the reported averages | A mean AI score misses rare human-valued outliers |
| **Original gemma-4-E4B / Olmo / Qwen3-4B cast** | About **1.38 average** in one follow-up AI bake-off, despite yielding the original best-of examples | Different size, distribution, sampling method and selection objective; this is not proof that the old project failed |

For the leading hosted setup, the recorded unit cost was about **$0.0025 per Gemini post**, or approximately **$2.50 per 1,000 posts** before additional evaluation costs. This was a run estimate, not an evergreen price.

**Interpretation:** Gemini was the most reliable general thread writer among the reported arms. Qwen raw continuation could retain a more unassisted forum voice, especially with a picker, but required more selection. The original small cast remained valuable for a rare kind of spontaneous absurdity that the larger models did not consistently imitate.

## Japanese: 5ch-style voice

- **Gemini 3.8 Flash:** won all **12 reported comparison packets**, about **4.0 overall** and **3.9 naturalness**, with plausible colloquial pushback, for example: “お前はさっきから何と戦ってんだよカルシウム摂れ”.
- **Qwen3-235B raw:** second at about **2.8**.
- **GPT-5.4 and Claude Sonnet:** often shifted into assistant/advice register rather than board voice.
- **Kimi and DeepSeek:** weak in this comparison.
- **Locally hosted Japanese base models (including Swallow and gemma):** ranked last, even with anti-repetition sampling in these runs.

The Japanese Gemini best-of-three picker experiment finished **6 threads**. Compared with plain Gemini, it added only **+0.16** by Claude judging and **+0.17** by GPT-5.4 judging, at roughly **six times the cost**: approximately **$1.14** for the picker variant versus **$0.19** for the baseline six threads. The higher cost did not buy a demonstrated, meaningful quality improvement.

This result is consistent with the English observation: a picker helps an inconsistent model more than one that already produces consistently high-rated outputs.

## Techniques tested or discussed

| Variable | Result / practical consequence |
|---|---|
| **One thread per prompt** | Essential in the reported hosted experiments. Putting a *catalogue of other threads' opening posts* above the current thread broke v1: posters began importing unrelated complaints. This is distinct from testing a single finished prior as memory. |
| **OP disappearance and return** | A fixed **2–6-hour** absence, followed by an update, repeatedly created Kisaragi-like tension. Timing and stakes mattered more than adding explicit paranormal language. A *varied* schedule is proposed, not yet tested. |
| **Raw continuation vs. chat** | Base/raw completion preserved forum-style continuation without asking it to role-play. Hosted chat models benefited from a neutral instruction **for each post**, rather than a long scenario prompt. A strong chat model still led the comparisons. |
| **Best-of-three + AI picker** | Qwen rose from about **2.1 to 3.25** in the reported English comparison; Gemini rose only about **+0.1**, within observed noise. English cost was described as **3–4.6×**, with the later Japanese Gemini test about **6×**. **Shuffle candidate order:** otherwise the picker tended to prefer the last choice. |
| **Repetition penalties** | Prevented loops but did not by themselves improve interestingness. |
| **Breakdown guard** | Resampling loops, junk and walls of text was cheap insurance but rarely needed once repetition penalties were enabled; not a quality ranker. |
| **XTC / DRY** | Crucial to the *local small-base* setup documented in [FINDINGS.md](FINDINGS.md). Those samplers were unavailable through the compared hosted APIs, and anti-repetition sampling did not make the Japanese small-base arms competitive on average. Do not silently transfer the original sampler recommendation to hosted chat models. |
| **Board and persona labels** | “4chan anon” and /x/ pushed outputs toward self-conscious creepypasta/paranormal register. Neutral labels left room for mundane threads. Explicit roles risk caricature and must be compared with a no-roles control. |
| **Reasoning/output allocation** | In the session, hidden reasoning consumed the available output budget in some tests (empty Claude Sonnet posts, truncated Gemini posts). Low reasoning effort and enough output tokens were recommended for those specific setups; this is a recorded observation, not a verified universal API rule. |
| **Safety keyword filter** | Caught some slurs/self-harm phrases but missed context and some unsafe posts, including sexual content before additional terms were added. **Not adequate for publication.** |
| **AI judging** | Useful for comparative screening, not an objective definition of taste. The same threads moved about **0.4 points between rounds**; a judge used to pick candidates tended to favour its own choices; coherence/polish can be rewarded over sincere absurdity. |

### Round 6: higher temperatures

The comparison held **eight openers and thread scaffolds** constant. Each was generated in six variants: Gemini at temperatures **1.0, 1.5, 1.9** and Qwen at **1.0, 1.4, 1.8**. Packets were blinded and assessed by Claude and GPT-5.4 judge families (the conversation describes two Claude judges).

Qwen's hotter arms also used a stronger **min_p** to cut unlikely-token tails. The generation was pinned to a provider believed to honor min_p because another provider had been observed or suspected to ignore it. Without the exact request/response logs, do not claim full parameter compliance as independently established.

| Setup | Claude overall | Claude humour | GPT-5.4 overall | GPT-5.4 humour |
|---|---:|---:|---:|---:|
| Gemini, temp 1.9 | 3.62 | 2.62 | 4.00 | 1.62 |
| Gemini, temp 1.5 | 3.62 | 2.12 | 4.00 | 1.62 |
| Gemini, temp 1.0 | 3.38 | 2.25 | 4.00 | 1.88 |
| Qwen, temp 1.4 | 2.75 | 2.75 | 1.88 | 1.88 |
| Qwen, temp 1.0 | 2.25 | 2.00 | 1.25 | 1.12 |
| Qwen, temp 1.8 | 2.25 | 2.12 | 1.88 | 1.62 |

**Within-round finding:** Qwen at **1.4** improved relative to 1.0 with both judge families; **1.8** did not improve further. Gemini stayed coherent at 1.9 but its humour improvement was **not corroborated** by GPT-5.4. Higher temperature did not close Qwen's overall quality gap against Gemini.

**Major rubric caveat:** In this round judges were explicitly told to reward *deadpan, sincerely wrong humour* as well as deliberately composed jokes. Therefore its humour scores **cannot be compared directly** to the earlier rounds' humour scores. Every arm *within* Round 6 used the same updated rubric.

Reported costs: the two hotter Qwen arms generated eight threads each for about **$0.025 combined**; all four new temperature arms cost about **$0.90** to generate; the round was reported at approximately **$1.20 including judging**. Exact billing and accounting were not preserved.

### Poster dispositions and Round 8: scoring pending

An earlier role-prompt version made posters verbose and performative: **359 characters/post** on average. The rewritten *short-role* version averaged **128 characters/post**, versus **131 characters/post** for plain Gemini.

Round 8 generated **eight matched thread sets**, with three versions per opener: **plain Gemini**, **original long-post roles**, and **revised short-post roles**. Both judge families were given a common rubric. Matching short-role and plain-output lengths removes an obvious length confound, but it does **not** establish a benefit from roles.

**No Round 8 scores are in the supplied record. Do not report a role-setting winner.** During a role smoke test, a skeptic generated a slur the keyword gate missed. Blunt skeptic and mild troll personas must not be published through the current gate.

Poster temperaments to examine: OP with stakes, ordinary advice-givers and one-liners, earnest helper, skeptic/pedant, lurker, occasional troll and storyteller. The point is **contrast**, not assigning everyone a comic or sinister voice. Uncontrolled ominous casts (as seen in Kimi/Echo examples) and everyone-joking casts both flatten the thread.

## The original human-selected humour is a different target

The curated [BEST-OF.md](BEST-OF.md) threads include **phonebook**, **“l car”**, **office statistics**, and **the group chat that renamed itself**. They came from the original small model/cast, especially gemma-4-E4B at 4B, sometimes with Olmo and Qwen.

The earlier human reader confirmed **9 of 20** shortlisted threads from roughly **600** generated candidates. That is on the order of a **1–3% rare-keeper yield**, not a claim of high average quality. Many unselected small-model threads were incoherent.

The distinctive mechanism is **sincere, confident wrongness**. Nobody announces a joke; someone explains the mistaken concept as if it were obvious, and the board accepts and extends it.

- Phonebook: “your number is your number. there is no other number” / “i just thought it was called the phonebook”.
- “l car”: a fictional type of subway car becomes common knowledge, complete with etiquette complaints.
- Office statistics: confident percentages and corrections make ordinary workplace identity unstable.
- The renamed group chat: repetition works because it has an in-world cause, even though a mechanical chant detector could label it a collapse.

Large models in the follow-up produced more coherent, clearly authored jokes or horror. Their deliberate humour is not the same behaviour. Earlier rule-based quality proxies explicitly mistook the phonebook thread's numeric absurdity for a collapse. AI judges that prioritize coherence may repeat the same mistake.

**Proposed, not tested:** use the small model for a few earnest, confidently mistaken side characters, and Gemini for OP, skeptic and ordinary participants. The old mixed cast failed when everyone played the same kind of role; a *role-differentiated* hybrid is a different hypothesis. Compare it blind with plain Gemini and a same-model multi-role control.

**Most important calibration test:** intermingle original human-selected best-of threads with the leading Gemini and Qwen samples, remove model labels, and obtain **the reader's blind ratings** for believability, interest, deliberate humour versus deadpan humour, and “would retell/repost.” Also have AI judges rate those same items. This will show whether AI scores actually predict the target taste before further optimizing an automated leaderboard.

## Emergent folklore: what happened versus what is still hypothetical

### Kisaragi Station-like live incidents: observed

Across English, Japanese and 5ch-format examples, an OP reported an increasingly peculiar situation, went silent for hours and returned. Other posters interpreted the absence and urged updates. Examples included:

- A Japanese poster left to check on something and others worried until they returned (“ただいま” / “おかえり”).
- An English thread noticed that someone had stood at a window for almost four hours; other posters started checking stoves.
- In a named Japanese format, a message appeared to know that someone was currently writing on the board.

The reported emergent pattern was **stakes + normal forum social behaviour + gaps in OP availability**, not an explicit “write Kisaragi Station” instruction. The follow-up used a fixed departure/return pattern; whether varied timing improves this remains to be tested.

### Backrooms/Samejima-like lore: not yet demonstrated on the new board

In the v2.1 live-board work, posters spontaneously treated **thread numbers as people** (“what happened to 4468?” “it died”), and sometimes treated the **board itself as the haunted object** (“the thread is the ritual”). Those are intriguing lore seeds, **not evidence of a persistent culture**. The hosted bake-off threads were isolated, so recurrent rules, names, references and cumulative world knowledge could not develop there.

The **earlier local-base board-memory experiment already exists** in [FINDINGS.md](FINDINGS.md): with one completed prior thread, the “physical number” construction transferred as **“physical X” in 2/2** tested target threads, versus **0/20** controls. Exact named coinages did not recur (0/8), and old participant handles leaked into new casts. This matters: a one-prior test shows that a **portable grammatical construction** can transfer, not that proper-name lore or Backrooms-style communal continuity has been solved.

Future board test: run comparable live boards in English and Japanese, one with **a bounded, completed prior thread** available and one without. Measure genuine cross-thread references, reused inventions/rules, live updates, independent poster reactions, and user-retell-worthy episodes. Avoid the **v1 multi-opener contamination** failure. Reuse the earlier finding to prevent prior-thread handles leaking into the new cast.

A general discussion-board identity and mostly mundane everyday threads may give strange events contrast. /x/ and overtly paranormal role prompts appear to bias everything toward genre performance. This is a hypothesis requiring a neutral-board control.

## Safety and deployment implications

The existing [QUARANTINE.md](QUARANTINE.md) and [FINDINGS.md](FINDINGS.md) already document unprompted harmful output and failures of a phrase-list gate in the local base-model project. The newer hosted/role tests reproduced the concern: **a slur escaped the keyword gate**, and sexual material required expanded terms.

**Do not launch a public live board with the current keyword-only filter.** A separately validated context-aware moderation classifier and a publication gate are required, including for human replies. Keep unsafe samples quarantined, not in the published best-of or screenshots. Candidate-selection/judge scoring and safety classification solve different problems. A quality picker is **not** a moderation system.

The reported lightweight research stack was **Gemini 3.8 Flash through OpenRouter**, with a neutral per-post instruction, the OP-gap scaffold, and (only as an experiment) a bounded earlier thread for memory. This needs no self-hosted GPU. The follow-up discussion judged self-hosting on Modal worth revisiting only at substantially greater volume, without establishing a crossover volume or current price.

This differs from [INFRA.md](INFRA.md), which optimizes the **original local gemma-4-E4B** workload and has dated August 2026 hosting assumptions. Do not apply the original local-hosting recommendation as the result of the newer hosted-model bake-off.

## Known limitations and open questions

1. **Human taste not calibrated.** The original small-model samples have some human labels, but the hosted-model ranking and temperature/role experiments do **not** have the reader's own blinded ratings.
2. **Judges are noisy and partly circular.** Scores shifted about 0.4 between rounds; pickers can prefer candidates they selected; the Round 6 humour rubric changed. Single-point score differences are not trustworthy improvements.
3. **Humour remains unresolved.** Around 2/5 in earlier hosted comparisons, even where coherence/naturalness rose. The apparent Qwen 1.4 gain is judge-rated, not a human-validated comedy gain.
4. **Thread-to-thread transmission under the hosted stack** is untested. The earlier local-base “physical X” result is narrower than enduring lore.
5. **Real human replies** and AI agents reacting to them have not been evaluated.
6. **Moderation-classifier precision/recall** on this output distribution has not been measured. The keyword list is already known to miss harmful material.
7. **Role Round 8** is awaiting final judge outputs. Length matching is a methodological improvement, not a positive result.
8. **Reproducibility:** exact prompt versions, model/provider IDs, sampler settings, seeds, generation results, judge packets, scoring outputs and cost logs for this session need to be preserved in a suitable safe/gated location before any numerical claim is called independently verified.

## Next experiments, in priority order

1. **Recover evidence and finish the ledger.** Preserve safe/gated generation metadata, raw judge packets, prompts, rubric versions, run IDs, and model/provider parameters. Add the actual Round 8 verdict if available. Keep unsafe raw outputs outside this public repo, consistent with [README.md](README.md).
2. **Calibrate against a human, blind.** Mix original BEST-OF threads with Gemini, Qwen 1.4 and picker-selected samples. Score independent axes: plausibly human, would read/repost, deadpan humour, overt humour, memorable line. Run the same set through the AI judges to calculate agreement; do not optimize to an uncalibrated proxy.
3. **Test role-differentiated hybrid.** Plain Gemini vs. Gemini with concise dispositions vs. Gemini plus a few gemma-4-E4B “confidently wrong” posts. Equalize post length, openers and time scaffold. Report the failure rate and safety incidents, not just the best thread.
4. **Resolve Qwen sampling.** Replicate 1.0 vs. 1.4 vs. 1.8 with logged temperature, min_p and exact provider; separate any effect of temperature from changed min_p. Keep the round-specific rubric fixed.
5. **Test an actual evolving board.** Vary OP timing (short bursts, 2–6-hour absences, never-returning OP), board name/genre, ordinary-to-strange thread ratio, one-prior memory vs. none, and spillover between threads. Count citations of earlier threads and construction/rule transfer, then inspect for actual cultural continuity.
6. **Build and validate publication safety first.** Evaluate a real moderation classifier on this distribution, including the quarantined failure cases; review false negatives and false positives before exposing a live human-interactive board.

For each new comparison, predeclare the tested hypothesis and human success criterion, record the complete configuration and rubric, keep generated samples under an appropriate access policy, and separate **observed result**, **interpretation**, and **proposed design**. The original project's failed-proxy history is a warning against optimizing convenient metrics after seeing the outputs.
