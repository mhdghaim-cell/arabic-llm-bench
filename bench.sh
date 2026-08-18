#!/bin/bash
M=$1
LOG="results/raw/$(echo $M | tr ':/' '__')_$(date +%Y%m%d_%H%M%S).txt"
P="اكتب رسالة رسمية من ٤ جمل إلى مدير إدارة تكنولوجيا المعلومات تطلب فيها الموافقة على تشغيل نموذج ذكاء اصطناعي على خوادم الجهة بدلًا من الخدمات السحابية. اذكر سببًا واحدًا يتعلق بسيادة البيانات."
python3 - "$M" "$P" << 'PY' | tee "$LOG"
import sys, json, urllib.request, datetime
m, p = sys.argv[1], sys.argv[2]
body = json.dumps({"model": m, "prompt": p, "stream": False,
                   "options": {"num_predict": 300, "temperature": 0.7, "seed": 42}}).encode()
r = json.load(urllib.request.urlopen(
    urllib.request.Request("http://localhost:11434/api/generate", body,
                           {"Content-Type": "application/json"})))
print(f"timestamp:   {datetime.datetime.now().isoformat()}")
print(f"model:       {m}")
print(f"eval count:  {r['eval_count']}")
print(f"eval rate:   {r['eval_count']/r['eval_duration']*1e9:.2f} tok/s")
print(f"prompt rate: {r['prompt_eval_count']/r['prompt_eval_duration']*1e9:.2f} tok/s")
print(f"total:       {r['total_duration']/1e9:.1f}s")
print("--- full output ---")
print(r['response'])
PY
