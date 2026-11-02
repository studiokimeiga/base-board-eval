# Experiment runs

Each script is one run, kept as it was run so the write-ups can be traced back to the code that
produced them. Run them from anywhere: they read `models/` from the repo root and write their
output JSON there. The final config is [`../generate.py`](../generate.py) (run 14).

| script | writes | what it tested |
|---|---|---|
| `generate1.py` | `threads.json` | Blind base-model comparison, one model at a time, append-only |
| `generate2.py` | `threads.json` | v2: named participants instead of "Anonymous" + post numbers |
| `generate3.py` | `threads.json` | v3: 6 openers × 6 threads per arm, across the five Q4_K_M arms |
| `generate4.py` | `threads.warmup.json` | gemma-4-E4B base at Q8_0 alone, 16-post threads |
| `generate5.py` | `threads.run5.json` | Volume run: how often one unassisted base model produces a keeper (142 threads, seeded vs. unseeded openers; see `PREREGISTRATION.md`) |
| `generate6.py` | `threads.long.json` | Mixed three-model cast, 50-post threads |
| `generate7.py` | `threads.upd.json` | 32 posts; OP forced to post at fixed points with a one- or two-word seed |
| `generate8.py` | `threads.iso.json` | Run 6 with only DRY changed, to isolate its effect on chanting |
| `generate9.py` | `threads.dry3.json` | DRY `allowed_length` 3 |
| `generate10.py` | `threads.xtc.json` | XTC on vs. off |
| `generate11.py` | `threads.fmt.json` | Nothing injected into any post: no stems, no seeded words |
| `generate12.py` | `threads.xtc2.json` | XTC on vs. off, repeated |
| `generate13.py` | `threads.sweep.json` | XTC strength sweep |
| `../generate.py` | `threads.final.json` | Run 14, the final config: 69 threads, paired XTC strength and DRY on/off |
| `generate15.py` | `threads.blind.json` | Blind three-arm test: is the older, chantier config more coherent? |
| `generate16.py` | `threads.optag.json` | Marking the thread starter's posts with (OP). Null result |
| `generate17.py` | `threads.memory.json` | Board memory: does a coinage from an earlier thread carry over? Needs earlier runs' output |
| `ablate1.py` | `ablation.json` | What stops distribution drift at 4–7B? |
| `ablate2.py` | `ablation2.json` | Loosest config that clears a drift gate, on Mistral-7B |
| `ablate3.py` | `ablation3.json` | Follow-up to `ablate2.py` |
