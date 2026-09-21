#!/usr/bin/env python3
"""
tests/check_ssh_budget.py  v1.0
v1.0  2026-09-21  r406 / OPS.32, S3.19 — A COMMAND BUDGET MUST NOT BE A
      CONNECT TIMEOUT WEARING A DIFFERENT HAT.

🔴 WHAT IT PROTECTS. `ssh_util.ssh_run` did `timeout = timeout or
config.SSH_CONNECT_TIMEOUT` and handed the subprocess `timeout + 10`, so every
caller that passed nothing — `fleet.py run` (every menu fan-out),
`wake_and_bake`'s remote step, `harvest`, `standings`, `eod_report` — was
bounded at **22 seconds** by a number whose job is *how long to wait for a TCP
handshake*.
📊 REPRODUCED ON CONTROL AGAINST LOOPBACK, NO FLEET INVOLVED: `sleep 5` ->
5.2s rc=0 with its output; `sleep 30` -> **22.0s, rc=255, "ssh timeout"** —
and the remote `sleep` kept running.

  S1  the command budget is NOT derived from SSH_CONNECT_TIMEOUT   (the defect)
  S2  -o ConnectTimeout IS still SSH_CONNECT_TIMEOUT               (control)
  S3  an explicit timeout= still wins                              (control)
  S4  the timeout message names the budget AND S3.19's live remote
  S5  fleet.py run --timeout reaches ssh_run  (vacuous under system py)
  S6  LIVE: a command past the OLD 22s bound now completes
  S7  wake_and_bake's --bake-only help does not claim a restart
  S8  🔴 NO function resolves its budget from the CONNECT timeout  (the shape)

🔑 S1/S2/S3 CAPTURE WHAT IS HANDED TO `subprocess.run`, not source text. The
number that matters is the one the subprocess actually receives, and a grep
would be satisfied by this file's own changelog (§20, §21).
⚠️ S6 IS THE ONLY ONE THAT NEEDS THE NETWORK, and it reports **GREEN
(VACUOUS)** with its reason when loopback ssh is unavailable rather than going
red for the environment — a gate that fails for the machine instead of the
content is the CV.1 failure this repo keeps naming ([[CHK.9]]).

Plain script with an exit code, stdlib only (§36, [[CHK.9]]).
"""
from __future__ import annotations
import ast
import os
import subprocess as _subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

_res = []


def ck(name, ok, why=""):
    _res.append((name, bool(ok), why))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {'' if ok else why}")


try:
    import config
    import ssh_util
except Exception as exc:                                        # noqa: BLE001
    for n in ("S1", "S2", "S3", "S4", "S5", "S6"):
        ck(n, False, f"import failed: {exc!r}")
    config = ssh_util = None


class _FakeProc:
    returncode = 0
    stdout = "ok"
    stderr = ""


class _Capture:
    """Stands in for `subprocess`, recording the argv and timeout it is given."""

    TimeoutExpired = _subprocess.TimeoutExpired

    def __init__(self, raise_timeout=False):
        self.argv = None
        self.timeout = None
        self._raise = raise_timeout

    def run(self, argv, **kw):
        self.argv = argv
        self.timeout = kw.get("timeout")
        if self._raise:
            raise _subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return _FakeProc()


def _drive(raise_timeout=False, **kw):
    cap = _Capture(raise_timeout)
    real = ssh_util.subprocess
    ssh_util.subprocess = cap
    try:
        res = ssh_util.ssh_run("10.0.0.9", "echo hi", **kw)
    finally:
        ssh_util.subprocess = real
    return cap, res


if ssh_util is not None:
    # ── S1 · THE BUDGET IS NOT THE CONNECT TIMEOUT ──────────────────────────
    # Driven with the two constants set to DIFFERENT values, so a budget taken
    # from the wrong one is arithmetically visible rather than a coincidence.
    _c_real, _k_real = config.SSH_CONNECT_TIMEOUT, getattr(
        config, "SSH_COMMAND_TIMEOUT", None)
    try:
        config.SSH_CONNECT_TIMEOUT = 7
        if hasattr(config, "SSH_COMMAND_TIMEOUT"):
            config.SSH_COMMAND_TIMEOUT = 50
        cap, _ = _drive()
        got = cap.timeout
        # the old code produced connect+10 = 17; the new one connect+command = 57
        ck("S1", got == 57,
           f"the subprocess budget must be CONNECT + COMMAND (7+50=57), not a "
           f"function of the connect timeout alone — got {got!r}. The old code "
           f"gave `SSH_CONNECT_TIMEOUT + 10` = 17, which is why every untimed "
           f"fleet command was bounded at 22s in production.")

        # ── S2 · THE CONNECT TIMEOUT KEEPS ITS OWN JOB ─────────────────────
        joined = " ".join(cap.argv or [])
        ck("S2", "ConnectTimeout=7" in joined,
           f"-o ConnectTimeout must still be SSH_CONNECT_TIMEOUT — separating "
           f"the two must not cost the connect bound, which is what refuses an "
           f"unreachable box fast: {joined[:120]}")

        # ── S3 · AN EXPLICIT BUDGET STILL WINS ─────────────────────────────
        # Eight callers already pass their own (rotate_tokens 45/90, eod_report
        # 300, the conductor's VERIFY_TIMEOUT_S, orchestrator 15, eod_backfill's
        # DRAIN_TIMEOUT). None of them may silently change meaning.
        cap3, _ = _drive(timeout=30)
        ck("S3", cap3.timeout == 37,
           f"an explicit timeout must still govern the command (7+30=37) — "
           f"got {cap3.timeout!r}")

        # ── S4 · THE MESSAGE TELLS THE TRUTH ABOUT WHAT IS STILL RUNNING ───
        _cap4, res4 = _drive(raise_timeout=True, timeout=30)
        msg = (res4[2] or "")
        ck("S4", "37s" in msg and "STILL RUNNING" in msg.upper()
           and "S3.19" in msg,
           f"the timeout message must name the budget it waited out and warn "
           f"that the REMOTE COMMAND SURVIVES the client (S3.19) — two "
           f"abandoned fan-outs once held feed_store.db open and cost three "
           f"nights (S3.17). got: {msg!r}")
    finally:
        config.SSH_CONNECT_TIMEOUT = _c_real
        if _k_real is not None:
            config.SSH_COMMAND_TIMEOUT = _k_real

    # ── S5 · THE LEVER REACHES THE SSH LAYER ───────────────────────────────
    seen = {}

    def _fake_ssh_run(ip, command, timeout=None):
        seen["timeout"] = timeout
        return 0, "ok", ""

    # 🔴 THE IMPORT IS GUARDED SEPARATELY FROM THE CHECK, AND THE REASON IS
    # [[OPS.22]] REACHING A NEW VICTIM. `import fleet` pulls in a module that
    # resolves the zone `US/Eastern`, a LEGACY LINK tzdata 2026c moved into an
    # uninstalled package — so under `/usr/bin/python3` this raises
    # `ZoneInfoNotFoundError` while the venv (which carries the `tzdata` pip
    # package) imports it fine. Measured here: 7/7 under the venv, 6/7 under
    # the system interpreter, failing ONLY on this import.
    # ⚠️ SO AN ENVIRONMENT FAULT REPORTS **GREEN (VACUOUS) AND SAYS SO**,
    # rather than red. [[CHK.9]]/CV.1: a gate that fails for the machine
    # instead of the content is one the operator learns to skip, and the land
    # gate runs every CHECK under bare `python3`. ⚠️ ANY OTHER IMPORT FAILURE
    # IS STILL RED — this excuses the tz link and nothing else.
    _fleet_mod, _env_skip = None, None
    try:
        import fleet as _fleet_mod
    except Exception as _imp:                                   # noqa: BLE001
        if "ZoneInfoNotFound" in type(_imp).__name__ or "US/Eastern" in str(_imp):
            _env_skip = ("%s — OPS.22's legacy tz link, not a defect in this "
                         "delivery" % (_imp,))
        else:
            _env_skip = False
            ck("S5", False, f"importing fleet raised: {_imp!r}")
    if _env_skip:
        ck("S5", True, "")
        print(f"  [S5] GREEN (VACUOUS) — {_env_skip}. The --timeout wiring was "
              f"NOT exercised under this interpreter; it is under the venv, "
              f"which is what a login-shell land uses.")
    elif _fleet_mod is None:
        pass                                   # already reported red above
    else:
      try:
        fleet = _fleet_mod
        _real_run, _real_fleet = ssh_util.ssh_run, fleet.get_fleet
        ssh_util.ssh_run = _fake_ssh_run
        fleet.get_fleet = lambda only=None: [("AMD", "10.0.0.9", "running")]
        try:
            fleet.cmd_run("echo hi", timeout=99)
        finally:
            ssh_util.ssh_run, fleet.get_fleet = _real_run, _real_fleet
        ck("S5", seen.get("timeout") == 99,
           f"fleet.py run --timeout must reach ssh_run — got "
           f"{seen.get('timeout')!r}. Without it a known-slow fan-out can only "
           f"be fixed by moving the global default.")
      except Exception as exc:                                  # noqa: BLE001
        ck("S5", False, f"driving fleet.cmd_run raised: {exc!r}")

    # ── S6 · LIVE, AGAINST LOOPBACK — PAST THE OLD BOUND ───────────────────
    # 🔑 THE ONLY CHECK THAT PROVES THE FIX RATHER THAN THE ARITHMETIC, and it
    # needs no fleet: control's own sshd answers on 127.0.0.1 with the fleet
    # key. 25s is chosen to sit just past the OLD 22s ceiling — enough to have
    # failed before, short enough not to pad the land.
    probe = ssh_util.ssh_run("127.0.0.1", "echo LOOPBACK_OK", timeout=10)
    if probe[0] != 0 or "LOOPBACK_OK" not in (probe[1] or ""):
        ck("S6", True, "")
        print("  [S6] GREEN (VACUOUS) — loopback ssh unavailable here, so the "
              "live case was NOT exercised. Nothing to check must never read "
              "as everything checked.")
    else:
        t0 = time.time()
        rc6, out6, err6 = ssh_util.ssh_run("127.0.0.1", "sleep 25; echo PAST_OLD_BOUND")
        el = time.time() - t0
        ck("S6", rc6 == 0 and "PAST_OLD_BOUND" in (out6 or ""),
           f"a 25s command must now COMPLETE — the old 22s bound killed it and "
           f"reported `rc=255 ssh timeout`, which reads as a dead box. "
           f"elapsed={el:.1f}s rc={rc6} err={(err6 or '')[:90]!r}")

# ── S7 · THE --bake-only HELP DOES NOT CLAIM A RESTART ─────────────────────
# 🔑 ON THE AST, AND ON THE `help=` VALUE ITSELF. A grep for the word would
# match the comment that EXPLAINS this defect and the changelog paragraph §5
# requires — §20's collision, exactly. The help string is a definition; the
# prose around it is not.
try:
    _wb = os.path.join(ROOT, "wake_and_bake.py")
    _tree = ast.parse(open(_wb, encoding="utf-8").read())
    _help = None
    for node in ast.walk(_tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "add_argument"
                and any(isinstance(a, ast.Constant) and a.value == "--bake-only"
                        for a in node.args)):
            for kw in node.keywords:
                if kw.arg == "help":
                    _help = ast.literal_eval(kw.value)
    ck("S7", _help is not None and "restart" not in _help.lower().replace(
            "does not restart", "").replace("not restart", ""),
       f"--bake-only's argparse help must not advertise a restart: it syncs "
       f"and does NOT restart (source :76, :457, and the menu label agree). "
       f"dtp r301/DEV.1 fixed the DOCSTRING and left this string — C.30, sweep "
       f"the readers. got {_help!r}")
except Exception as exc:                                        # noqa: BLE001
    ck("S7", False, f"wake_and_bake.py did not parse: {exc!r}")

# ── S8 · 🔴 THE SHAPE, NOT THE THREE NAMES ────────────────────────────────
# `ssh_run` was not the only offender: `scp_push` and `scp_pull` resolved their
# budget the same wrong way, and the FIRST cut of r406 fixed one of three. The
# delivery's own NEG assertion caught it, which is luck dressed as process —
# §23 (*fix the hop upstream, not just the one that broke*) and the half-sweep
# [[SH.2]], [[DEP.11]] and [[CFG.2]] each record.
# 🔑 SO THIS ASSERTS THE RELATIONSHIP OVER EVERY FUNCTION THAT TAKES A
# `timeout`, BY AST, rather than naming the three that exist today — a list of
# names rots permissively, which is r35's allow-list lesson. A fourth helper
# added next month is covered the day it is written.
try:
    _su = os.path.join(ROOT, "ssh_util.py")
    _t = ast.parse(open(_su, encoding="utf-8").read())
    _bad = []
    for fn in ast.walk(_t):
        if not isinstance(fn, ast.FunctionDef):
            continue
        if not any(a.arg == "timeout" for a in fn.args.args):
            continue
        for node in ast.walk(fn):
            # the shape `X = timeout or config.<NAME>`
            if not isinstance(node, ast.Assign):
                continue
            v = node.value
            if not (isinstance(v, ast.BoolOp) and isinstance(v.op, ast.Or)):
                continue
            for operand in v.values:
                if (isinstance(operand, ast.Attribute)
                        and getattr(operand.value, "id", "") == "config"
                        and operand.attr != "SSH_COMMAND_TIMEOUT"):
                    _bad.append((fn.name, operand.attr))
    ck("S8", not _bad,
       f"function(s) resolving a command budget from the wrong constant: "
       f"{_bad} — a timeout= default must come from SSH_COMMAND_TIMEOUT. "
       f"ssh_run, scp_push and scp_pull all had this and the first fix "
       f"repaired one of three.")
except Exception as exc:                                        # noqa: BLE001
    ck("S8", False, f"ssh_util.py did not parse: {exc!r}")

bad = [n for n, ok, _ in _res if not ok]
print(f"\n  {len(_res) - len(bad)}/{len(_res)} passed")
if bad:
    print(f"  FAILED: {', '.join(bad)}")
sys.exit(1 if bad else 0)
