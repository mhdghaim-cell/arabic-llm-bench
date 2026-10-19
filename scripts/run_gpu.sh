#!/bin/bash
# miqyas · front-desk test v1 — model-quality runs on a rented Linux GPU (e.g. RunPod RTX 4090).
#
# One command does everything: builds llama.cpp with CUDA, downloads the models,
# runs each configuration, scores it. Resumable — just run it again.
#
#   cd ~/miqyas && setsid nohup bash scripts/run_gpu.sh > gpu_run.log 2>&1 < /dev/null &
#   tail -f gpu_run.log            (Control-C stops watching, not the run)
#
# Optional: bash scripts/run_gpu.sh 7b    -> only one configuration (7b | 3.7b | qwen | 0.9b)
set -u
cd "$(dirname "$0")/.."
# Only one copy may run at a time: two copies share one server and corrupt each other's results.
exec 9> /tmp/run_gpu.lock
if ! flock -n 9; then echo "Another run_gpu.sh is already running — not starting a second one."; exit 1; fi
ROOT=$(pwd)
LLAMA="$HOME/llama.cpp/build/bin/llama-server"

# ---------- one-time setup ----------
if [ ! -x "$LLAMA" ]; then
  echo "== building llama.cpp with CUDA (about 10 minutes) =="
  pip install -q -U cmake huggingface_hub
  command -v git >/dev/null || (apt-get update -q && apt-get install -y -q git)
  [ -d "$HOME/llama.cpp" ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp "$HOME/llama.cpp"
  cd "$HOME/llama.cpp"
  cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=native \
    || { echo "cmake configure failed"; exit 1; }
  cmake --build build -j 16 --target llama-server || { echo "build failed"; exit 1; }
  cd "$ROOT"
fi
command -v hf >/dev/null || pip install -q -U huggingface_hub
"$LLAMA" --version
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

mkdir -p models/gpu results/frontdesk

#        key    label                    hf repo                 file                       mode  efforts
CONFIGS=(
  "7b    jais3-7b-q4-gpu-v1     IFM/Jais-3-7B-GGUF     Jais-3-7B-Q4_K_M.gguf     jais  low,high"
  "3.7b  jais3-3.7b-q4-gpu-v1   IFM/Jais-3-3.7B-GGUF   Jais-3-3.7B-Q4_K_M.gguf   jais  low,high"
  "qwen  qwen3-4b-q4-gpu-v1     Qwen/Qwen3-4B-GGUF     Qwen3-4B-Q4_K_M.gguf      chat  off,on"
  "0.9b  jais3-0.9b-q8-gpu-v1   IFM/Jais-3-0.9B-GGUF   Jais-3-0.9B-Q8_0.gguf     jais  low,high"
)

for row in "${CONFIGS[@]}"; do
  read -r key label repo file mode efforts <<< "$row"
  if [ $# -gt 0 ] && [ "$1" != "$key" ]; then continue; fi
  echo; echo "==================== $label ===================="
  [ -f "models/gpu/$file" ] || hf download "$repo" "$file" --local-dir models/gpu || { echo "download failed: $repo/$file"; continue; }

  pkill -f llama-server; sleep 2
  "$LLAMA" -m "models/gpu/$file" --jinja -ngl 99 -c 8192 --port 8080 > "/tmp/server_$key.log" 2>&1 &
  for i in $(seq 1 120); do curl -s localhost:8080/health | grep -q ok && break; sleep 2; done
  if ! curl -s localhost:8080/health | grep -q ok; then
    echo "server did not start for $label — last log lines:"; tail -15 "/tmp/server_$key.log"; continue
  fi
  echo "server ready: $file"

  python3 scripts/run_frontdesk.py --label "$label" --mode "$mode" --efforts ${efforts//,/ } --reps 3
  python3 scripts/score_frontdesk.py "results/frontdesk/$label" | tee "results/frontdesk/$label/scorecard.txt"
done
pkill -f llama-server
echo; echo "ALL DONE. Scorecards: results/frontdesk/*-gpu-v1/scorecard.txt"
