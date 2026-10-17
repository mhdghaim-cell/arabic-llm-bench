#!/usr/bin/env python3
"""
miqyas · front-desk trial — one message, clinic system prompt, three tools.

Usage (llama-server already running on :8080):
    python3 scripts/try_tools.py "<message>" [low|medium|high] [raw]

"raw" turns off llama-server's reasoning/tool-call parsing and prints the model's
exact output, to tell a model failure from a parser failure.
Every run is appended to results/frontdesk/trials.jsonl.
"""
import json
import sys
import os
import time
import urllib.request

TODAY = "2026-10-17 (السبت)"

# v0 — pilot prompt (run 1, 2026-10-17). Kept unchanged for the record.
SYSTEM_V0 = f"""أنت موظف الاستقبال الرقمي لعيادة "ابتسامة" لطب الأسنان في دبي.
اليوم: {TODAY}. ساعات العمل: من الأحد إلى الخميس، 9 صباحًا – 9 مساءً. السبت: 10 صباحًا – 4 عصرًا. الجمعة مغلق.
الخدمات: فحص عام، تنظيف، حشوة، تقويم، تبييض.

القواعد:
- لا تخترع مواعيد. استخدم check_availability قبل اقتراح أي وقت.
- لا تحجز قبل أن تعرف: الخدمة، والتاريخ، والوقت، واسم المريض.
- إذا كان الطلب غامضًا، اسأل سؤالًا واحدًا قصيرًا.
- الحالات الطارئة (نزيف، تورم شديد، ألم لا يُحتمل) أو أي شكوى أو طلب طبي: استخدم handoff_to_human فورًا.
- ردّ بلهجة العميل نفسها، باختصار."""

# v1 — frozen for the main experiment. Changes vs v0, each fixing an ambiguity found in the pilot:
#   * current TIME added ("today before 4" / "tonight" were unanswerable without it)
#   * check availability as soon as service + day are known, even without a name
#     (v0 said "don't book before you know the name", which a model could read as "don't even check")
#   * Arabic service names mapped to the tool's English values
#   * handing over means CALLING the tool — saying so is not enough (pilot failure mode)
#   * no invented prices/insurance; plain text, no bullet formatting (WhatsApp)
SYSTEM_V1 = """أنت موظف الاستقبال الرقمي لعيادة "ابتسامة" لطب الأسنان في دبي، وتردّ على رسائل واتساب.
الآن: السبت 2026-10-17، الساعة 11:00 صباحًا.
ساعات العمل: الأحد إلى الخميس من 9 صباحًا إلى 9 مساءً. السبت من 10 صباحًا إلى 4 عصرًا. الجمعة مغلق.
الخدمات: فحص عام (checkup)، تنظيف (cleaning)، حشوة (filling)، تقويم (orthodontics)، تبييض (whitening).

القواعد:
1. إذا طلب العميل موعدًا وعرفتَ الخدمة واليوم، استدعِ check_availability فورًا، حتى لو لم تعرف اسمه بعد. لا تقترح أي وقت من عندك.
2. لا تستدعِ book_appointment إلا بعد أن يوافق العميل على وقت ظهر في نتيجة check_availability، وبعد معرفة اسمه.
3. إذا نقصت الخدمة أو اليوم، اسأل سؤالًا واحدًا قصيرًا.
4. الحالات الطارئة (نزيف، تورم، ألم شديد، حرارة)، والشكاوى، والأسئلة الطبية: استدعِ handoff_to_human فورًا. لا يكفي أن تقول إنك ستحوّل الحالة؛ يجب استدعاء الأداة.
5. لا تخترع أسعارًا أو معلومات عن التأمين غير مذكورة هنا.
6. ردّ بلهجة العميل نفسها، باختصار، ومن غير نقاط أو عناوين."""

PROMPTS = {"v0": SYSTEM_V0, "v1": SYSTEM_V1}
SYSTEM = SYSTEM_V0   # try_tools.py trials used v0

TOOLS = [
    {"type": "function", "function": {
        "name": "check_availability",
        "description": "Check free appointment slots for a service on a date.",
        "parameters": {"type": "object", "properties": {
            "service": {"type": "string", "enum": ["checkup", "cleaning", "filling", "orthodontics", "whitening"]},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time_window": {"type": "string", "enum": ["morning", "afternoon", "evening", "any"]}},
            "required": ["service", "date"]}}},
    {"type": "function", "function": {
        "name": "book_appointment",
        "description": "Book a confirmed slot. Only after the patient agrees to a specific time.",
        "parameters": {"type": "object", "properties": {
            "service": {"type": "string", "enum": ["checkup", "cleaning", "filling", "orthodontics", "whitening"]},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM, 24h"},
            "patient_name": {"type": "string"}},
            "required": ["service", "date", "time", "patient_name"]}}},
    {"type": "function", "function": {
        "name": "handoff_to_human",
        "description": "Transfer to clinic staff: emergencies, complaints, medical questions, anything out of scope.",
        "parameters": {"type": "object", "properties": {
            "reason": {"type": "string", "enum": ["emergency", "complaint", "medical_question", "out_of_scope", "other"]},
            "summary": {"type": "string"}},
            "required": ["reason", "summary"]}}},
]


def main():
    msg = sys.argv[1]
    effort = sys.argv[2] if len(sys.argv) > 2 else "low"
    raw = len(sys.argv) > 3 and sys.argv[3] == "raw"
    body = {
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        "tools": TOOLS,
        "temperature": 0.7, "top_p": 0.95, "top_k": 20, "max_tokens": 4096,
        "chat_template_kwargs": {"reasoning_effort": effort},
    }
    if raw:
        body["reasoning_format"] = "none"
        body["parse_tool_calls"] = False
    req = urllib.request.Request("http://localhost:8080/v1/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req))
    wall = time.time() - t0
    ch = r["choices"][0]
    m, t, u = ch["message"], r.get("timings", {}), r["usage"]
    os.makedirs("results/frontdesk", exist_ok=True)
    with open("results/frontdesk/trials.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "msg": msg, "effort": effort, "raw": raw,
                            "wall_s": round(wall, 2), "usage": u, "timings": t,
                            "finish_reason": ch.get("finish_reason"), "message": m}, ensure_ascii=False) + "\n")
    if raw:
        print(f"== RAW effort={effort} | wall {wall:.1f}s | finish={ch.get('finish_reason')} | completion {u['completion_tokens']} tok")
        print(m.get("content"))
        return
    print(f"== effort={effort} | finish={ch.get('finish_reason')} | wall {wall:.1f}s | prompt {u['prompt_tokens']} tok | "
          f"completion {u['completion_tokens']} tok | gen {t.get('predicted_per_second', 0):.1f} tok/s")
    reasoning = m.get("reasoning_content") or ""
    print("REASONING:", (reasoning[:600] + " …") if len(reasoning) > 600 else (reasoning or "(none)"))
    for c in m.get("tool_calls") or []:
        print("TOOL CALL:", c["function"]["name"], c["function"]["arguments"])
    print("ANSWER:", m.get("content") or "(none)")


if __name__ == "__main__":
    main()
