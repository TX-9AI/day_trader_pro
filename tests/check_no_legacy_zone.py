#!/usr/bin/env python3
"""tests/check_no_legacy_zone.py  v1.0
OPS.22 — NO ZONE IS NAMED BY A LEGACY LINK; EVERY ZONE THE TREE NAMES RESOLVES HERE.

v1.0  2026-10-11  r479. tzdata 2026c moved the legacy links (US/Eastern and kin) into
      tzdata-legacy, which control does not install: ZoneInfo("US/Eastern") raised under
      bare python3 there (fleet.py after the 10-09 reboot), and a box whose OS took the
      same tzdata would have failed to import the condor and the ORB range. Every zone
      is now "America/New_York" — the zone US/Eastern linked to, so the rules are
      identical. Critiqued by OTV4TEST (MSG-QQQ-1011-18) before it was built. The SAME
      FILE runs in otv4, day_trader_pro and OTV4TEST (WA §38.9); it scans its own ROOT.

  Z1  no str constant ANYWHERE in the tree is a legacy link name (US/*, EST5EDT,
      CST6CDT, MST7MDT, PST8PDT) — the net: it also catches pandas tz="..." and a name
      held in a variable before it is used
  Z2  no ZONE ARGUMENT is a fixed abbreviation (EST, EDT, CST, ...): ZoneInfo(x),
      pytz.timezone(x), tz=x, tz_localize(x), tz_convert(x). A fixed -5 is wrong half
      the year. Matched only in argument position, so prose labels are untouched
  Z3  every zone NAME the tree passes in those positions (or holds in a *ZONE* /
      TIMEZONE constant) resolves under THIS interpreter — bare python3 included
  Z4  America/New_York keeps New York's rules: -05:00 / -04:00 either side of both
      2026 transitions (03-08 07:00Z, 11-01 06:00Z); and pytz agrees with zoneinfo
      when pytz is importable

Run:  python3 tests/check_no_legacy_zone.py   (stdlib only; any interpreter)
"""
import ast
import datetime as dt
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.abspath(__file__)
FAILS = []

LEGACY = re.compile(r"^(US/[A-Za-z_-]+|EST5EDT|CST6CDT|MST7MDT|PST8PDT)$")
ABBREV = {"EST", "EDT", "CST", "CDT", "MST", "MDT", "PST", "PDT", "ET"}
ZONE_FUNCS = {"ZoneInfo", "timezone", "tz_localize", "tz_convert"}


def ck(name, ok, det=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {det}" if det else ""))
    if not ok:
        FAILS.append(name)


def _fname(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def scan():
    legacy, abbrev, zones = [], [], {}
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in ("venv", ".git", "__pycache__", "node_modules")]
        for fn in fns:
            p = os.path.join(dp, fn)
            if not fn.endswith(".py") or os.path.abspath(p) == SELF:
                continue
            try:
                tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue
            rel = os.path.relpath(p, ROOT)
            for n in ast.walk(tree):
                if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                        and LEGACY.match(n.value):
                    legacy.append(f"{rel}:{n.lineno} {n.value!r}")
                args = []
                if isinstance(n, ast.Call):
                    if _fname(n) in ZONE_FUNCS and n.args:
                        args.append(n.args[0])
                    args += [k.value for k in n.keywords if k.arg in ("tz", "tzinfo", "zone")]
                elif isinstance(n, ast.Assign):
                    for t in n.targets:
                        nm = getattr(t, "id", "") or getattr(t, "attr", "")
                        if "ZONE" in nm.upper():
                            args.append(n.value)
                for a in args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        if a.value.upper() in ABBREV:
                            abbrev.append(f"{rel}:{a.lineno} {a.value!r}")
                        elif "/" in a.value or a.value in ("UTC", "GMT"):
                            zones.setdefault(a.value, f"{rel}:{a.lineno}")
    return legacy, abbrev, zones


print("\ncheck_no_legacy_zone\n")
legacy, abbrev, zones = scan()
ck("Z1  no legacy link name anywhere in the tree", not legacy,
   f"{len(legacy)}: {legacy[:6]}")
ck("Z2  no fixed abbreviation used as a zone", not abbrev, f"{abbrev[:6]}")

from zoneinfo import ZoneInfo                                   # noqa: E402
bad = []
for z, where in sorted(zones.items()):
    try:
        ZoneInfo(z)
    except Exception as exc:                                     # noqa: BLE001
        bad.append(f"{z} ({where}): {type(exc).__name__}")
ck(f"Z3  every zone named resolves under {sys.executable}", not bad and bool(zones),
   f"{len(zones)} named; unresolved {bad[:4]}")

ny, U = ZoneInfo("America/New_York"), dt.timezone.utc
want = [(dt.datetime(2026, 3, 8, 6, 59, tzinfo=U), -5), (dt.datetime(2026, 3, 8, 7, 1, tzinfo=U), -4),
        (dt.datetime(2026, 11, 1, 5, 59, tzinfo=U), -4), (dt.datetime(2026, 11, 1, 6, 1, tzinfo=U), -5)]
got = [(u.astimezone(ny).utcoffset().total_seconds() / 3600) for u, _ in want]
ck("Z4a America/New_York: -5/-4 across 03-08, -4/-5 across 11-01 (2026)",
   got == [w for _, w in want], f"{got}")
try:
    import pytz
    p_ny, p_us = pytz.timezone("America/New_York"), pytz.timezone("US/Eastern")
    diff = []
    t = dt.datetime(2026, 1, 1, tzinfo=U)
    while t.year == 2026:
        a, b, c = t.astimezone(ny).utcoffset(), t.astimezone(p_ny).utcoffset(), t.astimezone(p_us).utcoffset()
        if not (a == b == c):
            diff.append(t.isoformat())
        t += dt.timedelta(hours=6)
    ck("Z4b pytz America/New_York == pytz US/Eastern == zoneinfo, every 6 h of 2026",
       not diff, f"{diff[:3]}")
except ImportError:
    print("  NOTE  Z4b NOT RUN — pytz is not importable under this interpreter")

print()
if FAILS:
    print(f"check_no_legacy_zone: FAIL ({len(FAILS)}): {', '.join(FAILS)}")
    sys.exit(1)
print(f"check_no_legacy_zone: ALL PASS — {len(zones)} zone name(s), all resolvable")
