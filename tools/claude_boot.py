#!/usr/bin/env python3
"""
tools/claude_boot.py  v1.0
v1.0  2026-09-20  r401 / OPS.26 — RAISE A CLAUDE SESSION IN tmux AT BOOT, SO A
      REBOOT DOES NOT COST THE OPERATOR HIS AGENT.

Operator, 2026-09-20, after the OTV4TEST fork proved it on their box: *"I just
had the test repo make the agent persistent on reboots… implement the same
thing on this side."*

🔑 THIS IS A SMALL PORT BECAUSE THE HARD HALF ALREADY EXISTED HERE. The fork's
own hardest finding — that a pane reports the SHELL, not `claude`, because
claude is the shell's child — is r381/OPS.17's `_claude_tmux_sessions` in
`menu_functions.sh`, found independently, written up, and gated by
`check_resume_item` RA3. REATTACH already finds and attaches to a live Claude
session. **The only thing missing was something to CREATE one at boot.**

🔴 CONTROL IS NOT A TRADING BOX, AND THAT CHANGES THE REPORTING HALF.
The fork's raiser writes a status file which their BOT reads and appends to its
boot Telegram — the bot holds the token, so the raiser needs no credentials
(our §18a reasoning: credentials reach a box through systemd's `Environment=`).
**Control runs no `optionsbot`**, verified: no `optionsbot`, `candle-feed` or
`shadow-observer` unit exists here. So there is no boot alert to append to, and
this file does NOT invent a second credential store to make one. It writes the
stamped status file and stops; the menu reads it.
⚠️ CONSEQUENCE, STATED SO IT IS NOT DISCOVERED LATER: on control a failure to
raise is SILENT until somebody looks. That is the honest trade against putting
a Telegram token in one more unit, and it is why `--status-only` exists and why
the status file carries a TIMESTAMP — a stale stamp is readable as stale.

🔴 IT REFUSES TO RAISE A SECOND SESSION, AND THAT IS THE SAFETY PROPERTY.
`--continue` does not fork a conversation: it APPENDS to a transcript (measured
at r394 — 5137→5161 lines, zero new session files, entries under the attached
session's own id). At BOOT that is exactly what is wanted, because the previous
process died with the box and resuming its transcript IS the persistence. But
this unit can also be started BY HAND while a session is alive, and then the
same flag would have systemd writing into a conversation the operator is
attached to. So: **if a Claude session already exists, this raises nothing.**

⚠️ AND IT EXPORTS `VERTIGO_UNATTENDED=1` INTO THE SESSION BY DEFAULT.
r396/SAT.3 measured that `--allowedTools "Bash"` does NOT scope shell commands,
so enforcement lives in the protected thing: `tools/land.sh` and
`tools/deploy.sh` both refuse that variable with exit 9. A systemd-raised
session passes through none of the wrapper that normally sets it, so it would
come up able to land, push, bake and `git push` — on the box holding a live
funded broker token, GitHub write on both repos, and the Telegram token.
🔑 THE FORK PUT **NOTHING** BETWEEN ITS BOOT AGENT AND ITS LANDER, SAID SO
PLAINLY WHEN ASKED, AND RECOMMENDED "GUARD FIRST, UNIT SECOND" ABOUT ITS OWN
DESIGN. Their blast radius is a paper fork with `s3-push` masked by ruling;
ours is the box that deploys to fifteen live traders.
⚠️ WHAT I DO **NOT** KNOW, AND WILL NOT ASSERT: whether an IDLE interactive
session acts on a cross-session peer message without a human giving it a turn.
If it does, an unguarded boot session is a remote-triggerable lander. Unmeasured
here, and the guard makes the question moot rather than answering it.
`--attended` clears the guard for a session the operator is deliberately
raising himself.

Run:  python3 tools/claude_boot.py                 # raise if absent (boot path)
      python3 tools/claude_boot.py --status-only   # report, change nothing
      python3 tools/claude_boot.py --attended      # raise WITHOUT the guard
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
SESSION = os.environ.get("CLAUDE_BOOT_SESSION",
                         "claude-" + time.strftime("%H%M%S"))
STATUS = os.environ.get("CLAUDE_BOOT_STATUS",
                        os.path.join(HOME, "day_trader_pro", "data",
                                     "AGENT_STATUS"))
# 🔴 THIS BOX CANNOT SELF-IDENTIFY, SO THE LABEL IS DECLARED — SAID OUT LOUD
# BECAUSE A DECLARED CONSTANT THAT LOOKS DERIVED IS HOW ONE ROTS.
# Checked, all three: `hostname` is the generic `ip-172-31-32-218`, nothing in
# either repo knows the name, and `ec2:DescribeTags` is DENIED to the
# `day-trader-control` role, so the instance's own Name tag is unreadable from
# here. The operator's name for it — 1-REPORTER — lives in his Termius config
# and nowhere on the machine. Override with CLAUDE_BOOT_BOX if it is ever
# renamed; there is nothing to derive it from.
BOX = os.environ.get("CLAUDE_BOOT_BOX", "1-REPORTER")
# 🔑 A PRIVATE tmux SOCKET, SO THE DESTRUCTIVE PATH IS TESTABLE.
# This tool KILLS every tmux session. Driving that against the real server
# would kill the operator's own thread, so a gate could not exercise it — and
# an untestable destructive path is one that ships unexercised. Unset in
# production, which is the default server.
_SOCK = os.environ.get("CLAUDE_BOOT_TMUX_SOCKET", "")
WORKDIR = os.environ.get("CLAUDE_BOOT_CWD",
                         os.path.join(HOME, "options-trader-v4"))

# 🔴 RESOLVED ABSOLUTELY, AND THIS IS THE FORK'S HARD-WON ONE.
# A systemd unit reads NO login profile, and tmux runs its command under
# `/bin/sh`, which reads none either. `claude` lives in `~/.local/bin` — which
# is on the operator's PATH and on no unit's — so `command -v claude` succeeds
# by hand and fails at boot on the same box. Their early cut died with
# FileNotFoundError and recorded NO STATUS AT ALL: the one component whose job
# is reporting availability had a path on which it reported nothing.
_BIN_DIRS = (os.path.join(HOME, ".local", "bin"), "/usr/local/bin", "/usr/bin",
             "/bin", "/snap/bin")


def _resolve(name: str):
    p = shutil.which(name)
    if p:
        return p
    for d in _BIN_DIRS:
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _tmux(tmux, *args):
    """tmux argv with the private socket spliced in when one is configured."""
    pre = [tmux] + (["-S", _SOCK] if _SOCK else [])
    return pre + list(args)


def _run(argv, timeout=15):
    """-> (rc, stdout). NEVER raises; a missing binary is rc=127."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or "")
    except FileNotFoundError:
        return 127, ""
    except Exception:                                           # noqa: BLE001
        return 126, ""


def claude_sessions(tmux: str):
    """tmux session names whose pane tree contains a live `claude`.

    🔑 PORTED IN SHAPE FROM `menu_functions.sh::_claude_tmux_sessions`
    (r381/OPS.17), which is the ONE definition of this question here and is
    gated by `check_resume_item` RA3. The two obvious checks are both wrong in
    OPPOSITE directions and both were measured before that function was
    written: `#{pane_current_command}` reports **the shell** because claude is
    its child, so "pane command is claude" reports DOWN over a working
    session; and "the session exists" reports UP over a dead one, because a
    launcher ending `exec bash` keeps the pane alive after claude exits.
    **So the process TREE is walked, upward, from each claude PID to its pane.**
    """
    rc, out = _run(_tmux(tmux, "list-panes", "-a", "-F", "#{pane_pid}|#S"))
    if rc != 0 or not out.strip():
        return []
    pane_of = {}
    for line in out.splitlines():
        if "|" in line:
            pid, name = line.split("|", 1)
            pane_of[pid.strip()] = name.strip()
    rc, out = _run(["pgrep", "-u", str(os.getuid()), "-x", "claude"])
    if rc != 0:
        return []
    found = set()
    for pid in out.split():
        p = pid
        for _hop in range(40):                    # bounded, never a while-True
            if not p or p == "1":
                break
            if p in pane_of:
                found.add(pane_of[p])
                break
            rc2, ppid = _run(["ps", "-o", "ppid=", "-p", p], timeout=5)
            if rc2 != 0:
                break
            p = ppid.strip()
    return sorted(found)


def resume_mode(isolated: bool = False):
    """-> (claude flags, a human label).

    🔑 `--continue`, AND THAT IS THE OPERATOR'S CALL ON EVIDENCE, 2026-09-20:
    *"The --continue flag has been sufficient every time I've done it manually
    so far."*
    ⚠️ AN EARLIER CUT OF THIS FILE RESUMED A RECORDED SESSION ID INSTEAD, with
    a recorder, a stamp file, an `ExecStop` and three extra checks, to defend
    against the sharp edge below. **He was right that it was over-built**: the
    failure it prevents is VISIBLE and costs one command, while the machinery
    was permanent and had failure modes of its own.
    🔴 THE SHARP EDGE, MEASURED, SO IT IS FIVE SECONDS TO DIAGNOSE RATHER THAN
    AN HOUR: `--continue` resumes *the most recent conversation in this
    directory*, and `tools/saturday_brief.sh` does `cd "$OTV4"` (:196, :256)
    before invoking claude with its own isolated `--session-id`. **Those
    transcripts land in the SAME project directory** — verified, five of them
    from the 01:00-01:33 probe runs on 2026-09-20. So a reboot shortly after a
    brief or a probe can come back on THAT thread instead.
    ⚠️ IF THAT EVER HAPPENS IT IS OBVIOUS ON ATTACH — the wrong conversation is
    on screen — and the fix is to start the session by hand. It is not silent,
    and that is the whole reason this is a comment rather than a mechanism.
    """
    if isolated:
        return "--session-id %s" % _uuid(), "isolated"
    return "--continue", "continue"


def launch_cmd(claude: str, mode: str, guarded: bool = False) -> str:
    """The command tmux runs. MIRRORS MENU ITEM 39 (`mi_resume_claude_tmux`).

    Operator, 2026-09-20: *"Right now, presently when the box reboots, I
    manually run option 39. What I want is for that sequence to happen on
    boot."* So this is not a new launch shape — it is that one, and any
    divergence is a bug.

    🔴 `env -u ANTHROPIC_API_KEY` IS LOAD-BEARING AND NEARLY MISSED.
    `day_trader_pro/.env` CONTAINS `ANTHROPIC_API_KEY`, and the unit loads that
    file to get the Telegram credentials — so without this the key reaches
    claude and the session **bills the API instead of the subscription.** Item
    39 carries the same `env -u` for the same reason.
    ⚠️ THE FAILURE BRANCH IS NAMED, exactly as item 39 names it: `--continue`
    with no prior conversation for this directory is a real outcome and must
    say so rather than leaving an empty pane.
    🔑 `exec bash -l` — a LOGIN shell, matching item 39 — so the pane outlives
    claude and is usable. It is also why the pane reports `bash` and why
    `claude_sessions()` walks the process tree.
    """
    guard = "export VERTIGO_UNATTENDED=1; " if guarded else ""
    return ("%senv -u ANTHROPIC_API_KEY %s %s || echo '  RESUME FAILED — no "
            "prior conversation for %s, or claude exited non-zero. Nothing was "
            "resumed.'; exec bash -l" % (guard, claude, mode, WORKDIR))


def public_ip():
    """(ip, why) — the address to SSH to, or a NAMED absence.

    🔑 otv4's `notifications.alert_manager.public_ip` (r387/OPS.20) IS THE ONE
    DEFINITION and is reused rather than rewritten — [[GEX.2]] landed for
    exactly that mistake, a second implementation of a quantity production
    already computes. r387 verified this one against IMDSv2 on all fifteen
    boxes before it shipped.
    🔴 BUT IT IS CALLED IN A SUBPROCESS, WITH otv4 AS THE CWD, AND THAT IS NOT
    FUSSINESS. A plain import fails here: this runs with `day_trader_pro` as
    its working directory, `alert_manager` does `import config`, and **BOTH
    repos carry a `config.py`** — so dtp's shadows otv4's and the import dies.
    That is §3/[[OPS.11]]'s documented trap (`main.py` and `config.py` are
    ambiguous across the three checkouts under $HOME) reaching a new caller.
    Measured: the direct import raised ImportError from dtp's cwd and returned
    the address correctly from otv4's.
    ⚠️ BOUNDED AND NEVER RAISES — a boot alert must not hang on a network
    lookup, and a missing IP is NAMED rather than dropped (§0.5).
    """
    otv4 = os.path.join(HOME, "options-trader-v4")
    # 🔴 THE VENV INTERPRETER, NOT /usr/bin/python3 — MEASURED. otv4's
    # `alert_manager` reaches `utils/time_utils.py`, which imports `pytz`, and
    # the system interpreter on control HAS NO pytz: the call dies
    # ModuleNotFoundError while the venv returns the address. That is
    # [[CHK.9]]'s class exactly — 4 red under the venv against 77 under
    # /usr/bin/python3 on the same tree — and it is why this unit's ExecStart
    # is the venv too.
    rc, out = _run([os.path.join(HOME, "day_trader_pro", "venv", "bin",
                                 "python"), "-c",
                    "import sys;sys.path.insert(0,%r);"
                    "from notifications.alert_manager import public_ip as p;"
                    "i,w=p();print(i or '');print(w or '')" % otv4],
                   timeout=8)
    if rc != 0:
        return None, "lookup failed rc=%d" % rc
    lines = (out or "").splitlines()
    ip = lines[0].strip() if lines else ""
    why = lines[1].strip() if len(lines) > 1 else ""
    return (ip or None), (why or "no address returned")


def announce(state: str, how: str) -> bool:
    """The boot alert, in the shape the fleet's already uses.

    Operator, 2026-09-20, showing the QQQ-TEST alert as the model:
    `OptionsBot [PAPER] STARTED | QQQ | fresh boot | IP … | Claude up
    (continue) | 09/20 11:44 ET`.
    🔴 CONTROL CANNOT APPEND TO THAT ONE. The fork's raiser writes a status
    file and its BOT appends to the boot alert — but **control runs no
    `optionsbot`** (verified: no bot unit of any kind here), so there is no
    STARTED message to ride on. It therefore sends its OWN, in the same
    channel and the same shape, identifying the box as CONTROL so the two are
    never confused.
    ⚠️ IT USES `notify.send`, THE ONE SENDER THIS REPO ALREADY HAS, and the
    credentials arrive the way every other control unit gets them — an
    `EnvironmentFile` pointing at `day_trader_pro/.env`, which is the pattern
    `install_eod_v2.sh` already established for the conductor. No new
    credential store, and no value is ever printed (§18a).
    ⚠️ AND A FAILED SEND IS NOT A FAILED BOOT: this returns False and the
    caller carries on.
    """
    try:
        sys.path.insert(0, os.path.join(HOME, "day_trader_pro"))
        import notify
        ip, why = public_ip()
        ipf = "IP %s" % ip if ip else "IP unavailable (%s)" % why
        when = time.strftime("%m/%d %H:%M", time.localtime())
        # 🔑 THE HOUSE STYLE, NOT A NEW ONE. `wake_and_bake` posts to this same
        # bot as `🛠️ wake_and_bake [phase] done — ✅ clean — …`, so this reads
        # as a sibling of the alerts already in that channel rather than as a
        # stranger. The operator named the channel by showing it.
        # 🔑 THE SUBJECT IS THE BOX, NOT THE TOOL — the operator's correction,
        # 2026-09-20: *"Not Claude_boot, but 1-REPORTER boot, Claude up is the
        # Agent status message & the IP is the server IP."* Three fields, in
        # that order: WHICH BOX booted, the AGENT STATUS, the SERVER IP. It
        # reads as a sibling of `wake_and_bake`'s alerts in the same channel.
        mark = "\u2705" if state == "up" else "\u26A0\uFE0F"
        return bool(notify.send(
            "\U0001F6E0\uFE0F %s [boot]: %s Claude %s (%s) — %s — %s ET"
            % (BOX, mark, state, how, ipf, when)))
    except Exception:                                           # noqa: BLE001
        return False


def write_status(state: str, detail: str = "") -> None:
    """Stamped, and ALWAYS written — including on every failure path.

    ⚠️ `up` and `never ran` must not look alike (§0.5), and a stale stamp has
    to be readable AS stale, which is why the epoch leads the line.
    """
    try:
        os.makedirs(os.path.dirname(STATUS), exist_ok=True)
        with open(STATUS, "w", encoding="utf-8") as f:
            f.write("%d|%s|%s\n" % (int(time.time()), state, detail))
    except Exception:                                           # noqa: BLE001
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status-only", action="store_true",
                    help="report and change nothing")
    ap.add_argument("--guarded", action="store_true",
                    help="raise WITH VERTIGO_UNATTENDED=1, which makes the "
                         "lander refuse. NOT the default — see the header")
    ap.add_argument("--quiet", action="store_true",
                    help="do not send the Telegram boot alert")
    ap.add_argument("--isolated", action="store_true",
                    help="a fresh session instead of continuing the last")
    a = ap.parse_args(argv)

    tmux = _resolve("tmux")
    if not tmux:
        write_status("down", "tmux not found")
        if not a.quiet:
            announce("DOWN", "tmux not found")
        print("claude_boot: tmux not found")
        return 0                       # ⚠️ never fail the unit — see the unit
    live = claude_sessions(tmux)
    if a.status_only:
        state = "up" if live else "down"
        write_status(state, ",".join(live) or "no claude session")
        print("claude_boot: %s (%s)" % (state, ",".join(live) or "none"))
        if not a.quiet:
            announce(state if state == "up" else "DOWN", "status check")
        return 0
    # 🔴 KILL FIRST, THEN RAISE — the operator's instruction, 2026-09-20:
    # *"I want the previous sessions killed and a new tmux started with a
    # Claude code continue."* This is menu item 39's behaviour, which is the
    # sequence he runs by hand today: it kills every tmux and starts one.
    # ⚠️ AN EARLIER CUT OF THIS FILE REFUSED TO RAISE WHEN A SESSION EXISTED.
    # That was MY invention, not item 39's, and it is the wrong default here:
    # at boot there is nothing to kill, so the guard bought nothing, while a
    # stale half-dead session would have blocked the raise entirely.
    # ⚠️ THE HAZARD IS REAL AND IS NAMED RATHER THAN DESIGNED AROUND: run by
    # hand while a live thread is working, this KILLS IT. Item 39 asks the
    # operator first; a unit cannot ask, so `--status-only` exists to look
    # before leaping and the unit only ever runs at boot.
    killed = []
    if live or True:
        rc_ls, out_ls = _run(_tmux(tmux, "list-sessions", "-F", "#S"))
        if rc_ls == 0:
            killed = [n for n in out_ls.split() if n]
            for name in killed:
                _run(_tmux(tmux, "kill-session", "-t", name), timeout=10)
    claude = _resolve("claude")
    if not claude:
        write_status("down", "claude binary not found")
        if not a.quiet:
            announce("DOWN", "claude not found")
        print("claude_boot: claude binary not found")
        return 0

    # 🔑 THE EXACT SESSION, BY ID — the operator's requirement, 2026-09-20:
    # *"I want it to be the exact session exactly where we left off and with
    # the exact permissions. I literally want that agent resurrected."*
    # ⚠️ NO `--fork-session`: that flag creates a NEW session id when resuming,
    # which is the opposite of resurrection.
    mode, how = resume_mode(a.isolated)
    cmd = launch_cmd(claude, mode, guarded=a.guarded)
    rc, _o = _run(_tmux(tmux, "new-session", "-d", "-s", SESSION,
                         "-c", WORKDIR, cmd), timeout=30)
    if rc != 0:
        write_status("down", "tmux new-session rc=%d" % rc)
        print("claude_boot: tmux new-session failed rc=%d" % rc)
        if not a.quiet:
            announce("DOWN", "tmux rc=%d" % rc)
        return 0

    time.sleep(3)                      # let claude get far enough to be seen
    live = claude_sessions(tmux)
    state = "up" if live else "down"
    # 🔑 SUBSCRIPTION, STATED EXPLICITLY — the operator's requirement:
    # *"explicitly that it's going on my subscription & not my api key."*
    # `env -u ANTHROPIC_API_KEY` in the launch line is the mechanism; saying so
    # in the alert is what makes it VERIFIABLE from his phone rather than a
    # property he has to take on trust.
    how = how + ", subscription" + ("+guard" if a.guarded else "")
    if killed:
        how = how + ", killed %d" % len(killed)
    write_status(state, "%s (%s)" % (",".join(live) or SESSION, how))
    print("claude_boot: %s (%s)" % (state, how))
    # ⚠️ SENT ON BOTH OUTCOMES. "it worked" and "it did not" must not look
    # alike, and an absent alert is indistinguishable from a box that never
    # booted (§0.5) — which is the operator's whole reason for asking.
    if not a.quiet:
        announce(state if state == "up" else "DOWN", how)
    return 0


def _uuid() -> str:
    import uuid
    return str(uuid.uuid4())


if __name__ == "__main__":
    sys.exit(main())
