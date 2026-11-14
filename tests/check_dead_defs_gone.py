#!/usr/bin/env python3
# day_trader_pro/tests/check_dead_defs_gone.py — v1.0
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
    print("check_dead_defs_gone — the three dead dtp defs stay gone (r559 / B5.6)")

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

    print(f"check_dead_defs_gone: {'GREEN' if not _fails else 'RED'} ({len(_fails)} failed)")
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
