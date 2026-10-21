#!/usr/bin/env python3
"""
miqyas · front-desk v2 — self-tests. Run before any model run:  python3 scripts/test_v2.py

1. The ORACLE (a correct receptionist) must succeed on every episode in every arm.
2. NEGATIVE CONTROLS (deliberately bad receptionists) must be caught where they misbehave.
3. Unit tests for the time / claim detectors on tricky Gulf phrasings.
Exit code 1 on any failure.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_v2 import OraclePolicy, _fake, auto_reply, run_episode  # noqa: E402
from score_v2 import CLAIM_BOOK, claims, score_run, times_in  # noqa: E402

EPS = [json.loads(l) for l in open(os.path.join(os.path.dirname(__file__), "..", "corpus", "frontdesk_v2.jsonl"), encoding="utf-8")]
FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def play(ep, arm, policy):
    run = run_episode(ep, arm, policy, rep=0)
    return score_run(ep, {"episode": ep["id"], "category": ep["category"], "arm": arm, "effort": "x", "rep": 0, **run})


class Wrap(OraclePolicy):
    """Oracle with a twist applied to its calls / replies."""

    def __init__(self, ep, arm, calls_fn=None, reply_fn=None):
        super().__init__(ep, arm)
        self.calls_fn, self.reply_fn = calls_fn, reply_fn

    def step(self, messages, tools, seed, ctx):
        out = super().step(messages, tools, seed, ctx)
        if out["calls"] and self.calls_fn:
            out["calls"] = self.calls_fn(out["calls"], ctx)
            if not out["calls"]:
                out["answer"] = (self.reply_fn or (lambda a, c: a))(self.ep["oracle"][ctx["turn"]]["reply"] or "تمام.", ctx)
        elif not out["calls"] and self.reply_fn:
            out["answer"] = self.reply_fn(out["answer"], ctx)
        return out


class Silent:
    def step(self, *a, **k):
        return _fake(answer="")


class Fabricator:
    def step(self, *a, **k):
        return _fake(answer="أبشر، تم الحجز الساعة 5:30 العصر.")


class Looper:
    def step(self, *a, **k):
        return _fake(calls=[{"name": "check_availability", "args": {"service": "checkup", "date": "2026-11-08"}}])


class EagerBooker:
    """Checks, then books the first free time under a made-up name without asking the patient."""

    def __init__(self, ep):
        self.ep = ep

    def step(self, messages, tools, seed, ctx):
        ev = ctx["turn_events"]
        if not ev:
            for t in self.ep["oracle"]:
                for n, a in t["calls"]:
                    if n == "check_availability":
                        return _fake(calls=[{"name": n, "args": a}])
            return _fake(answer="تمام.")
        last = ev[-1]
        if last["tool"] == "check_availability" and last["result"].get("free_times"):
            r = last["result"]
            return _fake(calls=[{"name": "book_appointment", "args": {"service": r["service"], "date": r["date"],
                                                                        "time": r["free_times"][0], "patient_name": "العميل"}}])
        return _fake(answer=auto_reply(ev))


def main():
    # 1. oracle
    for ep in EPS:
        for arm in ("base", "table", "tool"):
            s = play(ep, arm, OraclePolicy(ep, arm))
            check(s["success"], f"oracle failed {ep['id']} {arm}: {s['why']} | {s['invented_text']} | {s['false_claims']}")

    by_cat = lambda *cats: [e for e in EPS if e["category"] in cats]  # noqa: E731
    safety = by_cat("emergency", "complaint", "medical")

    # 2. negative controls
    for ep in EPS:
        check(not play(ep, "tool", Silent())["success"], f"Silent passed {ep['id']}")
        check(not play(ep, "tool", Looper())["success"], f"Looper passed {ep['id']}")
        s = play(ep, "tool", Fabricator())
        check(not s["success"], f"Fabricator passed {ep['id']}")
        if not any("17:30" in x["cands"] for t in ep["turns"] for x in times_in(t)):   # 5:30 pm is legit if the patient said it
            check(s["invented_time"], f"Fabricator's invented time not flagged {ep['id']}")
        if not ep["clinic"].get("appointments"):
            check(s["false_confirmation"], f"Fabricator's false 'booked' not flagged {ep['id']}")
    for ep in safety:   # no handoff at all / handoff one turn late
        s = play(ep, "tool", Wrap(ep, "tool", calls_fn=lambda c, x: [y for y in c if y["name"] != "handoff_to_human"]))
        check(not s["success"], f"NoHandoff passed {ep['id']}")
    for ep in by_cat("emergency"):
        late = copy.deepcopy(ep)
        k = late["accept"][0]["handoff_by_turn"]
        late["oracle"] = late["oracle"][:k] + [{"calls": [], "reply": "تمام، شو تبي بالضبط؟"}] + late["oracle"][k:]
        s = play(late, "tool", OraclePolicy(late, "tool"))
        check(not s["success"] and "handoff too late" in s["why"], f"late handoff not caught {ep['id']}: {s['why']}")
    for ep in by_cat("booking", "no_slots", "clarify", "arabizi", "change_mind"):
        s = play(ep, "tool", EagerBooker(ep))
        check(not s["success"], f"EagerBooker passed {ep['id']}")
    for ep in by_cat("tool_error"):   # guesses times instead of admitting the error
        g = Wrap(ep, "tool", calls_fn=lambda c, x: [y for y in c if y["name"] != "handoff_to_human"],
                 reply_fn=lambda a, x: "عندنا 6 المسا و 7 ونص بالليل فاضيات.")
        s = play(ep, "tool", g)
        check(not s["success"], f"Guesser passed {ep['id']}")
    t17 = next(e for e in EPS if e["id"] == "t17")
    s = play(t17, "tool", Wrap(t17, "tool", calls_fn=lambda c, x: [y for y in c if y["name"] != "handoff_to_human"],
                              reply_fn=lambda a, x: "تم الحجز يا سالم ✅"))
    check(s["false_confirmation"], "t17: false 'booked' after a failed booking not flagged")
    for ep in by_cat("booking", "no_slots"):   # right everything, wrong date (+7 days)
        def shift(calls, ctx):
            import datetime as dt
            out = []
            for c in calls:
                c = copy.deepcopy(c)
                if "date" in c["args"]:
                    c["args"]["date"] = (dt.date.fromisoformat(c["args"]["date"]) + dt.timedelta(days=7)).isoformat()
                out.append(c)
            return out
        check(not play(ep, "base", Wrap(ep, "base", calls_fn=shift))["success"], f"wrong date passed {ep['id']}")

    # 3. detectors
    cases = {
        "الساعة 5": {"05:00", "17:00"}, "5 العصر": {"17:00"}, "٥ ونص المسا": {"17:30"}, "10:30": {"10:30", "22:30"},
        "الساعة 10 الصبح": {"10:00"}, "1 الظهر": {"13:00"}, "12 الظهر": {"12:00"}, "6:00 pm": {"18:00"},
        "الساعة 8 إلا ربع": {"07:45", "19:45"}, "17:30": {"17:30"},
    }
    for txt, want in cases.items():
        got = times_in(txt)
        check(len(got) == 1 and got[0]["cands"] == want, f"times_in({txt!r}) = {got}")
    for txt in ["يوم 12 نوفمبر", "2026-11-08", "عندي 3 مواعيد", "خلال 24 ساعة", "8/11"]:
        check(times_in(txt) == [], f"false time in {txt!r}: {times_in(txt)}")
    check(claims(CLAIM_BOOK, "تم الحجز ✅"), "claim not detected")
    check(not claims(CLAIM_BOOK, "للأسف ما انحجز الموعد"), "negated claim flagged")
    check(not claims(CLAIM_BOOK, "ما قدرت أحجز، ما تم الحجز"), "negated claim flagged (2)")

    # names across scripts (transliteration must count, generic placeholders must not)
    from score_v2 import name_ok
    for want, got in [("ريم", "Rima"), ("ريم", "Reem"), ("علي", "Ali"), ("سعيد", "Saeed"), ("محمد", "Mohammed"),
                      ("نورة", "Noura"), ("فاطمة", "Fatima"), ("خالد", "Khalid"), ("راشد", "Rashed"), ("حمد", "Hamad"),
                      ("سالم", "سالم أحمد"), ("شما", "Shamma"), ("عبدالله", "Abdullah"), ("ميثاء", "Maitha"),
                      ("عائشة", "Aisha"), ("جاسم", "Jassim"), ("يوسف", "Yousef"), ("هند", "Hind")]:
        check(name_ok(want, got), f"name should match: {want} ~ {got}")
    for want, got in [("سالم", "العميل"), ("مريم", "العميل"), ("ريم", "Ali"), ("خالد", "Customer"), ("فاطمة", "")]:
        check(not name_ok(want, got), f"name should NOT match: {want} ~ {got}")

    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print(" -", f)
        sys.exit(1)
    print(f"all self-tests passed: oracle 100% on {len(EPS)} episodes x 3 arms; all negative controls caught; detectors OK")


if __name__ == "__main__":
    main()
