#!/usr/bin/env python3
"""
day_trader_pro/tests/check_standings_parse.py  v1.1
v1.1  2026-09-10  dtp r345 - S6 and S7, the accounting invariant. r342 fixed
      the strip(); this pins the CLASS. Every line a box sends must land in
      exactly one bucket - closed, open or dropped - so a reader can never
      again turn "I could not parse this" into "there is nothing here". r331
      hid one row per box per run for a whole session and nothing in the
      report could notice.
v1.0  2026-09-10  dtp r342 / RPT.25 — the row the panel could not read.

🔴 THE REGRESSION, EXACTLY AS IT HAPPENED. r331 appended `center_symbol` as
the LAST field. It is empty on everything but a butterfly, so an open row's
line ENDS IN A TAB — and rows arrive `ORDER BY 1`, so 'C' sorts before 'O'
and the OPEN row is ALWAYS LAST. `(out or "").strip().splitlines()` removed
that trailing tab, the row parsed as 12 fields, and `continue` dropped it in
silence. Report 45 printed no open section while the box held a live credit
spread with margin against it.

  S1  an open row whose LAST field is empty survives the transport
  S2  it is classified LIVE, so the ● marker and the section render
  S3  closed rows are unaffected
  S4  a genuinely malformed row is COUNTED, not silently discarded
  S6  ACCOUNTING: every line the box sent lands in exactly one bucket —
      received == closed + open + dropped. r331 hid one row per box per run
      for a whole session and no invariant could notice; this is that
      invariant.
  S7  a malformed row is accounted for as DROPPED, not simply lost
  S5  no `.strip()` before `splitlines()` — the fix, pinned in source, because
      the next author reaching for it would reintroduce this exactly
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


CLOSED = "C\t2026-09-10 12:29:00\tNVDA\tSweepCreditSpread\t0.44\t0\t5\t-35.0\t220\tput\t1\t1\t"
OPEN = "O\t2026-09-10 12:40:15\tNVDA\tSweepCreditSpread\t0.435\t0.41\t5\t\t0.435\tput\t0\t1\t"
JUNK = "O\t2026-09-10 12:40:15\tNVDA\tShortRow"


def main():
    try:
        import standings
        import ssh_util
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  standings did not import: {}".format(exc))
        return 1

    def feed(lines):
        ssh_util.ssh_run = lambda ip, cmd, timeout=None: (0, "\n".join(lines), "")
        return standings._query("1.2.3.4", "-4 hours", "2026-09-10")

    d, e = feed([CLOSED, OPEN])
    if d is None:
        print("  FAIL  _query returned no data: {}".format(e))
        return 1

    check("S1", len(d["rows_open"]) == 1,
          "{} open row(s) survived (open row is LAST and ends in a tab)"
          .format(len(d["rows_open"])))
    check("S2", d["open_today"] == 1 and d["open_stale"] == 0,
          "open_today={} open_stale={}".format(d["open_today"], d["open_stale"]))
    check("S3", d["closed"] == 1 and abs(d["net"] + 35.0) < 1e-9,
          "closed={} net={}".format(d["closed"], d["net"]))

    d2, _ = feed([CLOSED, JUNK])
    check("S4", d2.get("dropped") == 1 and d2["closed"] == 1,
          "dropped={} (counted, not swallowed)".format(d2.get("dropped")))

    # ⚠️ CODE LINES ONLY. The fix's own header explains the bug and therefore
    # contains the offending phrase; a naive grep fails on the documentation
    # that exists to prevent the bug.
    check("S6", d.get("received") == 2
          and d["received"] == len(d["rows_closed"]) + len(d["rows_open"])
          + len(d["rows_ghost"]) + d.get("dropped", 0),
          "received={} accounted={}".format(d.get("received"),
                                            d.get("accounted")))
    check("S7", d2.get("received") == 2 and d2.get("accounted") == 2
          and d2.get("dropped") == 1,
          "received={} accounted={} dropped={}".format(
              d2.get("received"), d2.get("accounted"), d2.get("dropped")))

    src = open(os.path.join(REPO, "standings.py"), encoding="utf-8").read()
    bad = [ln for ln in src.splitlines()
           if "strip().splitlines()" in ln and not ln.lstrip().startswith("#")]
    check("S5", not bad,
          "strip() before splitlines() is back at: {}".format(bad[0].strip()[:60])
          if bad else "no strip() ahead of splitlines() in code")

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
