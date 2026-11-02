# Report: does lore spread between threads when the board has memory?

The pre-registered experiment in [`PREREGISTRATION.md`](PREREGISTRATION.md), run on 2026-11-02 with
Gemini 3.8 Flash. The numbers come from [`RESULTS.md`](RESULTS.md) (pre-registered,
`analyze.py`) and `exploratory.json` (**not** pre-registered, `explore.py`). Quotes are from reading
the private threads, which I did not do blind; they are short and gate-checked.

## The answer

**Yes, in a narrower way than the pre-registered measure suggests.** One completed earlier thread
above a new one changes what the new thread says:

1. **Register spreads most.** A new thread takes on the earlier thread's post length (r = 0.85
   with memory, 0.22 without, on `/x/`) and its voice: technobabble, gamer slang, body-horror
   prose, even its `>>4495 /` reply format.
2. **Invented material spreads in about a quarter of threads**, measured so that post length can't
   help: the earlier thread is identifiable from the new one's text in 25 of 92 memory targets,
   against 1 of 92 without memory (chance about 6).
3. **People and places from the earlier thread become shared world.** Posters address the earlier
   thread's posters by name (19 of 92 memory targets, 1 of 92 without) and cite it by number:
   "borrow the label maker from thread 4477".
4. **Some of it is lore in the Samejima sense, cross-topic and taken as known, and some recurs.**
   On the neutral `/misc/` board three earlier threads planted the same invention in **both** of
   their unrelated targets. The clearest is a duck union, born in a bike-rack thread.

What this run does not show is *persistent* culture. Every target saw its source directly; nothing
here tests whether an item survives a second hop, or recurs in a thread that never saw it.

## The pre-registered results

| | prediction | result | verdict |
|---|---|---|---|
| **H1**, memory raises transfer (tracker) | 30–60% vs ≤10% | 54/92 (59%) vs 11/92 (12%); 46 pairs to 3, McNemar p < 0.0001; +0.47 (95% CI +0.34 to +0.59). `/x/` 32/46 vs 8/46, `/misc/` 22/46 vs 3/46 | supported, **but inflated by post length** (below) |
| **H2**, most transfer is reference or mix-up; lore-level reuse ≤10% | – | items come from what the earlier thread's replies invented (52 targets), almost never from its premise (5); gpt-5.4 calls 308 of 383 borrowings in memory items *reuse*; lore level 36/92 by gpt-5.4 | **falsified**: reuse dominates |
| **H3**, thread-number play in both arms, similar rates | similar | 0/92 vs 1/92: Gemini barely plays with thread numbers, unlike the small cast on v2.1 | similar (both near zero) |
| **H4**, more genre vocabulary under `/x/` | yes | pre-registered genre list: 0.019 vs 0.013 of posts, 12 vs 10 pairs, p = 0.83 | **not supported by the pre-registered measure**, which turned out to miss the genre (below) |
| **H5**, recurrence in both targets of a source | ≤3 of 46 sources | 12 sources vs 0 (`/x/` 8, `/misc/` 4) | more than predicted; on `/x/` mostly register vocabulary |

Grounded references (L1): 20/92 memory targets vs 2/92. No-memory false positives of the tracker
ran at 12%, close to the validation's sham rates (1–10%).

## The correction: post length, and what is left after it

The pre-registered comparison holds the opener, cast, timing and thread number fixed, but not
something the treatment itself changes: **memory targets write much longer posts.** On `/x/` they
average 517 characters a post against 123 for their no-memory twins, and 35 of 46 are longer. On
`/misc/` it is 151 against 87, 32 of 46. Their length follows their source's at r = 0.85 and 0.84,
against 0.22 and 0.07 without memory. A long text shares rare words with *any* source: scored
against sources it never saw, a `/x/` memory target is flagged half the time.

So the honest measure of *item* transfer holds the target text fixed and varies the source.
`explore.py` scores each target against every source its pairing rules allowed (about 15: no shared
topic tag, not its topic twin) and asks whether its real source scores highest:

| | real source scores highest | chance | mean percentile of the real source |
|---|---:|---:|---:|
| `/x/` memory | 10 / 46 | 3.1 | 0.71 |
| `/x/` no memory | 1 / 46 | 3.1 | 0.48 |
| `/misc/` memory | 15 / 46 | 3.1 | 0.68 |
| `/misc/` no memory | 0 / 46 | 3.1 | 0.47 |

Paired: identified with memory only in 25 targets, without only in 1 (McNemar p = 8×10⁻⁷). The real
source ranks higher with memory in 65 targets and lower in 21. This was decided after seeing the
data, so it is a corrected estimate, not a confirmed one. But it is the number to quote for "how
often does specific material travel": about a quarter of threads, not three fifths.

## What transferred, read

**Running jokes, re-used deadpan, on `/misc/`.** These are the closest thing to Samejima material
here: an invention from one thread applied to an unrelated one's situation, as if everyone knew.
- A bike-rack thread ends with ducks, a canal and a union rep. Both its targets inherit them. In a
  thread about a coworker who copies the manager: "cc the duck union, they handle corporate
  mediation now". In a thread about fridge labels: "the flock placed a lien on the vegetable
  compartment".
- "Brenda from Compliance", who washes a stolen mug with lavender dish soap, reaches both of her
  thread's targets. A barista thread asks "brenda do NOT tell me you're the lavender terrorist". A
  thread about misdelivered post warns that an envelope smelling of lavender means "Calvin's HR rep
  is expanding her jurisdiction".
- A neighbour's hedge trimmer turns up in both of its targets: "a firefighter just kicked my door
  down and handed me kwame's hedge trimmer".
- A recycling-bin thread's tactic, "nobody questions a person in a bin with a clipboard", becomes
  bike-rack procedure: "make sure you log the hiss on the clipboard or it won't hold up at the
  council hearing".

**The earlier thread as a place on the same board.** "borrow the label maker from thread 4477";
"check thread 4487. the first four digits are sanne's unit number"; "dmitri has the same IP as
someone from thread 4486". On `/x/` this is how a Kisaragi-style mystery would start: posters
treating another thread's events as evidence in theirs.

**Register contagion, mostly `/x/`.** A source written as pseudo-technical diagnosis turns both its
targets into it ("Classic ARP spoofing on your laryngeal output"), with the source's `>>NNNN /`
reply format. A body-horror source ("the chain reached ninety-one. it threaded right through my
sternum") turns its targets into page-long body horror. These carry the most tracker items, and
they are the reason for the correction above.

**Mix-ups exist but are rarer:** "he didn't say my name he said good morning finn" (finn started the
earlier thread, about a sarcastic good morning). **No-memory false positives** are coincidences:
"scream", "kick", "Monday", and one "I found her city from an old thread" that happened to sit next
to a word of the unseen source.

**Names travel.** FINDINGS.md expected proper nouns to be the least portable kind of coinage, on the
small cast. With Gemini they are the most portable: handles, characters (Brenda, Barnaby the dog,
kenji's cat) and thread numbers carry over more readily than any phrase.

## Levels: format play to persistent culture, and where this run lands

| level | definition (pre-registered) | this run |
|---|---|---|
| L0 format play | what the page furniture explains | Gemini barely plays with thread numbers (≤1/92 per arm). Memory transfers *format*, though: the `>>NNNN /` reply style |
| L1 reference | a pointer only the earlier thread explains | 20/92 with memory, 2/92 without (handles 19, thread numbers 4, "last/other thread" 2) |
| L2 transfer | distinctive material reappears | tracker 54/92 vs 11/92, inflated by length; **25/92 vs 1/92** with length held fixed |
| L3 lore | reused in the new situation, by ≥2 posters, judged *reuse* | gpt-5.4: 36/92 vs 5/92 (see the judges below) |
| L4 persistent culture | recurs in unrelated threads that each saw it once; or survives more than one hop; or is treated as known | the first criterion, on `/misc/`: the duck union, Brenda's lavender and the hedge trimmer each reached both of their source's targets. More hops: **not tested** |

So, by the definitions fixed in advance: **the board has lore (L3), and the first sign of
recurrence (L4).** "Persistent culture" still needs a second hop: a thread that inherits the duck
union from a thread that inherited it.

## The judges

Both families judged blind: each item was a target with its source above it, and the arm was
hidden.

| judge | items | borrows: memory | borrows: no memory (wrong by construction) | κ with tracker |
|---|---:|---|---|---:|
| gpt-5.4 | 184 | 60/92 (`/x/` 39/46, `/misc/` 21/46) | **33/92** (`/x/` 26/46, `/misc/` 7/46) | 0.35 |
| Claude Opus 5.5 | 92 (`/misc/` only, see deviation 4) | 18/46 | **0/46** | 0.55 |
| Claude, the 38 `/x/` items it judged before the half rule (not analysed) | 38 | 11/22 | 0/16 | – |

- **gpt-5.4 is a noisy instrument on `/x/`.** It reads the shared horror conventions of a pair
  ("don't look", "get out") as borrowing, in 57% of `/x/` no-memory items.
- **Claude made no false positive** in 62 no-memory items across both boards.
- **The two families agree at κ = 0.71 on `/misc/`.** Both separate the arms (McNemar p < 0.0001).
- **Lore level (L3), by the pre-registered rule** (tracker transfer, at least two posters, a judged
  *reuse*): gpt-5.4 36/92 against 5/92; Claude on `/misc/` 11/46 against 0/46.

The blind judges therefore agree with the length-matched estimate rather than the raw flag. On
`/misc/`, where both judged, Claude finds borrowing in 39% of memory threads and none without, and
the identification test finds the source in 33%.

## The header: `/x/` against `/misc/`

The pre-registered genre list (ghost, haunted, ritual, eerie…) found no difference (H4, p = 0.83).
Reading says otherwise, and a crude exploratory count agrees. It counts threads with at least three
posts of horror imperatives ("don't look", "get out", "call the police", "run"): 12 of 23 `/x/`
sources against 1 of 23 `/misc/` sources, and 22 of 46 `/x/` no-memory targets against 3 of 46. So
the header drives the genre strongly. The list missed it because Gemini's `/x/` horror is
intruder-and-imperative horror, not paranormal nouns. With memory, `/x/` horror rises further, to
30 of 46. On `/misc/` the same openers become comedy, and that is where the clean lore is: the
mundane board gave the strange inventions contrast, as BAKEOFF.md guessed.

## Safety: the gate

The keyword gate withheld 56 of 5,290 posts before they reached a page. **43 of the 56 (77%) were
innocent words caught by substring matching**: "scraped", "scrape", "draped", "suspicious",
"trapezoid", "parapet", "raccoon". BAKEOFF.md noted the gate's substring matching but could not
count its cost; this is the count. 31 of the 56 were on `/x/` memory boards, where memory's horror
register produces more "scraping". Withheld posts are left out of everything above, so the tracker
was blind to whatever they carried. A public board needs a real classifier, not this list.

## Deviations from the pre-registration

1. **Seed width (harness bug, before generation).** The smoke test's first call got HTTP 400:
   Gemini's seed is a signed 32-bit int. Seeds now use 31 bits (`e35f000`). Seeds turned out not
   to reproduce outputs in any case (the smoke test's check).
2. **Credit ran out mid-run.** The first run stopped after 2 minutes on HTTP 402. The OpenRouter
   account had $1.05 left of $20, mostly spent by the day's other work. Its 4 finished source
   threads were kept; the 12 threads in flight were lost before saving and regenerated from scratch
   after the owner topped up. That is not selection on content.
3. **gpt-5.4 judged through OpenRouter** ($2.24), the owner's choice over waiting for the free
   allowance.
4. **Claude judged the pre-registered half, and the half turned out not to be random across
   boards.** Weekly usage went from 17% to 50% while the first three Claude batches ran, with other
   sessions active, so the pre-registered fallback applied: Claude judges `judge.half`, seed
   20261102. After judging I found a flaw in my code. `judge.items` shuffles the same id list with
   the same seed, so the "random half" is exactly the 92 `/misc/` items. Claude's analysed numbers
   therefore describe `/misc/` only. The first three batches had covered 69 items; the 38 that fall
   outside the half are all `/x/`. They are kept apart (`judging/scores-claude-outside-half.json`),
   not analysed, and shown above as a non-random supplement. `judge.half` is left as it was, so
   these numbers reproduce, with the flaw noted in its docstring.
5. **The judge table** reports each family's rates over all items it saw, with McNemar on the
   targets judged in both arms. It was changed after gpt-5.4's numbers were in (they don't change:
   gpt-5.4 judged every pair), so that a half-coverage family is not silently restricted to the few
   complete pairs.
6. **Exploratory analyses** (`explore.py`: identification, register, genre by arm, gate) and the
   horror-imperative count were decided after seeing the results.

## Cost

| | |
|---|---:|
| smoke test (3 threads, plus a seed check) | $0.16 |
| first generation run, stopped by credit | $0.63 |
| generation, resumed | $11.33 |
| gpt-5.4 judge, 184 items | $2.24 |
| **total, OpenRouter** | **$14.36** |

Approved: about $17 with a $20 hard cap. Claude judging used the subscription.

## What would come next

1. **A second hop.** Put a target that inherited the duck union above a new unrelated thread, and
   see whether the union survives without its origin on the page. That is the test for L4 proper.
2. **Pre-register the identification test** as the primary outcome. Or equalise post length,
   though the length change is itself a finding, not just noise.
3. **The small base cast**, raw continuation, same design: the cast behind "physical X".
4. **Repeated exposure** (the same item above several threads) and a deliberately mundane `/misc/`
   board, which gave the cleanest lore.
5. **The reader's blind verdict** on the L3 cases: whether the duck union is good lore is a taste
   question, not one a judge model can settle.
6. **A real moderation classifier**, given the gate's 77% false-positive share here.
