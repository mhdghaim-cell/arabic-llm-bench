#!/bin/bash
# miqyas · front-desk v2 — speed on the reception laptop (Intel MacBook Air 2020, CPU only).
#
#   bash scripts/run_air_v2.sh bench      # download models + measure laptop speed  (~3-4 h, overnight)
#   bash scripts/run_air_v2.sh validate   # 10 real conversations on the laptop + check the speed model (~1 h)
#   bash scripts/run_air_v2.sh predict    # after the GPU test run is copied back: laptop wait per configuration
#
# Keep the laptop plugged in. The script keeps it awake with caffeinate.
set -u
cd "$(dirname "$0")/.."
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"          # override: LLAMA_DIR=/path/to/llama.cpp bash scripts/run_air_v2.sh bench
if [ ! -d "$LLAMA_DIR" ]; then
  echo "llama.cpp not found at $LLAMA_DIR."
  echo "Find it with:  find ~ -maxdepth 4 -name llama-server -type f"
  echo "then run:      LLAMA_DIR=<folder that contains build/> bash scripts/run_air_v2.sh $*"
  exit 1
fi
export LLAMA_BENCH="$LLAMA_DIR/build/bin/llama-bench"
STEP=${1:-}
VALIDATE_EPS="t02 t06 t11 t13 t15 t20 t23 t29 t38 t41"

#      name               hf repo                file
MODELS=(
  "jais3-3.7b-q4    IFM/Jais-3-3.7B-GGUF   Jais-3-3.7B-Q4_K_M.gguf"
  "jais3-7b-q4      IFM/Jais-3-7B-GGUF     Jais-3-7B-Q4_K_M.gguf"
  "qwen3-4b-q4      Qwen/Qwen3-4B-GGUF     Qwen3-4B-Q4_K_M.gguf"
  "qwen3-8b-q4      Qwen/Qwen3-8B-GGUF     Qwen3-8B-Q4_K_M.gguf"
)

if [ -z "${CAFFEINATED:-}" ] && command -v caffeinate >/dev/null; then
  CAFFEINATED=1 exec caffeinate -dims bash "$0" "$@"
fi
mkdir -p models/air results/frontdesk_v2/air_speed

case "$STEP" in
bench)
  [ -x "$LLAMA_BENCH" ] || (cd "$LLAMA_DIR" && cmake --build build -j 4 --target llama-bench llama-server) || exit 1
  for row in "${MODELS[@]}"; do
    read -r name repo file <<< "$row"
    [ -f "models/air/$file" ] || hf download "$repo" "$file" --local-dir models/air || { echo "download failed: $file"; continue; }
    [ -f "results/frontdesk_v2/air_speed/$name.json" ] && { echo "$name already measured"; continue; }
    echo "== measuring $name =="
    python3 scripts/air_speed.py bench "models/air/$file" "$name" || echo "bench failed for $name (not enough memory?)"
  done
  ;;
validate)
  pkill -f llama-server; sleep 2
  "$LLAMA_DIR/build/bin/llama-server" -m models/air/Jais-3-3.7B-Q4_K_M.gguf --jinja -ngl 0 -c 16384 -np 1 --port 8080 > /tmp/server_air.log 2>&1 &
  for i in $(seq 1 300); do curl -s localhost:8080/health | grep -q '"ok"' && break; sleep 2; done
  # CPU only (-ngl 0), exactly like the llama-bench measurement; the Intel graphics chip is not used.
  # warm-up: the first request after loading pays a one-off disk read; a real front desk keeps the model loaded
  curl -s localhost:8080/completion -d '{"prompt":"مرحبا","n_predict":8}' > /dev/null
  python3 scripts/run_v2.py --label jais3-3.7b-q4-air-v2 --mode jais --split test --arms tool --efforts low \
      --reps 1 --safety-reps 0 --only $VALIDATE_EPS
  pkill -f llama-server
  python3 scripts/air_speed.py validate jais3-3.7b-q4 results/frontdesk_v2/jais3-3.7b-q4-air-v2 \
      | tee results/frontdesk_v2/air_speed/validation.txt
  ;;
predict)
  for pair in "jais3-3.7b-q4:jais3-3.7b-q4-v2" "jais3-3.7b-q4:jais3-3.7b-q4-v2-low" "jais3-7b-q4:jais3-7b-q4-v2" \
              "qwen3-4b-q4:qwen3-4b-q4-v2" "qwen3-4b-q4:qwen3-4b-q4-v2-off" "qwen3-8b-q4:qwen3-8b-q4-v2"; do
    name=${pair%%:*}; label=${pair##*:}
    [ -f "results/frontdesk_v2/air_speed/$name.json" ] && [ -d "results/frontdesk_v2/$label" ] || continue
    python3 scripts/air_speed.py predict "$name" "results/frontdesk_v2/$label"
  done | tee results/frontdesk_v2/air_speed/predicted_waits.txt
  ;;
*)
  echo "usage: bash scripts/run_air_v2.sh bench | validate | predict"; exit 1 ;;
esac
