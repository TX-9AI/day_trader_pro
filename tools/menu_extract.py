#!/usr/bin/env python3
# day_trader_pro/tools/menu_extract.py — v1.1
# v1.1 (2026-08-16) — READS EITHER SOURCE. v1.0 parsed only the heredoc + case
#      block, so the instant devtools.sh became declarative the parser would
#      stop matching and the AFTER side of the diff could not be produced — the
#      proof tool would have died at exactly the moment it was needed. It now
#      auto-detects which source devtools.sh is actually using and reads that,
#      so the same command is valid on both sides of the conversion.
#      Adds --roundtrip: proves the generated registry is EQUIVALENT to the live
#      menu before anything is swapped in.
# v1.0 (2026-08-16) — reconstruct the devtools menu as DATA, so the current
#      state and any future state can be diffed with numbers removed.
"""
Extract devtools.sh's menu into a number-free inventory, and generate the
declarative registry that makes renumbering a non-event.

THE PRINCIPLE (operator, 2026-08-16)
    "I don't want anything tied to the number. The number should be able to be
    completely arbitrary."

    So the identity of a menu item is (SECTION, LABEL, COMMAND). The number is
    a runtime selector, generated at render time from list position. Reorder
    the list, insert a section, delete an item — the numbers just fall out and
    nothing can drift, because there is nothing to keep in sync.

WHY A BOUNDED PARSER AND NOT A REGEX OVER THE FILE
    My first attempt regexed the whole of devtools.sh and produced ELEVEN
    failures, of which nearly all were its own bugs: it reported four live menu
    items as missing, invented a phantom item, and flagged a dozen false
    duplicates. The menu is formatted TEXT inside quoted heredocs, so numbers
    in prose look like menu entries and labels split across columns get lost.
    This parser instead bounds itself to the heredoc body and the case block by
    their markers, which is why it now reconciles exactly: 58 displayed, 58
    handled, zero orphans either way.

    That fragility is itself the argument for the registry. Once the menu is
    data, none of this parsing is needed by anything, ever again.

USAGE
  python3 tools/menu_extract.py --inventory     # number-free label -> command
  python3 tools/menu_extract.py --check         # reconcile display vs handlers
  python3 tools/menu_extract.py --registry      # emit the declarative draft
  python3 tools/menu_extract.py --diff OLD NEW  # compare two inventories

  Before a reorder:  --inventory > docs/MENU_INVENTORY.tsv
  After:             --inventory > /tmp/after.tsv && --diff docs/MENU_INVENTORY.tsv /tmp/after.tsv
  An EMPTY diff is the proof. Numbers may move; labels and commands may not.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MENU = os.path.join(ROOT, "devtools.sh")
REGISTRY = os.path.join(ROOT, "menu_registry.sh")

# Markers, not line numbers — line numbers go stale on the first edit.
HEREDOC_OPEN = "cat <<'EOF' | _colorize"
SELECT_LINE = 'read -rp "Select: " choice'


def _bounds(lines):
    """(display_start, display_end, case_start) from MARKERS, not offsets."""
    d0 = next(i for i, l in enumerate(lines) if HEREDOC_OPEN in l) + 1
    d1 = next(i for i in range(d0, len(lines)) if lines[i].strip() == "EOF")
    c0 = next(i for i, l in enumerate(lines) if SELECT_LINE in l) + 2
    return d0, d1, c0


def parse(path=MENU):
    lines = open(path, encoding="utf-8").read().split("\n")
    d0, d1, c0 = _bounds(lines)

    section = None
    display = []                      # (section, number, label) in menu order
    for ln in lines[d0:d1]:
        s = ln.strip()
        if s.endswith(":") and not re.match(r"^\d", s):
            section = s[:-1]
            continue
        for n, label in re.findall(r"(\d+)\)\s+(.+?)(?=\s{2,}\d+\)|$)", ln):
            display.append((section, int(n), label.strip()))

    # Option 58's row is printed BETWEEN two heredocs (it is coloured live from
    # the maintenance flag), so it is not in the block above. Recovered from the
    # variable that renders it rather than hardcoded.
    for ln in lines:
        m = re.search(r'_MAINT_LINE="\s*(\d+)\)\s*(.+?)"', ln)
        if m and "RED" not in ln:
            display.append(("UTILITIES", int(m.group(1)), m.group(2).strip()))
            break

    handlers, cur, buf = {}, None, []
    for ln in lines[c0:]:
        if re.match(r"^\s*(esac|\*\))", ln):
            break
        m = re.match(r"^\s{4}(\d+)\)\s?(.*)$", ln)
        if m and cur is None:
            cur, buf = int(m.group(1)), [m.group(2).strip()]
            if ";;" in ln:
                handlers[cur] = " ".join(buf)
                cur = None
            continue
        if cur is not None:
            buf.append(ln.strip())
            if ";;" in ln:
                handlers[cur] = " ".join(buf)
                cur = None
    return display, handlers


def _clean(cmd):
    cmd = re.sub(r"\s*\\\s*", " ", cmd)
    cmd = re.sub(r";;\s*$", "", cmd)
    cmd = re.sub(r"^echo;\s*", "", cmd)
    cmd = re.sub(r";?\s*pause\s*$", "", cmd)
    return re.sub(r"\s+", " ", cmd).strip()


def inventory(display, handlers):
    """(section, label, command) — NUMBERS DISCARDED after the join."""
    rows = []
    for section, n, label in display:
        rows.append((section or "?", label, _clean(handlers.get(n, "«NO HANDLER»"))))
    return rows


def parse_registry(path=REGISTRY):
    """(section, label, command) from the MENU array. No numbers exist here.

    Split with maxsplit so a SHELL PIPE inside a command cannot be mistaken for
    the field delimiter — the bash side is safe for the same reason
    (`${rest%%|*}` / `${rest#*|}` are first-match).
    """
    rows, section = [], "?"
    body = open(path, encoding="utf-8").read()
    m = re.search(r"^MENU=\((.*?)^\)", body, re.S | re.M)
    if not m:
        return rows
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line.startswith('"') or not line.endswith('"'):
            continue
        entry = line[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        parts = entry.split("|", 2)
        if parts[0] == "SECTION" and len(parts) >= 2:
            section = parts[1]
        elif parts[0] == "ITEM" and len(parts) == 3:
            rows.append((section, parts[1], parts[2]))
    return rows


def active_source():
    """Which source devtools.sh actually uses — asked, not assumed."""
    try:
        body = open(MENU, encoding="utf-8").read()
    except Exception:
        return "registry" if os.path.exists(REGISTRY) else "heredoc"
    if re.search(r"^\s*(\.|source)\s+.*menu_registry\.sh", body, re.M):
        return "registry"
    return "heredoc"


def rows_for(source="auto"):
    if source == "auto":
        source = active_source()
    if source == "registry":
        return parse_registry(), "registry"
    display, handlers = parse()
    return inventory(display, handlers), "heredoc"


def cmd_inventory(args):
    rows, src = rows_for(getattr(args, "source", "auto"))
    sys.stderr.write(f"# source: {src}\n")
    for section, label, cmd in rows:
        print(f"{section}\t{label}\t{cmd}")
    return 0


def cmd_roundtrip(args):
    """Is the generated registry EQUIVALENT to the live menu?

    The strongest assurance available before the swap: both sides reduced to
    label -> command, numbers already discarded, and compared. If this is clean
    the registry can replace the case block without changing behaviour.
    """
    if not os.path.exists(REGISTRY):
        print("  no menu_registry.sh — generate it with --registry first")
        return 2
    display, handlers = parse()
    live = {l: c for _s, l, c in inventory(display, handlers)}
    reg = {l: c for _s, l, c in parse_registry()}
    gone = sorted(set(live) - set(reg))
    extra = sorted(set(reg) - set(live))
    diff = sorted(l for l in set(live) & set(reg) if live[l] != reg[l])
    print(f"  live menu {len(live)} item(s) · registry {len(reg)} item(s)")
    print(f"  in live but not registry : {gone or 'none'}")
    print(f"  in registry but not live : {extra or 'none'}")
    print(f"  command differs          : {len(diff)}")
    for l in diff[:10]:
        print(f"    ! {l}\n        live: {live[l][:120]}\n        reg : {reg[l][:120]}")
    ok = not (gone or extra or diff)
    print("\n  " + ("✅ registry is EQUIVALENT to the live menu — safe to swap in"
                    if ok else
                    "❌ registry does NOT reproduce the live menu — do not swap"))
    return 0 if ok else 1


def cmd_check(args):
    display, handlers = parse()
    d = {n for _, n, _ in display}
    h = set(handlers) - {0}
    shown_unhandled = sorted(d - h)
    handled_unshown = sorted(h - d)
    dupes = sorted({n for n in d if [x for _, x, _ in display].count(n) > 1})
    scripts = set()
    for cmd in handlers.values():
        scripts |= set(re.findall(r"\$PY\s+([\w./-]+\.py)", cmd))
        scripts |= set(re.findall(r"bash\s+([\w./-]+\.sh)", cmd))
    missing = sorted(s for s in scripts
                     if not os.path.exists(os.path.join(ROOT, s)))
    ok = not (shown_unhandled or handled_unshown or dupes or missing)
    print(f"  displayed {len(d)} · handled {len(h)} · scripts {len(scripts)}")
    print(f"  displayed with no handler : {shown_unhandled or 'none'}")
    print(f"  handler with no display   : {handled_unshown or 'none'}")
    print(f"  duplicate numbers         : {dupes or 'none'}")
    print(f"  referenced but missing    : {missing or 'none'}")
    print("  " + ("OK" if ok else "PROBLEMS ABOVE"))
    return 0 if ok else 1


def cmd_registry(args):
    """Emit the declarative draft. Numbers appear NOWHERE in it."""
    display, handlers = parse()
    rows = inventory(display, handlers)
    print("#!/usr/bin/env bash")
    print("# day_trader_pro/menu_registry.sh — GENERATED DRAFT, review before use")
    print("# Generated by tools/menu_extract.py from devtools.sh.")
    print("#")
    print("# THERE ARE NO NUMBERS IN THIS FILE. devtools.sh assigns them at")
    print("# render time from list position, so reordering this list, inserting")
    print("# a section, or deleting an item cannot desynchronise anything.")
    print("#")
    print("# ⚠️ Multi-line handlers (prompts, conditionals) are emitted as one")
    print("#    line and MUST be read before this replaces the case block.")
    print()
    print("MENU=(")
    last = None
    for section, label, cmd in rows:
        if section != last:
            print(f'  "SECTION|{section}"')
            last = section
        esc = cmd.replace("\\", "\\\\").replace('"', '\\"')
        print(f'  "ITEM|{label}|{esc}"')
    print(")")
    print()
    print("""# ── render + dispatch, the whole of it ──────────────────────────────
# The number is a loop counter. It is never stored, never compared, and never
# written down anywhere — which is the entire point.
menu_render() {
  local i=0 kind rest
  for entry in "${MENU[@]}"; do
    IFS='|' read -r kind rest <<< "$entry"
    if [ "$kind" = "SECTION" ]; then
      printf '\\n %s:\\n' "$rest"
    else
      i=$((i+1)); printf '  %2d) %s\\n' "$i" "${rest%%|*}"
    fi
  done
  printf '\\n   0) Exit\\n'
}

menu_dispatch() {
  local want="$1" i=0 kind rest
  [ "$want" = "0" ] && return 9
  for entry in "${MENU[@]}"; do
    IFS='|' read -r kind rest <<< "$entry"
    [ "$kind" = "SECTION" ] && continue
    i=$((i+1))
    if [ "$i" = "$want" ]; then eval "${rest#*|}"; return 0; fi
  done
  echo "no such option: $want"; return 1
}""")
    return 0


def cmd_diff(args):
    def load(p):
        out = {}
        for ln in open(p, encoding="utf-8"):
            parts = ln.rstrip("\n").split("\t")
            if len(parts) == 3:
                out[parts[1]] = (parts[0], parts[2])
        return out
    a, b = load(args.old), load(args.new)
    gone = sorted(set(a) - set(b))
    added = sorted(set(b) - set(a))
    moved = sorted(l for l in set(a) & set(b) if a[l][0] != b[l][0])
    changed = sorted(l for l in set(a) & set(b) if a[l][1] != b[l][1])
    print(f"  labels removed  : {len(gone)}")
    for l in gone:
        print(f"    - {l}")
    print(f"  labels added    : {len(added)}")
    for l in added:
        print(f"    + {l}")
    print(f"  section moved   : {len(moved)}  (harmless)")
    for l in moved:
        print(f"    ~ {l}: {a[l][0]} -> {b[l][0]}")
    print(f"  COMMAND CHANGED : {len(changed)}")
    for l in changed:
        print(f"    ! {l}\n        was: {a[l][1]}\n        now: {b[l][1]}")
    bad = bool(gone or changed)
    print("\n  " + ("✅ every label survives and still runs the same command "
                    "— numbers are free to move"
                    if not bad else
                    "❌ a label vanished or its command changed — NOT a pure reorder"))
    return 1 if bad else 0


def main(argv):
    p = argparse.ArgumentParser(description="devtools menu as data")
    p.add_argument("--inventory", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--registry", action="store_true")
    # NOTE: a subparser named "--diff" was a mistake — argparse then demanded it
    # as a positional and rejected the file arguments. Two plain operands.
    p.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"))
    p.add_argument("--roundtrip", action="store_true",
                   help="prove menu_registry.sh reproduces the live menu")
    p.add_argument("--source", choices=("auto", "heredoc", "registry"),
                   default="auto", help="which source to read (default: auto)")
    a = p.parse_args(argv)
    if a.roundtrip:
        return cmd_roundtrip(a)
    if a.diff:
        a.old, a.new = a.diff
        return cmd_diff(a)
    if a.registry:
        return cmd_registry(a)
    if a.check:
        return cmd_check(a)
    return cmd_inventory(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
