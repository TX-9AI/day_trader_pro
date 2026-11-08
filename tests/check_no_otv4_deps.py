#!/usr/bin/env python3
"""
day_trader_pro/tests/check_no_otv4_deps.py  v1.0
v1.0  2026-11-08  dtp r532 / OTV4DEP.1 — NO dtp TOOL READS CODE OR LIVE DOCS FROM THE FROZEN TREE. The 11-07
      Saturday brief (section 5 item 7) found dtp tools still importing from, or defaulting to, ~/options-trader-v4,
      frozen since otv4 r500: claude_boot's boot-alert address, brief_sigint's SPX weighting rule, the level-history
      builder (whose trading-side module OTV5 never carried), gen_handoff's reading list. r532 moves each to OTV5 or
      removes it. This gate keeps it that way for dtp's own code (tests/ is hygiene item 7's, not this gate's).

  N1  every reference to the frozen tree in dtp code (a string constant outside a docstring in a .py, a non-comment
      line in a .sh) sits in an ALLOWED file, at most as many times as that file is allowed, each for a named reason.
  N2  no name bound to the frozen tree is put on sys.path, or joined to a `tests` path, anywhere in dtp code.
  N3  a name bound to the frozen tree is joined to `docs` only where the allow-list says the read is history.
  N4  the scan is not vacuous: it parsed more than 60 dtp .py files (80 at r532, tests/ excluded).
  N5  CONTROL: on a fixture tree the same scanner flags an unlisted reference, a sys.path insert and a tests join,
      a docs join, and passes a comment, a docstring and an allowed reference.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r"options-trader-v4|DTP_OTV4_DIR")

# file -> (max references, why). A new reference anywhere else, or one more here, turns N1 red.
ALLOWED = {
    "menu_functions.sh": (1, "CLAUDE_SESSION_DIR: the operator's Claude working directory (project memory is keyed "
                             "by that folder name), by design"),
    "tools/check_land_discipline.py": (1, "dtp's own ledger rows live in otv4's GENESIS (the docs half of every land)"),
    "tools/checker_sweep.py": (2, "otv4 is swept only when asked for by name"),
    "tools/claude_boot.py": (1, "WORKDIR: the Claude session's cwd, not a code tree"),
    "tools/gen_handoff.py": (2, "the frozen tree is LISTED as frozen; the transcript folder is Claude's project name"),
    "tools/genesis_find.py": (3, "otv4 GENESIS/BACKLOG are searched as HISTORY, after OTV5"),
    "tools/saturday_brief.sh": (1, "ANCHOR: the Claude session's cwd (project memory), r527"),
    "tools/scratch_purge.py": (2, "HANDOFF_DIRS is the history folder it rehomes; the recreate note names the docs half"),
    "tools/transcript_text.py": (1, "Claude's project transcript folder name"),
}
# file -> why: the only places a frozen-tree name may be joined to docs/.
DOCS_JOIN_OK = {"tools/genesis_find.py": "history search"}

FAILED, RAN = [], []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    RAN.append(name)
    if not ok:
        FAILED.append(name)


def _docstrings(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                out.add(id(b.value))
    return out


def _mentions(node):
    return any(isinstance(c, ast.Constant) and isinstance(c.value, str) and PAT.search(c.value)
               for c in ast.walk(node))


def scan_py(rel, src):
    """(references, sys_path_hits, tests_joins, docs_joins) for one .py file."""
    tree = ast.parse(src)
    docs = _docstrings(tree)
    refs = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and PAT.search(n.value)]
    tainted = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None and _mentions(n.value):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Name):
                    tainted.add(t.id)

    def is_tainted(e):
        return (isinstance(e, ast.Name) and e.id in tainted) or _mentions(e) or (
            isinstance(e, ast.Call) and any(is_tainted(a) for a in e.args))

    sysp, tj, dj = [], [], []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute):
            continue
        f = n.func
        owner = ast.unparse(f.value) if hasattr(ast, "unparse") else ""
        if owner == "sys.path" and f.attr in ("insert", "append") and any(is_tainted(a) for a in n.args):
            sysp.append(n.lineno)
        if owner == "os.path" and f.attr == "join" and n.args and is_tainted(n.args[0]):
            rest = [a.value for a in n.args[1:] if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if "tests" in rest:
                tj.append(n.lineno)
            if "docs" in rest:
                dj.append(n.lineno)
    return refs, sysp, tj, dj


def scan_sh(src):
    return [i for i, ln in enumerate(src.split("\n"), 1)
            if not ln.strip().startswith("#") and PAT.search(ln)]


def scan(root, files, allowed, docs_ok):
    """{'n1': [...], 'n2': [...], 'n3': [...], 'parsed': int}"""
    res = {"n1": [], "n2": [], "n3": [], "parsed": 0}
    for rel in files:
        if rel.startswith("tests/") or not rel.endswith((".py", ".sh")):
            continue
        try:
            src = open(os.path.join(root, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if rel.endswith(".py"):
            try:
                refs, sysp, tj, dj = scan_py(rel, src)
            except SyntaxError:
                continue
            res["parsed"] += 1
            res["n2"] += [f"{rel}:{x} sys.path" for x in sysp] + [f"{rel}:{x} join(tests)" for x in tj]
            if rel not in docs_ok:
                res["n3"] += [f"{rel}:{x} join(docs)" for x in dj]
        else:
            refs = scan_sh(src)
        cap = allowed.get(rel, (0, ""))[0]
        if len(refs) > cap:
            res["n1"].append(f"{rel}: {len(refs)} reference(s), {cap} allowed (lines {refs[:6]})")
    return res


def tracked(root):
    out = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True).stdout.split()
    return out or [os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root)
                   if ".git" not in d for f in fs]


def control():
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "tools"))
        w = lambda rel, body: open(os.path.join(td, rel), "w").write(body)   # noqa: E731
        w("tools/bad_ref.py", 'X = "/home/ubuntu/options-trader-v4/x"\n')
        w("tools/bad_path.py", 'import os, sys\nOT = os.environ.get("DTP_OTV4_DIR", "y")\n'
                               'sys.path.insert(0, os.path.join(OT, "tests"))\n'
                               'D = os.path.join(OT, "docs", "BACKLOG.md")\n')
        w("tools/ok_comment.py", '"""mentions ~/options-trader-v4 in a docstring"""\n# ~/options-trader-v4\nA = 1\n')
        w("tools/ok_allowed.py", 'H = "~/options-trader-v4/handoffs"\n')
        w("tools/bad.sh", 'cd ~/options-trader-v4 && ls\n# ~/options-trader-v4 in a comment\n')
        files = ["tools/bad_ref.py", "tools/bad_path.py", "tools/ok_comment.py", "tools/ok_allowed.py", "tools/bad.sh"]
        r = scan(td, files, {"tools/ok_allowed.py": (1, "fixture")}, {})
        n1 = " ".join(r["n1"])
        n2 = " ".join(r["n2"])
        ok = ("bad_ref.py" in n1 and "bad_path.py" in n1 and "bad.sh" in n1 and "ok_comment" not in n1
              and "ok_allowed" not in n1 and "bad_path.py:3 sys.path" in n2 and "join(tests)" in n2
              and any("bad_path.py:4 join(docs)" in x for x in r["n3"]))
        return ok, f"n1={r['n1']} n2={r['n2']} n3={r['n3']}"


def main():
    print("check_no_otv4_deps — dtp code does not read code or live docs from ~/options-trader-v4")
    files = tracked(ROOT)
    r = scan(ROOT, files, ALLOWED, DOCS_JOIN_OK)
    check("N1", not r["n1"], "; ".join(r["n1"]) or f"{len(ALLOWED)} allowed file(s), each within its count")
    check("N2", not r["n2"], "; ".join(r["n2"]) or "no frozen-tree name on sys.path or joined to tests/")
    check("N3", not r["n3"], "; ".join(r["n3"]) or "docs/ joins only where the read is history")
    check("N4", r["parsed"] > 60, f"{r['parsed']} .py files parsed")
    ok, why = control()
    check("N5", ok, "" if ok else why)
    print(f"check_no_otv4_deps: {'ALL PASS' if not FAILED else 'FAIL ' + ' '.join(FAILED)} ({len(RAN)} checks)")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
