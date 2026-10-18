#!/bin/bash
# miqyas · front-desk test v1 — all Mac mini M4 configurations in one go.
#
# Usage, from the repo folder on the M4:
#     bash scripts/run_m4.sh            # runs everything, resumable
#     bash scripts/run_m4.sh 7b         # just one configuration (7b | 3.7b | qwen | 0.9b)
#
# Order matters: the 7B ceiling check runs first. If it can't clear the bar,
# the test itself is in question and the rest can wait.
set -u
cd "$(dirname "$0")/.."
LLAMA=${LLAMA:-llama-server}
mkdir -p models/m4 results/frontdesk

#        key    label                     hf repo                 file                          mode  efforts
CONFIGS=(
  "7b    jais3-7b-q4-m4-v1      IFM/Jais-3-7B-GGUF     Jais-3-7B-Q4_K_M.gguf     jais  low,high"
  "3.7b  jais3-3.7b-q4-m4-v1    IFM/Jais-3-3.7B-GGUF   Jais-3-3.7B-Q4_K_M.gguf   jais  low,high"
  "qwen  qwen3-4b-q4-m4-v1      Qwen/Qwen3-4B-GGUF     Qwen3-4B-Q4_K_M.gguf      chat  off,on"
  "0.9b  jais3-0.9b-q8-m4-v1    IFM/Jais-3-0.9B-GGUF   Jais-3-0.9B-Q8_0.gguf     jais  low,high"
)

for row in "${CONFIGS[@]}"; do
  read -r key label repo file mode efforts <<< "$row"
  if [ $# -gt 0 ] && [ "$1" != "$key" ]; then continue; fi
  echo; echo "==================== $label ===================="
  [ -f "models/m4/$file" ] || hf download "$repo" "$file" --local-dir models/m4 || { echo "download failed: $repo/$file"; continue; }

  pkill -f llama-server; sleep 2
  "$LLAMA" -m "models/m4/$file" --jinja -ngl 99 -c 8192 --port 8080 > "/tmp/server_$key.log" 2>&1 &
  for i in $(seq 1 120); do curl -s localhost:8080/health | grep -q ok && break; sleep 2; done
  if ! curl -s localhost:8080/health | grep -q ok; then
    echo "server did not start for $label — last log lines:"; tail -15 "/tmp/server_$key.log"; continue
  fi
  echo "server ready: $file"

  python3 scripts/run_frontdesk.py --label "$label" --mode "$mode" --efforts ${efforts//,/ } --reps 3
  python3 scripts/score_frontdesk.py "results/frontdesk/$label" | tee "results/frontdesk/$label/scorecard.txt"
done
pkill -f llama-server
echo; echo "All done. Scorecards are in results/frontdesk/*-m4-v1/scorecard.txt"
