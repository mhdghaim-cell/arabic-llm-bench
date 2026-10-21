#!/usr/bin/env python3
"""
miqyas · front-desk v2 — the simulated clinic.

Everything a receptionist model can touch lives here: the clock, the calendar, the
patient's existing appointments, and the tools. It is fully deterministic (no RNG,
no wall clock), so every run of every model sees exactly the same clinic.

    Clinic(episode).call(name, args) -> dict      # executes one tool call
    Clinic(episode).events                         # what happened, for the scorer
"""
import datetime as dt
import hashlib
import json

NOW = dt.datetime(2026, 11, 5, 15, 30)          # Thursday 5 Nov 2026, 3:30 pm (Dubai)
WEEKDAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
SERVICES = ["checkup", "cleaning", "filling", "orthodontics", "whitening"]
WINDOWS = {"morning": (0, 12 * 60), "afternoon": (12 * 60, 17 * 60), "evening": (17 * 60, 24 * 60), "any": (0, 24 * 60)}
HANDOFF_REASONS = ["emergency", "complaint", "medical_question", "out_of_scope", "other"]
HORIZON_DAYS = 30                               # bookings open up to 30 days ahead


def hours(date):
    """Opening hours (open_min, close_min) or None if closed."""
    wd = date.weekday()                         # Mon=0 … Sun=6
    if wd == 4:                                 # Friday
        return None
    if wd == 5:                                 # Saturday
        return (10 * 60, 16 * 60)
    return (9 * 60, 21 * 60)                    # Sun–Thu


def fmt(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def base_free(date, service):
    """Deterministic base calendar: each 30-min slot is free with ~40% probability (hash, not RNG)."""
    h = hours(date)
    if not h:
        return []
    out = []
    for m in range(h[0], h[1], 30):
        key = f"{date.isoformat()}|{service}|{fmt(m)}".encode()
        if int(hashlib.sha256(key).hexdigest(), 16) % 10 < 4:
            out.append(fmt(m))
    return out


def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s).strip())
    except Exception:
        return None


# ---------------------------------------------------------------- tool schemas
def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


T_FIND_DATE = _fn(
    "find_date",
    "Convert a day the patient mentions into an exact calendar date. Use this instead of calculating dates yourself. "
    "Give EITHER days_from_today (today=0, tomorrow=1, day after tomorrow=2) OR weekday (+ optional occurrence: "
    "1 = the first such weekday after today, 2 = the one after that) OR day_of_month (the next date with that day number).",
    {"days_from_today": {"type": "integer"},
     "weekday": {"type": "string", "enum": ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]},
     "occurrence": {"type": "integer", "enum": [1, 2]},
     "day_of_month": {"type": "integer"}},
    [])
T_CHECK = _fn(
    "check_availability", "List the free appointment times for a service on a date.",
    {"service": {"type": "string", "enum": SERVICES},
     "date": {"type": "string", "description": "YYYY-MM-DD"},
     "time_window": {"type": "string", "enum": list(WINDOWS)}},
    ["service", "date"])
T_BOOK = _fn(
    "book_appointment", "Book a time that check_availability returned, after the patient chose it and gave their name.",
    {"service": {"type": "string", "enum": SERVICES},
     "date": {"type": "string", "description": "YYYY-MM-DD"},
     "time": {"type": "string", "description": "HH:MM, 24h"},
     "patient_name": {"type": "string"}},
    ["service", "date", "time", "patient_name"])
T_LIST = _fn(
    "list_my_appointments", "List this patient's upcoming appointments (the patient is identified by their WhatsApp number).",
    {}, [])
T_CANCEL = _fn(
    "cancel_appointment", "Cancel one of this patient's appointments by its booking_id.",
    {"booking_id": {"type": "string"}}, ["booking_id"])
T_HANDOFF = _fn(
    "handoff_to_human", "Transfer the chat to clinic staff: emergencies, complaints, medical questions, out-of-scope requests, or when a tool fails.",
    {"reason": {"type": "string", "enum": HANDOFF_REASONS},
     "summary": {"type": "string"}},
    ["reason", "summary"])

TOOLS_BASE = [T_CHECK, T_BOOK, T_LIST, T_CANCEL, T_HANDOFF]
TOOLS_WITH_DATE = [T_FIND_DATE] + TOOLS_BASE


def tools_for(arm):
    return TOOLS_WITH_DATE if arm == "tool" else TOOLS_BASE


# ---------------------------------------------------------------- the clinic
class Clinic:
    """One fresh clinic per episode run. `episode['clinic']` may override the base calendar:
         full:   [[date, service], ...]           -> no free slots that day for that service
         extra:  [[date, service, "HH:MM"], ...]  -> force a slot free (so a scripted patient's choice exists)
         taken:  [[date, service, "HH:MM"], ...]  -> force a slot busy
         fail:   ["check_availability", ...]      -> that tool returns an error ("calendar system down")
         appointments: [{booking_id, service, date, time, patient_name}, ...]  -> patient's existing bookings
    """

    def __init__(self, episode=None, arm="base"):
        c = (episode or {}).get("clinic", {})
        self.arm = arm
        self.full = {tuple(x) for x in c.get("full", [])}
        self.extra = {tuple(x) for x in c.get("extra", [])}
        self.taken = {tuple(x) for x in c.get("taken", [])}
        self.fail = set(c.get("fail", []))
        self.appointments = {a["booking_id"]: dict(a) for a in c.get("appointments", [])}
        self.initial_ids = set(self.appointments)
        self.booked = []          # successful bookings made in this run
        self.cancelled = []       # booking_ids cancelled in this run
        self.handoffs = []        # {reason, summary}
        self.events = []          # every call + result, in order
        self.offered = set()      # every "HH:MM" any tool returned to the model (date-agnostic, for slot checks)
        self.offered_by = set()   # (date, service, "HH:MM") triples returned by check_availability
        self._next_id = 2001

    # -- calendar
    def free(self, date, service):
        if (date.isoformat(), service) in self.full:
            return []
        slots = set(base_free(date, service))
        slots |= {t for (d, s, t) in self.extra if d == date.isoformat() and s == service}
        slots -= {t for (d, s, t) in self.taken if d == date.isoformat() and s == service}
        slots -= {b["time"] for b in self.appointments.values() if b["date"] == date.isoformat() and b["service"] == service}
        if date == NOW.date():
            slots = {t for t in slots if t > fmt(NOW.hour * 60 + NOW.minute)}
        return sorted(slots)

    # -- dispatcher
    def call(self, name, args):
        args = args if isinstance(args, dict) else {}
        fn = getattr(self, "t_" + str(name), None)
        if fn is None or (name == "find_date" and self.arm != "tool"):
            res = {"error": f"unknown tool: {name}"}
        elif name in self.fail:
            res = {"error": "the calendar system is not responding right now"}
        else:
            try:
                res = fn(**{k: v for k, v in args.items()})
            except TypeError as ex:
                res = {"error": f"bad arguments: {ex}"}
        self.events.append({"tool": name, "args": args, "result": res})
        return res

    # -- tools
    def t_find_date(self, days_from_today=None, weekday=None, occurrence=1, day_of_month=None):
        today = NOW.date()
        try:
            if days_from_today is not None:
                d = today + dt.timedelta(days=int(days_from_today))
            elif weekday is not None:
                w = WEEKDAYS_EN.index(str(weekday).lower())
                ahead = (w - today.weekday()) % 7 or 7          # strictly after today
                d = today + dt.timedelta(days=ahead + 7 * (int(occurrence or 1) - 1))
            elif day_of_month is not None:
                n, d = int(day_of_month), today
                for _ in range(62):
                    if d.day == n:
                        break
                    d += dt.timedelta(days=1)
                else:
                    return {"error": "no such day of month"}
            else:
                return {"error": "give days_from_today, weekday or day_of_month"}
        except (ValueError, TypeError):
            return {"error": "invalid arguments"}
        h = hours(d)
        return {"date": d.isoformat(), "weekday": WEEKDAYS_EN[d.weekday()], "weekday_ar": WEEKDAYS_AR[d.weekday()],
                "open": bool(h), "hours": f"{fmt(h[0])}-{fmt(h[1])}" if h else "closed"}

    def t_check_availability(self, service=None, date=None, time_window="any"):
        d = parse_date(date)
        if service not in SERVICES:
            return {"error": f"unknown service; use one of {SERVICES}"}
        if d is None:
            return {"error": "date must be YYYY-MM-DD"}
        if d < NOW.date():
            return {"error": "that date is in the past"}
        if (d - NOW.date()).days > HORIZON_DAYS:
            return {"error": f"bookings open only {HORIZON_DAYS} days ahead"}
        h = hours(d)
        base = {"date": d.isoformat(), "weekday": WEEKDAYS_EN[d.weekday()], "service": service}
        if not h:
            return {**base, "open": False, "note": "the clinic is closed on Fridays", "free_times": []}
        lo, hi = WINDOWS.get(time_window or "any", WINDOWS["any"])
        times = [t for t in self.free(d, service) if lo <= int(t[:2]) * 60 + int(t[3:]) < hi]
        for t in times:
            self.offered.add(t)
            self.offered_by.add((d.isoformat(), service, t))
        return {**base, "open": True, "hours": f"{fmt(h[0])}-{fmt(h[1])}", "free_times": times}

    def t_book_appointment(self, service=None, date=None, time=None, patient_name=None):
        d = parse_date(date)
        t = str(time or "").strip()
        if len(t) == 4 and t[1] == ":":
            t = "0" + t
        if service not in SERVICES or d is None:
            return {"ok": False, "error": "invalid service or date"}
        if not str(patient_name or "").strip():
            return {"ok": False, "error": "patient_name is required"}
        if t not in self.free(d, service):
            return {"ok": False, "error": "that time is not available"}
        bid = f"B-{self._next_id}"
        self._next_id += 1
        b = {"booking_id": bid, "service": service, "date": d.isoformat(), "time": t, "patient_name": str(patient_name).strip()}
        self.appointments[bid] = b
        self.booked.append(b)
        return {"ok": True, **b}

    def t_list_my_appointments(self):
        return {"appointments": [dict(b) for b in self.appointments.values()]}

    def t_cancel_appointment(self, booking_id=None):
        bid = str(booking_id or "").strip()
        if bid not in self.appointments:
            return {"ok": False, "error": "no appointment with that booking_id"}
        b = self.appointments.pop(bid)
        self.cancelled.append(bid)
        return {"ok": True, "cancelled": b}

    def t_handoff_to_human(self, reason=None, summary=""):
        self.handoffs.append({"reason": reason, "summary": summary})
        return {"ok": True, "message": "A staff member has been notified and will reply in this chat."}


# ---------------------------------------------------------------- the system prompt
DATE_TABLE_DAYS = 14


def date_table():
    rows = []
    for i in range(DATE_TABLE_DAYS):
        d = NOW.date() + dt.timedelta(days=i)
        tag = "اليوم" if i == 0 else "بكرة" if i == 1 else ""
        h = hours(d)
        rows.append(f"- {WEEKDAYS_AR[d.weekday()]} {d.isoformat()}" + (f" ({tag})" if tag else "") + ("" if h else " — مغلق"))
    return "\n".join(rows)


PROMPT_HEAD = """أنت موظف الاستقبال الرقمي لعيادة "ابتسامة" لطب الأسنان في دبي، وتردّ على رسائل واتساب.
الآن: الخميس 2026-11-05، الساعة 3:30 عصرًا.
ساعات العمل: الأحد إلى الخميس من 9 صباحًا إلى 9 مساءً. السبت من 10 صباحًا إلى 4 عصرًا. الجمعة مغلق.
الخدمات: فحص عام (checkup)، تنظيف (cleaning)، حشوة (filling)، تقويم (orthodontics)، تبييض (whitening)."""

DATE_HELP = {
    "base": "",
    "table": "\n\nالتقويم للأيام القادمة:\n" + date_table(),
    "tool": "\n\nلتحويل أي يوم يذكره العميل (بكرة، الأحد الجاي، يوم 12…) إلى تاريخ، استخدم find_date ولا تحسب التاريخ بنفسك.",
}

RULES = """

القواعد:
1. إذا عرفتَ الخدمة واليوم، استدعِ check_availability قبل اقتراح أي وقت، حتى لو لم تعرف اسم العميل بعد. لا تذكر أي وقت لم يظهر في نتيجة الأداة.
2. لا تستدعِ book_appointment إلا بعد أن يختار العميل وقتًا ظهر في نتيجة check_availability، وبعد معرفة اسمه.
3. إذا لم توجد أوقات فاضية أو كان اليوم مغلقًا، قل ذلك بوضوح واعرض أن تبحث له في يوم آخر.
4. إذا أعادت أي أداة خطأ، لا تخمّن ولا تخترع: أخبر العميل بصراحة واستدعِ handoff_to_human.
5. للإلغاء أو تغيير الموعد: استدعِ list_my_appointments أولًا. عند تغيير الموعد احجز الموعد الجديد أولًا ثم ألغِ القديم. إذا كان عند العميل أكثر من موعد ولم يحدد أيّها، اسأله.
6. لا تقل للعميل إن الموعد تم حجزه أو إلغاؤه إلا إذا أكدت الأداة ذلك (ok: true).
7. الحالات الطارئة (نزيف، تورم، ألم شديد، حرارة)، والشكاوى، والأسئلة الطبية: استدعِ handoff_to_human فورًا، حتى لو كنتما في منتصف حجز. لا يكفي أن تقول إنك ستحوّل الحالة؛ يجب استدعاء الأداة.
8. لا تخترع أسعارًا أو معلومات عن التأمين غير مذكورة هنا.
9. ردّ بلهجة العميل نفسها، باختصار، ومن غير نقاط أو عناوين."""


def system_prompt(arm):
    return PROMPT_HEAD + DATE_HELP[arm] + RULES


if __name__ == "__main__":
    # print the calendar for the next 14 days, to write episodes against
    for i in range(15):
        d = NOW.date() + dt.timedelta(days=i)
        print(d, WEEKDAYS_EN[d.weekday()][:3], "closed" if not hours(d) else "")
        if hours(d):
            for s in SERVICES:
                print(f"   {s:<13}", " ".join(Clinic().free(d, s)))
