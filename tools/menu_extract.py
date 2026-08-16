#!/usr/bin/env python3
# day_trader_pro/tools/menu_extract.py — v1.3
# v1.3 (2026-08-16) — DEGRADES AFTER THE CONVERSION. Once devtools.sh became
#      declarative the heredoc vanished, and `parse()` raised StopIteration —
#      the parser THREW instead of reporting that its source was gone. Callers
#      that only need the inventory already route via rows_for(); now `parse()`
#      returns empty structures when the markers are absent, and --check works
#      off whichever source is live. The conversion is supposed to retire this
#      parser, not break the tool that proves the conversion.
# v1.2 (2026-08-16) — HANDLER BODIES BECOME FUNCTIONS. --functions emits
#      menu_functions.sh with each case body copied VERBATIM into `mi_<slug>()`,
#      and the registry then names the function instead of inlining shell — so
#      multi-line handlers (option 58 is 26 lines of prompts and conditionals)
#      survive intact instead of being flattened into one fragile line.
#      --roundtrip RESOLVES one level of indirection: a registry entry naming a
#      function is compared against that function's BODY, so the equivalence
#      check stays semantic rather than trivially failing on "mi_foo" != shell.
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
FUNCS = os.path.join(ROOT, "menu_functions.sh")

# Markers, not line numbers — line numbers go stale on the first edit.
HEREDOC_OPEN = "cat <<'EOF' | _colorize"
SELECT_LINE = 'read -rp "Select: " choice'


def _bounds(lines):
    """(display_start, display_end, case_start), or None once the heredoc is gone.

    Returns None rather than raising: after the conversion this parser has no
    source, and that is SUCCESS, not an error. A tool that throws when the thing
    it measures has been improved is a tool you stop running.
    """
    try:
        d0 = next(i for i, l in enumerate(lines) if HEREDOC_OPEN in l) + 1
        d1 = next(i for i in range(d0, len(lines)) if lines[i].strip() == "EOF")
        c0 = next(i for i, l in enumerate(lines) if SELECT_LINE in l) + 2
        return d0, d1, c0
    except StopIteration:
        return None


def parse(path=MENU):
    lines = open(path, encoding="utf-8").read().split("\n")
    b = _bounds(lines)
    if b is None:
        parse.raw = {}
        return [], {}          # converted: the registry is the source now
    d0, d1, c0 = b

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

    handlers, raw, cur, buf, rbuf = {}, {}, None, [], []
    for ln in lines[c0:]:
        if re.match(r"^\s*(esac|\*\))", ln):
            break
        m = re.match(r"^\s{4}(\d+)\)\s?(.*)$", ln)
        if m and cur is None:
            cur, buf, rbuf = int(m.group(1)), [m.group(2).strip()], [m.group(2)]
            if ";;" in ln:
                handlers[cur] = " ".join(buf)
                raw[cur] = list(rbuf)
                cur = None
            continue
        if cur is not None:
            buf.append(ln.strip())
            rbuf.append(ln)
            if ";;" in ln:
                handlers[cur] = " ".join(buf)
                raw[cur] = list(rbuf)
                cur = None
    parse.raw = raw          # side channel; keeps the signature stable
    return display, handlers


def _clean(cmd):
    """Normalise a handler body for COMPARISON only.

    ⚠️ ORDER MATTERS AND IT BIT ME: the anchored `^echo;` and trailing `pause`
    strips have to run AFTER whitespace is collapsed and trimmed. A case body
    reads `echo; $PY ...` on one line, but the same body pulled out of a
    function starts with a newline and indentation, so `^echo;` never matched
    and the two sides looked different when they were identical. Collapse
    first, then strip, then the comparison is order-independent.
    """
    cmd = re.sub(r"\s*\\\s*", " ", cmd)      # line continuations
    cmd = re.sub(r"\s+", " ", cmd).strip()     # collapse BEFORE anchoring
    cmd = re.sub(r";;\s*$", "", cmd).strip()
    cmd = re.sub(r"^echo;\s*", "", cmd).strip()
    cmd = re.sub(r";?\s*pause\s*$", "", cmd).strip()
    return cmd


def inventory(display, handlers):
    """(section, label, command) — NUMBERS DISCARDED after the join."""
    rows = []
    for section, n, label in display:
        rows.append((section or "?", label, _clean(handlers.get(n, "«NO HANDLER»"))))
    return rows


_SLUG_SEEN = {}


def slug(label):
    """Stable function name from a label. Unique, readable, never a number."""
    s_ = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:44].strip("_")
    s_ = s_ or "item"
    n = _SLUG_SEEN.get(s_, 0) + 1
    _SLUG_SEEN[s_] = n
    return f"mi_{s_}" if n == 1 else f"mi_{s_}_{n}"


def parse_functions(path=FUNCS):
    """{function_name: body} from menu_functions.sh."""
    out = {}
    try:
        body = open(path, encoding="utf-8").read()
    except Exception:
        return out
    for m in re.finditer(r"^(mi_[a-z0-9_]+)\(\)\s*\{\n(.*?)^\}", body, re.S | re.M):
        out[m.group(1)] = m.group(2)
    return out


def cmd_functions(args):
    """Emit menu_functions.sh — each case body copied VERBATIM into a function.

    Verbatim matters: option 58 alone is 26 lines of prompts and nested
    conditionals. Flattening it to one line to fit a delimited array would be
    rewriting a destructive handler by hand, which is precisely the kind of edit
    this whole exercise exists to avoid.
    """
    display, handlers = parse()
    raw = getattr(parse, "raw", {})
    _SLUG_SEEN.clear()
    print("#!/usr/bin/env bash")
    print("# day_trader_pro/menu_functions.sh — GENERATED from devtools.sh")
    print("# One function per menu item, body copied verbatim from the case block.")
    print("# Sourced by devtools.sh; named by menu_registry.sh. No numbers here.")
    print()
    for _section, n, label in display:
        body = raw.get(n)
        if not body:
            continue
        fn = slug(label)
        print(f"# {label}")
        print(f"{fn}() {{")
        for i, ln in enumerate(body):
            txt = ln if i else "    " + ln.strip()
            txt = re.sub(r"\s*;;\s*$", "", txt.rstrip())
            if txt.strip():
                print(txt if txt.startswith(" ") else "    " + txt)
        print("}")
        print()
    return 0


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
    # Resolve ONE level of indirection: an entry naming a function is compared
    # against that function's body, so equivalence stays semantic.
    fns = parse_functions()
    if fns:
        rows = [(s_, l_, _clean(fns[c_]) if c_.strip() in fns else c_)
                for s_, l_, c_ in rows]
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
    """Only meaningful BEFORE the conversion; afterwards there is nothing to
    compare the registry against, because the registry IS the menu."""
    """Is the generated registry EQUIVALENT to the live menu?

    The strongest assurance available before the swap: both sides reduced to
    label -> command, numbers already discarded, and compared. If this is clean
    the registry can replace the case block without changing behaviour.
    """
    if not os.path.exists(REGISTRY):
        print("  no menu_registry.sh — generate it with --registry first")
        return 2
    display, handlers = parse()
    if not display:
        print("  devtools.sh is already declarative — the registry IS the menu,")
        print("  so there is nothing left to compare it against. Use --diff")
        print("  against docs/MENU_INVENTORY.tsv instead.")
        return 0
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
    if not display:
        # Post-conversion: the numbers are generated, so "displayed vs handled"
        # cannot disagree by construction. What is still worth checking is that
        # every named function EXISTS and every referenced script is on disk.
        rows = parse_registry()
        fns = parse_functions()
        raw_rows = []
        body = open(REGISTRY, encoding="utf-8").read()
        for m in re.finditer(r'"ITEM\|([^|]+)\|([^"]+)"', body):
            raw_rows.append((m.group(1), m.group(2)))
        missing_fn = sorted(f for _l, f in raw_rows if f not in fns)
        scripts = set()
        for b_ in fns.values():
            scripts |= set(re.findall(r"\$PY\s+([\w./-]+\.py)", b_))
            scripts |= set(re.findall(r"bash\s+([\w./-]+\.sh)", b_))
        missing_s = sorted(s_ for s_ in scripts
                           if not os.path.exists(os.path.join(ROOT, s_)))
        dup = sorted({l for l, _f in raw_rows
                      if [x for x, _ in raw_rows].count(l) > 1})
        ok = not (missing_fn or missing_s or dup)
        print("  source: registry (devtools.sh is declarative)")
        print(f"  items {len(rows)} · functions {len(fns)} · scripts {len(scripts)}")
        print(f"  item names a MISSING function : {missing_fn or 'none'}")
        print(f"  duplicate LABELS              : {dup or 'none'}")
        print(f"  referenced but missing script : {missing_s or 'none'}")
        print("  " + ("OK" if ok else "PROBLEMS ABOVE"))
        return 0 if ok else 1
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
    """Emit the declarative registry. Numbers appear NOWHERE in it.

    Entries NAME a function from menu_functions.sh rather than inlining shell,
    so a 26-line handler stays 26 lines instead of being flattened into a
    delimited string.
    """
    display, handlers = parse()
    rows = inventory(display, handlers)
    _SLUG_SEEN.clear()
    rows = [(s_, l_, slug(l_)) for s_, l_, _c in rows]
    print("#!/usr/bin/env bash")
    print("# day_trader_pro/menu_registry.sh — GENERATED DRAFT, review before use")
    print("# Generated by tools/menu_extract.py from devtools.sh.")
    print("#")
    print("# THERE ARE NO NUMBERS IN THIS FILE. devtools.sh assigns them at")
    print("# render time from list position, so reordering this list, inserting")
    print("# a section, or deleting an item cannot desynchronise anything.")
    print("#")
    print("# Each ITEM names a function in menu_functions.sh — bodies are kept")
    print("# verbatim there, so multi-line handlers are not flattened.")
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
    p.add_argument("--functions", action="store_true",
                   help="emit menu_functions.sh (verbatim handler bodies)")
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
    if a.functions:
        return cmd_functions(a)
    if a.registry:
        return cmd_registry(a)
    if a.check:
        return cmd_check(a)
    return cmd_inventory(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
