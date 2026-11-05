"""THROWAWAY SPIKE: run live_board.py on a Modal L4 instead of the home PC.

The L4 has 24 GB, so all three voices sit on the GPU at once. Model weights and the
board itself live on Modal Volumes, so a run picks up the board where the last one left off.

  uvx modal run spike/modal_board.py::download             once: weights -> volume (~20 GB)
  uvx modal run --detach spike/modal_board.py::main --hours 2   run; prints the private watch URL
  uvx modal run spike/modal_board.py::fetch            copy board.json back to spike/remote/
  uvx modal run spike/modal_board.py::reset            start the next run on an empty board

The watch URL contains a random key and nothing is served without it.
"""
import json, os, secrets, subprocess, sys, time
import modal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# same weights as models/ locally -- byte sizes match
MODELS = {
    "arm1b.gguf":   ("ggml-org/gemma-4-E4B-GGUF", "gemma-4-E4B-Q8_0.gguf"),
    "qwen-q8.gguf": ("mradermacher/Qwen3-4B-Base-GGUF", "Qwen3-4B-Base.Q8_0.gguf"),
    "olmo-q8.gguf": ("lmstudio-community/Olmo-3-1025-7B-GGUF", "Olmo-3-1025-7B-Q8_0.gguf"),
}
# bake-off only (bakeoff.py); kept under their upstream file names
BIG_MODELS = {
    "gemma-4-31B-Q8_0.gguf": ("ggml-org/gemma-4-31B-GGUF", "gemma-4-31B-Q8_0.gguf"),
    "Meta-Llama-3.1-70B.Q4_K_M.gguf": ("mradermacher/Meta-Llama-3.1-70B-GGUF",
                                       "Meta-Llama-3.1-70B.Q4_K_M.gguf"),
    # Japanese bake-off: Llama 3.3 with Japanese continued pretraining (Institute of Science Tokyo)
    "Llama-3.3-Swallow-70B-v0.4.Q4_K_M.gguf": ("mradermacher/Llama-3.3-Swallow-70B-v0.4-GGUF",
                                               "Llama-3.3-Swallow-70B-v0.4.Q4_K_M.gguf"),
}

app = modal.App("base-board-live")
models_vol = modal.Volume.from_name("base-board-models", create_if_missing=True)
data_vol = modal.Volume.from_name("base-board-data", create_if_missing=True)

# nearest published CUDA build to the b11310 used locally
image = (
    modal.Image.from_registry("ghcr.io/ggml-org/llama.cpp:server-cuda12-b11312", add_python="3.12")
    .entrypoint([])
    .env({"LLAMA_SERVER": "/app/llama-server", "LD_LIBRARY_PATH": "/app",
          "LLAMA_CAST_GPU_LAYERS": "arm1b.gguf=99,qwen-q8.gguf=99,olmo-q8.gguf=99",
          "BOARD_MODELS_DIR": "/models", "BOARD_DATA_DIR": "/data", "BOARD_HOST": "0.0.0.0",
          "PYTHONUNBUFFERED": "1"})
    .add_local_file(os.path.join(ROOT, "llama.py"), "/repo/llama.py")
    .add_local_file(os.path.join(ROOT, "generate.py"), "/repo/generate.py")
    .add_local_file(os.path.join(ROOT, "openers.py"), "/repo/openers.py")
    .add_local_file(os.path.join(HERE, "live_board.py"), "/repo/spike/live_board.py")
    .add_local_file(os.path.join(HERE, "index.html"), "/repo/spike/index.html")
    .add_local_file(os.path.join(HERE, "bakeoff.py"), "/repo/spike/bakeoff.py")
    .add_local_file(os.path.join(HERE, "jp_bakeoff.py"), "/repo/spike/jp_bakeoff.py")
    .add_local_file(os.path.join(HERE, "round3.py"), "/repo/spike/round3.py")
    .add_local_file(os.path.join(ROOT, "experiments", "generate1.py"), "/repo/experiments/generate1.py")
)
dl_image = modal.Image.debian_slim(python_version="3.12").pip_install("huggingface_hub==2.4.0")


@app.function(image=dl_image, volumes={"/models": models_vol}, timeout=2 * 3600)
def download(big: bool = False):
    from huggingface_hub import hf_hub_download
    for name, (repo, fname) in (BIG_MODELS if big else MODELS).items():
        dest = "/models/" + name
        if os.path.exists(dest):
            print("have", name, os.path.getsize(dest)); continue
        p = hf_hub_download(repo, fname, local_dir="/models/.hf")   # same filesystem as dest
        os.replace(p, dest)
        models_vol.commit()
        print("got", name, os.path.getsize(dest))


@app.function(image=image, gpu=["L4", "A10G"],   # A10G when no L4 is free
              volumes={"/models": models_vol, "/data": data_vol},
              timeout=24 * 3600)
def run(hours: float = 2.0):
    key = secrets.token_urlsafe(18)
    port = 8765
    with modal.forward(port) as tunnel:
        print("\nWATCH: %s/%s/\n" % (tunnel.url, key), flush=True)
        proc = subprocess.Popen([sys.executable, "/repo/spike/live_board.py", "--hours", str(hours),
                                 "--port", str(port)], env=dict(os.environ, BOARD_KEY=key))
        while proc.poll() is None:
            time.sleep(60)
            data_vol.commit()
    data_vol.commit()


@app.function(image=dl_image, volumes={"/data": data_vol})
def _read():
    p = "/data/board.json"
    return open(p, "rb").read() if os.path.exists(p) else b""


@app.function(image=dl_image, volumes={"/data": data_vol})
def _reset():
    for f in ("board.json", "quarantine.jsonl"):
        if os.path.exists("/data/" + f):
            os.rename("/data/" + f, "/data/%s.%d" % (f, int(time.time())))
    data_vol.commit()


@app.local_entrypoint()
def main(hours: float = 2.0):
    run.remote(hours)


@app.local_entrypoint()
def fetch():
    out = os.path.join(HERE, "remote", "board.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    b = _read.remote()
    open(out, "wb").write(b)
    print("wrote", out, len(b), "bytes")


@app.local_entrypoint()
def reset():
    _reset.remote()
    print("old board kept on the volume with a timestamp suffix; next run starts empty")


# ---- bake-off: three arms, one after another, on one 80 GB card ----
@app.function(image=image, gpu="A100-80GB", volumes={"/models": models_vol, "/data": data_vol},
              timeout=3 * 3600)
def bake(arms: str = "cast,g31,l70"):
    for arm in arms.split(","):
        print("=== arm", arm, flush=True)
        subprocess.run([sys.executable, "/repo/spike/bakeoff.py", "--arm", arm,
                        "--models", "/models", "--out", "/data"], check=False)
        data_vol.commit()


@app.function(image=dl_image, volumes={"/data": data_vol})
def _read_bake():
    out = {}
    for f in os.listdir("/data"):
        if f.startswith("bakeoff-") and f.endswith(".json"):
            out[f] = open("/data/" + f, "rb").read()
    return out


@app.local_entrypoint()
def fetch_bake():
    for name, b in _read_bake.remote().items():
        out = os.path.join(HERE, "remote", name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(b)
        print("wrote", out, len(b), "bytes")


# ---- Japanese bake-off: the self-hosted base models, both page formats ----
@app.function(image=image, gpu="A100-80GB", volumes={"/models": models_vol, "/data": data_vol},
              timeout=3 * 3600)
def jp_bake(arms: str = "swallow70,g31"):
    import urllib.request
    sys.path.insert(0, "/repo"); sys.path.insert(0, "/repo/spike")
    from llama import start_server
    from jp_bakeoff import ARMS
    for arm in arms.split(","):
        proc = start_server("/models/" + ARMS[arm][1], 8300)
        for _ in range(900):
            try:
                if json.load(urllib.request.urlopen("http://127.0.0.1:8300/health", timeout=2)).get("status") == "ok":
                    break
            except Exception:
                time.sleep(1)
        for fmt in ("5ch", "named"):
            print("=== jp", arm, fmt, flush=True)
            subprocess.run([sys.executable, "/repo/spike/jp_bakeoff.py", arm, fmt, "--llama", "8300",
                            "--out", "/data"], check=False)
            data_vol.commit()
        proc.kill(); proc.wait()


@app.function(image=dl_image, volumes={"/data": data_vol})
def _read_jp():
    return {f: open("/data/" + f, "rb").read() for f in os.listdir("/data") if f.startswith("jp-")}


@app.local_entrypoint()
def fetch_jp():
    for name, b in _read_jp.remote().items():
        out = os.path.join(HERE, "remote", name)
        open(out, "wb").write(b)
        print("wrote", out, len(b), "bytes")


# ---- round 7: Gemini cast with small-model "naif" posters (gemma-E4B on the GPU) ----
def _openrouter_secret():
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".env"))
               if "=" in l and not l.lstrip().startswith("#")) if os.path.exists(os.path.join(ROOT, ".env")) else {}
    return modal.Secret.from_dict({"OPENROUTER_API_KEY": env.get("OPENROUTER_API_KEY", "")})


@app.function(image=image, gpu=["L4", "A10G"], volumes={"/models": models_vol, "/data": data_vol},
              timeout=3 * 3600, secrets=[_openrouter_secret()])
def r7(arms: str = "naif,naifroles"):
    import urllib.request
    sys.path.insert(0, "/repo")
    from llama import start_server
    proc = start_server("/models/arm1b.gguf", 8400)
    for _ in range(600):
        try:
            if json.load(urllib.request.urlopen("http://127.0.0.1:8400/health", timeout=2)).get("status") == "ok":
                break
        except Exception:
            time.sleep(1)
    for arm in arms.split(","):
        print("=== r7", arm, flush=True)
        subprocess.run([sys.executable, "/repo/spike/round3.py", arm], check=False,
                       env=dict(os.environ, BAKEOFF_OUT="/data", NAIF_PORT="8400"))
        data_vol.commit()
    proc.kill()
