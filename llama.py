"""Shared llama-server launcher.

The scripts were written on a 64 GB M3 Max and passed `-ngl 99` (every layer on the GPU). On
the 12 GB RTX 3080 Ti the three-voice cast cannot all live in VRAM, so placement is explicit.

Measured on the 3080 Ti, -c 8192, a ~1.4k-token thread prompt, shipping sampler config:

    voice   VRAM if fully offloaded   GPU gen     CPU gen     one post, GPU / CPU
    gemma   ~4.9 GB                   ~80-90 t/s  ~8 t/s      1.3 s / 11 s
    qwen    ~5.2 GB                   ~100 t/s    ~9 t/s      1.1 s / 11 s
    olmo    ~9.2 GB (big KV cache)    ~67 t/s     ~5.5 t/s    1.9 s / 17 s

gemma + all of qwen on the GPU is ~10.8 GB. With a browser and the usual desktop apps holding
1-2 GB, that puts the card at 11.9 of 12 GB, and WDDM starts paging: gemma fell to 55-60 t/s and
qwen posts swung from 1.3 s to 4.8 s. qwen at 28 of its 36 layers keeps the card at ~11.2 GB:
gemma holds ~90 t/s and qwen posts a steady ~3 s, the faster thread overall since gemma writes
the most posts. olmo runs on the CPU from system RAM; its speed is memory-bandwidth bound (8,
16 and 24 threads all give ~6.3 t/s), and giving it even 3 GPU layers slowed the other two.

Why not llama.cpp's automatic `--fit`? Under Windows WDDM the CUDA driver reports VRAM used by
other processes (browser, games) as free -- it said 11.1 GB free while 4 GB was in use -- so
--fit overfills the card. Windows then pages model memory to shared RAM and generation drops
to ~1 t/s. Single-model scripts still use --fit (one model alone fits), but the cast servers
get the fixed placement in CAST_GPU_LAYERS.

If you are gaming or otherwise short on VRAM, lower the numbers (layers: gemma 42, qwen 36,
olmo 32), or set LLAMA_CAST_GPU_LAYERS, e.g. "arm1b.gguf=99,qwen-q8.gguf=0,olmo-q8.gguf=0".

Note: newer llama.cpp rejects dry_penalty_last_n=-1 ("whole context") with HTTP 400, so the
scripts pass 8192 -- the same window, since every server here runs with -c 8192.
"""
import os, shutil, subprocess

DEFAULT_WINDOWS_PATH = os.path.expanduser(r"~\tools\llama.cpp\llama-server.exe")

CAST_GPU_LAYERS = {"arm1b.gguf": 99, "qwen-q8.gguf": 28, "olmo-q8.gguf": 0}
if os.environ.get("LLAMA_CAST_GPU_LAYERS"):
    for item in os.environ["LLAMA_CAST_GPU_LAYERS"].split(","):
        name, n = item.split("=")
        CAST_GPU_LAYERS[name.strip()] = int(n)


def server_binary():
    """LLAMA_SERVER env var, then PATH, then the default install location."""
    env = os.environ.get("LLAMA_SERVER")
    if env:
        return env
    found = shutil.which("llama-server")
    if found:
        return found
    if os.path.exists(DEFAULT_WINDOWS_PATH):
        return DEFAULT_WINDOWS_PATH
    raise FileNotFoundError("llama-server not found: install llama.cpp or set LLAMA_SERVER")


def start_server(model_path, port, cast=False, ctx=8192):
    """Launch one llama-server with the settings every script in this repo used.

    cast=True means several servers will share the GPU: use the fixed placement above and
    turn --fit off. Otherwise leave -ngl unset so --fit (on by default) places the model.
    """
    placement = []
    if cast:
        ngl = CAST_GPU_LAYERS.get(os.path.basename(model_path), 0)
        placement = ["-ngl", str(ngl), "-fit", "off"]
    return subprocess.Popen(
        [server_binary(), "-m", model_path, "-c", str(ctx), "--cache-reuse", "256",
         "--port", str(port), "--host", "127.0.0.1", "-np", "1"] + placement,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
