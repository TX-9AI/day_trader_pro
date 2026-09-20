#!/usr/bin/env python3
"""
tests/check_claude_boot.py  v1.0
v1.0  2026-09-20  r401 / OPS.26 — the gate on the boot-time agent raiser.

🔴 WHAT IT PROTECTS. `tools/claude_boot.py` runs from a systemd unit at boot,
with no login profile, no PATH and nobody watching. Every failure it can have
is SILENT on control, because — unlike the OTV4TEST fork's box — control runs
no `optionsbot` and there is therefore no boot alert for a status to ride on.

  B1  both binaries resolve with NO login PATH          (the fork's hard one)
  B2  an EXISTING claude session means it raises NOTHING (the safety property)
  B3  the resurrected agent carries the operator's REAL permissions
  B4  `--guarded` is a real opt-in, exporting BEFORE the binary
  B8  it continues the last conversation and never `--fork-session`s
  B11 🔴 THIS GATE CANNOT PAGE THE OPERATOR — capture is forced (§17)
  B11b and the guard is ASSERTED without exercising what it guards
  B12 🔴 the launch line UNSETS ANTHROPIC_API_KEY — subscription, not API
  B13 🔴 previous tmux sessions are KILLED first, driven on a private server
  B5  a status line is written on EVERY path, including failures
  B6  the session finder walks the PROCESS TREE, driven against a real tmux
  B7  it never exits non-zero — a failed raise must not fail the unit

⚠️ B6 IS DRIVEN AGAINST A PRIVATE tmux SERVER, not asserted from source, which
is the shape `check_resume_item` RA3 already uses for the same question.
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOT = os.path.join(ROOT, "tools", "claude_boot.py")
FAILS, RAN = [], []
_SANDBOX = tempfile.mkdtemp(prefix="cb_sandbox_")


def ck(name, ok, detail=""):
    RAN.append(name)
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def child_env(extra=None):
    """The environment every child of this gate gets. EXTRACTED SO IT IS
    ASSERTABLE WITHOUT RUNNING THE THING IT PROTECTS.

    🔴 TWO LAYERS, AND THE SECOND EXISTS BECAUSE THE FIRST WAS NOT ENOUGH.
    · `DTP_NOTIFY_CAPTURE=1` makes `notify` capture instead of send.
    · `DTP_TELEGRAM_TOKEN=""` makes a send IMPOSSIBLE even if the first is
      removed — `notify.send` refuses without a token.

    🔴 WHY BOTH, WRITTEN AT THE SITE SO NOBODY TRIMS IT BACK TO ONE.
    On 2026-09-20 this gate paged the operator TWICE, in two different ways.
    First: `run()` did not set capture at all, so every invocation found his
    live session and sent a real Telegram. Then, proving the fix, **the
    MUTATION removed the capture and the gate was RUN — which is the unsafe
    behaviour, executed for real, and sent two more.**
    ⚠️ **THAT IS THE LESSON AND IT GENERALISES: MUTATING A SAFETY PROPERTY AND
    THEN EXECUTING IT PERFORMS THE UNSAFE ACT.** A mutation test on a guard
    whose job is preventing a real-world side effect must be run where the side
    effect CANNOT happen — otherwise the proof is the incident. The blanked
    token is what makes that true here, so the capture can be mutated freely.
    §17: a channel that has cried wolf once gets read more slowly forever.
    """
    e = dict(os.environ)
    e["DTP_NOTIFY_CAPTURE"] = "1"
    e["DTP_TELEGRAM_TOKEN"] = ""
    # 🔴 AND IT NEVER WRITES TO THE LIVE STATUS PATH. B13's first cut omitted
    # this and stamped `day_trader_pro/data/AGENT_STATUS` in the REAL tree —
    # a checker mutating the repo it is checking, found only because
    # `git status` went dirty on the way to a land.
    e.setdefault("CLAUDE_BOOT_STATUS", os.path.join(_SANDBOX, "AGENT_STATUS"))
    if extra:
        e.update(extra)
    return e


def run(args, env=None, timeout=60):
    r = subprocess.run([sys.executable, BOOT] + args, capture_output=True,
                       text=True, timeout=timeout, env=child_env(env))
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cb", BOOT)
    cb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cb)

    # ── B1 — the failure the fork actually had. A unit reads no profile and
    # tmux runs under /bin/sh; `claude` lives in ~/.local/bin, so `command -v`
    # succeeds by hand and fails at boot ON THE SAME BOX.
    import shutil as _sh
    real_which, seen = _sh.which, {}

    def _blind(n, *a, **k):
        seen[n] = True
        return None                      # simulate: nothing on PATH at all
    cb.shutil.which = _blind
    got_t, got_c = cb._resolve("tmux"), cb._resolve("claude")
    cb.shutil.which = real_which
    ck("B1", bool(got_t) and bool(got_c) and seen,
       "both binaries resolve with NO PATH at all: tmux={} claude={}".format(
           got_t, got_c))

    tmpd = tempfile.mkdtemp(prefix="cb_")
    st = os.path.join(tmpd, "AGENT_STATUS")

    # ── B2/B7 — this box HAS a live claude session (this one). The raiser must
    # see it and raise nothing, and must exit 0.
    rc, out = run(["--status-only"], {"CLAUDE_BOOT_STATUS": st})
    ck("B2", rc == 0 and "up (" in out,
       "--status-only REPORTS the live agent and changes nothing: {}".format(
           out.strip().splitlines()[-1] if out.strip() else "(no output)"))
    ck("B7", rc == 0, "exit code is 0 so a raise failure cannot fail the "
                      "unit (rc={})".format(rc))

    # ── B5 — the status file exists and is stamped, on the path just taken.
    body = open(st, encoding="utf-8").read().strip() if os.path.exists(st) else ""
    parts = body.split("|")
    ck("B5", len(parts) >= 2 and parts[0].isdigit() and int(parts[0]) > 1_700_000_000,
       "a STAMPED status line is written: {!r}".format(body))

    # ── B3/B4 — the guard is in the command the raiser would run. Asserted on
    # the COMMAND STRING the module builds, not on a source grep.
    # ⚠️ CALLED, NOT GREPPED (§21). A source match would be satisfied by the
    # function's own docstring, which names the variable.
    default_cmd = cb.launch_cmd("/x/claude", "--resume abc")
    guarded_cmd = cb.launch_cmd("/x/claude", "--resume abc", guarded=True)
    # 🔴 THE DEFAULT IS *UNGUARDED*, BY THE OPERATOR'S EXPLICIT RULING
    # (2026-09-20): "the exact permissions. I literally want that agent
    # resurrected." A guard would make the resurrected agent REFUSE to land,
    # which is not the same agent. The exposure is recorded in [[OPS.26]];
    # this check pins that the ruling is what shipped.
    ck("B3", "VERTIGO_UNATTENDED" not in default_cmd,
       "the resurrected agent carries the operator's REAL permissions, not a "
       "neutered set: {!r}".format(default_cmd))
    ck("B4", "export VERTIGO_UNATTENDED=1;" in guarded_cmd
       and guarded_cmd.index("VERTIGO_UNATTENDED") < guarded_cmd.index("/x/claude"),
       "--guarded is available and exports BEFORE the binary, so the opt-in "
       "is real: {!r}".format(guarded_cmd))

    # ── B8 — `--continue`, and never a fork. `--fork-session` would create a
    # NEW session id when resuming, which is the opposite of what the operator
    # asked for and would look identical in the status line.
    mode8, how8 = cb.resume_mode(False)
    cmd8 = cb.launch_cmd("/x/claude", mode8)
    ck("B8", mode8 == "--continue" and "--fork-session" not in cmd8,
       "it continues the last conversation and never forks: {!r}".format(cmd8))

    # ── B6 — DRIVEN. A private tmux server with a pane whose command is a
    # SHELL: the finder must not report it as a claude session.
    tmux = cb._resolve("tmux")
    sock = os.path.join(tmpd, "s")
    ok6 = False
    if tmux:
        subprocess.run([tmux, "-S", sock, "new-session", "-d", "-s", "decoy",
                        "sleep 30"], capture_output=True, timeout=30)
        env2 = dict(os.environ, TMUX_TMPDIR=tmpd)
        r = subprocess.run([tmux, "-S", sock, "list-panes", "-a", "-F",
                            "#{pane_pid}|#S"], capture_output=True, text=True,
                           timeout=15, env=env2)
        got = [ln for ln in r.stdout.splitlines() if "decoy" in ln]
        # the decoy exists as a pane, and carries NO claude in its tree
        ok6 = bool(got) and "decoy" not in cb.claude_sessions(tmux)
        subprocess.run([tmux, "-S", sock, "kill-server"], capture_output=True,
                       timeout=15)
    ck("B6", ok6,
       "a real tmux session with NO claude in its pane tree is NOT reported "
       "as an agent — 'the session exists' would have said UP")

    # ── B11 — 🔴 THIS GATE CANNOT PAGE THE OPERATOR. Driven, not asserted:
    # run the real entry point with capture ON and require that the alert was
    # COMPOSED and CAPTURED rather than sent. Capturing is strictly stronger
    # than silencing, because it proves the message was built (notify.py's own
    # reasoning, and the shape r387's gate uses).
    import json as _json
    probe = os.path.join(tempfile.mkdtemp(prefix="cb_tg_"), "out.json")
    code = ("import sys,json,importlib.util;"
            "spec=importlib.util.spec_from_file_location('cb',%r);"
            "cb=importlib.util.module_from_spec(spec);spec.loader.exec_module(cb);"
            "cb.announce('up','continue');"
            "sys.path.insert(0,%r);import notify;"
            "open(%r,'w').write(json.dumps(notify.captured()))"
            % (BOOT, os.path.join(os.path.expanduser("~"), "day_trader_pro"),
               probe))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=60,
                       env=child_env())
    try:
        caught = _json.load(open(probe))
    except Exception:                                           # noqa: BLE001
        caught = []
    # ⚠️ ASSERTS THE BOX LABEL, not the tool name. The operator corrected the
    # subject on 2026-09-20 and this is what pins it: the alert must identify
    # WHICH BOX booted, because it lands in a channel shared with fifteen
    # others and `claude_boot` names none of them.
    ck("B11", len(caught) == 1 and "1-REPORTER [boot]" in caught[0]
       and "Claude up" in caught[0] and " IP " in caught[0],
       "the alert is COMPOSED and CAPTURED, never sent — this checker cannot "
       "page the operator (§17): {!r}".format(caught[0] if caught else None))

    # ── B11b — THE GUARD IS ASSERTED WITHOUT EXERCISING WHAT IT GUARDS.
    # Checked on the env dict itself, so proving this can never page anyone —
    # which is precisely the mistake that produced it.
    _e = child_env()
    ck("B11b", _e.get("DTP_NOTIFY_CAPTURE") == "1"
       and _e.get("DTP_TELEGRAM_TOKEN") == "",
       "every child gets BOTH capture AND a blanked token, so a send is "
       "impossible even if capture is removed")

    # ── B12 — 🔴 THE SUBSCRIPTION, NOT THE API KEY. The operator's explicit
    # requirement. `day_trader_pro/.env` CONTAINS `ANTHROPIC_API_KEY` and the
    # unit loads that file for the Telegram credentials, so without the unset
    # the resumed session bills the API. Item 39 carries the same `env -u`.
    _c12 = cb.launch_cmd("/x/claude", "--continue")
    ck("B12", _c12.startswith("env -u ANTHROPIC_API_KEY ")
       or " env -u ANTHROPIC_API_KEY " in _c12,
       "the launch line UNSETS ANTHROPIC_API_KEY before claude, so the "
       "session runs on the subscription: {!r}".format(_c12[:60]))

    # ── B13 — 🔴 KILL-FIRST, DRIVEN AGAINST A PRIVATE SERVER.
    # This tool kills every tmux session. Exercising that against the real
    # server would kill the operator's own thread, so `CLAUDE_BOOT_TMUX_SOCKET`
    # exists purely to make the destructive path testable — an untestable
    # destructive path is one that ships unexercised.
    sock2 = os.path.join(tmpd, "s2")
    ok13 = False
    if tmux:
        for nm in ("victim-a", "victim-b"):
            subprocess.run([tmux, "-S", sock2, "new-session", "-d", "-s", nm,
                            "sleep 60"], capture_output=True, timeout=30)
        before = subprocess.run([tmux, "-S", sock2, "list-sessions", "-F", "#S"],
                                capture_output=True, text=True, timeout=15).stdout.split()
        run(["--quiet"], {"CLAUDE_BOOT_TMUX_SOCKET": sock2,
                          "CLAUDE_BOOT_CWD": tmpd})
        after = subprocess.run([tmux, "-S", sock2, "list-sessions", "-F", "#S"],
                               capture_output=True, text=True, timeout=15).stdout.split()
        ok13 = (len(before) == 2 and "victim-a" not in after
                and "victim-b" not in after)
        subprocess.run([tmux, "-S", sock2, "kill-server"], capture_output=True,
                       timeout=15)
    ck("B13", ok13,
       "every pre-existing tmux session is KILLED before the new one is "
       "raised (item 39's behaviour): before={} after={}".format(
           before if tmux else "?", after if tmux else "?"))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS ({})".format(len(RAN)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
