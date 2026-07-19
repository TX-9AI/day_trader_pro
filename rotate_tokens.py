#!/usr/bin/env python3
"""
rotate_tokens.py — fleet credential rotation, run from the control box
(wired into devtools). v1.0 — 2026-07-18.

WHAT IT DOES
  Prompts ONCE for each rotatable variable. For each, you paste a new value or
  press <Enter> to leave it unchanged. Whatever you supply is pushed to EVERY
  running trading box, where a small remote updater rewrites the inline
  `Environment=` lines in optionsbot.service (+ candle-feed.service for the
  TT_* creds), reloads systemd, and restarts both services.

SECURITY MODEL (why it's built this way)
  - Secrets are NEVER written to a file on the control box. They live only in
    this process's memory for the duration of the run.
  - Secrets are NEVER passed as command-line arguments (which would show in
    `ps` and in the bot's own process list). They travel over the SSH channel
    on STDIN to the remote updater. On the box they are read into shell vars,
    used, and gone when the process exits.
  - Prompts use getpass so values don't echo to the terminal or land in scroll
    history.
  - The remote updater rewrites units to mode 600 temp files and aborts on a
    truncated result, so a bad edit can't brick a box.

USAGE
  python3 rotate_tokens.py              # rotate — all running boxes
  python3 rotate_tokens.py --only SPX QQQ
  python3 rotate_tokens.py --dry-run    # show plan, prompt, but push nothing
  python3 rotate_tokens.py --audit      # read-only: which vars are set per box
  python3 rotate_tokens.py --audit --only SPX

  The remote updater is SHIPPED inline each run (base64 over stdin/argv-safe),
  so boxes need nothing pre-installed and always run the current version.

COVERAGE
  Rotatable (prompted): TT_CLIENT_SECRET, TT_REFRESH_TOKEN, TT_ACCOUNT_NUMBER,
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GITHUB_REPO, GITHUB_TOKEN.
  OT_INSTRUMENT is DELIBERATELY not rotatable here — it is the box's identity
  (which symbol it trades); changing it blindly across the fleet would be a
  foot-gun. It IS shown in --audit. Change a box's instrument via re-provision
  or configure.sh, not this tool. Together these 8 = every var in
  bootstrap.example.sh.
"""

import argparse
import base64
import getpass
import os
import sys

import config
import fleet          # get_fleet() -> [(symbol, ip, state)]
import ssh_util       # ssh_run(ip, command, timeout)

HERE = os.path.dirname(os.path.abspath(__file__))
REMOTE_SCRIPT = os.path.join(HERE, "rotate_env_remote.sh")
VERIFY_SCRIPT = os.path.join(HERE, "verify_creds_remote.py")

# (prompt label, env var name, secret?) — order shown to the operator.
FIELDS = [
    ("Tastytrade Client Secret",  "TT_CLIENT_SECRET",  True),
    ("Tastytrade Refresh Token",  "TT_REFRESH_TOKEN",  True),
    ("Tastytrade Account Number", "TT_ACCOUNT_NUMBER", False),
    ("Telegram Bot Token",        "TELEGRAM_TOKEN",    True),
    ("Telegram Chat ID",          "TELEGRAM_CHAT_ID",  False),
    ("GitHub Username (repo owner)", "GITHUB_REPO",     False),  # see note below
    ("GitHub Token",              "GITHUB_TOKEN",      True),
]

# NOTE on GitHub: the boxes store GITHUB_REPO as "owner/repo". If the operator
# rotates the username we can't know the repo half here, so we prompt for the
# full "owner/repo" value under the GitHub Username field and write it verbatim.


def prompt_values():
    """Prompt once per field. Returns {VAR: value} for supplied (non-blank)
    fields only. Blank => not included => box leaves it unchanged."""
    print("\n=== Fleet token rotation ===")
    print("Paste a new value, or press <Enter> to leave a variable UNCHANGED.")
    print("Secret fields do not echo as you type.\n")
    values = {}
    for label, var, secret in FIELDS:
        if var == "GITHUB_REPO":
            print("  (GitHub: enter full 'owner/repo', e.g. TX-9AI/options_trader_v3)")
        raw = (getpass.getpass if secret else input)(f"  {label} [{var}]: ")
        raw = raw.strip()
        if raw:
            values[var] = raw
    return values


def confirm(values, targets, dry_run):
    print("\n--- Plan ---")
    print(f"  Variables to rotate: {', '.join(values) if values else '(none)'}")
    print(f"  Target boxes ({len(targets)} running): "
          f"{', '.join(s for s, _, _ in targets)}")
    if dry_run:
        print("  DRY RUN — nothing will be pushed.")
        return False
    if not values:
        print("  Nothing to do (all fields left blank).")
        return False
    ans = input("\nProceed? Type 'yes' to push: ").strip().lower()
    return ans == "yes"


def build_stdin_payload(values):
    """KEY=VALUE lines, newline-separated. This is what the remote reads on
    stdin — never an argument."""
    return "".join(f"{k}={v}\n" for k, v in values.items())


def audit_box(symbol, ip, script_b64):
    """Run the remote updater in --audit mode: no stdin payload, read-only,
    returns the per-var report (names/presence/fingerprints, never values)."""
    remote_cmd = (
        "set -e; "
        "d=$(mktemp); "
        f"echo {script_b64} | base64 -d > \"$d\"; "
        "chmod +x \"$d\"; "
        "bash \"$d\" --audit; "
        "rc=$?; "
        "rm -f \"$d\"; "
        "exit $rc"
    )
    rc, out, err = ssh_util.ssh_run(ip, remote_cmd, timeout=45)
    return rc, out.strip(), err.strip()


def run_audit(running, skipped, script_b64):
    print("\n=== Fleet credential audit (read-only — no values exposed) ===")
    print("  Non-secrets shown in full; secrets shown as SET/MISSING + len/last-4.\n")
    for symbol, ip, _ in running:
        rc, out, err = audit_box(symbol, ip, script_b64)
        print(f"── {symbol} ({ip}) ──")
        if rc == 0 and out:
            print(out)
        else:
            print(f"  🚨 audit failed rc={rc} {err or out or '(no output)'}")
        print()
    if skipped:
        print("Skipped (not running): "
              + ", ".join(f"{s}({st})" for s, st in skipped))
    return 0


def _verify_flags_for(rotated_vars):
    """Given the set of vars that were rotated, return the --skip-* flags so
    verify only exercises the credential groups that actually changed. If
    rotated_vars is None (standalone --verify), check everything."""
    if rotated_vars is None:
        return []
    tt = {"TT_CLIENT_SECRET", "TT_REFRESH_TOKEN", "TT_ACCOUNT_NUMBER"}
    tg = {"TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"}
    gh = {"GITHUB_TOKEN", "GITHUB_REPO"}
    flags = []
    if not (set(rotated_vars) & tt): flags.append("--skip-tt")
    if not (set(rotated_vars) & tg): flags.append("--skip-telegram")
    if not (set(rotated_vars) & gh): flags.append("--skip-github")
    return flags


def verify_box(symbol, ip, verify_b64, flags):
    """Ship verify_creds_remote.py (base64) to the box, run it under the box's
    venv python so the tastytrade SDK is importable, return its report."""
    flag_str = " ".join(flags)
    remote_cmd = (
        "set -e; "
        "d=$(mktemp --suffix=.py); "
        f"echo {verify_b64} | base64 -d > \"$d\"; "
        # Prefer the box's venv python (has tastytrade); fall back to python3.
        "PY=~/options-trader/venv/bin/python; [ -x \"$PY\" ] || PY=python3; "
        f"\"$PY\" \"$d\" {flag_str}; "
        "rc=$?; rm -f \"$d\"; exit $rc"
    )
    rc, out, err = ssh_util.ssh_run(ip, remote_cmd, timeout=90)
    return rc, out.strip(), err.strip()


def run_verify(running, skipped, verify_b64, rotated_vars=None, header=True):
    """Functional credential verification on each running box. Echoes per-box
    SUCCESS/FAIL. rotated_vars narrows the checks; None = check all."""
    flags = _verify_flags_for(rotated_vars)
    if header:
        scope = ("rotated creds" if rotated_vars is not None else "ALL creds")
        print(f"\n=== Functional credential verification ({scope}) — "
              f"live checks, read-only ===")
    ok = fail = 0
    for symbol, ip, _ in running:
        rc, out, err = verify_box(symbol, ip, verify_b64, flags)
        passed = (rc == 0 and "VERIFY: SUCCESS" in out)
        marker = "✅" if passed else "🚨"
        print(f"── {marker} {symbol} ({ip}) ──")
        # indent the remote report
        for ln in (out or err or "(no output)").splitlines():
            print(f"    {ln}")
        if passed:
            ok += 1
        else:
            fail += 1
    print(f"\nVerify: {ok} SUCCESS, {fail} FAIL"
          + (f", {len(skipped)} skipped (not running)" if skipped else ""))
    return 0 if fail == 0 else 1


def push_to_box(symbol, ip, script_b64, payload):
    """Ship the updater (base64, decoded remotely) and feed the KEY=VALUE
    payload to it on stdin — all in one SSH invocation. The secret payload is
    piped, never argv."""
    # Remote command: decode the script to a temp file, run it with our stdin
    # (the payload) forwarded past the decode step via a heredoc split.
    # We keep the script and the payload on separate channels: the script is
    # materialized from an argv-safe base64 blob (not secret), and the payload
    # arrives on the process stdin.
    remote_cmd = (
        "set -e; "
        "d=$(mktemp); "
        f"echo {script_b64} | base64 -d > \"$d\"; "
        "chmod +x \"$d\"; "
        "bash \"$d\"; "
        "rc=$?; "
        "rm -f \"$d\"; "
        "exit $rc"
    )
    # ssh_util.ssh_run doesn't forward stdin, so call ssh directly with the
    # same key/policy, piping payload to stdin.
    import subprocess
    cmd = [
        "ssh", "-i", config.SSH_KEY_PATH,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={config.SSH_CONNECT_TIMEOUT}",
        f"{config.SSH_USER}@{ip}", remote_cmd,
    ]
    try:
        p = subprocess.run(cmd, input=payload, capture_output=True,
                           text=True, timeout=90)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 255, "", "ssh timeout"
    except Exception as exc:  # noqa: BLE001
        return 255, "", f"ssh error: {exc}"


def main(argv):
    ap = argparse.ArgumentParser(description="Fleet token rotation")
    ap.add_argument("--only", nargs="*", help="rotate/audit only these symbols")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit", action="store_true",
                    help="read-only: report which vars are set per box, no changes")
    ap.add_argument("--verify", action="store_true",
                    help="functional check: prove creds actually WORK on each box "
                         "(TT auth+balances, Telegram send, GitHub API). Read-only.")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the automatic post-rotation functional verify")
    args = ap.parse_args(argv)

    if not os.path.exists(REMOTE_SCRIPT):
        print(f"ERROR: remote updater not found at {REMOTE_SCRIPT}")
        return 1
    with open(REMOTE_SCRIPT, "rb") as fh:
        script_b64 = base64.b64encode(fh.read()).decode()
    verify_b64 = None
    if os.path.exists(VERIFY_SCRIPT):
        with open(VERIFY_SCRIPT, "rb") as fh:
            verify_b64 = base64.b64encode(fh.read()).decode()

    fleet_rows = fleet.get_fleet(args.only)
    running = [(s, ip, st) for s, ip, st in fleet_rows if st == "running" and ip]
    skipped = [(s, st) for s, _, st in fleet_rows if st != "running"]

    if not running:
        print("No running boxes to target. (Needs a live SSH; wake boxes first.)")
        if skipped:
            print("  Skipped (not running): "
                  + ", ".join(f"{s}({st})" for s, st in skipped))
        return 1

    # Audit is read-only — do it and return before any prompt.
    if args.audit:
        return run_audit(running, skipped, script_b64)

    # Standalone functional verify — read-only, checks ALL creds, no rotation.
    if args.verify:
        if verify_b64 is None:
            print(f"ERROR: verify script not found at {VERIFY_SCRIPT}")
            return 1
        return run_verify(running, skipped, verify_b64, rotated_vars=None)

    values = prompt_values()
    if not confirm(values, running, args.dry_run):
        print("Aborted — nothing pushed.")
        return 0

    payload = build_stdin_payload(values)
    rotated_vars = list(values)   # remember what changed BEFORE we scrub

    print("\n--- Pushing ---")
    ok = fail = 0
    for symbol, ip, _ in running:
        rc, out, err = push_to_box(symbol, ip, script_b64, payload)
        tag = out or err or "(no output)"
        if rc == 0 and out.startswith("OK"):
            print(f"  ✅ {symbol:<8} {out}")
            ok += 1
        else:
            print(f"  🚨 {symbol:<8} rc={rc} {tag}")
            fail += 1

    # Scrub references (best-effort; GC handles the rest).
    payload = "x" * len(payload)
    del values

    print(f"\nDone: {ok} ok, {fail} failed, {len(skipped)} skipped.")
    if skipped:
        print("  Skipped (not running, rotate later): "
              + ", ".join(f"{s}({st})" for s, st in skipped))
    if fail:
        print("  Re-run against the failed symbols with --only once reachable.")

    # Auto functional-verify the boxes that took the push — proves the new
    # creds actually WORK, not just that they landed. Narrowed to the groups
    # that were rotated. Skip with --no-verify.
    pushed = [(s, ip, st) for s, ip, st in running]  # all attempted
    if not args.no_verify and verify_b64 and pushed and rotated_vars:
        print("\n--- Auto-verify (functional) ---")
        run_verify(pushed, skipped, verify_b64,
                   rotated_vars=rotated_vars, header=False)
    elif verify_b64 is None:
        print("  (verify script absent — skipping functional check)")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
