#!/bin/bash
M=$1; PID=$2
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p results/raw
LOG="results/raw/w2_${PID}_${M}_${TS}.json"
P=$(cat prompts/${PID}.txt | tr -d '\n')
BODY="{\"model\":\"$M\",\"prompt\":\"$P\",\"stream\":false,\"options\":{\"num_predict\":500,\"temperature\":0.7,\"seed\":42}}"
curl -s http://localhost:11434/api/generate -d "$BODY" > "$LOG"
echo "=== $PID | $M ==="
grep -o '"response":"[^"]*"' "$LOG" | head -c 2000
echo
echo "--- $(grep -o '"eval_count":[0-9]*' "$LOG") | $(grep -o '"done_reason":"[^"]*"' "$LOG") ---"
