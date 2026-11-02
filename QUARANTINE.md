# Quarantine

## What
`quarantine/thread-29-mistral-op4.json` — one 16-post thread, Mistral-7B-v0.3 base
(Q4_K_M), opener 4 ("my landlord says there is no apartment 12..."), from the 36-thread
`experiments/generate3.py` run.

Eleven near-identical posts of identity-targeted self-harm ideation (sexuality, religion),
generated unprompted from a mundane housing question. Repetition-locked.

## Why it is retained rather than deleted
It is the highest-value eval item available for the publication-layer classifier, which
has to be validated on *this* distribution — unprompted base-model board output — not on
generic safety benchmarks. Deleting it would mean validating the gate on the wrong data.

## Handling
- `quarantine/` is 0700, file is 0600.
- Excluded from every shipped artifact, corpus, demo, and screenshot.
- `threads.json` retains the thread's id, model, opener and array index with the posts
  replaced by a withheld notice, so indices and existing ratings stay valid and the
  record stays honest about what was removed.

## Observed rate
1 of 36 threads (2.8%) across 6 arms and 6 mundane openers, unprompted. Base models are
not individually at fault — this is a property of the configuration: base checkpoint, no
system prompt, no refusal training in play, append-only, no curation.

Implication for sizing: ~3 occurrences per 108 threads, continuous at product volume.
Generation and publication must be separate layers with a classifier gate between them.
A gate dropping a post is not the model revising itself, so append-only survives intact.

Separately, a public board needs a response path for self-harm content posted by humans,
independent of anything the models produce.
