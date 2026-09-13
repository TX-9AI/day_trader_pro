#!/usr/bin/env python3
"""
day_trader_pro/tools/push_level_history.py  v1.0
v1.0  2026-09-13  r379 / LVL.17 — DELIVER THE LEVEL HISTORY TO THE BOXES.

OPERATOR, 2026-09-13: *"leave them up to accept the seeded ledger files."* So the
fleet stays running and control pushes; a trading box never reaches S3, which is
the operator's own framing — *"I'm not saying the bots would 'pull' from s3. I'm
saying we could construct their ledgers from that data."* §30 holds: the bot owns
its book, control is the source of the HISTORY and nothing else.

🔑 ONE SYMBOL PER BOX. Each box runs one instrument, so it gets exactly its own
file and no other. Sending the whole set would put 14 irrelevant symbols' zones
on every box for a loader that matches on price — and a price zone from another
name is a coincidence waiting to be matched.

🔴 IT VERIFIES BY PARSING ON THE BOX, NOT BY TRUSTING scp's EXIT CODE. §18 —
BUILT, PUSHED and BAKED are three different claims, and a file that landed but
cannot be read is the PUSHED-looking-like-WORKING case. The check runs the box's
own python against the box's own copy and reports the zone count it found, so a
truncated or half-written file is caught here rather than at 09:30.
⚠️ AND IT REPORTS THE SCHEMA THE FILE DECLARES, because the loader REFUSES a
history built for a different ledger schema — a silent refusal at the open would
look exactly like a box with no history.

⚠️ STOPPED BOXES ARE NAMED, NEVER SKIPPED QUIETLY. A box that was down during the
push has no history and will trade without it; that is a fact the operator has to
be able to read off this run's output. Exit code is non-zero if any targeted box
did not end up with a readable file.
"""
import argparse
import json
import os
import sys

DTP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DTP)
os.chdir(DTP)

import config                                                   # noqa: E402
import instance_registry                                        # noqa: E402
import ssh_util                                                 # noqa: E402

# The bot checkout on the boxes. Read off the r378 deploy transcript, which
# printed `Bot dir: /home/ubuntu/options-trader` for all 15 — NOT
# `options-trader-v4`, which is the CONTROL path. Getting this wrong writes the
# file into a directory nothing reads, and the loader's own "no file" path is
# silent by design, so the mistake would not surface until a session ran without
# history and nobody could say why.
BOT_DIR = os.environ.get("DTP_BOT_DIR", "options-trader")
REMOTE_REL = "data/level_history"


def main():
    ap = argparse.ArgumentParser(description="push per-symbol level history to "
                                            "the running fleet")
    ap.add_argument("--dir", required=True, help="directory of <SYM>.json files")
    ap.add_argument("--only", default="", help="comma list; default every file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(a.dir):
        print("no such directory: %s" % a.dir)
        return 1
    files = {f[:-5].upper(): os.path.join(a.dir, f)
             for f in sorted(os.listdir(a.dir)) if f.endswith(".json")}
    if a.only:
        want = {s.strip().upper() for s in a.only.split(",") if s.strip()}
        files = {k: v for k, v in files.items() if k in want}
    if not files:
        print("no history files to push in %s" % a.dir)
        return 1

    mapping, _ = instance_registry.discover(sorted(files))
    print("pushing %d file(s) to %s/%s\n" % (len(files), BOT_DIR, REMOTE_REL))
    ok, failed, down = 0, [], []
    for sym in sorted(files):
        rec = mapping.get(sym) or {}
        ip = rec.get("private_ip", "")
        state = rec.get("state", "?")
        if state != "running" or not ip:
            # NAMED, not skipped: this box will trade with no defense history.
            down.append(sym)
            print("  %-6s SKIPPED — state=%s ip=%s; it will run with NO history"
                  % (sym, state, ip or "-"))
            continue
        local = files[sym]
        remote_dir = "%s/%s" % (BOT_DIR, REMOTE_REL)
        remote = "%s/%s.json" % (remote_dir, sym)
        if a.dry_run:
            print("  %-6s would push %s -> %s" % (sym, local, remote))
            ok += 1
            continue
        rc, _o, err = ssh_util.ssh_run(ip, "mkdir -p ~/%s" % remote_dir)
        if rc != 0:
            failed.append(sym)
            print("  %-6s FAILED to create %s: %s" % (sym, remote_dir, err.strip()))
            continue
        rc, _o, err = ssh_util.scp_push(ip, local, remote)
        if rc != 0:
            failed.append(sym)
            print("  %-6s FAILED to copy: %s" % (sym, err.strip()))
            continue
        # ── VERIFY ON THE BOX. scp exiting 0 says bytes moved, not that the bot
        # can read them. This parses the box's copy with the box's python.
        probe = ("python3 -c \"import json;d=json.load(open('%s'));"
                 "print(d['symbol'],len(d['zones']),d['ledger_schema'],"
                 "d['window']['sessions'])\"" % remote)
        rc, out, err = ssh_util.ssh_run(ip, probe)
        if rc != 0 or not out.strip():
            failed.append(sym)
            print("  %-6s LANDED BUT UNREADABLE on the box: %s"
                  % (sym, (err or out).strip()[:120]))
            continue
        parts = out.split()
        print("  %-6s ok — %s zone(s), ledger schema %s, %s session(s) of history"
              % (sym, parts[1], parts[2], parts[3]) if len(parts) >= 4
              else "  %-6s ok — %s" % (sym, out.strip()))
        ok += 1

    print()
    print("%d delivered, %d failed, %d box(es) down" % (ok, len(failed), len(down)))
    if failed:
        print("FAILED: %s" % ", ".join(failed))
    if down:
        print("NO HISTORY (box down): %s" % ", ".join(down))
    return 0 if not failed and not down else 1


if __name__ == "__main__":
    sys.exit(main())
