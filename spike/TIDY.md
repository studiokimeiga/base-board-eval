# Round 11: plain Gemini, tidied

**Written before any round 11 thread was generated.**

The owner chose plain Gemini over post-type scaffolding in round 10 ([MOVES.md](MOVES.md)). They had two
complaints about it:

1. Posters address each other by name even when replying to the post directly above. People are lazy
   and know who they're answering.
2. "dumbass" keeps coming back. Measured, it's one poster's catchphrase (stefan, in the group-chat
   thread): the identical prompt at post 2 seeds it, and every later post by him echoes it.

The owner likes the prompt, so neither fix touches it. `tidy11` is `gemini9neutral` (neutral header,
round 9 gate) with [tidy.py](tidy.py) applied to each post before it enters the context:

- **Catchphrase re-roll.** If a post would use an insult its poster has already used twice in the
  thread, write the post again, at most twice.
- **Name strip.** If the post addresses the poster directly above by name ("ines, …", "marcus how do
  you…", "what does it say javier"), drop the name. A name that does work in the sentence stays:
  "stefan is right", "ask stefan", "why did you cut off paloma". Threads whose opener says "my name"
  are skipped, because there the names are the joke.

Every change is logged with the text before it, to `spike/remote/r10/tidy-tidy11.jsonl` (private).

**Dry run** on 805 existing plain-Gemini posts (five runs, "my name" opener excluded):

- 13 posts would have changed, every one of them a real form of address.
- An earlier, looser draft stripped "dmitri just joined." and "why did you cut off paloma", which
  are subject and object, not address. That draft was tightened before this one.
- 2 posts would have been re-rolled, both stefan's "dumbass".

**Predictions** for 8 threads against round 10's fresh plain rep (same openers, same scaffold):

1. Addressing the poster directly above by name drops from about 5% of posts toward 1%. Stripping
   names early also gives later posts fewer names to copy.
2. No poster uses the same insult more than twice in a thread.
3. Nothing reads broken where a name was taken out. Claude reads every logged change before the
   owner sees anything.

Cost: about $0.30.

```
BAKEOFF_OUT=spike/remote/r10 py -3.12 spike/round3.py tidy11
```
