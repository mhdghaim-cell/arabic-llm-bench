#!/bin/bash
# miqyas · qt-01 — ALLaM 7B Quick Trial on the clinic front desk (trials/qt-01-allam-7b-clinic.yaml).
# Pre-registered setup: tool arm, prompted-JSON adapter (amendment 2), ALLaM model-card sampling,
# 4,096-token window, public test set (42 episodes) x 3 reps + 2 extra reps for safety episodes.
#
# On a RunPod pod (RTX 4090, PyTorch template), from the repo root:
#   bash scripts/run_qt01.sh setup     # build llama.cpp, download ALLaM, convert + quantise to Q4_K_M, self-tests (~20 min)
#   bash scripts/run_qt01.sh pilot     # 12 DEV episodes, 1 rep: check the tool adapter before the test (~5 min)
#   bash scripts/run_qt01.sh test      # the pre-registered TEST run (~1 h). Start it detached:
#       setsid nohup bash scripts/run_qt01.sh test > qt01_test.log 2>&1 < /dev/null &   then: tail -f qt01_test.log
#   bash scripts/run_qt01.sh pack      # one archive to download: qt01_results.tar.gz
set -u
cd "$(dirname "$0")/.."
exec 9> /tmp/run_qt01.lock
if ! flock -n 9; then echo "Another run_qt01.sh is already running — not starting a second one."; exit 1; fi
ROOT=$(pwd)
LL="$HOME/llama.cpp"
SERVER="$LL/build/bin/llama-server"
QUANT="$LL/build/bin/llama-quantize"
REPO="ALLaM-AI/ALLaM-7B-Instruct-preview"
GGUF="models/gpu/ALLaM-7B-Instruct-preview-Q4_K_M.gguf"
OUT="results/qt01"
LABEL="allam-7b-q4-qt01"
CTX=4096

start_server () {
  pkill -f llama-server; sleep 2
  "$SERVER" -m "$GGUF" --jinja -ngl 99 -c $CTX -np 1 --port 8080 > /tmp/server_qt01.log 2>&1 &
  for i in $(seq 1 180); do curl -s localhost:8080/health | grep -q '"ok"' && return 0; sleep 2; done
  echo "server did not start — last log lines:"; tail -20 /tmp/server_qt01.log; return 1
}

case "${1:-}" in
setup)
  if [ ! -x "$SERVER" ] || [ ! -x "$QUANT" ]; then
    echo "== building llama.cpp with CUDA (about 10 minutes) =="
    pip install -q -U cmake huggingface_hub
    command -v git >/dev/null || (apt-get update -q && apt-get install -y -q git)
    [ -d "$LL" ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LL"
    (cd "$LL" && cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=native \
      && cmake --build build -j 16 --target llama-server llama-quantize) || exit 1
  fi
  (cd "$LL" && git rev-parse --short HEAD) > /tmp/llama_commit.txt
  pip install -q -r "$LL/requirements/requirements-convert_hf_to_gguf.txt" || pip install -q gguf sentencepiece safetensors transformers
  mkdir -p models/gpu models/hf "$OUT"
  if [ ! -f "$GGUF" ]; then
    hf download "$REPO" --local-dir models/hf/allam-7b || { echo "DOWNLOAD FAILED: $REPO"; exit 1; }
    python3 "$LL/convert_hf_to_gguf.py" models/hf/allam-7b --outtype f16 --outfile models/gpu/allam-7b-f16.gguf || exit 1
    "$QUANT" models/gpu/allam-7b-f16.gguf "$GGUF" Q4_K_M || exit 1
  fi
  { echo "llama.cpp $(cat /tmp/llama_commit.txt)"; (cd models/hf/allam-7b && git rev-parse HEAD 2>/dev/null || ls); sha256sum "$GGUF"; } > "$OUT/model_provenance.txt"
  cat "$OUT/model_provenance.txt"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
  python3 scripts/test_v2.py || exit 1
  echo "SETUP OK — next: bash scripts/run_qt01.sh pilot"
  ;;
pilot)
  start_server || exit 1
  P="pilot2-$LABEL"   # pilot 1 (llama.cpp generic tools) dropped the tool definitions: kept as evidence, see amendment 2
  python3 scripts/run_v2.py --label "$P" --mode prompted --sampling allam --split dev --arms tool --efforts off \
      --reps 1 --safety-reps 0 --n-predict 4096 --out-root "$OUT"
  python3 scripts/score_v2.py "$OUT/$P" | tee "$OUT/$P/scorecard.txt"
  python3 - "$OUT/$P/runs.jsonl" <<'PY'
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1])]
err=sum('error' in r for r in rows); ctx=sum(r.get('flags',{}).get('context',False) for r in rows)
calls=sum(len(s['calls']) for r in rows if 'steps' in r for s in r['steps'])
unparsed=sum(1 for r in rows if 'steps' in r for s in r['steps'] for c in s['calls'] if '_unparsed' in c['args'])
bad=sum(1 for r in rows if 'steps' in r for s in r['steps'] if s.get('parsed') is False)
p0=[r['steps'][0]['prompt_n'] for r in rows if r.get('steps')]
print(f"PILOT CHECK: runs {len(rows)} · errors {err} · context overflows {ctx} · tool calls {calls} · unparsed {unparsed} · non-JSON replies {bad} · first prompt tokens {min(p0) if p0 else '-'}")
PY
  pkill -f llama-server
  echo "PILOT DONE — send the PILOT CHECK line and scorecard to Claude before running 'test'."
  ;;
test)
  start_server || exit 1
  python3 scripts/run_v2.py --label "$LABEL" --mode prompted --sampling allam --split test --arms tool --efforts off \
      --reps 3 --safety-reps 2 --n-predict 4096 --out-root "$OUT"
  python3 scripts/score_v2.py "$OUT/$LABEL" | tee "$OUT/$LABEL/scorecard.txt"
  pkill -f llama-server; echo "TEST DONE — next: bash scripts/run_qt01.sh pack"
  ;;
pack)
  tar czf qt01_results.tar.gz "$OUT" && ls -la qt01_results.tar.gz
  echo "Download qt01_results.tar.gz (Jupyter file browser, or: runpodctl send qt01_results.tar.gz). Then STOP the pod."
  ;;
*)
  echo "usage: bash scripts/run_qt01.sh setup | pilot | test | pack"; exit 1 ;;
esac
