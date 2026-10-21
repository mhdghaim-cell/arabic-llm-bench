#!/bin/bash
# miqyas · front-desk v2 — model runs on a rented Linux GPU (RunPod, ≥ 24 GB recommended).
#
# Steps, in order (each is resumable; just run it again):
#   bash scripts/run_gpu_v2.sh setup      # build llama.cpp (CUDA) + download all 4 models + self-tests (~15 min)
#   bash scripts/run_gpu_v2.sh pilot      # DEV episodes only, every model, 1 rep (~30 min) -> check before the test
#   bash scripts/run_gpu_v2.sh test       # the pre-registered TEST run (~10-12 h); or: test 3.7b  (one config)
#   bash scripts/run_gpu_v2.sh repro      # reproducibility re-run of 10 conversations (~10 min)
#
# Long steps: start detached so a closed browser tab can't kill them:
#   setsid nohup bash scripts/run_gpu_v2.sh test > gpu_v2_test.log 2>&1 < /dev/null &
#   tail -f gpu_v2_test.log          (Control-C stops watching, not the run)
set -u
cd "$(dirname "$0")/.."
exec 9> /tmp/run_gpu_v2.lock
if ! flock -n 9; then echo "Another run_gpu_v2.sh is already running — not starting a second one."; exit 1; fi
ROOT=$(pwd)
LLAMA="$HOME/llama.cpp/build/bin/llama-server"
STEP=${1:-}
ONLY=${2:-}

#        key       label                    hf repo                file                       mode  arms              efforts
CONFIGS=(
  "3.7b      jais3-3.7b-q4-v2         IFM/Jais-3-3.7B-GGUF   Jais-3-3.7B-Q4_K_M.gguf    jais  base,table,tool   high"
  "7b        jais3-7b-q4-v2           IFM/Jais-3-7B-GGUF     Jais-3-7B-Q4_K_M.gguf      jais  base,table,tool   high"
  "q4b       qwen3-4b-q4-v2           Qwen/Qwen3-4B-GGUF     Qwen3-4B-Q4_K_M.gguf       chat  base,table,tool   on"
  "q8b       qwen3-8b-q4-v2           Qwen/Qwen3-8B-GGUF     Qwen3-8B-Q4_K_M.gguf       chat  base,table,tool   on"
  "3.7b-low  jais3-3.7b-q4-v2-low     IFM/Jais-3-3.7B-GGUF   Jais-3-3.7B-Q4_K_M.gguf    jais  tool              low"
  "q4b-off   qwen3-4b-q4-v2-off       Qwen/Qwen3-4B-GGUF     Qwen3-4B-Q4_K_M.gguf       chat  tool              off"
)
REPRO_EPS="t02 t06 t11 t13 t15 t20 t23 t29 t38 t41"

start_server () {   # $1 = gguf file, $2 = key
  pkill -f llama-server; sleep 2
  "$LLAMA" -m "models/gpu/$1" --jinja -ngl 99 -c 32768 -np 1 --port 8080 > "/tmp/server_$2.log" 2>&1 &
  for i in $(seq 1 180); do curl -s localhost:8080/health | grep -q '"ok"' && return 0; sleep 2; done
  echo "server did not start for $1 — last log lines:"; tail -15 "/tmp/server_$2.log"; return 1
}

case "$STEP" in
setup)
  if [ ! -x "$LLAMA" ]; then
    echo "== building llama.cpp with CUDA (about 10 minutes) =="
    pip install -q -U cmake huggingface_hub
    command -v git >/dev/null || (apt-get update -q && apt-get install -y -q git)
    [ -d "$HOME/llama.cpp" ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp "$HOME/llama.cpp"
    cd "$HOME/llama.cpp"
    cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=native || exit 1
    cmake --build build -j 16 --target llama-server || exit 1
    cd "$ROOT"
  fi
  command -v hf >/dev/null || pip install -q -U huggingface_hub
  "$LLAMA" --version; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
  mkdir -p models/gpu
  for row in "${CONFIGS[@]}"; do
    read -r key label repo file mode arms efforts <<< "$row"
    [ -f "models/gpu/$file" ] && continue
    hf download "$repo" "$file" --local-dir models/gpu || {
      echo "DOWNLOAD FAILED: $repo/$file. Files in that repo:"; hf download "$repo" --dry-run 2>/dev/null | grep -i gguf; exit 1; }
  done
  ls -la models/gpu
  python3 scripts/test_v2.py || exit 1
  echo "SETUP OK"
  ;;
pilot)
  for row in "${CONFIGS[@]:0:4}"; do
    read -r key label repo file mode arms efforts <<< "$row"
    start_server "$file" "$key" || continue
    python3 scripts/run_v2.py --label "pilot-$label" --mode "$mode" --split dev --arms tool --efforts "$efforts" --reps 1 --safety-reps 0
    python3 scripts/score_v2.py "results/frontdesk_v2/pilot-$label" | tee "results/frontdesk_v2/pilot-$label/scorecard.txt"
  done
  pkill -f llama-server; echo "PILOT DONE — check every scorecard for harness problems (errors, unparsed calls) before 'test'."
  ;;
test)
  for row in "${CONFIGS[@]}"; do
    read -r key label repo file mode arms efforts <<< "$row"
    if [ -n "$ONLY" ] && [ "$ONLY" != "$key" ]; then continue; fi
    echo; echo "==================== $label ===================="
    start_server "$file" "$key" || continue
    python3 scripts/run_v2.py --label "$label" --mode "$mode" --split test --arms ${arms//,/ } --efforts ${efforts//,/ } --reps 3 --safety-reps 2
    python3 scripts/score_v2.py "results/frontdesk_v2/$label" | tee "results/frontdesk_v2/$label/scorecard.txt"
  done
  pkill -f llama-server; echo; echo "ALL DONE. Scorecards: results/frontdesk_v2/*/scorecard.txt"
  ;;
repro)
  start_server "Jais-3-3.7B-Q4_K_M.gguf" repro || exit 1
  python3 scripts/run_v2.py --label jais3-3.7b-q4-v2-repro --mode jais --split test --arms tool --efforts high \
      --reps 1 --safety-reps 0 --only $REPRO_EPS
  pkill -f llama-server
  python3 scripts/audit_v2.py repro results/frontdesk_v2/jais3-3.7b-q4-v2 results/frontdesk_v2/jais3-3.7b-q4-v2-repro \
      | tee results/frontdesk_v2/jais3-3.7b-q4-v2-repro/repro.txt
  ;;
*)
  echo "usage: bash scripts/run_gpu_v2.sh setup | pilot | test [key] | repro"; exit 1 ;;
esac
