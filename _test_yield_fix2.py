"""Edge-case validation for yield query fixes."""
from app.agents.analysis_agent.nodes.method_selector import _extract_station_filter, _extract_date_range
from datetime import date

# Quote variation tests
print("=== Station filter (quote variations) ===")
cases = [
    ('\u201cPOL\u6291\u5149\u201d\u5de5\u7ad9\u6700\u8fd17\u5929', '"POL\u6291\u5149"\u5de5\u7ad9'),
    ("'CMP\u5de5\u7ad9\u6700\u8fd17\u5929", "'CMP\u5de5\u7ad9"),
    ('"CVD\u6c89\u79ef"\u5de5\u7ad9', '"CVD\u6c89\u79ef"\u5de5\u7ad9'),
    ('POL\u6291\u5149\u5de5\u7ad9', 'POL\u6291\u5149\u5de5\u7ad9 (no quotes)'),
    ('\u7edf\u8ba1\u6bcf\u4e2a\u7ad9\u70b9\u6700\u8fd1\u4e00\u5468\u7684\u4e00\u6b21\u826f\u7387', '\u6bcf\u4e2a\u7ad9\u70b9 (should=no filter)'),
    ('\u60f3\u770b\u8fd9\u5468\u5404\u5de5\u7ad9\u826f\u7387\u8d8b\u52bf', '\u5404\u5de5\u7ad9 (should=no filter)'),
]

all_ok = True
for q, lbl in cases:
    r = _extract_station_filter(q).strip()
    ok = True
    if 'no filter' in lbl and r != '':
        ok = False
    mark = '  OK' if ok else '  FAIL'
    print(f"{mark} {lbl}")
    if r:
        print(f"      => {r}")
    all_ok = all_ok and ok

print()
print("=== Date range tests ===")
date_cases = [
    ('\u6700\u8fd17\u5929', 7),
    ('\u6700\u8fd1\u4e00\u5468', 7),
    ('\u6700\u8fd13\u5468', 21),
    ('\u6700\u8fd130\u5929', 30),
]
for q, expected_days in date_cases:
    s, e = _extract_date_range(q)
    delta = (date.fromisoformat(e) - date.fromisoformat(s)).days + 1
    ok = delta == expected_days
    mark = '  OK' if ok else '  FAIL'
    all_ok = all_ok and ok
    print(f"{mark} {repr(q)}: {delta}\u5929 (expected={expected_days})")

print()
print('ALL PASS' if all_ok else 'SOME FAILURES')
