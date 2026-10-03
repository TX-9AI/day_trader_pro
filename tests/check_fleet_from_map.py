#!/usr/bin/env python3
"""
tests/check_fleet_from_map.py  v1.0
v1.0  2026-10-03  r457 / OPS.64 — EVERY READER OF "WHICH BOXES EXIST" ASKS THE
      INSTANCE MAP. Operator: *"How can we reroute all those non-automatic tasks
      to also consult the instance map so it truly is completely automatic?"*

  THE CONTRACT, driven with a FAKE instance map (no AWS call is made):
    the map holds NEWBOX (tagged, never listed) and KEPT (tagged, listed);
    config.UNIVERSE also lists RETIRED (untagged — a retirement).
  F1  instance_registry.discover() with no list returns the MAP, not the list
  F2  fleet_members() is the map, sorted
  F3  map unreadable -> fleet_members() falls back to config.UNIVERSE, PRINTED
  F3b map empty      -> the same fallback, printed
  F4  eod_backfill._missing() on an empty tape dir reports the MAP's boxes and
      never RETIRED (the sat-out wake it feeds would otherwise wake a ghost)
  F5  wake_and_bake._discover(None) is the map
  F6  warehouse_coverage._members() is the map
  F7  s3_sweep protects a box strategy_registry has ever attributed (history
      survives retirement) and a newly tagged box, with no list edit
  F8  no dtp module still calls instance_registry.discover(config.UNIVERSE)
      (an AST scan of CALLS, so prose naming it is not flagged — the backstop for callers F1-F6 do not execute)
  F9  the production engine is named OTV4, and a legacy "MAIN" tag resolves to it

  BORN RED on dtp eb3ac22: F1 F2 F3 F3b F4 F5 F6 F7 F8 F9 (fleet_members, the
  map default, _members and the OTV4 name do not exist there).

Run:  cd ~/day_trader_pro && python3 tests/check_fleet_from_map.py
"""
import ast
import io
import contextlib
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


FAKE = {"NEWBOX": {"instance_id": "i-new", "state": "stopped", "pinned": False},
        "KEPT":   {"instance_id": "i-kept", "state": "running", "pinned": False}}


def main():
    import config
    import ec2ops
    import instance_registry as ir

    real = (ir.discover_fleet, config.UNIVERSE, ec2ops.describe_by_names)
    config.UNIVERSE = ["KEPT", "RETIRED"]
    ir.discover_fleet = lambda *a, **k: {k2: dict(v) for k2, v in FAKE.items()}
    ec2ops.describe_by_names = lambda names: {
        n: {"instance_id": f"i-{n.lower()}", "state": "stopped"} for n in names}
    try:
        try:
            m, _ = ir.discover()
            ck("F1", sorted(m) == ["KEPT", "NEWBOX"],
               f"discover() with no list is the instance map — got {sorted(m)}")
        except Exception as exc:                                  # noqa: BLE001
            ck("F1", False, f"{type(exc).__name__}: {exc}")

        fm = getattr(ir, "fleet_members", None)
        ck("F2", fm is not None and fm() == ["KEPT", "NEWBOX"],
           f"fleet_members() is the map — got {fm() if fm else 'ABSENT'}")

        def _boom(*a, **k):
            raise RuntimeError("EC2 unavailable")
        ir.discover_fleet = _boom
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = fm() if fm else None
        ck("F3", got == ["KEPT", "RETIRED"] and "falling back" in buf.getvalue(),
           f"unreadable map -> the list, printed — got {got}, "
           f"printed={'falling back' in buf.getvalue()}")
        ir.discover_fleet = lambda *a, **k: {}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = fm() if fm else None
        ck("F3b", got == ["KEPT", "RETIRED"] and "falling back" in buf.getvalue(),
           f"empty map -> the list, printed — got {got}")
        ir.discover_fleet = lambda *a, **k: {k2: dict(v) for k2, v in FAKE.items()}

        try:
            import eod_backfill
            with tempfile.TemporaryDirectory() as tmp:
                real_ohlc = config.OHLC_DIR
                config.OHLC_DIR = tmp
                eod_backfill.config.OHLC_DIR = tmp
                try:
                    miss = sorted(eod_backfill._missing("2026-10-02"))
                finally:
                    config.OHLC_DIR = real_ohlc
                    eod_backfill.config.OHLC_DIR = real_ohlc
            ck("F4", miss == ["KEPT", "NEWBOX"],
               f"_missing() reports the map's boxes, never RETIRED — got {miss}")
        except Exception as exc:                                  # noqa: BLE001
            ck("F4", False, f"{type(exc).__name__}: {exc}")

        try:
            import wake_and_bake
            got = sorted(wake_and_bake._discover(None))
            ck("F5", got == ["KEPT", "NEWBOX"], f"wake_and_bake sees the map — got {got}")
        except Exception as exc:                                  # noqa: BLE001
            ck("F5", False, f"{type(exc).__name__}: {exc}")

        import warehouse_coverage as wc
        mem = getattr(wc, "_members", None)
        try:
            got = mem() if mem else "ABSENT"
        except Exception as exc:                                  # noqa: BLE001
            got = f"{type(exc).__name__}"
        ck("F6", got == ["KEPT", "NEWBOX"], f"the coverage board's boxes are the map — got {got}")

        import s3_sweep
        import strategy_registry as sr
        if hasattr(s3_sweep, "_ENGINE_BOXES"):
            s3_sweep._ENGINE_BOXES = None
        hist = next((b for b in sr.MAIN_BOXES if b not in s3_sweep.PANEL), None)
        ok_hist = hist is not None and s3_sweep._is_protected(hist)
        ok_new = s3_sweep._is_protected("NEWBOX")
        ck("F7", ok_hist and ok_new,
           f"protected: retired-with-history {hist}={ok_hist}, newly tagged NEWBOX={ok_new}")
    finally:
        ir.discover_fleet, config.UNIVERSE, ec2ops.describe_by_names = real

    offenders = []
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git", "tests", "__pycache__")]
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(dirpath, f)
                src = open(path, encoding="utf-8", errors="replace").read()
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):   # CALLS only — prose may name it
                    if (isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "discover"
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "instance_registry"
                            and node.args
                            and isinstance(node.args[0], ast.Attribute)
                            and node.args[0].attr == "UNIVERSE"):
                        offenders.append(os.path.relpath(path, ROOT))
                        break
    ck("F8", not offenders, f"still passing the list to discover(): {offenders}")

    import strategy_registry as sr
    ck("F9", sr.MAIN == "OTV4"
       and sr.resolve_lineage({"lineage": "OTV4"}) == "OTV4"
       and sr.resolve_lineage({"lineage": "MAIN"}) == "OTV4"
       and sr.resolve_lineage({"lineage": "TEST"}) == "TEST",
       f"MAIN={sr.MAIN!r}; OTV4->{sr.resolve_lineage({'lineage': 'OTV4'})} "
       f"MAIN->{sr.resolve_lineage({'lineage': 'MAIN'})}")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — every reader of the fleet asks the instance map; the list is "
          "a printed fallback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
