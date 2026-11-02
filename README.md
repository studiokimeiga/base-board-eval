# base-board-eval

Can small **base** language models (not instruct or chat models) write imageboard-style threads
that read like real people talking?

This repo has the generators, metrics and write-ups from about 600 generated threads with
4–8B base checkpoints running locally on llama.cpp. Every claim in the write-ups is backed by a
run, and the claims that were wrong are written down too.

## The short version

- **Base, not instruct.** Given "just got a text from my own number", the instruct model replied
  "That is deeply unsettling". It named the feeling instead of producing it. Base models,
  given only the opener, produce it.
- **The prompt is the opener and nothing else.** No system prompt, no example thread, no seeded
  words. Every injected template eventually showed up in the output.
- **Sampling does most of the work.** XTC (threshold 0.05, probability 0.50) plus DRY took the
  "chant" failure (everyone repeating one line) from 14% of threads to 0%.
- **What makes a thread good** is reference instability treated calmly: the thing under
  discussion quietly changes what it is, and nobody is alarmed.

The full config and evidence are in [FINDINGS.md](FINDINGS.md).

## Documents

| file | what it is |
|---|---|
| [FINDINGS.md](FINDINGS.md) | What works, why, and the claims that had to be withdrawn |
| [BEST-OF.md](BEST-OF.md) | Hand-picked threads, with model and config for each |
| [board.html](board.html) | The same picks rendered as a board, built by `build_board.py` |
| [PREREGISTRATION.md](PREREGISTRATION.md) | Outcome measures fixed before reading run 5 |
| [PREDICTIONS.md](PREDICTIONS.md) | Predictions about the human ratings, written before the ratings |
| [QUARANTINE.md](QUARANTINE.md) | The unprompted self-harm output, how often it happened, and what that means for a product |
| [SETUP-PC.md](SETUP-PC.md) | Running the three-model cast on a 12 GB GPU under Windows |
| [experiments/](experiments/README.md) | Every earlier run, with what each one tested |

## Running it

You need [llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server` on `PATH`, or set
`LLAMA_SERVER`) and Python 3. The scripts use only the standard library.

1. **Get the models** into `models/`:
   - The final cast is three Q8_0 GGUFs: gemma-4-E4B base as `arm1b.gguf` (the ggml-org quant;
     the Q4_K_M of this checkpoint is broken), Qwen3-4B-Base as `qwen-q8.gguf`, and
     Olmo-3-1025-7B as `olmo-q8.gguf`.
   - `dl.sh` downloads the Q4_K_M set the early comparison runs used (`arm1`–`arm5`).
2. **Check the cast:** `python smoke_cast.py` loads each model and times one post.
3. **Generate:** `python generate.py` runs the final config and writes `threads.final.json`.
   GPU placement is set in `llama.py` (`CAST_GPU_LAYERS`, or the `LLAMA_CAST_GPU_LAYERS` env var).
4. **Measure:** `python metrics.py threads.final.json` prints the per-arm metrics.
   `drift.py` measures how often other posters take over the OP's situation.

## Generated data is not included

The raw corpora are unfiltered base-model output, and they include slurs, sexual violence and,
in one thread, self-harm content (see [QUARANTINE.md](QUARANTINE.md)). They are kept out of this
repo on purpose. Only the curated threads in `BEST-OF.md` and `board.html` are published.

This includes the rating viewers the write-ups mention (`blind.html`, `xtc.html`, etc.). If you
run the generators yourself, expect the same kind of output. Don't publish it without a
classifier and a human check in between.

## License

[MIT](LICENSE)
