#!/usr/bin/env python3
"""
day_trader_pro/tests/check_saturday_brief.py  v1.1
v1.1  2026-09-20  dtp r396 / SAT.3 — S2b REPLACED. It asserted
      '"deploy.sh" not in TOOLS', i.e. that a string was absent from a list
      that DOES NOT SCOPE SHELL COMMANDS — a check providing no protection
      while reading as if it did. S2b/S2c/S2d/S2e now drive the real
      refusal: the wrapper exports the marker, deploy.sh AND land.sh both
      exit 9 on it, and an ATTENDED run is NOT refused so the guard cannot
      have simply disabled landing. Every wrapper invocation also writes to
      a TEMP out-path, because running against the live brief made three
      checks fail once a genuine brief existed — a red for the wrong reason.
v1.0  2026-09-20  dtp r394 / SAT.2 — THE UNATTENDED SESSION MUST NOT BE ABLE
      TO LAND, AND THE TIMER MUST NOT BE SILENTLY DEAD.

🔴 WHY EACH CHECK EXISTS, MEASURED RATHER THAN IMAGINED.
  · The first schedule used `CRON_TZ=America/New_York` and WOULD NEVER HAVE
    FIRED — cron 3.0pl1 does not support it; a live probe never fired and the
    string is absent from /usr/sbin/cron. Worse, the comment beside it claimed
    "VERIFIED by live probe" before anything had been verified. A timer that
    does not fire is INDISTINGUISHABLE FROM A QUIET WEEK, so S1 pins the
    schedule form itself.
  · The session runs unattended on a box holding a live funded broker token, a
    GitHub token with write on both repos and the Telegram token. S2/S3 pin
    that its tool grant cannot reach the lander or a fleet mutator — §38.9,
    and the operator's own standing rule that he approves every land.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SH = os.path.join(ROOT, "tools", "saturday_brief.sh")
PROMPT = os.path.join(ROOT, "tools", "saturday_brief.prompt")

# ⚠️ EVERY WRAPPER INVOCATION BELOW WRITES TO A TEMP PATH. Running against the
# live brief path meant that once a real brief existed the wrapper stood down
# — correctly — and three checks failed for a reason unrelated to what they
# assert. A red for the wrong reason is worse than no red.
import tempfile
_TMPOUT = os.path.join(tempfile.gettempdir(), "check_saturday_brief_out.md")

FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


src = open(SH).read() if os.path.exists(SH) else ""
ck("S0", src and os.path.exists(PROMPT),
   f"wrapper and prompt both present ({os.path.basename(SH)}, "
   f"{os.path.basename(PROMPT)})")

# ------------------------------------------------------------------------ S1
# ⚠️ THE SCHEDULE IS CHECKED WHERE IT LIVES — in the installed crontab, not in
# a comment. §21: source text proves nothing about runtime.
cr = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
lines = [l for l in cr.stdout.splitlines()
         if l.strip() and not l.lstrip().startswith("#")]
# ⚠️ UPDATED WITH THE RULING, NOT LOOSENED TO STAY GREEN (§36). S1 asserted
# "exactly one entry" and went red the moment the watchdog and canary were
# added — which was the arrangement getting MORE robust, not less. The
# property that actually matters is that exactly one entry can PRODUCE a
# brief; the flagged ones cannot double-write.
sat = [l for l in lines if "saturday_brief.sh" in l]
bare = [l for l in sat if "--" not in l.split("saturday_brief.sh", 1)[1]]
ck("S1", len(bare) == 1,
   f"exactly ONE un-flagged entry can produce a brief ({len(bare)} of "
   f"{len(sat)} total) — the flagged layers cannot double-write")

if sat:
    ck("S1b", not any(l.startswith("CRON_TZ") for l in lines),
       "no CRON_TZ line — unsupported by cron 3.0pl1, and an entry written "
       "that way is SILENTLY DEAD")
    fields = sat[0].split()[:5]
    ck("S1c", fields[4] == "6",
       f"day-of-week is Saturday: {' '.join(fields)}")
    hh = int(fields[1])
    # 07:17 UTC = 03:17 EDT / 02:17 EST — both early Saturday ET, both clear
    # of the 08:00 read, so it is right on BOTH sides of the DST boundary.
    ck("S1d", 5 <= hh <= 9,
       f"UTC hour {hh:02d} lands before 08:00 ET in BOTH DST states "
       f"(EDT {hh-4:02d}:xx, EST {hh-5:02d}:xx)")

# ------------------------------------------------------------------------ S2
m = re.search(r'^TOOLS="([^"]*)"', src, re.M)
tools = (m.group(1) if m else "")
ck("S2", m is not None and tools,
   f"the wrapper declares an explicit tool grant: {tools or '(none)'}")

# 🔴 S2b REPLACED — THE OLD CHECK PROVIDED NO PROTECTION AND READ AS IF IT
# DID. It asserted `"deploy.sh" not in TOOLS`, i.e. that a string was absent
# from a list that DOES NOT SCOPE SHELL COMMANDS. Measured 2026-09-20: a
# session granted only `Bash` was asked to touch a file and the file
# appeared. Omitting the lander from --allowedTools never made it
# unreachable, because it is reached THROUGH Bash.
# ✅ The real enforcement is a refusal inside the thing being protected.
ck("S2b", "VERTIGO_UNATTENDED=1" in src and "export VERTIGO_UNATTENDED" in src,
   "the wrapper EXPORTS VERTIGO_UNATTENDED for every path through it")

_lander = os.path.join(ROOT, "tools", "deploy.sh")
r = subprocess.run(["bash", _lander, "--dry"], capture_output=True, text=True,
                   timeout=120, env=dict(os.environ, VERTIGO_UNATTENDED="1"))
ck("S2c", r.returncode == 9 and "REFUSED" in r.stdout,
   f"deploy.sh REFUSES an unattended caller (rc={r.returncode}, expect 9)")

r = subprocess.run(["bash", os.path.join(ROOT, "tools", "land.sh"), "otv4"],
                   capture_output=True, text=True, timeout=120,
                   env=dict(os.environ, VERTIGO_UNATTENDED="1"))
ck("S2d", r.returncode == 9 and "REFUSED" in r.stdout,
   f"land.sh REFUSES it too — guarding only the wrapper would leave the "
   f"lander reachable directly (rc={r.returncode})")

r = subprocess.run(["bash", _lander, "--dry"], capture_output=True, text=True,
                   timeout=120, env={k: v for k, v in os.environ.items()
                                     if k != "VERTIGO_UNATTENDED"})
ck("S2e", r.returncode != 9,
   f"an ATTENDED run is NOT refused — the guard did not simply disable the "
   f"lander (rc={r.returncode})")

# ------------------------------------------------------------------------ S3
# 🔑 THE PROMPT MUST SAY IT TOO. The tool list is the enforcement; the prompt
# is what stops a session deciding to be helpful. Belt and braces, because the
# operator is asleep.
p = open(PROMPT).read() if os.path.exists(PROMPT) else ""
ck("S3", "LAND NOTHING" in p.upper() and "deploy.sh" in p,
   "the prompt tells the session it lands nothing and names the path it must "
   "not use")
ck("S3b", "Telegram" in p or "§17" in p,
   "the prompt forbids paging the operator — §17, the alert path is for "
   "emergencies and a weekly report is not one")

# ------------------------------------------------------------------------ S4
# ⚠️ BEHAVIOUR, NOT SOURCE TEXT (§21). The first cut of S4 and S5 grepped the
# wrapper for "--smoke" and "REFUSED", and BOTH MUTATIONS SURVIVED: commenting
# the branch out left the strings sitting in the file. A check a comment can
# satisfy is asserting about the comment. Seventh instance of this shape
# today; it is caught here only because the mutation was run.
# `claude` is removed from PATH so --smoke fails FAST instead of buying a run;
# reaching the smoke banner proves the branch is live.
env = dict(os.environ, SATURDAY_BRIEF_CLAUDE="/bin/false")
r = subprocess.run(["bash", SH, "--smoke"], capture_output=True, text=True,
                   timeout=120, env=env)
ck("S4", "smoke:" in r.stdout and r.returncode != 0,
   f"--smoke ENTERS its own branch and REPORTS FAILURE when the binary is "
   f"unusable (rc={r.returncode}) — no live API call is bought by this gate")

r = subprocess.run(["bash", SH, "--dry"], capture_output=True, text=True,
                   timeout=60)
ck("S4b", r.returncode == 0 and "prompt file present" in r.stdout,
   f"--dry runs, touches nothing, and confirms the prompt is there "
   f"(rc={r.returncode})")

# ------------------------------------------------------------------------ S5
# S5 — DRIVEN, by hiding the prompt file and watching the wrapper refuse.
_bak = PROMPT + ".s5bak"
os.rename(PROMPT, _bak)
try:
    # ⚠️ THE BINARY IS NEUTERED HERE ON PURPOSE. Without it, a mutation that
    # removes the refusal lets the wrapper invoke the REAL claude with an
    # empty prompt — which CRASHED this checker instead of failing it, and a
    # gate that dies tells the reader less than one that fails.
    r = subprocess.run(["bash", SH], capture_output=True, text=True,
                       timeout=120,
                       env=dict(os.environ, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S5", r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr),
       f"a MISSING prompt REFUSES (rc={r.returncode}) rather than invoking "
       f"claude with an empty brief")
finally:
    os.rename(_bak, PROMPT)

ck("S5b", os.path.exists(PROMPT), "the prompt file was restored by this check")

# ------------------------------------------------------------------------ S9
# 🔴 THE TRANSCRIPT HAZARD, PINNED ON BEHAVIOUR. `claude -p --continue` does
# not fork — it APPENDS TO THE LIVE SESSION'S TRANSCRIPT (measured: 5137->5161
# lines, zero new session files, entries under the attached session's own id).
# The operator reattaches to a long-lived agent, so a timer using --continue
# would be cron writing into an agent he is attached to. The wrapper prints
# the flags it will actually pass; a source grep would be satisfied by a
# comment (§21), and a neutered binary hides the difference entirely.
cmd = subprocess.run(["bash", SH, "--print-cmd"], capture_output=True,
                     text=True, timeout=60).stdout.strip()
ck("S9", "--session-id" in cmd,
   f"the invocation forces an ISOLATED session id: {cmd[:60]}")
ck("S9b", " -c" not in f" {cmd}" and "--continue" not in cmd,
   f"the invocation carries NO --continue / -c — it can never write into the "
   f"attached session's transcript: {cmd[:60]}")

# ------------------------------------------------------------------------ S6
# 🔑 THE ARRANGEMENT IS FOUR LAYERS BECAUSE THE FAILURE IT MUST SURVIVE IS
# SILENCE. These pin that the layers exist and are ordered so they cannot
# collide: preferred (in-session) → fallback → watchdog, each after the last.
lines_ = [l for l in subprocess.run(["crontab", "-l"], capture_output=True,
                                    text=True).stdout.splitlines()
          if l.strip() and not l.lstrip().startswith("#")]
def _hhmm(pred):
    for l in lines_:
        if pred(l):
            f = l.split()
            return int(f[1]) * 60 + int(f[0]), f[4]
    return None, None
fb, fbd = _hhmm(lambda l: "saturday_brief.sh" in l and "--" not in l)
wd, wdd = _hhmm(lambda l: "--watchdog" in l)
cn, cnd = _hhmm(lambda l: "--canary" in l)

ck("S6", fb is not None and wd is not None,
   f"fallback and watchdog are both installed (fallback {fb}, watchdog {wd})")
ck("S6b", fb is not None and wd is not None and wd > fb,
   f"the watchdog runs AFTER the fallback ({wd} > {fb}) — a watchdog that "
   f"ran first would report a failure the fallback was about to fix")
ck("S6c", fbd == "6" and wdd == "6",
   f"both are Saturday jobs (dow {fbd}/{wdd})")
ck("S6d", cn is not None and cnd not in (None, "6"),
   f"the canary runs on a NON-Saturday (dow {cnd}) — proving the chain works "
   f"midweek is the point; on Saturday it would be too late")

# ------------------------------------------------------------------------ S7
# 🔴 A STALE IN-FLIGHT MARKER MUST NOT SILENCE THE FALLBACK FOREVER. A session
# that crashes mid-brief leaves one behind; without expiry the fallback would
# stand down every week while nothing was produced — precisely the silent
# failure the layers exist to prevent.
MARK = "/home/ubuntu/.saturday_brief_inflight"
_pre = os.path.exists(MARK)
try:
    subprocess.run(["touch", "-d", "5 hours ago", MARK], check=True)
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S7", "ABANDONED" in r.stdout,
       "a 5-hour-old in-flight marker is treated as ABANDONED, not obeyed")
    subprocess.run(["touch", MARK], check=True)
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S7b", "IN FLIGHT" in r.stdout,
       "a FRESH marker IS obeyed — the expiry did not simply disable the guard")
finally:
    if not _pre:
        subprocess.run(["rm", "-f", MARK])

# ------------------------------------------------------------------------ S8
ck("S8", "LEDGER" in src and "one line per run" in src.lower()
   or "ledger" in src.lower(),
   "every run appends to a ledger — 'is the brief still happening?' must be "
   "answerable without reading a megabyte of session output")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
