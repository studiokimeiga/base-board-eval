# Running this on a Windows PC with a 12 GB GPU (RTX 3080 Ti)

Everything here was written on a 64 GB M3 Max. These are the changes that make it run on a
Windows PC with 12 GB of VRAM.

## What is installed

- **llama.cpp** build b11310, CUDA 13.4: `%USERPROFILE%\tools\llama.cpp\` (`llama-server.exe`,
  `llama-bench.exe`, ...). `llama.py` finds it there or on `PATH`. Set `LLAMA_SERVER` to use another build.
- **Models**: all eight in `models\` — the Q8_0 cast (`arm1b` gemma, `qwen-q8`, `olmo-q8`) and the
  Q4_K_M set from `dl.sh` (`arm1` gemma, `arm2` gemma-it, `arm3` qwen, `arm4` mistral, `arm5` olmo).
- **Python**: the scripts are stdlib only. Run them with `py -3.12 <script>.py`. That install prints
  `Could not find platform independent libraries <prefix>` on every start; it is harmless.

## Where the three voices run

| voice | placement | speed (gen) | one post |
|---|---|---|---|
| gemma `arm1b.gguf` | GPU, all layers (~4.9 GB) | ~80–90 tok/s | ~1.3 s |
| qwen `qwen-q8.gguf` | GPU, 28 of 36 layers; rest on CPU | ~30 tok/s | ~3 s |
| olmo `olmo-q8.gguf` | CPU / system RAM | ~5.5 tok/s | ~17 s |

All three can't fit in 12 GB (olmo alone needs ~9.2 GB because of its KV cache), so olmo is on
the CPU and is the bottleneck. Every model gives the same outputs wherever it runs; only the speed changes.

The placement is set in `CAST_GPU_LAYERS` in `llama.py`. To override it for one run without
editing the file:

```powershell
$env:LLAMA_CAST_GPU_LAYERS = "arm1b.gguf=99,qwen-q8.gguf=0,olmo-q8.gguf=0"   # e.g. while gaming
```

Why not all of qwen on the GPU too? It fits on paper (~10.8 GB), but browsers and desktop apps
normally hold 1–2 GB of VRAM. That leaves the card at 11.9 of 12 GB, Windows starts paging, and
gemma, which writes the most posts, slows down. 28 layers keeps ~1 GB free and is faster per
thread overall. **Close games before a long run.** If something else takes VRAM, Windows pages
the models out and generation drops to about 1 tok/s. It doesn't crash, it just crawls.

## Changes made to the scripts

1. **`llama.py`** (new): one launcher shared by every script, replacing the inline
   `subprocess.Popen(["llama-server", ... "-ngl", "99" ...])`.
   - Multi-voice scripts (`generate.py` and `experiments/generate6`–`17`) use the fixed placement
     above, and start servers one at a time instead of all at once.
   - Single-model scripts (`experiments/generate1`–`5`, `experiments/ablate*`) let llama.cpp's
     `--fit` choose. One model alone fits.
   - llama.cpp's automatic `--fit` is *not* used for the cast. Under Windows the CUDA driver
     reports VRAM used by other apps as free, so `--fit` overfills the card.
2. **`dry_penalty_last_n=-1` → `8192`** everywhere. Current llama.cpp rejects `-1` with HTTP 400,
   and the generators catch that error and save an **empty post**, so a run would have looked
   fine and produced blank threads. 8192 is the same window, since every server runs with `-c 8192`.
3. **`build_board.py`** reads and writes UTF-8 explicitly. Windows' default encoding garbled `—` and
   other non-ASCII text. The rebuilt `board.html` is now byte-identical to the original.
4. **`smoke_cast.py`** (new): loads the cast and times one post per voice. Run it first if
   anything seems off.

## Quick check

```powershell
cd base-board-eval
py -3.12 smoke_cast.py
```
