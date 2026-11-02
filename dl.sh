#!/bin/bash
cd "$(dirname "$0")/models"
get(){ curl -sL --retry 2 -o "$2" "$1" && echo "DONE $2 $(du -h "$2"|cut -f1)" || echo "FAIL $2"; }
get "https://huggingface.co/mradermacher/gemma-4-E4B-GGUF/resolve/main/gemma-4-E4B.Q4_K_M.gguf" arm1.gguf &
get "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf" arm2.gguf &
wait
get "https://huggingface.co/mradermacher/Qwen3-4B-Base-GGUF/resolve/main/Qwen3-4B-Base.Q4_K_M.gguf" arm3.gguf &
get "https://huggingface.co/QuantFactory/Mistral-7B-v0.3-GGUF/resolve/main/Mistral-7B-v0.3.Q4_K_M.gguf" arm4.gguf &
get "https://huggingface.co/lmstudio-community/Olmo-3-1025-7B-GGUF/resolve/main/Olmo-3-1025-7B-Q4_K_M.gguf" arm5.gguf &
wait
echo ALLDONE
