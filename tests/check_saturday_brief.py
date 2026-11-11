#!/usr/bin/env python3
"""
day_trader_pro/tests/check_saturday_brief.py  v1.7
v1.7  2026-11-11  dtp r550 / CASH.1. S22/S22b: the QQQ cash size table runs every Saturday until 2026-12-07 and then
      skips itself. The prompt and the spec name both schemes ($250/$500 and $500/$750, cap = the ramp max), the
      refusal (never rounded to 1), fees beside EV, the date stop, and REPORT ONLY; the item stays out of the study queue.
v1.6  2026-11-11  dtp r549 / SAT.8. S21/S21b/S21c: the study queue runs on the boxes. The prompt starts
      tools/study_dispatch.py after the box reads, collects it with `wait`, runs `cleanup`, and does not CLOSE while
      it runs; the spec names the same; the wrapper exports STUDY_DISPATCH_DEADLINE_ET and runs the cleanup after
      the session. S20 still holds (the control fallback keeps the heavy lock).
v1.5  2026-11-11  dtp r548 / SAT.7. S20/S20b: the prompt and the spec name the study queue ~/reviews/WEEKEND_STUDIES.md and
      its rules (seal first, run once, the heavy lock, unfinished items to NOT MEASURED).
v1.4  2026-11-08  dtp r527 / SAT.6 (the 11-07 brief R9). S5 was RED in the 11-07 sweep, rc=0: the sweep ran while
      the real brief held the LIVE in-flight marker, the wrapper stood down on it, and the refusal was never
      reached. Worse, S7 touched that same live marker to "6 hours ago" and then left it — a sweep during a
      real brief backdated the running brief's guard. Every wrapper run here now uses a SCRATCH marker
      (_SCRATCH carries SATURDAY_BRIEF_MARKER); S5c DRIVES the 11-07 shape (a fresh marker AND no prompt must
      still REFUSE, and write one REFUSED ledger line); S18 the run parameters and --dry carry OTV5's and dtp's
      HEADs (fixture repos) and never otv4's; S19 the prior comes from the weekly folder only (an anchor with
      handoffs/saturday_*.md is ignored), and S19b/S19c a prior without a _work folder is passed as NONE while
      one with it is passed as the --prior path.
v1.3  2026-10-31  dtp r520 / SAT.4 — THE BRIEF IS THE OPERATOR'S SEVEN SECTIONS, FOR THE FLEET THAT EXISTS.
      The operator, 2026-10-31: "Re-do the entire brief" and "don't list the retired strategies either".
      S10/S10b the prompt and the tracked spec (docs/SATURDAY_BRIEF.md) name the same seven sections in order;
      S11/S11b no retired strategy or retired section is named in the prompt, or in the spec's report sections
      (the search list lives in the spec's RETIRED-SEARCH block, read from there); S12 the prompt follows the
      tracked spec, not handoffs/; S13 the brief is written outside handoffs/ (check_scratch_purge P12);
      S14 the standing rules are in the prompt; S15-S17 DRIVEN: a deadline is passed to timeout(1), and a real
      run holds its own in-flight marker while the session runs, hands it BRIEF/WORK/DEADLINE, and clears it.
      S7's abandoned marker is 6 h old (the expiry moved from 3 h to 5 h).
v1.2  2026-09-26  r432 — writes to ITS OWN log and ledger, never the operator's.
      The ledger exists to answer "is the brief still happening?" by `tail`.
      This file was filling it with deliberate failures, and on 2026-09-26
      that answer came back wrong on the morning of the first real Saturday.
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
_SCRATCH = {
    "SATURDAY_BRIEF_LOG": os.path.join(tempfile.gettempdir(),
                                       "check_saturday_brief.log"),
    "SATURDAY_BRIEF_LEDGER": os.path.join(tempfile.gettempdir(),
                                          "check_saturday_brief.ledger"),
    # v1.4: NEVER the live marker. A sweep running during the real brief made the wrapper stand down on
    # the brief's own marker (S5 red, rc=0), and S7 backdated that marker.
    "SATURDAY_BRIEF_MARKER": os.path.join(tempfile.gettempdir(),
                                          "check_saturday_brief.inflight"),
}
_MK = _SCRATCH["SATURDAY_BRIEF_MARKER"]
if os.path.exists(_MK):
    os.remove(_MK)


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
env = dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false")
r = subprocess.run(["bash", SH, "--smoke"], capture_output=True, text=True,
                   timeout=120, env=env)
ck("S4", "smoke:" in r.stdout and r.returncode != 0,
   f"--smoke ENTERS its own branch and REPORTS FAILURE when the binary is "
   f"unusable (rc={r.returncode}) — no live API call is bought by this gate")

r = subprocess.run(["bash", SH, "--dry"], env=dict(os.environ, **_SCRATCH), capture_output=True, text=True,
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
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S5", r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr),
       f"a MISSING prompt REFUSES (rc={r.returncode}) rather than invoking "
       f"claude with an empty brief")
    # S5c — THE 11-07 SHAPE: a FRESH in-flight marker AND no prompt. The refusal must come first.
    open(_MK, "w").close()
    _led = _SCRATCH["SATURDAY_BRIEF_LEDGER"]
    _n0 = sum(1 for _ in open(_led)) if os.path.exists(_led) else 0
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    _new = open(_led).read().splitlines()[_n0:] if os.path.exists(_led) else []
    ck("S5c", r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr)
       and any("REFUSED no_prompt" in l for l in _new),
       f"a missing prompt REFUSES even while a fresh in-flight marker stands (rc={r.returncode}), "
       f"and writes one REFUSED ledger line ({len(_new)} new)")
finally:
    os.rename(_bak, PROMPT)
    if os.path.exists(_MK):
        os.remove(_MK)

ck("S5b", os.path.exists(PROMPT), "the prompt file was restored by this check")

# ------------------------------------------------------------------------ S9
# 🔴 THE TRANSCRIPT HAZARD, PINNED ON BEHAVIOUR. `claude -p --continue` does
# not fork — it APPENDS TO THE LIVE SESSION'S TRANSCRIPT (measured: 5137->5161
# lines, zero new session files, entries under the attached session's own id).
# The operator reattaches to a long-lived agent, so a timer using --continue
# would be cron writing into an agent he is attached to. The wrapper prints
# the flags it will actually pass; a source grep would be satisfied by a
# comment (§21), and a neutered binary hides the difference entirely.
cmd = subprocess.run(["bash", SH, "--print-cmd"], env=dict(os.environ, **_SCRATCH), capture_output=True,
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
# 🔴 THE GATE WRITES TO ITS OWN LOG AND LEDGER, NEVER THE OPERATOR'S.
# This file runs the real script with /bin/false standing in for claude — a
# correct test of the failure path — and every one of those runs used to
# append `FAILED fallback rc=1` to the ledger the operator tails to ask "is
# the brief still happening?". 97 such lines accumulated and on 2026-09-26
# they were read as a broken timer, on the morning of its FIRST Saturday.

MARK = _MK  # v1.4: the scratch marker, never the live one
_pre = os.path.exists(MARK)
try:
    subprocess.run(["touch", "-d", "6 hours ago", MARK], check=True)
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S7", "ABANDONED" in r.stdout,
       "a 6-hour-old in-flight marker is treated as ABANDONED, not obeyed")
    subprocess.run(["touch", MARK], check=True)
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
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

# ------------------------------------------------------------------------ S10
# 🔑 v1.3 — THE OPERATOR'S SEVEN SECTIONS (2026-10-31), IN THE PROMPT AND IN THE TRACKED SPEC, IN ORDER.
SPEC = os.path.join(ROOT, "docs", "SATURDAY_BRIEF.md")
spec = open(SPEC).read() if os.path.exists(SPEC) else ""
SECTIONS = ["## 1. TRADING SUMMARY", "## 2. ISSUES FROM THE BOT LOGS", "## 3. FLEET HEALTH",
            "## 4. DOCUMENTATION CORRECTIONS", "## 5. CODE HYGIENE", "## 6. PROPOSED STUDIES TO INCREASE P&L",
            "## 7. RECOMMENDATIONS"]


def _in_order(text, heads):
    pos = [text.find(h) for h in heads]
    return all(x >= 0 for x in pos) and pos == sorted(pos)


ck("S10", _in_order(p, SECTIONS), "the prompt names all seven sections, in the operator's order")
ck("S10b", _in_order(spec, SECTIONS), "the tracked spec has the same seven sections, in the same order")

# ------------------------------------------------------------------------ S11
# 🔴 "don't list the retired strategies either." The search list is the spec's own RETIRED-SEARCH block, so the
# list exists once; the prompt may name none of it, and neither may the spec outside that block and its
# retirement table.
_blk = re.search(r"<!-- RETIRED-SEARCH.*?-->(.*?)<!-- /RETIRED-SEARCH -->", spec, re.S)
RETIRED = [t for t in re.split(r"\s{2,}|\n", _blk.group(1)) if t.strip()] if _blk else []
RETIRED = [t.strip() for t in RETIRED] + ["ORB", "AAL", "SEVENTEEN", "veto"]


def _named(text):
    hits = []
    for t in RETIRED:
        rx = r"(?<![\w-])" + re.escape(t) + r"(?![\w])"
        if re.search(rx, text, 0 if any(c.isupper() for c in t) else re.I):
            hits.append(t)
    return hits


ck("S11", len(RETIRED) >= 12 and not _named(p),
   f"the prompt names no retired strategy or section ({len(RETIRED)} terms searched; named: {_named(p) or 'none'})")
_report = spec
if _blk:
    _report = _report.replace(_blk.group(0), "")
_report = _report.split("## WHAT THIS SPEC RETIRED")[0]
_report = _report[_report.find("## 1. TRADING SUMMARY"):] if "## 1. TRADING SUMMARY" in _report else ""
_named_spec = [t for t in _named(_report) if t not in ("ORB",)]   # 5. says the ORB *engine* stays
ck("S11b", bool(_report) and not _named_spec,
   f"the spec's seven sections name no retired strategy outside the search block (named: {_named_spec or 'none'})")

# ------------------------------------------------------------------------ S12
ck("S12", "/home/ubuntu/day_trader_pro/docs/SATURDAY_BRIEF.md" in p and "handoffs/SATURDAY" not in p,
   "the prompt follows the tracked spec in dtp docs/, not the gitignored handoffs/ copy")
_ign = subprocess.run(["git", "-C", ROOT, "check-ignore", "-q", "docs/SATURDAY_BRIEF.md"]).returncode
ck("S12b", bool(spec) and _ign == 1, f"docs/SATURDAY_BRIEF.md exists and is not gitignored (check-ignore rc={_ign})")

# ------------------------------------------------------------------------ S13
_env13 = {k: v for k, v in os.environ.items() if k not in ("SATURDAY_BRIEF_OUT", "SATURDAY_BRIEF_WEEKLY")}
_env13.update(_SCRATCH)
r = subprocess.run(["bash", SH, "--dry"], env=_env13, capture_output=True, text=True, timeout=60)
_out = re.search(r"output: (\S+)", r.stdout)
_out = _out.group(1) if _out else ""
ck("S13", _out.startswith("/home/ubuntu/reviews/weekly/saturday_") and "handoffs" not in _out
   and "/options-trader-v4/" not in _out,
   f"the default brief path is outside handoffs/ and outside every repo: {_out or '(none)'}")

# ------------------------------------------------------------------------ S14
_rules = {"wake": "--wake-only" in p and "--shutdown-only" in p and "wake_and_bake" in p,
          "they/them": "they/them" in p,
          "no env": "Never print an environment" in p and "is-active" in p,
          "read-only": "mode=ro" in p and "Reads only" in p,
          "fees": "never inside EV" in p,
          "filter": "mainline()" in p,
          "not measured": "NOT MEASURED" in p,
          "otv5 r suite": "/home/ubuntu/OTV5/tests/" in p and "r_ledger" in p,
          "non-events": "No non-events" in p and "Checked, nothing to report" in p,
          "venv": "/home/ubuntu/day_trader_pro/venv/bin/python" in p}
ck("S14", all(_rules.values()), f"the standing rules are in the prompt (missing: "
   f"{[k for k, v in _rules.items() if not v] or 'none'})")

# ------------------------------------------------------------------------ S15
_pc = subprocess.run(["bash", SH, "--print-cmd"], env=dict(os.environ, **_SCRATCH), capture_output=True,
                     text=True, timeout=60).stdout
_t = re.search(r"timeout=(\d+)", _pc)
ck("S15", bool(_t) and 0 < int(_t.group(1)) <= 18000,
   f"the session is given a deadline: {(_t.group(0) if _t else 'none')} (≤ 5 h, ends by 07:30 ET on a timer run)")

# ------------------------------------------------------------------------ S16
# DRIVEN: a stub stands in for claude, records whether the in-flight marker exists while it runs, and keeps the
# prompt it was handed. The wrapper used to write no marker of its own, so the watchdog's retry could start a
# second brief beside a long-running first one.
_d = tempfile.mkdtemp(prefix="chk_satbrief_")
_stub = os.path.join(_d, "claude_stub.sh")
_mk = os.path.join(_d, "inflight")
open(_stub, "w").write(f'#!/bin/bash\n[ -f "{_mk}" ] && echo yes > "{_d}/seen"\nprintf "%s\\n" "$@" > "{_d}/prompt"\nexit 0\n')
os.chmod(_stub, 0o755)
_o16 = os.path.join(_d, "weekly", "saturday_TEST.md")
r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                   env=dict(os.environ, **dict(_SCRATCH, SATURDAY_BRIEF_MARKER=_mk), SATURDAY_BRIEF_CLAUDE=_stub,
                            SATURDAY_BRIEF_WEEKLY=os.path.join(_d, "weekly"), SATURDAY_BRIEF_OUT=_o16))
ck("S16", os.path.exists(os.path.join(_d, "seen")) and not os.path.exists(_mk),
   "a real run holds its own in-flight marker while the session runs, and clears it after")
_hp = open(os.path.join(_d, "prompt")).read() if os.path.exists(os.path.join(_d, "prompt")) else ""
ck("S17", f"exactly this path: {_o16}" in _hp and "WORK" in _hp and "DEADLINE" in _hp
   and os.path.isdir(_o16[:-3] + "_work") and "## 1. TRADING SUMMARY" in _hp,
   "the session is handed the prompt, its BRIEF path, its WORK folder (created) and its DEADLINE")

# ------------------------------------------------------------------------ S18 / S19
# v1.4 — DRIVEN on fixtures. Two throwaway git repos stand in for OTV5 and dtp, an anchor with a
# handoffs/ brief stands in for the frozen otv4, and a weekly folder holds the priors.
import shutil
_f = tempfile.mkdtemp(prefix="chk_satbrief_trees_")
def _repo(name):
    d = os.path.join(_f, name); os.makedirs(d)
    g = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
             GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", d], check=True, env=g)
    open(os.path.join(d, "f"), "w").write(name)
    subprocess.run(["git", "-C", d, "add", "f"], check=True, env=g)
    subprocess.run(["git", "-C", d, "commit", "-qm", name], check=True, env=g)
    return d, subprocess.run(["git", "-C", d, "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
_o5, _h5 = _repo("otv5fx")
_dt, _hd = _repo("dtpfx")
_an, _ha = _repo("anchorfx")
os.makedirs(os.path.join(_an, "handoffs"))
open(os.path.join(_an, "handoffs", "saturday_2026-09-01.md"), "w").write("old")
_wk = os.path.join(_f, "weekly"); os.makedirs(_wk)
_fx = dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_OTV5=_o5, SATURDAY_BRIEF_DTP=_dt,
           SATURDAY_BRIEF_ANCHOR=_an, SATURDAY_BRIEF_WEEKLY=_wk,
           SATURDAY_BRIEF_OUT=os.path.join(_wk, "saturday_TEST.md"))
def _dry():
    return subprocess.run(["bash", SH, "--dry"], env=_fx, capture_output=True, text=True, timeout=60).stdout
_d0 = _dry()
_tl = next((l for l in _d0.splitlines() if l.strip().startswith("trees:")), "")
ck("S18", f"OTV5 {_h5}" in _tl and f"dtp {_hd}" in _tl and _ha not in _tl,
   f"the brief's trees are OTV5 and dtp, never the anchor (otv4): {_tl.strip()[:90]}")
_pl = next((l for l in _d0.splitlines() if l.strip().startswith("prior:")), "")
_pw = next((l for l in _d0.splitlines() if l.strip().startswith("prior_work:")), "")
ck("S19", "(none)" in _pl and "handoffs" not in _d0 and "NONE" in _pw,
   f"with an empty weekly folder there is NO prior, even though the anchor holds handoffs/saturday_*.md: "
   f"{_pl.strip()} | {_pw.strip()[:40]}")
open(os.path.join(_wk, "saturday_2026-10-31.md"), "w").write("p1")
_d1 = _dry()
_pw1 = next((l for l in _d1.splitlines() if l.strip().startswith("prior_work:")), "")
ck("S19b", "saturday_2026-10-31.md" in _d1 and "NONE" in _pw1 and "does not exist" in _pw1,
   f"a prior whose _work folder is missing is passed as NONE with the reason: {_pw1.strip()[:70]}")
os.makedirs(os.path.join(_wk, "saturday_2026-11-07_work"))
open(os.path.join(_wk, "saturday_2026-11-07.md"), "w").write("p2")
_d2 = _dry()
_pw2 = next((l for l in _d2.splitlines() if l.strip().startswith("prior_work:")), "")
ck("S19c", _pw2.strip() == f"prior_work: {os.path.join(_wk, 'saturday_2026-11-07_work')}",
   f"the newest prior with a _work folder is the --prior path: {_pw2.strip()[:80]}")
# and the real run hands the session the same TREES line (stub claude, scratch marker)
_st = os.path.join(_f, "stub.sh")
open(_st, "w").write(f'#!/bin/bash\nprintf "%s\\n" "$@" > "{_f}/prompt"\nexit 0\n')
os.chmod(_st, 0o755)
subprocess.run(["bash", SH], env=dict(_fx, SATURDAY_BRIEF_CLAUDE=_st), capture_output=True, text=True,
               timeout=120)
_hp2 = open(os.path.join(_f, "prompt")).read() if os.path.exists(os.path.join(_f, "prompt")) else ""
ck("S18b", f"TREES   the trees this brief reports on" in _hp2 and f"OTV5 {_h5}" in _hp2
   and f"dtp {_hd}" in _hp2 and f"PRIOR_WORK" in _hp2
   and os.path.join(_wk, "saturday_2026-11-07_work") in _hp2,
   "the real run's parameters carry the OTV5 and dtp HEADs and the prior _work path")
shutil.rmtree(_f, ignore_errors=True)

# S20 (v1.5, dtp r548 / SAT.7): THE STUDY QUEUE. The operator, 2026-11-10: "Make sure you add whatever we want
# to study to the 0300 weekend activity." The prompt and the spec both name ~/reviews/WEEKEND_STUDIES.md, tell the
# session to seal before testing and run once, run the queue through the heavy lock, and send unfinished items to
# NOT MEASURED.
_q = "/home/ubuntu/reviews/WEEKEND_STUDIES.md"
ck("S20", _q in p and "SEAL.txt" in p and "ONCE" in p and "claude-heavy.lock" in p
   and "NOT MEASURED" in p.split("THE STUDY QUEUE", 1)[-1][:2000],
   "the prompt runs the study queue blind (seal, run once), through the heavy lock, unfinished to NOT MEASURED")
ck("S20b", "WEEKEND_STUDIES.md" in spec and "SEAL.txt" in spec and "claude-heavy.lock" in spec,
   "the spec names the same study queue and its rules")

# S21 (v1.6, dtp r549 / SAT.8): THE STUDY QUEUE RUNS ON THE BOXES. The operator, 2026-11-11: "What about just
# waking more boxes at the 0300 to run these studies in parallel?"
_q6 = p.split("THE STUDY QUEUE", 1)[-1][:4000]
ck("S21", "tools/study_dispatch.py run" in _q6 and "study_dispatch.py wait" in _q6 and "FALLBACK" in _q6
   and "Do NOT CLOSE while it runs" in p and "study_dispatch.py cleanup" in p,
   "the prompt starts the box dispatch after the reads, collects it, cleans up, and does not CLOSE while it runs")
ck("S21b", "study_dispatch.py" in spec and "CLOSED only after" in spec and "box_claims" in spec,
   "the spec names the box dispatch, its claims, and the late CLOSE")
_shs = open(SH).read()
ck("S21c", 'export STUDY_DISPATCH_DEADLINE_ET="$_deadline_hm"' in _shs and '"$_SD" cleanup' in _shs
   and _shs.index("export STUDY_DISPATCH_DEADLINE_ET") < _shs.index('timeout "$BUDGET_S"'),
   "the wrapper hands the deadline to the dispatcher before the session and runs its cleanup after")

# S22 (v1.7, dtp r550 / CASH.1): THE QQQ CASH SIZE TABLE. The operator, 2026-11-11: "On the weekend prior, let's do a
# table of $250/$500 & $500/$750 with a cap at the ramp max", then "just brief it every weekend until the date arrives".
_c = p.split("THE QQQ CASH SIZE TABLE", 1)[-1][:2500] if "THE QQQ CASH SIZE TABLE" in p else ""
_c1 = p.find("THE QQQ CASH SIZE TABLE")
ck("S22", bool(_c) and "on or after 2026-12-07, skip it" in _c and "$250, ramp max $500" in _c
   and "$500, ramp max $750" in _c and "cap = the ramp max" in _c and "never rounded down to 1" in _c
   and "fees beside it (never in it)" in _c and "REPORT ONLY" in _c and "~/reviews/trades/*.csv" in _c
   and p.find("## 1. TRADING SUMMARY") < _c1 < p.find("## 2. ISSUES FROM THE BOT LOGS"),
   "the prompt's section 1 sizes QQQ under both schemes until 2026-12-07, refuses not floors, report only")
_c8 = spec.split("**1.8 The QQQ cash size table", 1)[-1][:3000] if "**1.8 The QQQ cash size table" in spec else ""
ck("S22b", bool(_c8) and "On or after 2026-12-07 the brief skips this item" in _c8 and "| A | $250 | $500 |" in _c8
   and "| B | $500 | $750 |" in _c8 and "never rounded down to one" in _c8 and "Report only:" in _c8
   and spec.find("\n## 1. TRADING SUMMARY") < spec.find("**1.8 The QQQ cash size table") < spec.find("\n## 2. ISSUES FROM THE BOT LOGS"),
   "the spec's 1.8 names the same two schemes, the refusal, the date stop and report only")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
