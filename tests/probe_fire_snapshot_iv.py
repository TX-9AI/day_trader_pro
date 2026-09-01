#!/usr/bin/env python3
"""day_trader_pro/tests/probe_fire_snapshot_iv.py — v1.2
DOES THE BUCKET ACTUALLY CARRY `atm_iv`, AND FOR WHICH SYMBOLS?

v1.2  2026-08-31 — `price` and `atm_iv` live inside `payload`, a JSON STRING
      (derived/snapshot.py:170). v1.1 read the row and stopped one layer short.
      Nesting is envelope -> record[] -> payload -> the measurements; all three
      layers now read from source rather than inferred.
v1.1  2026-08-31 — the row key is `record`, not `rows`. v1.0 reported 29 good
      objects as UNUSABLE because it read the envelope as the row. Also prints
      the envelope and record keys, so a shape mismatch is visible rather than
      inferred from a column of zeroes.
v1.0  2026-08-31 — read-only diagnostic. Writes nothing, to S3 or to disk.

🔑 WHY THIS EXISTS. The operator asked for a fifteen-symbol ORB budget
estimate. The assistant had spot for about ten of them and IV for NONE, and a
table built on invented IVs would have looked precise, been fiction, and been
used to size real budgets (WORKING_AGREEMENT §0). The budget survey reads
`atm_iv` out of `derived_fire_snapshot` instead — and THAT ASSUMPTION IS
UNVERIFIED. This probe checks it before anything is built on top.

⚠️ `fire_snapshot` only writes WHEN A TRADE FIRES. A quiet box has no rows for
that date. Empty output for one symbol is not the same as a missing field, and
this prints the difference rather than collapsing them.

⚠️ THE ENVELOPE SHAPE IS NOT ASSUMED. The push format is reported back rather
than guessed at — which is what caught v1.0's own bug: it looked for a `rows`
key when `s3_push._wrap` writes `record`, so 29 perfectly good objects were
reported UNUSABLE. Reporting the shape instead of asserting it turned a
guessing loop into one read of the source.

⚠️ v1.1 ALSO PRINTS THE ENVELOPE KEYS on the first object of each date, so a
future format change is visible immediately rather than inferred from a column
of zeroes.

Usage:
    python3 tests/probe_fire_snapshot_iv.py
    python3 tests/probe_fire_snapshot_iv.py --date 2026-08-31
    python3 tests/probe_fire_snapshot_iv.py --days 5
"""
import argparse
import collections
import datetime as dt
import json
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

try:
    import warehouse_reader as WR
except Exception as exc:                                        # noqa: BLE001
    print(f"FATAL: cannot import warehouse_reader from {_root}: {exc}")
    sys.exit(2)

DATATYPE = "derived_fire_snapshot"


def _rows_of(env):
    """Rows from an envelope, without assuming its shape. Returns (rows, shape).

    🔴 v1.1 — v1.0 LOOKED FOR `rows` AND THE KEY IS `record`. `s3_push._wrap`
    (line 717) builds every envelope as
        {schema_version, datatype, symbol, dt, src_host, pushed_at_utc, record}
    and `push_derived` puts a BATCH of rows in `record` with `n_rows` beside it.
    So v1.0 counted each batch as a single row and looked for `price` at the
    envelope level, where it never was — and reported 29 usable-looking objects
    as UNUSABLE. The data was fine; the reader was wrong.
    ⚠️ Kept general on purpose: `record` may be a list (derived batches) or a
    single dict (per-row pushes from `push_table`), and both are handled.
    """
    if isinstance(env, dict):
        rec = env.get("record")
        if isinstance(rec, list):
            return rec, "envelope{record:[...]}"
        if isinstance(rec, dict):
            return [rec], "envelope{record:{...}}"
        if isinstance(env.get("rows"), list):
            return env["rows"], "dict{rows:[...]}"
        return [env], "bare dict (no `record` key — shape is NOT as pushed)"
    if isinstance(env, list):
        return env, "bare list"
    return [], f"unexpected {type(env).__name__}"


def _flatten(row):
    """A fire_snapshot row with its `payload` unpacked.

    🔴 v1.2 — THE THIRD LAYER. The row is
        {_rid, fired_ts, payload, symbol, trade_id}
    and `price` / `atm_iv` are inside `payload`, which
    `derived/snapshot.py:170` writes as `json.dumps(build_payload(ctx))` —
    a JSON STRING in a TEXT column. v1.1 read the row and stopped there.
    ⚠️ Handles payload as str OR dict: the column is text, but a future
    reader that pre-parses it should not silently produce zeroes again.
    """
    if not isinstance(row, dict):
        return {}
    pl = row.get("payload")
    if isinstance(pl, str):
        try:
            pl = json.loads(pl)
        except Exception:                                       # noqa: BLE001
            return row
    if isinstance(pl, dict):
        merged = dict(row)
        merged.update(pl)          # payload wins; it holds the measurements
        return merged
    return row


def probe_date(s3, date):
    try:
        objs = WR.read_prefix(s3, DATATYPE, date)
    except Exception as exc:                                    # noqa: BLE001
        # ⚠️ Named, never swallowed. A blank line here would read as "no data".
        print(f"  {date}  READ FAILED: {exc}")
        return None

    if not objs:
        print(f"  {date}  no objects under raw/{DATATYPE}/dt={date}/")
        return {}

    # ⚠️ Print the actual keys once per date. v1.0's failure was invisible
    # because a wrong reader and an empty table look identical.
    if objs:
        _s, _e = objs[0]
        if isinstance(_e, dict):
            print(f"    envelope keys: {sorted(_e.keys())}")
            _r = _e.get("record")
            if isinstance(_r, list) and _r and isinstance(_r[0], dict):
                print(f"    record[0] keys: {sorted(_r[0].keys())[:14]}"
                      f"{' ...' if len(_r[0]) > 14 else ''}")
                _f0 = _flatten(_r[0])
                _extra = sorted(set(_f0) - set(_r[0]))
                if _extra:
                    print(f"    payload keys: {_extra[:16]}"
                          f"{' ...' if len(_extra) > 16 else ''}")
            elif isinstance(_r, dict):
                print(f"    record keys: {sorted(_r.keys())[:14]}"
                      f"{' ...' if len(_r) > 14 else ''}")

    shapes = collections.Counter()
    per = {}
    for sym, env in objs:
        rows, shape = _rows_of(env)
        shapes[shape] += 1
        rows = [_flatten(r) for r in rows]
        tot = len(rows)
        with_iv = sum(1 for r in rows
                      if isinstance(r, dict) and r.get("atm_iv"))
        with_px = sum(1 for r in rows
                      if isinstance(r, dict) and r.get("price"))
        both = sum(1 for r in rows if isinstance(r, dict)
                   and r.get("atm_iv") and r.get("price"))
        ivs = [float(r["atm_iv"]) for r in rows
               if isinstance(r, dict) and r.get("atm_iv")]
        d = per.setdefault(sym, {"rows": 0, "iv": 0, "px": 0, "both": 0,
                                 "ivs": []})
        d["rows"] += tot
        d["iv"] += with_iv
        d["px"] += with_px
        d["both"] += both
        d["ivs"] += ivs

    print(f"  {date}  {len(objs)} object(s), envelope shape(s): "
          f"{dict(shapes)}")
    print(f"    {'sym':<6} {'rows':>6} {'price':>7} {'atm_iv':>7} "
          f"{'both':>6}   {'IV range':>18}")
    for sym in sorted(per):
        d = per[sym]
        rng = (f"{min(d['ivs']):.3f} - {max(d['ivs']):.3f}"
               if d["ivs"] else "—")
        flag = "" if d["both"] else "   <- UNUSABLE for the budget survey"
        print(f"    {sym:<6} {d['rows']:>6} {d['px']:>7} {d['iv']:>7} "
              f"{d['both']:>6}   {rng:>18}{flag}")
    return per


def main(argv):
    ap = argparse.ArgumentParser(description="probe derived_fire_snapshot")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (single date)")
    ap.add_argument("--days", type=int, default=3,
                    help="how many recent dates to probe (default 3)")
    a = ap.parse_args(argv)

    try:
        s3 = WR._client()
    except Exception as exc:                                    # noqa: BLE001
        print(f"FATAL: no S3 client: {exc}")
        return 2
    print(f"  bucket={getattr(WR, 'BUCKET', '?')}  prefix="
          f"{getattr(WR, 'PREFIX', '?')}/{DATATYPE}/")

    if a.date:
        dates = [a.date]
    else:
        try:
            first, last = WR.warehouse_range(s3, datatype=DATATYPE)
        except Exception as exc:                                # noqa: BLE001
            print(f"FATAL: cannot list partitions: {exc}")
            return 2
        if not last:
            print(f"  NO PARTITIONS AT ALL under raw/{DATATYPE}/.")
            print("  Nothing has ever been pushed for this table — the budget")
            print("  survey cannot be built on it. Check s3_push DERIVED_TABLES.")
            return 1
        print(f"  partitions present: {first} .. {last}")
        end = dt.date.fromisoformat(str(last))
        dates = [(end - dt.timedelta(days=i)).isoformat()
                 for i in range(a.days)]

    print()
    grand = collections.Counter()
    syms = set()
    for d in dates:
        per = probe_date(s3, d)
        print()
        if not per:
            continue
        for sym, v in per.items():
            syms.add(sym)
            grand["rows"] += v["rows"]
            grand["both"] += v["both"]

    print(f"  TOTAL across {len(dates)} date(s): {grand['rows']} row(s), "
          f"{grand['both']} usable (price AND atm_iv), "
          f"{len(syms)} symbol(s) seen")
    if not grand["both"]:
        print("  ⚠️  NOTHING USABLE. The budget survey needs price and atm_iv")
        print("      in the same row. Either no trades fired in this window,")
        print("      or atm_iv is not being populated at fire time.")
        return 1
    print("  ✓  usable rows exist — the budget survey can read this table.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
