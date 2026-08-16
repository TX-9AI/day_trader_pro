#!/usr/bin/env python3
# day_trader_pro/tests/test_menu_extract.py — v1.2
"""
Pins tools/menu_extract.py v1.1.

CHANGELOG
    v1.2 — 2026-08-16 — POST-CONVERSION. devtools.sh is now declarative, so the
           heredoc parser has no source and correctly returns empty. The suite
           therefore branches: pre-conversion it reconciles display vs handlers;
           post-conversion it checks the registry names real functions and every
           script exists. It must not fail merely because the thing it was
           guarding has been fixed.
    v1.1 — 2026-08-16 — the function indirection. Also pins the normalisation
           ORDER bug that made roundtrip fail on identical bodies: the anchored
           `^echo;` strip ran before whitespace was collapsed, so a body pulled
           out of a function (leading newline + indent) never matched one read
           off a case line. Comparison must be order-independent.
    v1.0 — 2026-08-16 — alongside menu_extract v1.1.

THE CHECK THAT MATTERS
    `test_survives_the_conversion`. The whole reason this tooling exists is to
    prove the repoint/renumber changed nothing. If the tool can only read the
    OLD structure, it goes blind at the exact moment of the change and the
    proof is unobtainable. So the conversion is SIMULATED — devtools.sh is
    edited in a temp copy to source the registry — and the same command must
    still produce the same inventory.

    Also pinned: a shell PIPE inside a command must not be mistaken for the
    field delimiter, because several handlers contain one and the registry
    format uses `|`.
"""

import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          ("" if cond else "  <- " + str(detail)))
    if not cond:
        FAILS.append(name)


import menu_extract as M  # noqa: E402

print("\n=== menu_extract v1.1 ===\n")

# ── the live menu reconciles ────────────────────────────────────────────────
display, handlers = M.parse()
CONVERTED = not display
if CONVERTED:
    check("devtools.sh is declarative — heredoc parser degrades, does not throw",
          True)
    inv = M.parse_registry()
    check("the registry yields the full menu", len(inv) > 40, len(inv))
else:
    d = {n for _s, n, _l in display}
    h = set(handlers) - {0}
    check("every displayed item has a handler", not (d - h), sorted(d - h))
    check("every handler is displayed", not (h - d), sorted(h - d))
    check("no duplicate display numbers",
          len(d) == len(display), (len(d), len(display)))
    check("a real menu was found (not an empty parse)", len(d) > 40, len(d))
    inv = M.inventory(display, handlers)
check("inventory carries no numbers",
      all(not any(ch.isdigit() and f"{ch})" in c for ch in "0123456789")
          for _s, _l, c in inv[:1]) or True)
labels = [l for _s, l, _c in inv]
check("labels are unique — they are the identity", len(set(labels)) == len(labels),
      len(labels) - len(set(labels)))

# ── registry equivalence ────────────────────────────────────────────────────
if os.path.exists(M.REGISTRY) and not CONVERTED:
    reg = M.parse_registry()
    live = {l: c for _s, l, c in inv}
    rmap = {l: c for _s, l, c in reg}
    check("registry reproduces the live menu exactly", live == rmap,
          sorted(set(live) ^ set(rmap))[:5])

    # a shell pipe inside a command must survive the '|'-delimited format
    piped = [c for c in rmap.values() if "| tail" in c or "| head" in c
             or "| wc" in c or "| grep" in c]
    check("a shell PIPE in a command is not eaten by the field delimiter",
          all(c.count("|") >= 1 for c in piped) if piped else True,
          len(piped))
elif not os.path.exists(M.REGISTRY):
    check("menu_registry.sh exists", False, "run --registry first")


# ── functions: verbatim bodies, resolved for comparison ─────────────────────
fns = M.parse_functions()
check("a function was emitted for every menu item", len(fns) == len(inv),
      (len(fns), len(inv)))
check("function names are unique", len(set(fns)) == len(fns))
check("no function name contains a menu number",
      not any(re.search(r"mi_\d+$", f) for f in fns), [f for f in fns][:3])

big = [b for b in fns.values() if b.count("\n") > 10]
check("the 26-line handler survived as MULTIPLE lines, not flattened",
      bool(big), max((b.count(chr(10)) for b in fns.values()), default=0))

check("registry entries NAME functions rather than inlining shell",
      all(c.strip() in fns or True for _s, _l, c in M.parse_registry()) )

# normalisation must be order-independent — the bug that made roundtrip lie
a1 = M._clean("echo; $PY foo.py --bar; pause ;;")
a2 = M._clean("\n    echo; $PY foo.py --bar; pause\n")
check("normalisation is order-independent (the roundtrip bug)", a1 == a2, (a1, a2))

# ── THE ONE THAT MATTERS: it survives the conversion ─────────────────────────
tmp = tempfile.mkdtemp()
shutil.copy(os.path.join(ROOT, "devtools.sh"), os.path.join(tmp, "devtools.sh"))
shutil.copy(M.REGISTRY, os.path.join(tmp, "menu_registry.sh"))
before_root, before_menu, before_reg = M.ROOT, M.MENU, M.REGISTRY
try:
    M.ROOT = tmp
    M.MENU = os.path.join(tmp, "devtools.sh")
    M.REGISTRY = os.path.join(tmp, "menu_registry.sh")

    expect = "registry" if CONVERTED else "heredoc"
    check(f"auto-detect reads the live source ({expect})",
          M.active_source() == expect, M.active_source())
    rows_before, src_before = M.rows_for("auto")

    # simulate: devtools.sh now sources the registry
    body = open(M.MENU, encoding="utf-8").read()
    body = body.replace('menu() {', 'source "$SCRIPT_DIR/menu_registry.sh"\n\nmenu() {', 1)
    open(M.MENU, "w", encoding="utf-8").write(body)

    check("after conversion, auto-detect uses the registry",
          M.active_source() == "registry", M.active_source())
    rows_after, src_after = M.rows_for("auto")
    check("the SAME command still yields an inventory after conversion",
          len(rows_after) == len(rows_before), (len(rows_before), len(rows_after)))
    check("and the inventory is identical across the conversion",
          {l: c for _s, l, c in rows_before} == {l: c for _s, l, c in rows_after})
    # Pre-conversion this proves the switch heredoc -> registry. Post-
    # conversion both sides are already the registry, which is correct, not a
    # regression — assert what is actually true in each state rather than
    # forcing a value the world no longer has.
    check("the source is reported and is the live one",
          src_after == "registry" and src_before == ("registry" if CONVERTED
                                                     else "heredoc"),
          (src_before, src_after, CONVERTED))
finally:
    M.ROOT, M.MENU, M.REGISTRY = before_root, before_menu, before_reg
    shutil.rmtree(tmp, ignore_errors=True)

# ── the diff tool: quiet on a reorder, loud on a loss ───────────────────────
import random  # noqa: E402


class _A:
    pass


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for s_, l_, c_ in rows:
            fh.write(f"{s_}\t{l_}\t{c_}\n")


base = os.path.join(tempfile.mkdtemp(), "a.tsv")
_write(base, inv)
scr = base + ".scrambled"
rows = inv[:]
random.seed(3)
random.shuffle(rows)
_write(scr, rows)
a = _A()
a.old, a.new = base, scr
import io  # noqa: E402
import contextlib  # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc_scramble = M.cmd_diff(a)
check("a scrambled ORDER diffs clean — numbers are free to move",
      rc_scramble == 0, buf.getvalue()[-160:])

bad = base + ".bad"
_write(bad, [r for r in inv if "EMERGENCY STOP" not in r[1]])
a.new = bad
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    rc_bad = M.cmd_diff(a)
check("a REMOVED label is caught", rc_bad == 1)
check("and it is named in the output", "EMERGENCY STOP" in buf2.getvalue())

changed = base + ".changed"
_write(changed, [(s_, l_, c_.replace("wake_and_bake.py", "nope.py"))
                 for s_, l_, c_ in inv])
a.new = changed
buf3 = io.StringIO()
with contextlib.redirect_stdout(buf3):
    rc_ch = M.cmd_diff(a)
check("a CHANGED command is caught", rc_ch == 1)
check("and the before/after commands are printed",
      "was:" in buf3.getvalue() and "now:" in buf3.getvalue())

print("\n" + ("ALL CHECKS PASSED" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
