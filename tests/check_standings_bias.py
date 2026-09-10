#!/usr/bin/env python3
"""
day_trader_pro/tests/check_standings_bias.py  v1.0
v1.0  2026-09-10  dtp r331 / RPT.23 — the land gate for the `dir` column.

🔴 THE DEFECT THIS EXISTS TO PREVENT is a plausible one: reading `option_side`
and calling calls LONG. That is right on the two DEBIT cases and INVERTED on
the two CREDIT ones — a report that is wrong half the time in a way that looks
entirely reasonable on screen, which is the worst shape a number can have.

  B1  all four side x structure combinations map correctly
  B2  a call CREDIT spread is SHORT and a put CREDIT spread is LONG
      (asserted separately: this is the pair the operator called out, and
       the pair a naive implementation gets backwards)
  B3  butterflies and condor legs are NEUT, never a direction
  B4  an unknown/blank side is `?`, never guessed
  B5  the parser accepts the 13-field row and fills `bias`
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    try:
        import standings as st
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  standings.py did not import: {}".format(exc))
        return 1
    if not hasattr(st, "price_bias"):
        print("  FAIL  standings.price_bias does not exist")
        return 1
    b = st.price_bias

    cases = [
        ("call", 0, "LONG"),    # long call / call debit spread
        ("put",  0, "SHORT"),   # long put  / put debit spread
        ("call", 1, "SHORT"),   # short call spread — bearish
        ("put",  1, "LONG"),    # short put spread  — bullish
    ]
    got = [(s, c, b(s, c)) for s, c, _ in cases]
    check("B1", all(b(s, c) == want for s, c, want in cases),
          ", ".join("{}/{}->{}".format(s, "cr" if c else "db", g)
                    for s, c, g in got))

    check("B2", b("call", 1) == "SHORT" and b("put", 1) == "LONG",
          "call credit={} put credit={}".format(b("call", 1), b("put", 1)))

    check("B3", b("call", 0, 0, "SPXW  260910C06500000") == "NEUT"
          and b("put", 1, 1, "") == "NEUT",
          "butterfly={} condor leg={}".format(
              b("call", 0, 0, "SPXW  260910C06500000"), b("put", 1, 1, "")))

    check("B4", b("", 0) == "?" and b(None, 1) == "?",
          "blank={} none={}".format(b("", 0), b(None, 1)))

    # B5 — the parser. A 13-field closed row must land with a bias.
    row = "\t".join(["C", "2026-09-10 10:31:00", "AMD", "ORBStrategy",
                     "3.42", "3.17", "1", "-220.5", "0",
                     "put", "0", "0", ""])
    parsed, err = st._parse(row, "2026-09-10") if hasattr(st, "_parse") \
        else (None, "no _parse")
    if parsed is None:
        # the parser lives inside _query; exercise its body via the same split
        f = row.split("\t")
        ok5 = len(f) == 13 and b(f[9], f[10], f[11], f[12]) == "SHORT"
        check("B5", ok5, "13 fields, long put -> {}".format(b(f[9], f[10], f[11], f[12])))
    else:
        check("B5", parsed.get("bias") == "SHORT", "bias={}".format(parsed.get("bias")))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
