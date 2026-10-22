"""Replace phone-like numbers in published transcripts with «[رقم محذوف]».
Models sometimes invent phone numbers that may belong to real people. Originals are kept privately
(private/qt01_results.tar.gz). ISO dates, times and booking ids are not touched.
Usage: python3 scripts/redact_phones.py <file.jsonl|file.csv> ...   (in place; prints the count)"""
import json, re, sys

P = re.compile(r"(?<![\d:/])(\+?\d[\d\- ]{6,}\d)(?![\d:])")
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}|20\d{2}[01]\d[0-3]\d)$")   # 2026-11-07 or 20261107
MARK = "[رقم محذوف]"


def redact(text):
    n = 0
    def sub(m):
        nonlocal n
        s = m.group(1)
        if DATE.match(s.strip()) or len(re.sub(r"\D", "", s)) < 7:
            return s
        n += 1
        return MARK
    return P.sub(sub, text), n


def walk(o):
    if isinstance(o, str):
        return redact(o)
    if isinstance(o, list):
        out, n = [], 0
        for x in o:
            y, k = walk(x); out.append(y); n += k
        return out, n
    if isinstance(o, dict):
        out, n = {}, 0
        for key, x in o.items():
            y, k = walk(x); out[key] = y; n += k
        return out, n
    return o, 0


for path in sys.argv[1:]:
    total = 0
    if path.endswith(".jsonl"):
        lines = []
        for l in open(path, encoding="utf-8"):
            if l.strip():
                o, n = walk(json.loads(l)); total += n
                lines.append(json.dumps(o, ensure_ascii=False))
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    else:
        t, total = redact(open(path, encoding="utf-8-sig").read())
        open(path, "w", encoding="utf-8-sig").write(t)
    print(f"{path}: {total} redacted")
