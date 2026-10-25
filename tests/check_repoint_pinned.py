#!/usr/bin/env python3
"""
tests/check_repoint_pinned.py  v1.1
v1.1  2026-10-25  dtp r507 / OPS.72 — P8a/P8c pass install=False: they pin the managed (git-only) repoint's phases 1-2,
      and since r507 a pinned repoint also installs when the pinned tree supports it (gate: check_repoint_install.py).
      No expectation changed.
v1.0  2026-10-14  dtp r489 / OPS.67 — THE MANAGED REPOINT, RUN FOR REAL ON A FAKE BOX.

  fleet.py v0.12.0 `repoint --sha`. The generated per-box scripts are executed
  by bash in a scratch HOME: ~/options-trader is a clone of a local bare repo,
  and sudo / systemctl / venv pip are stubs that log what they were asked.
  Nothing here touches a real box, a real unit or the network.

  P1  the bot and the feed are stopped BEFORE the tree changes
  P2  the box lands on the PINNED commit, not on origin/main's newer tip
  P3  the bot and the feed are never started or restarted
  P4  shadow: a tree without shadow/ disables the enabled units after
      recording them; the same command pinned back at a tree WITH shadow/
      re-enables exactly the recorded ones (a unit that was off stays off)
  P5  deps: requirements.lock on python 3.14 when the tree has one, else
      requirements.txt
  P6  an entry point that will not import stops the box (rc 12, no OK line)
  P7  phase 1 refuses an open trade, an unreadable trades.db and a pin the
      fetch does not hold; a clean box prints nothing
  P8  cmd_repoint: a refused box aborts the run before phase 2; --sha
      validates its value and forces no restart
  P9  the timer-launched writers stop before the reset; a job already
      running is waited for (rc 13 if it never ends, tree untouched); only the
      timers that were on are started again, after the import check
  P10 tools/shadow_watch.py v1.2: a box whose tree has no shadow/ answers
      shadow=absent and is skipped, never paged; a tree with shadow/ is still
      measured (both found by OTV4TEST, MSG-QQQ-1014-02)
  BORN RED on dtp 98980e2 (no `sha` parameter).

Run:  python3 tests/check_repoint_pinned.py
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PROBLEMS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    if not ok:
        PROBLEMS.append(name)


SYSTEMCTL = r'''#!/bin/bash
# stub: state in $FAKE/units/<name> (active|inactive), $FAKE/enabled/<name>
echo "systemctl $*" >> "$FAKE/calls"
case "$1" in
  stop)    shift; for u in "$@"; do echo inactive > "$FAKE/units/$u";
           echo "HEAD_AT_STOP $u $(git -C "$HOME/options-trader" rev-parse HEAD)" >> "$FAKE/calls"; done ;;
  start|restart) shift; for u in "$@"; do echo active > "$FAKE/units/$u";
           echo "HEAD_AT_START $u $(git -C "$HOME/options-trader" rev-parse HEAD)" >> "$FAKE/calls"; done ;;
  is-active) shift; q=0; [ "$1" = -q ] && { q=1; shift; }
           # a job "running" for $FAKE/busy more polls, then done
           if [ -f "$FAKE/busy" ]; then b=$(cat "$FAKE/busy"); if [ "$b" -gt 0 ]; then
             echo $((b-1)) > "$FAKE/busy"; exit 0; fi; fi
           rc=3; for u in "$@"; do st=$(cat "$FAKE/units/$u" 2>/dev/null || echo inactive)
             [ $q = 1 ] || echo "$st"; [ "$st" = active ] && rc=0; done; exit $rc ;;
  is-enabled) [ -f "$FAKE/enabled/$2" ] && { echo enabled; exit 0; }
              [ -f "$FAKE/known/$2" ] && { echo disabled; exit 1; }; exit 1 ;;
  enable)  [ "$2" = --now ] && shift; shift; for u in "$@"; do touch "$FAKE/enabled/$u"; done ;;
  disable) [ "$2" = --now ] && shift; shift; for u in "$@"; do rm -f "$FAKE/enabled/$u"; done ;;
  show)    echo "Environment=OT_INSTRUMENT=QQQ OT_RISK_USD=1050" ;;
esac
exit 0
'''
SUDO = '#!/bin/bash\nexec "$@"\n'
PIP = '#!/bin/bash\necho "pip $*" >> "$FAKE/calls"\nexit 0\n'


def git(cwd, *a):
    return subprocess.run(["git", "-C", cwd, *a], check=True, capture_output=True,
                          text=True).stdout.strip()


def commit(work, files, msg):
    for path, body in files.items():
        full = os.path.join(work, path)
        if body is None:
            if os.path.isdir(full):
                shutil.rmtree(full)
            elif os.path.exists(full):
                os.remove(full)
            continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(body)
    git(work, "add", "-A")
    git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)
    return git(work, "rev-parse", "HEAD")


ENTRY = {"main.py": "", "data/__init__.py": "", "data/candle_feed.py": "",
         "data/candle_logger.py": "", "warehouse/__init__.py": "",
         "warehouse/s3_push.py": "", "warehouse/retention_purge.py": "",
         "warehouse/self_close.py": "", "tools/__init__.py": "",
         "tools/emergency_watchdog.py": ""}


def build():
    """A bare origin with: A (mainline-shaped, shadow/), B (test-shaped, lock),
    C (a newer tip). Returns (tmp, origin_url, A, B, C)."""
    tmp = tempfile.mkdtemp(prefix="repoint_")
    origin = os.path.join(tmp, "origin.git")
    work = os.path.join(tmp, "work")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", origin], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", work], check=True)
    files = dict(ENTRY)
    files.update({"shadow/observer.py": "", "requirements.txt": "pandas\n"})
    A = commit(work, files, "A")
    B = commit(work, {"shadow/observer.py": None, "requirements.lock": "pandas==2.2\n",
                      "tools/eod_summary.py": ""}, "B")
    C = commit(work, {"later.txt": "x"}, "C")
    git(work, "remote", "add", "origin", origin)
    git(work, "push", "-q", "origin", "main")
    return tmp, "file://" + origin, A, B, C


def box(tmp, origin_url, at):
    """A fake box at commit `at`: HOME, units, stubs, a venv, a trades.db."""
    home = os.path.join(tmp, "home")
    fake = os.path.join(tmp, "fake")
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(fake, ignore_errors=True)
    for d in ("units", "enabled", "known", "bin"):
        os.makedirs(os.path.join(fake, d))
    subprocess.run(["git", "clone", "-q", origin_url.replace("file://", ""),
                    os.path.join(home, "options-trader")], check=True)
    tree = os.path.join(home, "options-trader")
    git(tree, "reset", "-q", "--hard", at)
    venv = os.path.join(tree, "venv", "bin")
    os.makedirs(venv)
    os.symlink(sys.executable, os.path.join(venv, "python"))
    for name, body in (("pip", PIP),):
        p = os.path.join(venv, name)
        open(p, "w").write(body)
        os.chmod(p, 0o755)
    for name, body in (("systemctl", SYSTEMCTL), ("sudo", SUDO)):
        p = os.path.join(fake, "bin", name)
        open(p, "w").write(body)
        os.chmod(p, 0o755)
    for u in ("optionsbot", "candle-feed", "s3-push.timer", "candle-logger.timer"):
        open(os.path.join(fake, "units", u), "w").write("active\n")
    # optbot-self-close.timer installed but NOT active: must stay off
    for u in ("shadow-observer.service", "shadow-start.timer", "shadow-stop.timer"):
        open(os.path.join(fake, "known", u), "w").close()
    # observer and start are enabled; stop is installed but OFF
    open(os.path.join(fake, "enabled", "shadow-observer.service"), "w").close()
    open(os.path.join(fake, "enabled", "shadow-start.timer"), "w").close()
    con = sqlite3.connect(os.path.join(tree, "trades.db"))
    con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, status TEXT)")
    con.execute("INSERT INTO trades (status) VALUES ('closed')")
    con.commit()
    con.close()
    open(os.path.join(fake, "calls"), "w").close()
    env = dict(os.environ, HOME=home, FAKE=fake,
               PATH=os.path.join(fake, "bin") + os.pathsep + os.environ["PATH"])
    return home, fake, tree, env


def run(script, env):
    r = subprocess.run(["bash", "-c", script], env=env, capture_output=True,
                       text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def calls(fake):
    return open(os.path.join(fake, "calls")).read().splitlines()


def main():
    import fleet
    tmp, url, A, B, C = build()
    try:
        _main(fleet, tmp, url, A, B, C)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if not PROBLEMS else f"FAIL: {', '.join(PROBLEMS)}")
    return 0 if not PROBLEMS else 1


def _main(fleet, tmp, url, A, B, C):
    py314 = sys.version_info[:2] == (3, 14)

    # ── forward: A (mainline-shaped) -> pinned B ────────────────────────────
    home, fake, tree, env = box(tmp, url, A)
    rc, out = run(fleet._phase2_commit_cmd(url, None, True, B[:7]), env)
    log = calls(fake)
    head = git(tree, "rev-parse", "HEAD")
    stops = {l.split()[1]: l.split()[2] for l in log if l.startswith("HEAD_AT_STOP")}
    check("P1 the bot, the feed and the writer timers stop before the tree changes",
          all(stops.get(u) == A for u in ("optionsbot", "candle-feed", "s3-push.timer",
                                          "candle-logger.timer")), str(stops))
    starts = {l.split()[1]: l.split()[2] for l in log if l.startswith("HEAD_AT_START")}
    check("P9a only the timers that were on come back, after the tree is the pin",
          sorted(starts) == ["candle-logger.timer", "s3-push.timer"]
          and all(h == B for h in starts.values()), str(starts))
    check("P2 the box lands on the PINNED commit, not origin/main",
          rc == 0 and head == B and head != C, f"rc={rc} head={head[:7]}\n{out}")
    check("P3 the bot and the feed are never started",
          not [u for u in starts if u in ("optionsbot", "candle-feed")]
          and not [l for l in log if l.split()[1:2] == ["restart"]]
          and open(os.path.join(fake, "units", "optionsbot")).read().strip() == "inactive",
          str(log))
    enabled = sorted(os.listdir(os.path.join(fake, "enabled")))
    rec = os.path.join(home, ".repoint_shadow_units")
    recorded = open(rec).read().split() if os.path.exists(rec) else None
    check("P4a a tree without shadow/ disables the shadow units, recording the enabled ones",
          enabled == [] and recorded == ["shadow-observer.service", "shadow-start.timer"],
          f"enabled={enabled} recorded={recorded}")
    pip = [l for l in log if l.startswith("pip ")]
    want = "requirements.lock" if py314 else "requirements.txt"
    check("P5a deps: requirements.lock on 3.14 when the tree has one",
          len(pip) == 1 and want in pip[0], str(pip))
    check("P2b the OK line names the move", f"{fleet._SENTINEL_OK} {A[:7]} -> {B[:7]}" in out, out)

    # ── rollback: the same command pinned at A re-enables the record ────────
    open(os.path.join(fake, "calls"), "w").close()
    rc, out = run(fleet._phase2_commit_cmd(url, None, True, A[:7]), env)
    enabled = sorted(os.listdir(os.path.join(fake, "enabled")))
    check("P4b pinned back at a tree with shadow/, exactly the recorded units return",
          rc == 0 and git(tree, "rev-parse", "HEAD") == A
          and enabled == ["shadow-observer.service", "shadow-start.timer"]
          and not os.path.exists(rec), f"rc={rc} enabled={enabled}\n{out}")
    pip = [l for l in calls(fake) if l.startswith("pip ")]
    check("P5b deps: a tree without a lock installs requirements.txt",
          len(pip) == 1 and "requirements.txt" in pip[0], str(pip))
    check("P4c a skipped entry point is named, not failed",
          "import skip: tools.eod_summary" in out, out)

    # ── a push already running finishes; one that never does stops the box ──
    home, fake, tree, env = box(tmp, url, A)
    open(os.path.join(fake, "busy"), "w").write("3")
    rc, out = run(fleet._phase2_commit_cmd(url, None, True, B[:7]), env)
    check("P9b a running timer job is waited for, then the repoint proceeds",
          rc == 0 and git(tree, "rev-parse", "HEAD") == B, f"rc={rc}\n{out}")
    home, fake, tree, env = box(tmp, url, A)
    open(os.path.join(fake, "busy"), "w").write("999")
    script = fleet._phase2_commit_cmd(url, None, True, B[:7]).replace("sleep 2", "sleep 0")
    rc, out = run(script, env)
    check("P9c a job that never ends stops the box before the reset (rc 13)",
          rc == 13 and git(tree, "rev-parse", "HEAD") == A, f"rc={rc}\n{out}")

    # ── shadow_watch: a box whose tree has no shadow/ is skipped, not paged ──
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import shadow_watch
    home, fake, tree, env = box(tmp, url, B)       # test-shaped: no shadow/
    rc, out = run(shadow_watch.REMOTE, env)
    check("P10a shadow_watch's remote line answers shadow=absent on a tree without shadow/",
          rc == 0 and out.strip() == "shadow=absent", out)
    home, fake, tree, env = box(tmp, url, A)       # mainline-shaped, no file today
    rc, out = run(shadow_watch.REMOTE, env)
    check("P10b a tree with shadow/ is still measured (file=none, not skipped)",
          "file=none" in out and "shadow=absent" not in out, out)
    import io
    import contextlib
    sentm = []
    real_sw = (fleet._exec, fleet.get_fleet, shadow_watch.notify,
               shadow_watch.control_state.is_enabled, shadow_watch.market_calendar.is_trading_day)
    fleet.get_fleet = lambda only=None: [("QQQ", "10.0.0.1", "running"), ("SPX", "10.0.0.2", "running")]
    fleet._exec = lambda sym, ip, cmd, timeout=None: (0, "shadow=absent\n", "")
    shadow_watch.notify = type("N", (), {"send": staticmethod(lambda m: sentm.append(m) or True)})
    shadow_watch.control_state.is_enabled = lambda: True
    shadow_watch.market_calendar.is_trading_day = lambda d: True
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = shadow_watch.main([])
        check("P10c a fleet of repointed boxes pages nothing",
              rc == 0 and not sentm and "2 run no shadow" in buf.getvalue(), buf.getvalue())
    finally:
        (fleet._exec, fleet.get_fleet, shadow_watch.notify,
         shadow_watch.control_state.is_enabled, shadow_watch.market_calendar.is_trading_day) = real_sw

    # ── an entry point that will not import ─────────────────────────────────
    home, fake, tree, env = box(tmp, url, A)
    bad = commit(os.path.join(tmp, "work"), {"data/candle_feed.py": "raise ImportError('x')\n"}, "D")
    git(os.path.join(tmp, "work"), "push", "-q", "origin", "main")
    rc, out = run(fleet._phase2_commit_cmd(url, None, True, bad[:7]), env)
    check("P6 an entry point that will not import stops the box (rc 12, no OK)",
          rc == 12 and fleet._SENTINEL_OK not in out
          and "import check FAILED: data.candle_feed" in out, f"rc={rc}\n{out}")

    # ── phase 1 ─────────────────────────────────────────────────────────────
    home, fake, tree, env = box(tmp, url, A)
    p1 = fleet._phase1_check_cmd(url, None, B[:7])
    rc, out = run(p1, env)
    check("P7a a clean box prints nothing", rc == 0 and out.strip() == "", out)
    con = sqlite3.connect(os.path.join(tree, "trades.db"))
    con.execute("INSERT INTO trades (status) VALUES ('open')")
    con.commit()
    con.close()
    rc, out = run(p1, env)
    check("P7b an open trade is refused", f"{fleet._SENTINEL_OPEN} 1" in out, out)
    os.remove(os.path.join(tree, "trades.db"))
    rc, out = run(p1, env)
    check("P7c an unreadable trades.db is refused",
          f"{fleet._SENTINEL_OPEN} unreadable" in out, out)
    rc, out = run(fleet._phase1_check_cmd(url, None, "deadbee"), env)
    check("P7d a pin the fetch does not hold is refused", fleet._SENTINEL_NO_SHA in out, out)
    MUT = ("stop", "start", "restart", "enable", "disable")
    muts = [l for l in calls(fake) if l.split()[1:2] and l.split()[1] in MUT or l.startswith("pip ")]
    check("P7e phase 1 changes nothing (no unit verb, no pip, same HEAD)",
          not muts and git(tree, "rev-parse", "HEAD") == A, str(muts))

    # ── cmd_repoint orchestration (mocked boxes) ────────────────────────────
    import config
    sent = []
    real = (fleet._exec, fleet.get_fleet, fleet.survey_remotes, config.MOCK_AWS)
    fleet.get_fleet = lambda only=None: [("QQQ", "10.0.0.1", "running"),
                                         ("SPX", "10.0.0.2", "running")]
    fleet.survey_remotes = lambda running, exec_fn=None: {s: "options_trader_v4" for s, _, _ in running}
    config.MOCK_AWS = False

    def fake_exec(sym, ip, cmd, timeout=None):
        sent.append((sym, cmd))
        if "ls-tree" in cmd and sym == "SPX":
            return 0, f"{fleet._SENTINEL_OPEN} 2\n", ""
        return 0, "", ""
    fleet._exec = fake_exec
    try:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fleet.cmd_repoint("https://github.com/TX-9AI/OTV4TEST.git",
                                   only=["QQQ", "SPX"], assume_yes=True, sha="cbad05a", install=False)
        p2 = [c for _, c in sent if "reset --hard" in c]
        check("P8a a refused box aborts the run before phase 2",
              rc == 1 and not p2 and "refused" in buf.getvalue(), buf.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            rc = fleet.cmd_repoint("https://github.com/TX-9AI/OTV4TEST.git",
                                   only=["QQQ"], assume_yes=True, sha="not-a-sha!")
        check("P8b --sha validates its value", rc == 2)
        sent.clear()
        fleet._exec = lambda sym, ip, cmd, timeout=None: (sent.append(cmd) or (
            (0, f"{fleet._SENTINEL_OK} a -> b\n", "") if "reset --hard" in cmd else (0, "", "")))
        with contextlib.redirect_stdout(io.StringIO()):
            rc = fleet.cmd_repoint("https://github.com/TX-9AI/OTV4TEST.git",
                                   only=["QQQ"], assume_yes=True, sha="cbad05a", restart=True, install=False)
        p2 = [c for c in sent if "reset --hard" in c]
        check("P8c --sha forces no restart even when restart was asked",
              rc == 0 and len(p2) == 2 and all("restart" not in c and "start optionsbot" not in c
                                               for c in p2), f"rc={rc} n={len(p2)}")
    finally:
        fleet._exec, fleet.get_fleet, fleet.survey_remotes, config.MOCK_AWS = real


if __name__ == "__main__":
    sys.exit(main())
