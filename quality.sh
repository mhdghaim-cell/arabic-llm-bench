#!/bin/bash
M=$1; PID=$2; THINK=$3
TS=$(date +%Y%m%d_%H%M%S)
LOG="results/raw/q_${PID}_$(echo $M | tr ':/' '__')${THINK:+_nothink}_${TS}.txt"
P=$(cat prompts/${PID}.txt | tr -d '\n')
TFLAG=""
[ -n "$THINK" ] && TFLAG=',"think":false'
BODY="{\"model\":\"$M\",\"prompt\":\"$P\",\"stream\":false,\"options\":{\"num_predict\":500,\"temperature\":0.7,\"seed\":42}$TFLAG}"
curl -s http://localhost:11434/api/generate -d "$BODY" > /tmp/q.json
echo "=== $PID | $M ${THINK:+think:false} | $TS ===" | tee "$LOG"
cat /tmp/q.json | tee -a "$LOG"
echo "" | tee -a "$LOG"
