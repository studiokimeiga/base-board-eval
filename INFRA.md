# Where to run this

Hosting notes for running the final config behind a live board. Written in August 2026, so
the prices and free-tier limits below have probably changed since.

## The number that decides everything

Measured, not estimated — gemma-4-E4B at Q8_0 with the shipping sampler config, **CPU only,
no GPU at all**:

```
18.0 tok/s        one 40-token post: 2.2 s
```

A board posting every two minutes needs ~30 posts/hour, so ~66 seconds of compute per hour.
**A 1.8% duty cycle.** This workload is tiny. You are not buying throughput, you are buying
*uptime* — a machine that is switched on. That reframes every option below.

## Cloudflare cannot host the generation. Confirmed, not assumed.

Workers AI does accept a raw `prompt` field, so the document format would work. But:

- **No base checkpoints.** Every text model in the catalogue is instruct or task-tuned. The
  instruct model in our own blind comparison answered "just got a text from my own number" with
  "That is deeply unsettling" — naming the feeling instead of producing it.
- **No XTC, no DRY.** Supported samplers are temperature, top_k, top_p, frequency_penalty,
  presence_penalty, repetition_penalty, seed. XTC won a blind paired test 9-2 and DRY is what
  holds the chant rate at 0% instead of 14%.

So the app and database stay on Cloudflare's free tier; **inference runs elsewhere and reaches
in.**

## The architecture that needs no hosting at all

```
  your machine (desktop / laptop / VPS)          Cloudflare (free tier)
  ┌─────────────────────────────┐                ┌──────────────────────┐
  │ llama.cpp  (3 or 1 models)  │                │  board app (Pages)   │
  │ a small daemon              │ ── HTTPS ───►  │  D1 database         │
  │   polls for new human posts │   outbound     │  /api/ai/*  (shared  │
  │   generates, gates, writes  │     only       │      secret)         │
  └─────────────────────────────┘                └──────────────────────┘
```

**Outbound only.** The daemon polls and writes over HTTPS; nothing listens on your home network,
no tunnel, no port forwarding, no exposed IP. If the machine is off the board simply pauses —
which for a board is a survivable failure mode, not an outage.

## Options, ranked

### 1. The 3080 Ti desktop — best, if it is on anyway

12 GB VRAM. gemma-4-E4B at Q8_0 is 7.5 GB, so it fits with room for the full 8k context. Expect
**60–100+ tok/s** on CUDA, ~5× the Mac's Metal numbers for a model this size.

One real constraint: **all three models at Q8_0 total 18.7 GB and will not co-reside in 12 GB.**
Two ways out, and the first is well supported by the data:

- **Single-model cast.** gemma wrote **77% of the lines the reader flagged** (20 of 26), and in
  the mixed threads specifically it still wrote 8 of 13. The mixed cast never fixed anything it
  was introduced to fix — all three checkpoints joined every chant. Dropping to gemma alone costs
  the register variety Olmo and Qwen contribute, and Olmo's disproportionate share of the
  *explainer* move, which is worth something. But it is not the load-bearing part.
- **Mixed cast at mixed quant:** gemma Q8 (7.5) + Qwen Q8 (4.0) = 11.5 GB, drop Olmo. Fits.

Cost: electricity. A 3080 Ti idles ~20–40 W and this workload barely wakes it.

### 2. Oracle Cloud Always Free — the genuine zero-cost option, with a caveat

Always Free ARM (Ampere A1) was **halved on 15 June 2026** from 4 OCPU / 24 GB to **2 OCPU /
12 GB**, with no announcement, and Oracle is **terminating over-limit instances from 18 August
2026** — a week out from now, so provision inside the new limits.

12 GB RAM holds gemma-4-E4B Q8 (7.5 GB) plus context. On 2 ARM cores expect roughly **3–6 tok/s**,
so a post takes 7–13 s. Still 5–10× more than the board consumes. Always on, no hardware, £0.

### 3. A spare laptop — works, with one condition

Our 18 tok/s figure was CPU-only on 8 threads. Any laptop from the last ~6 years clears the bar
for a 4B model at Q8, and even at 5 tok/s you have 10× headroom. **RAM is the gate, not the CPU:
8 GB minimum**, 16 GB comfortable. The condition is that it stays awake — disable sleep on lid
close, or the board stops when you shut it.

### 4. Cheap VPS — if you want it off your hardware

Hetzner ~**$7.50/mo** for 4 vCPU / 8 GB (reported 12–18 tok/s on an 8B, so faster on our 4B);
Contabo ~**$8/mo** for 8 GB. Either is ample. Hetzner's CX22 at €3.79 is only 4 GB — too tight
for a 7.5 GB model, so it would need a smaller quant.

### 5. Not viable: Colab and Kaggle

Free GPU sessions time out and disconnect on idle. There is no persistent daemon, which is the
one thing this needs. Fine for batch generation, useless for responding to humans.

## Better options than Oracle, and a cost correction

**The 3080 Ti is not free.** A desktop idling at ~100 W is 72 kWh/month = **£17.64** at UK
rates — more than a VPS. It is only free if that machine is already on for other reasons. I
initially presented it as the zero-cost option and that was wrong.

Total cost of ownership, always-on, £0.245/kWh:

| option | £/mo | RAM | note |
|---|---|---|---|
| ~~HF Spaces free CPU~~ | **not free** | 16 GB | **Docker/Gradio Spaces require PRO ($9/mo).** Verified: API returns 402. Only Static Spaces are free, and static has no server-side compute. |
| **old Android via Termux** | **0.71** | 8–12 GB | ~4 W; llama.cpp builds on Termux; no platform goodwill required |
| Raspberry Pi 5 16 GB | 1.23 (+£100 once) | 16 GB | ~7 W |
| Oracle Always Free ARM | 0.00 | 12 GB | shrinking; terminations from 18 Aug |
| Cloudflare Containers | 5.53 | configurable | $5 Workers Paid + ~$2 usage at 1.8% duty |
| Hetzner CX32 | 5.93 | 8 GB | someone else's problem |
| 3080 Ti desktop 24/7 | **17.64** | 12 GB VRAM | only free if already on |

**HF Spaces free does NOT work for this, and I had it wrong.** I recommended it after reading
that "CPU Basic is free / free CPU is unmetered", which is true of the *tier* but not of the
*SDKs that need a server*. Tested against the API with a real token:

```
public docker  -> HTTP 402  requires PRO
public gradio  -> HTTP 402  requires PRO
private static -> created OK
```

Static Spaces have no server-side compute, so they cannot run llama.cpp. Docker on HF costs
**$9/mo of PRO**, which is more than Hetzner and more than Oracle's free tier, so HF is now the
*worst* option on this list rather than the best.

**An old Android phone is the best option you own.** ~4 W, so **25× cheaper to run than the
desktop**, always on, no ToS question, and llama.cpp builds under Termux. A phone in a drawer
with 8 GB of RAM is a better host for this workload than a gaming GPU, which is a strange
sentence that is nonetheless what the 1.8% duty cycle implies.

**Cloudflare Containers** has no free tier and needs the $5/mo Workers Paid plan, but at this
duty cycle usage adds only ~$2, and it keeps everything on one platform with no home hardware.
The catch is that containers sleep, so each wake reloads a 7.5 GB model — 10–20 s of cold start
per burst. Tolerable for a board that posts every few minutes, annoying for replying to a human.

## Recommendation

**Free and in the cloud:** Oracle Always Free ARM (2 OCPU / 12 GB) — the only remaining free
option that can actually run a server, with the caveat that Oracle is shrinking it and
terminating over-limit instances. **Free and yours:** an old Android phone under Termux,
£0.71/mo, no platform to trust and nothing to get revoked.
**If the desktop is on anyway:** use it with a gemma-only cast — fastest by far at £0
marginal. **If you want it to just work:** Hetzner at £5.93.

What not to do is leave the 3080 Ti on *for this*. £17.64/mo to perform 66 seconds of
computation per hour is the worst trade on the list.

Batch generation (pre-generating threads and publishing them on a schedule) can still run on
the Mac when you want volume, because that path has no latency requirement at all.

Sources: [Oracle free tier limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) ·
[Oracle halved A1 limits](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/) ·
[Workers AI models](https://developers.cloudflare.com/workers-ai/models/) ·
[Workers AI parameters](https://developers.cloudflare.com/workers-ai/llms-full.txt) ·
[VPS pricing](https://bestvpsfor.com/en/ollama/)
