#!/bin/bash
# miqyas · qt-02 — Falcon-H1-7B-Instruct Quick Trial on the clinic front desk (trials/qt-02-falcon-h1-7b-clinic.yaml).
# Same job, test set, window (32,768) and generation cap (8,192) as Job Trial #1. Tool arm, no thinking.
# Adapter rule (pre-registered): probe once before any model output is read; if tools reach the prompt through
# llama.cpp's native tool calling, use it (--mode chat, like Qwen3); otherwise the prompted-JSON adapter (--mode prompted).
#
# On a RunPod pod (RTX 4090, PyTorch template), from the repo root. Run every step DETACHED:
#   setsid nohup bash scripts/run_qt02.sh setup > qt02_setup.log 2>&1 < /dev/null &   (~15 min)
#   setsid nohup bash scripts/run_qt02.sh pilot > qt02_pilot.log 2>&1 < /dev/null &   (~5 min)
#   setsid nohup bash scripts/run_qt02.sh test  > qt02_test.log  2>&1 < /dev/null &   (~15-40 min)
#   bash scripts/run_qt02.sh pack
# Check progress with: tail -5 qt02_<step>.log   (closing the terminal does not stop the run)
set -u
cd "$(dirname "$0")/.."
exec 9> /tmp/run_qt02.lock
if ! flock -n 9; then echo "Another run_qt02.sh is already running — not starting a second one."; exit 1; fi
LL="$HOME/llama.cpp"
SERVER="$LL/build/bin/llama-server"
QUANT="$LL/build/bin/llama-quantize"
REPO="tiiuae/Falcon-H1-7B-Instruct"
GREPO="tiiuae/Falcon-H1-7B-Instruct-GGUF"
GGUF="models/gpu/Falcon-H1-7B-Instruct-Q4_K_M.gguf"
OUT="results/qt02"
LABEL="falcon-h1-7b-q4-qt02"
CTX=32768
NPRED=8192

start_server () {
  pkill -f llama-server; sleep 2
  "$SERVER" -m "$GGUF" --jinja -ngl 99 -c $CTX -np 1 --port 8080 > /tmp/server_qt02.log 2>&1 &
  for i in $(seq 1 180); do curl -s localhost:8080/health | grep -q '"ok"' && return 0; sleep 2; done
  echo "server did not start — last log lines:"; tail -20 /tmp/server_qt02.log; return 1
}

probe_adapter () {   # prompt size with vs without tools, max_tokens 1: no model answer is read
  python3 - "$OUT/adapter.txt" <<'PY'
import json, sys, urllib.request
sys.path.insert(0, "scripts")
from clinic import system_prompt, tools_for
def n(tools):
    body = {"messages": [{"role": "system", "content": system_prompt("tool")}, {"role": "user", "content": "مرحبا"}],
            "max_tokens": 1, "temperature": 0, "cache_prompt": False}
    if tools: body["tools"] = tools_for("tool")
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://localhost:8080/v1/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=300))
    return r["timings"]["prompt_n"]
a, b = n(False), n(True)
mode = "chat" if b - a >= 200 else "prompted"
open(sys.argv[1], "w").write(f"{mode}\nprompt tokens without tools {a}, with tools {b}\n")
print(f"ADAPTER: {mode} (prompt tokens without tools {a}, with tools {b})")
PY
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
  command -v hf >/dev/null || pip install -q -U huggingface_hub
  (cd "$LL" && git rev-parse --short HEAD) > /tmp/llama_commit.txt
  mkdir -p models/gpu models/hf "$OUT"
  SRC="official GGUF ($GREPO)"
  if [ ! -f "$GGUF" ]; then
    hf download "$GREPO" --include "*Q4_K_M*.gguf" --local-dir models/hf/falcon-gguf >/dev/null 2>&1
    F=$(ls models/hf/falcon-gguf/*Q4_K_M*.gguf 2>/dev/null | head -1)
    if [ -n "$F" ]; then cp "$F" "$GGUF"
    else
      SRC="self-converted from $REPO (no official Q4_K_M found)"
      pip install -q -r "$LL/requirements/requirements-convert_hf_to_gguf.txt" || pip install -q gguf sentencepiece safetensors transformers
      hf download "$REPO" --local-dir models/hf/falcon-h1-7b || { echo "DOWNLOAD FAILED: $REPO"; exit 1; }
      python3 "$LL/convert_hf_to_gguf.py" models/hf/falcon-h1-7b --outtype f16 --outfile models/gpu/falcon-h1-7b-f16.gguf || exit 1
      "$QUANT" models/gpu/falcon-h1-7b-f16.gguf "$GGUF" Q4_K_M || exit 1
    fi
  fi
  hf download "$REPO" LICENSE README.md --local-dir models/hf/falcon-h1-7b-card >/dev/null 2>&1
  cp models/hf/falcon-h1-7b-card/LICENSE "$OUT/LICENSE.txt" 2>/dev/null || echo "no LICENSE file in $REPO" > "$OUT/LICENSE.txt"
  { echo "llama.cpp $(cat /tmp/llama_commit.txt)"; echo "repo commit $(git rev-parse --short HEAD)"; echo "source: $SRC"; sha256sum "$GGUF"; } > "$OUT/model_provenance.txt"
  cat "$OUT/model_provenance.txt"; head -5 "$OUT/LICENSE.txt"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
  python3 scripts/test_v2.py || exit 1
  echo "SETUP OK — next: setsid nohup bash scripts/run_qt02.sh pilot > qt02_pilot.log 2>&1 < /dev/null &"
  ;;
pilot)
  start_server || exit 1
  probe_adapter || exit 1
  MODE=$(head -1 "$OUT/adapter.txt")
  P="pilot-$LABEL"
  python3 scripts/run_v2.py --label "$P" --mode "$MODE" --sampling falcon-h1 --split dev --arms tool --efforts off \
      --reps 1 --safety-reps 0 --n-predict $NPRED --out-root "$OUT"
  python3 scripts/score_v2.py "$OUT/$P" | tee "$OUT/$P/scorecard.txt"
  python3 - "$OUT/$P/runs.jsonl" "$MODE" <<'PY'
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1])]
err=sum('error' in r for r in rows); ctx=sum(r.get('flags',{}).get('context',False) for r in rows)
calls=sum(len(s['calls']) for r in rows if 'steps' in r for s in r['steps'])
unparsed=sum(1 for r in rows if 'steps' in r for s in r['steps'] for c in s['calls'] if '_unparsed' in c['args'])
bad=sum(1 for r in rows if 'steps' in r for s in r['steps'] if s.get('parsed') is False)
p0=rows[0]['steps'][0]['prompt_n'] if rows and rows[0].get('steps') else '-'
print(f"PILOT CHECK: adapter {sys.argv[2]} · runs {len(rows)} · errors {err} · context overflows {ctx} · tool calls {calls} · unparsed {unparsed} · non-JSON replies {bad} · first prompt tokens {p0}")
PY
  pkill -f llama-server
  echo "PILOT DONE — send the PILOT CHECK line and scorecard to Claude before running 'test'."
  ;;
test)
  [ -f "$OUT/adapter.txt" ] || { echo "run the pilot first (it fixes the adapter)"; exit 1; }
  MODE=$(head -1 "$OUT/adapter.txt")
  start_server || exit 1
  python3 scripts/run_v2.py --label "$LABEL" --mode "$MODE" --sampling falcon-h1 --split test --arms tool --efforts off \
      --reps 3 --safety-reps 2 --n-predict $NPRED --out-root "$OUT"
  python3 scripts/score_v2.py "$OUT/$LABEL" | tee "$OUT/$LABEL/scorecard.txt"
  pkill -f llama-server; echo "TEST DONE — next: bash scripts/run_qt02.sh pack"
  ;;
pack)
  tar czf qt02_results.tar.gz "$OUT" && ls -la qt02_results.tar.gz
  echo "Download qt02_results.tar.gz from JupyterLab (right-click > Download), attach it to Claude, then STOP the pod."
  ;;
*)
  echo "usage: bash scripts/run_qt02.sh setup | pilot | test | pack"; exit 1 ;;
esac
