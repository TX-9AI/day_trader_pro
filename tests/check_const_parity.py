#!/usr/bin/env python3
"""
day_trader_pro/tests/check_const_parity.py  v1.0
v1.0  2026-11-08  dtp r535 / CONST.1 — ONE OWNER FOR EVERY CONSTANT dtp AND OTV5 BOTH CARRY. The 11-07 Saturday brief
      (section 5 item 8; hygiene queue item 10) found the warehouse bucket as a literal default in 11 code sites, the
      engine epoch in 4, the box panel three times in dtp, and OTV5's OTV5_SINCE claiming to mirror dtp's while
      carrying one box. r535 makes config.WAREHOUSE_BUCKET / config.ENGINE_EPOCH the only dtp copies and
      selector.PANEL / s3_sweep's fallback read config.UNIVERSE. OTV5 owns every value a box uses; dtp cannot import
      OTV5 at runtime from every cwd and venv, so where a copy has to stay, this gate fails the day the two differ.

  P1  bucket: dtp config.WAREHOUSE_BUCKET's default == OTV5 warehouse/s3_push.BUCKET's default == OTV5
      tests/warehouse_source.BUCKET's default == deploy/s3-push.service's OT_S3_BUCKET; every one reads OT_S3_BUCKET.
  P2  no dtp code site (outside config.py, comments and tests/) carries the bucket literal.
  P3  epoch: dtp config.ENGINE_EPOCH's default == OTV5 tests/trade_report.ENGINE_EPOCH's default ==
      tests/warehouse_source.DAY_ONE == tests/brief_bias_join.EPOCH; dtp trade_report's standalone fallback agrees, and no
      other dtp module binds ENGINE_EPOCH / EPOCH / DAY_ONE to a literal (TEST_EPOCH, ARTIFACT_EPOCH are other dates).
  P4  the OTV4TEST fleet: OTV5 warehouse_source.OTV4TEST_BOXES == dtp strategy_registry.TEST_BOXES (as sets), and for
      every OTV4TEST box OTV5 warehouse_source.OTV5_SINCE agrees with dtp strategy_registry.OTV5_SINCE (both absent,
      or the same day). The OTV4TEST filter and the registry must answer the same row the same way.
  P5  the calendar: dtp market_calendar and OTV5 utils/market_calendar agree on the holiday set, the early closes,
      and the trading-day and half-day verdict of every day 2026-01-01..2050-12-31.
  P6  the dxlink node book: dtp tools/dxlink_probe.FORGET_S == OTV5 data/candle_feed.NODE_FORGET_S.
  P7  the panel: selector.PANEL and s3_sweep's fallback are config.UNIVERSE (no literal list left in either file).
  P8  wake_and_bake._in_rth follows the calendar: a weekday holiday is not RTH, 11-27 14:00 is not RTH, 11-27 10:00
      and an ordinary 15:59 are, 16:01 is not.
  P9  CONTROL: the extractors flag a fixture pair that differs (bucket, epoch, OTV5_SINCE, forget), so a green P1-P6
      is not an extractor that always returns equal values.

Run:  venv/bin/python tests/check_const_parity.py      (DTP_OTV5_DIR, default ~/OTV5)
"""
from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OTV5 = os.path.expanduser(os.environ.get("DTP_OTV5_DIR", "~/OTV5"))
sys.path.insert(0, ROOT)

FAILED, RAN = [], []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    RAN.append(name)
    if not ok:
        FAILED.append(name)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def env_default(src, name):
    """(env_key, default) of the first module-level `NAME = os.environ.get("KEY", "DEFAULT")` in src, else (None, None)."""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            v = node.value
            if (isinstance(v, ast.Call) and getattr(v.func, "attr", "") == "get" and len(v.args) == 2
                    and all(isinstance(a, ast.Constant) for a in v.args)):
                return v.args[0].value, v.args[1].value
    return None, None


def const(src, name):
    """The value of a module-level `NAME = <literal>` in src, else None."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except Exception:                                           # noqa: BLE001
                return None
    return None


def int_expr(src, name):
    """The integer value of a module-level `NAME = <arithmetic of literals>` (e.g. 14 * 86400), else None."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            try:
                return int(eval(compile(ast.Expression(node.value), "<c>", "eval"), {"__builtins__": {}}))
            except Exception:                                           # noqa: BLE001
                return None
    return None


def unit_value(text, key):
    for line in text.splitlines():
        m = re.match(r'^Environment="?%s=([^"\s]+)"?\s*$' % re.escape(key), line.strip())
        if m:
            return m.group(1)
    return None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


def code_literals(path, needle):
    """Lines of a .py where `needle` sits in a string constant outside a docstring or comment."""
    src = read(path)
    tree = ast.parse(src)
    doc = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                doc.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and needle in node.value \
                and id(node) not in doc:
            out.append(node.lineno)
    return out


def dtp_code_files():
    for d, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(d, ROOT)
        parts = rel.split(os.sep)
        if parts[0] in ("venv", ".git", "tests", "docs", "reports", "data", "__pycache__") or "__pycache__" in parts:
            dirs[:] = []
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(d, f)


# ── P1-P3 extractors (shared with the P9 control) ──────────────────────────────────────────────────────────────────
def bucket_pairs(dtp_config, s3_push, wsrc, unit):
    return {
        "dtp config.WAREHOUSE_BUCKET": env_default(dtp_config, "WAREHOUSE_BUCKET"),
        "OTV5 warehouse/s3_push.BUCKET": env_default(s3_push, "BUCKET"),
        "OTV5 tests/warehouse_source.BUCKET": env_default(wsrc, "BUCKET"),
        "OTV5 deploy/s3-push.service": ("OT_S3_BUCKET", unit_value(unit, "OT_S3_BUCKET")),
    }


def epoch_values(dtp_config, otv5_report, wsrc, bbj):
    return {
        "dtp config.ENGINE_EPOCH": env_default(dtp_config, "ENGINE_EPOCH")[1],
        "OTV5 tests/trade_report.ENGINE_EPOCH": env_default(otv5_report, "ENGINE_EPOCH")[1],
        "OTV5 tests/warehouse_source.DAY_ONE": const(wsrc, "DAY_ONE"),
        "OTV5 tests/brief_bias_join.EPOCH": const(bbj, "EPOCH"),
    }


def since_disagreements(test_boxes, otv5_since, dtp_since):
    return [b for b in sorted(test_boxes) if otv5_since.get(b) != dtp_since.get(b)]


def main():
    print(f"CONST PARITY: dtp {ROOT} against OTV5 {OTV5}")
    p = lambda *a: os.path.join(OTV5, *a)                               # noqa: E731
    dtp_config = read(os.path.join(ROOT, "config.py"))
    s3_push, wsrc = read(p("warehouse", "s3_push.py")), read(p("tests", "warehouse_source.py"))
    unit, otv5_report = read(p("deploy", "s3-push.service")), read(p("tests", "trade_report.py"))
    bbj = read(p("tests", "brief_bias_join.py"))

    # P1
    pairs = bucket_pairs(dtp_config, s3_push, wsrc, unit)
    vals = {k: v[1] for k, v in pairs.items()}
    keys = {k: v[0] for k, v in pairs.items()}
    check("P1 one bucket in both repos", len(set(vals.values())) == 1 and None not in vals.values(), str(vals))
    check("P1 every bucket default reads OT_S3_BUCKET", set(keys.values()) == {"OT_S3_BUCKET"}, str(keys))

    # P2
    bucket = vals["dtp config.WAREHOUSE_BUCKET"] or "vertigo-warehouse-tx9ai"
    stray = []
    for f in dtp_code_files():
        if os.path.relpath(f, ROOT) == "config.py":
            continue
        for ln in code_literals(f, bucket):
            stray.append(f"{os.path.relpath(f, ROOT)}:{ln}")
    check("P2 no dtp code site outside config.py carries the bucket literal", not stray, ", ".join(stray))

    # P3
    ev = epoch_values(dtp_config, otv5_report, wsrc, bbj)
    check("P3 one engine epoch in both repos", len(set(ev.values())) == 1 and None not in ev.values(), str(ev))
    epoch = ev["dtp config.ENGINE_EPOCH"]
    tr = read(os.path.join(ROOT, "trade_report.py"))
    fallback = re.findall(r'os\.environ\.get\("DTP_ENGINE_EPOCH", "([0-9-]+)"\)', tr)
    check("P3 dtp trade_report's standalone fallback is the same epoch", fallback == [epoch], str(fallback))
    other = []
    for f in dtp_code_files():
        rel = os.path.relpath(f, ROOT)
        if rel in ("config.py", "trade_report.py"):
            continue
        # the ENGINE epoch by name (ENGINE_EPOCH, EPOCH, DAY_ONE) - TEST_EPOCH and ARTIFACT_EPOCH are other dates
        for m in re.finditer(r'^\s*(?:ENGINE_EPOCH|EPOCH|DAY_ONE)\s*=\s*(?!config\.).*"(\d{4}-\d\d-\d\d)"', read(f), re.M):
            other.append(f"{rel}: {m.group(1)}")
    check("P3 no other dtp module-level engine-epoch literal (ENGINE_EPOCH / EPOCH / DAY_ONE)", not other,
          ", ".join(other))

    # P4
    import strategy_registry as SR
    ws = load("_ws_parity", p("tests", "warehouse_source.py"))
    check("P4 OTV4TEST boxes: OTV5 warehouse_source == dtp strategy_registry.TEST_BOXES",
          set(ws.OTV4TEST_BOXES) == set(SR.TEST_BOXES), f"{sorted(ws.OTV4TEST_BOXES)} vs {sorted(SR.TEST_BOXES)}")
    dis = since_disagreements(SR.TEST_BOXES, ws.OTV5_SINCE, SR.OTV5_SINCE)
    check("P4 OTV5_SINCE agrees on every OTV4TEST box", not dis,
          ", ".join(f"{b}: OTV5 {ws.OTV5_SINCE.get(b)} dtp {SR.OTV5_SINCE.get(b)}" for b in dis))

    # P5
    dmc = load("_dmc_parity", os.path.join(ROOT, "market_calendar.py"))
    omc = load("_omc_parity", p("utils", "market_calendar.py"))
    dh = {str(x)[:10] for x in dmc.HOLIDAYS_US}
    oh = {str(x)[:10] for x in omc.US_MARKET_HOLIDAYS}
    check("P5 the holiday sets are equal", dh == oh,
          f"only dtp {sorted(dh - oh)[:5]} only OTV5 {sorted(oh - dh)[:5]}")
    de = {str(x)[:10] for x in getattr(dmc, "EARLY_CLOSES", {})}
    oe = {str(x)[:10] for x in getattr(omc, "EARLY_CLOSES", {})}
    check("P5 the early-close sets are equal", de == oe and len(de) > 0,
          f"only dtp {sorted(de - oe)[:5]} only OTV5 {sorted(oe - de)[:5]}")
    bad, day, n = [], dt.date(2026, 1, 1), 0
    while day <= dt.date(2050, 12, 31):
        a = (bool(dmc.is_trading_day(day)), bool(dmc.is_half_day(day)))
        b = (bool(omc.is_trading_day(day)), bool(omc.is_half_day(day)))
        if a != b:
            bad.append(f"{day} dtp {a} OTV5 {b}")
        day += dt.timedelta(days=1)
        n += 1
    check(f"P5 trading and half-day verdicts agree on all {n} days 2026-2050", not bad, ", ".join(bad[:5]))

    # P6
    fd = int_expr(read(os.path.join(ROOT, "tools", "dxlink_probe.py")), "FORGET_S")
    fo = int_expr(read(p("data", "candle_feed.py")), "NODE_FORGET_S")
    check("P6 dxlink FORGET_S == candle_feed NODE_FORGET_S", fd is not None and fd == fo, f"dtp {fd} OTV5 {fo}")

    # P7
    import config
    import selector
    check("P7 selector.PANEL is config.UNIVERSE", list(selector.PANEL) == list(config.UNIVERSE))
    sel_src, sw_src = read(os.path.join(ROOT, "selector.py")), read(os.path.join(ROOT, "s3_sweep.py"))
    lit = re.compile(r'\{?\[?"NVDA", "SPX", "QQQ"')
    check("P7 no literal fleet list left in selector.py or s3_sweep.py",
          not lit.search(sel_src) and not lit.search(sw_src))

    # P8
    import wake_and_bake as W
    ET = W._ET
    cases = [
        (dt.datetime(2026, 11, 26, 11, 0, tzinfo=ET), False, "Thanksgiving 11:00"),
        (dt.datetime(2026, 11, 27, 14, 0, tzinfo=ET), False, "11-27 half day 14:00"),
        (dt.datetime(2026, 11, 27, 10, 0, tzinfo=ET), True, "11-27 half day 10:00"),
        (dt.datetime(2026, 11, 9, 15, 59, tzinfo=ET), True, "11-09 15:59"),
        (dt.datetime(2026, 11, 9, 16, 1, tzinfo=ET), False, "11-09 16:01"),
        (dt.datetime(2026, 11, 7, 11, 0, tzinfo=ET), False, "Saturday 11:00"),
    ]
    wrong = [f"{lbl}: {W._in_rth(t)}" for t, want, lbl in cases if bool(W._in_rth(t)) != want]
    check("P8 wake_and_bake._in_rth follows the calendar", not wrong, ", ".join(wrong))

    # P9 control
    cfg_a = 'X = 1\nWAREHOUSE_BUCKET = os.environ.get("OT_S3_BUCKET", "bucket-a")\nENGINE_EPOCH = os.environ.get("DTP_ENGINE_EPOCH", "2026-09-01")\n'
    push_b = 'BUCKET = os.environ.get("OT_S3_BUCKET", "bucket-b")\n'
    ws_c = 'BUCKET = os.environ.get("OT_WAREHOUSE_BUCKET", "bucket-a")\nDAY_ONE = "2026-08-25"\n'
    unit_q = 'Environment="OT_S3_BUCKET=bucket-a"\n'
    fp = bucket_pairs(cfg_a, push_b, ws_c, unit_q)
    fe = epoch_values(cfg_a, 'ENGINE_EPOCH = os.environ.get("DTP_ENGINE_EPOCH", "2026-09-01")\n', ws_c, 'EPOCH = "2026-09-01"\n')
    ok = (len({v[1] for v in fp.values()}) > 1 and {v[0] for v in fp.values()} != {"OT_S3_BUCKET"}
          and fp["OTV5 deploy/s3-push.service"][1] == "bucket-a" and len(set(fe.values())) > 1
          and since_disagreements(("SOFI", "AAL"), {"SOFI": "2026-10-25"}, {"SOFI": "2026-10-26"}) == ["SOFI"]
          and since_disagreements(("SOFI", "AAL"), {"SOFI": "2026-10-25"}, {"SOFI": "2026-10-25"}) == []
          and int_expr("NODE_FORGET_S = 14 * 86400\n", "NODE_FORGET_S") == 1209600
          and int_expr("FORGET_S = 7 * 86400\n", "FORGET_S") != 1209600)
    check("P9 CONTROL: the extractors see a differing fixture pair", ok, f"{fp} {fe}")

    print(f"check_const_parity: {'ALL PASS' if not FAILED else 'FAIL ' + ' '.join(FAILED)} ({len(RAN)} checks)")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
