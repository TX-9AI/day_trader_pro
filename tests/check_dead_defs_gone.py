#!/usr/bin/env python3
# day_trader_pro/tests/check_dead_defs_gone.py — v1.1
# v1.1 (2026-11-15) — dtp r561 / B5.8 (the 11-14 Saturday brief section 5 item 8). THE THREE GEX-FLY STUDY TOOLS STAY GONE.
#   tools/bfly_pin_study.py, tools/bfly_reach_probe.py and tools/pin_strength_study.py (825 lines) studied GEXPinButterfly,
#   removed at OTV5 r103/r107; no menu item, timer, cron, prompt or study read them. r561 deletes them and their test
#   tests/test_pin_strength.py, and re-points test_warehouse_cache C6 at tools/stop_report.py. BORN RED on r560 at D4.
#   D4   the three tools and test_pin_strength.py are not in the tree, and no dtp module (tests included) names one of
#        their files in a string (an import by path, a subprocess, a menu row)
#   D4b  the kept tool C6 now reads, tools/stop_report.py (CLI; its own test is test_excursion_reports), is there and still writes via report_path and closes its cache
#        in a finally
# v1.0 (2026-11-14) — dtp r559 / B5.6 (the 11-14 Saturday brief section 5 item 6). THE THREE DEAD dtp DEFS STAY GONE.
#   wake_and_bake.stage_pyclear (dead since the EMERGENCY STOP dropped its pycache clear, 2026-07-18, 1edfc41),
#   orchestrator._fmt_score and strategy_registry.lineages_for had no caller anywhere in dtp, OTV5, the control units,
#   the timers or the prompts. r559 deletes them and wake_and_bake's unread `import eod_report`. BORN RED on r558 at D1.
#   Mirrors OTV5 tests/check_retired_gone.py G15/G16 (r118, r119): a guard on the deleted names AND on the kept
#   neighbours, so a "cleanup" that takes a live helper with it is caught too.
#
#   D1   no dtp module (tests excluded) DEFINES any deleted name again
#   D1b  the neighbours that stay are still defined: stage_restart, stage_shutdown, PYCLEAR (+ RESTART_CMD runs it),
#        _short, _format_ack, status, superseded_by, resolve_lineage, box_lineage
#   D2   wake_and_bake does not import eod_report (nothing in it reads that module)
#   D3   --shutdown-only's argparse help no longer advertises a pycache clear (the mode has none since 2026-07-18)
#
# ON THE AST, NOT A GREP: the headers that record the deletion name every deleted def, so a grep would see them.
# Run:  venv/bin/python tests/check_dead_defs_gone.py
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"venv", ".git", "__pycache__", "tests", "node_modules"}

DELETED = {
    "stage_pyclear": "wake_and_bake.py",
    "_fmt_score": "orchestrator.py",
    "lineages_for": "strategy_registry.py",
}
KEPT = {
    "wake_and_bake.py": ("stage_restart", "stage_shutdown"),
    "orchestrator.py": ("_short", "_format_ack"),
    "strategy_registry.py": ("status", "superseded_by", "resolve_lineage", "box_lineage"),
}
# B5.8 (r561): files deleted whole. Named by FILE, because a module is reached by path (spec_from_file_location,
# subprocess, the menu), not only by import.
DELETED_FILES = (
    "tools/bfly_pin_study.py",
    "tools/bfly_reach_probe.py",
    "tools/pin_strength_study.py",
    "tests/test_pin_strength.py",
)

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _tree(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return ast.parse(f.read(), filename=rel)


def _defs(tree):
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _assigns(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = n.value
    return out


def _modules():
    for d, ds, fs in os.walk(ROOT):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            if f.endswith(".py"):
                yield os.path.relpath(os.path.join(d, f), ROOT)


def main():
    print("check_dead_defs_gone — the dead dtp defs (r559 / B5.6) and the GEX-fly study tools (r561 / B5.8) stay gone")

    # D1 — no module defines a deleted name
    back = []
    for rel in sorted(_modules()):
        try:
            names = _defs(_tree(rel))
        except SyntaxError as exc:
            check(f"D1 {rel} parses", False, repr(exc))
            continue
        back += [f"{rel}:{n}" for n in DELETED if n in names]
    check("D1 no dtp module defines stage_pyclear / _fmt_score / lineages_for", not back, ", ".join(back))

    # D1b — the neighbours that stay
    for rel, names in KEPT.items():
        have = _defs(_tree(rel))
        missing = [n for n in names if n not in have]
        check(f"D1b {rel} keeps {', '.join(names)}", not missing, f"missing {missing}")
    wb = _tree("wake_and_bake.py")
    a = _assigns(wb)
    runs = "RESTART_CMD" in a and any(isinstance(n, ast.Name) and n.id == "PYCLEAR"
                                      for n in ast.walk(a["RESTART_CMD"]))
    check("D1b wake_and_bake keeps PYCLEAR and RESTART_CMD runs it", "PYCLEAR" in a and runs)

    # D2 — the unread eod_report import stays out of wake_and_bake
    imported = set()
    for n in ast.walk(wb):
        if isinstance(n, ast.Import):
            imported |= {x.name.split(".")[0] for x in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    check("D2 wake_and_bake does not import eod_report", "eod_report" not in imported)

    # D3 — the --shutdown-only help string is the definition an operator reads; it must not promise a pycache clear
    help_ = None
    for n in ast.walk(wb):
        if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_argument"
                and any(isinstance(x, ast.Constant) and x.value == "--shutdown-only" for x in n.args)):
            for kw in n.keywords:
                if kw.arg == "help":
                    help_ = ast.literal_eval(kw.value)
    h = (help_ or "").lower().replace("no pycache clear", "")
    check("D3 --shutdown-only help does not advertise a pycache clear",
          help_ is not None and "pycache" not in h, repr(help_))

    # D4 — the B5.8 files are gone and nothing reaches them by file name
    present = [f for f in DELETED_FILES if os.path.exists(os.path.join(ROOT, f))]
    check("D4 the GEX-fly study tools and test_pin_strength.py are not in the tree", not present, ", ".join(present))
    stems = [os.path.basename(f) for f in DELETED_FILES]
    me = os.path.relpath(os.path.abspath(__file__), ROOT)
    named = []
    for d, ds, fs in os.walk(ROOT):
        ds[:] = [x for x in ds if x not in (SKIP_DIRS - {"tests"})]
        for f in fs:
            if not f.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(d, f), ROOT)
            if rel == me:
                continue
            try:
                tree = _tree(rel)
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    named += [f"{rel}:{n.lineno}:{st}" for st in stems if st in n.value]
                elif isinstance(n, (ast.Import, ast.ImportFrom)):
                    mods = [x.name for x in n.names] if isinstance(n, ast.Import) else [n.module or ""] + [x.name for x in n.names]
                    named += [f"{rel}:{n.lineno}:{m}" for m in mods
                              for st in stems if m.split(".")[-1] == st[:-3]]
    check("D4 no dtp module names a deleted fly tool's file", not named, ", ".join(named))

    # D4b — the live tool test_warehouse_cache C6 now reads
    sp = os.path.join(ROOT, "tools", "stop_report.py")
    src = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
    check("D4b tools/stop_report.py is there, writes via report_path and closes in a finally",
          "report_path(" in src and "finally:" in src and "cache.close()" in src)

    print(f"check_dead_defs_gone: {'GREEN' if not _fails else 'RED'} ({len(_fails)} failed)")
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
