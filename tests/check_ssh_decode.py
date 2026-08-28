#!/usr/bin/env python3
"""check_ssh_decode.py — v1.0

🔴 REMOTE OUTPUT IS DECODED AS UTF-8, AND NEVER RAISES ON A SPLIT CHARACTER.

⚠️ `subprocess.run(..., text=True)` with no encoding uses the CONTROL SERVER'S
LOCALE. The boxes print box-drawing rules — `═` is U+2550, **three bytes** in
UTF-8 — and when the ssh stream chunks mid-character the decoder loses sync.

⚠️ MEASURED, 2026-08-28: a 62-character rule in `query.py` came back as ~186
QUESTION MARKS — **one per byte, 62 x 3 = 186** — in two panels, while the
other fifteen rules on the same page came through clean. That byte count is
what identified the cause; it was not a width bug in `sep()`.

⚠️ `errors="replace"` MATTERS AS MUCH AS THE ENCODING. The default is STRICT,
which raises UnicodeDecodeError — losing the ENTIRE box's output over one
broken character. A garbled rule is cosmetic; a swallowed report is not.
"""
import ast
import codecs
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fails = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  — {detail}" if detail else ""))
    if not cond:
        _fails.append(label)


def main():
    src = open(os.path.join(_root, "ssh_util.py"), encoding="utf-8").read()
    tree = ast.parse(src)

    # ── S1/S2 — EVERY subprocess.run decodes explicitly ──────────────────
    # ⚠️ BOTH sites, not just ssh_run: scp output can carry non-ASCII too.
    runs = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "run"]
    kw = [{k.arg for k in n.keywords} for n in runs]
    check("S1 every subprocess.run names an encoding",
          all("encoding" in k for k in kw), f"{len(runs)} call(s)")
    check("S2 every subprocess.run sets errors=replace",
          all("errors" in k for k in kw))

    # ── 🔴 S3 — THE FAILURE, REPRODUCED ──────────────────────────────────
    rule = ("═" * 62).encode("utf-8")
    check("S3 a 62-char rule is 186 bytes (the question-mark count)",
          len(rule) == 186, f"{len(rule)} bytes")

    # decoding each chunk separately — what a per-chunk decoder does
    a, b = rule[:100], rule[100:]
    per_chunk = a.decode("utf-8", errors="replace") + b.decode("utf-8", errors="replace")
    check("S4 decoding per chunk corrupts a split character",
          per_chunk != "═" * 62, f"{len(per_chunk)} chars")

    # ── S5 — and an incremental UTF-8 decoder gets it right ──────────────
    d = codecs.getincrementaldecoder("utf-8")(errors="replace")
    joined = d.decode(a) + d.decode(b, True)
    check("S5 a single utf-8 decode over the whole stream is clean",
          joined == "═" * 62, f"{len(joined)} chars")

    # ── S6 — strict would have lost the whole report ─────────────────────
    try:
        a.decode("utf-8")
        strict_ok = True
    except UnicodeDecodeError:
        strict_ok = False
    check("S6 strict decoding RAISES on the split (why errors=replace)",
          not strict_ok)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("check_ssh_decode: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
