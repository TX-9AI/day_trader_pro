#!/usr/bin/env python3
"""
tools/check_trade_report_fees.py  v1.0
v1.0  2026-09-07  dtp r311 / FEE.6 — the land gate for the fees column.

Pins the four properties that make this change safe to look at and unsafe to
"simplify" later. Every one is EXECUTED against the real `show()` and the real
`stats_of()`; none reads source text (WA §21).
"""
from __future__ import annotations
import io, contextlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import trade_report as tr                                        # noqa: E402

F: list = []
def check(n, ok, d=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"  — {d}" if d else ""))
    if not ok: F.append(n)

def _rows(n=4, **kw):
    r = dict(symbol="NVDA", strategy="ORBStrategy", setup_type="orb_break",
             contracts=2, status="closed", entry_premium=1.0,
             exit_premium=1.5, pnl_usd=100.0, option_side="call",
             exit_reason="orb_trail_stop", _hold=4.0)
    r.update(kw)
    return [dict(r, trade_id=f"t{i}") for i in range(n)]

def render(d, min_n=8):
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        tr.show("T", d, min_n)
    return b.getvalue()

def main() -> int:
    print("\ncheck_trade_report_fees\n")
    d = tr.bucket(_rows(4), "strategy")
    out = render(d)

    # T1 — the marker is gone from the RENDERED output, not from the source.
    check("T1  `<- thin` no longer renders on a below-min_n bucket",
          "<- thin" not in out, out.strip().splitlines()[-1][:60])
    check("T1b a FEES column renders instead", "FEES $" in out)

    # T2 — min_n SURVIVES as a threshold. Deleting the flag must not have
    # deleted the guard: rank() still refuses to name a bucket too thin.
    # ⚠️ A FIRST CUT OF THIS CHECK GUESSED AT `rank()`'s RETURN SHAPE and blew
    # up on a NoneType subscript. It is CALLED here, both ways, so the
    # assertion is about behaviour and not about my memory of a signature.
    thin_ranked = tr.rank(d, 8)          # every bucket n=4, so none eligible
    fat = tr.bucket(_rows(12), "strategy")
    fat_ranked = tr.rank(fat, 8)         # n=12, eligible
    check("T2  min_n STILL gates rank() — the threshold survived the marker",
          not thin_ranked and bool(fat_ranked),
          f"thin -> {thin_ranked!r}, fat -> "
          f"{'ranked' if fat_ranked else 'none'}")

    # T3 — ABSENCE IS NEVER ZERO. With the model unavailable the column must
    # read n/a, never 0.00. Driven by removing the module, not by asserting a
    # branch exists.
    saved = tr._fees
    try:
        tr._fees = None
        d2 = tr.bucket(_rows(4), "strategy")
        out2 = render(d2)
        # ⚠️ ASSERT ON THE FEE FIELD, NOT THE WHOLE LINE. A first cut checked
        # that "0.00" was absent from the row and went red on `400.00` in the
        # NET column — a check failing for a reason unrelated to what it
        # checks, which is worse than no check (WA §0.6).
        row = [l for l in out2.strip().splitlines() if "ORBStrategy" in l][0]
        st2 = tr.stats_of(_rows(4))
        check("T3  no fee model -> the column reads n/a, never 0.00",
              row.rstrip().rstrip("*").endswith("n/a") and st2["fees"] is None,
              f"tail={row.rstrip()[-14:]!r}  stats fees={st2['fees']!r}")
        check("T3b and the unpriced count is the WHOLE bucket, not zero",
              st2["fees_unpriced"] == 4, f"{st2['fees_unpriced']} of 4")
    finally:
        tr._fees = saved

    # T4 — fees are NEGATIVE and NET $ is untouched (still gross).
    st = tr.stats_of(_rows(4))
    check("T4  NET $ is still the GROSS sum — unchanged by this revision",
          abs(st["net"] - 400.0) < 1e-9, f"net={st['net']}")
    check("T4b the fee total is positive in the stats and rendered negative",
          st["fees"] is not None and st["fees"] > 0 and "-" in out,
          f"fees={st['fees']}")

    print()
    if F:
        print(f"check_trade_report_fees: FAIL ({len(F)}): {', '.join(F)}")
        return 1
    print("check_trade_report_fees: ALL PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
