import sys, json, time, urllib.request
msg, effort = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "low")
body = {"messages": [{"role": "user", "content": msg}], "temperature": 0.7, "top_p": 0.95, "top_k": 20,
        "max_tokens": 4096, "chat_template_kwargs": {"reasoning_effort": effort}}
req = urllib.request.Request("http://localhost:8080/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
t0 = time.time(); r = json.load(urllib.request.urlopen(req)); wall = time.time() - t0
m, t, u = r["choices"][0]["message"], r.get("timings", {}), r["usage"]
print(f"== effort={effort} | wall {wall:.1f}s | completion tokens {u['completion_tokens']} | gen {t.get('predicted_per_second',0):.1f} tok/s")
print("REASONING:\n", (m.get("reasoning_content") or "(none)")[:1200])
print("\nANSWER:\n", m.get("content"))
