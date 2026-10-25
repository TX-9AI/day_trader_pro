#!/usr/bin/env python3
"""
tests/check_fleet_reinstall.py  v1.0
v1.0  2026-10-25  dtp r504 / OPS.69 — `fleet.py reinstall`: THE BOOTSTRAP INSTALL, IN PLACE, RUN FOR REAL ON A FAKE BOX.
      The generated box script (fleet._reinstall_cmd) is executed by bash in a scratch HOME: ~/options-trader is a git
      checkout at the pin holding a bootstrap template shaped like OTV5's; sudo maps /etc/systemd/system to a fixture
      directory holding a unit with FAKE credentials; systemctl answers from fixture state; curl writes an install.sh
      that records the environment it was given. Nothing touches a real box, a real unit or the network.
      BORN RED on dtp ef6229d (no reinstall).

  I1  a running bot or feed is refused (rc 10) and no bootstrap is built
  I2  an open trade is refused (rc 10)
  I3  a HEAD that is not the pin is refused (rc 7)
  I4  the install receives EXACTLY the unit's instrument and five credentials, OT_GIT_REF = the full pinned SHA,
      OT_CLAUDE_AT_BOOT=0 and OT_CLAUDE_SETTINGS=pull-only; the OK line is printed
  I5  no credential value appears anywhere in the output; the log's "TT Account:" line is redacted; ~/bootstrap.sh
      is gone afterwards and was mode 600 while it existed
  I6  a unit without a TastyTrade credential is refused (rc 16), and no bootstrap is left behind
  I7  a box whose push is installed is DRAINED first; a drain that is not OK refuses (rc 15) before any bootstrap
  I8  cmd_reinstall refuses without exactly one --only box or without --sha (rc 2), and a repoint that fails stops it
      before the install (phase 3 never runs)
  I9  the install runs DETACHED in tmux session 'reinstall' (a dropped SSH cannot kill it) and the box waits for it
Run:  python3 tests/check_fleet_reinstall.py   (OT_TPL=<path to an OTV5 bootstrap.example.sh>, default: a fixture)
"""
import os
import shutil
import sqlite3
import stat
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


SECRETS = {"TT_CLIENT_SECRET": "cs-SECRET-111", "TT_REFRESH_TOKEN": "rt-SECRET-222",
           "TT_ACCOUNT_NUMBER": "5WTSECRET3", "TELEGRAM_TOKEN": "tg-SECRET-444", "TELEGRAM_CHAT_ID": "SECRET555"}

TEMPLATE = """#!/bin/bash
# bootstrap.example.sh (fixture, OTV5-shaped export lines)
export OT_INSTRUMENT="REPLACE_ME"
export OT_RISK_USD="200"
export OT_GIT_REF="main"
export TT_CLIENT_SECRET="REPLACE_ME"
export TT_REFRESH_TOKEN="REPLACE_ME"
export TT_ACCOUNT_NUMBER="REPLACE_ME"
export TELEGRAM_TOKEN="REPLACE_ME"
export TELEGRAM_CHAT_ID="REPLACE_ME"
export GITHUB_REPO="TX-9AI/OTV5"
export GITHUB_TOKEN=""
export OT_CLAUDE_AT_BOOT="1"
export OT_CLAUDE_SETTINGS=""
curl -fsSL "https://raw.githubusercontent.com/${GITHUB_REPO}/${OT_GIT_REF}/deploy/install.sh" -o install.sh \\
    && bash install.sh
"""

SUDO = r'''#!/bin/bash
args=(); for a in "$@"; do args+=("${a//\/etc\/systemd\/system\//$FAKE/etc/}"); done
exec "${args[@]}"
'''
SYSTEMCTL = r'''#!/bin/bash
case "$1" in
  is-active) [ "$2" = optionsbot ] && { echo "${BOT_STATE:-inactive}"; exit 0; }; echo inactive; exit 3 ;;
  is-enabled) [ "$2" = -q ] && { [ "$3" = s3-push.timer ] && [ -n "$PUSH_ON" ] && exit 0; exit 1; }
              echo disabled; exit 1 ;;
esac
exit 0
'''
CURL = r'''#!/bin/bash
out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && { out="$2"; shift; }; shift; done
cat > "$out" <<'INST'
#!/bin/bash
env | grep -E '^(OT_INSTRUMENT|TT_CLIENT_SECRET|TT_REFRESH_TOKEN|TT_ACCOUNT_NUMBER|TELEGRAM_TOKEN|TELEGRAM_CHAT_ID|OT_GIT_REF|OT_CLAUDE_AT_BOOT|OT_CLAUDE_SETTINGS)=' | sort > "$FAKE/seen"
stat -c %a "$HOME/bootstrap.sh" > "$FAKE/mode"
echo "  TT Account:  $TT_ACCOUNT_NUMBER"
echo "  Every step completed"
INST
exit 0
'''
TMUX = r'''#!/bin/bash
# stub: `new-session -d -s NAME CMD` runs CMD synchronously, as tmux would (with $TMUX set); anything else is a no-op
[ "$1" = new-session ] && { TMUX=stub bash -c "${@: -1}"; exit $?; }
exit 0
'''
S3PUSH = 'import os\nprint("DRAIN sym=X " + ("OK" if os.environ.get("DRAIN_OK") else "SHORT 3"))\n'


def box(unit_keys=None, open_trades=0, head_is_pin=True):
    tmp = tempfile.mkdtemp(prefix="reinstall_")
    home, fake = os.path.join(tmp, "home"), os.path.join(tmp, "fake")
    tree = os.path.join(home, "options-trader")
    os.makedirs(os.path.join(tree, "warehouse"))
    os.makedirs(os.path.join(fake, "etc"))
    os.makedirs(os.path.join(fake, "bin"))
    tpl = os.environ.get("OT_TPL")
    shutil.copy(tpl, os.path.join(tree, "bootstrap.example.sh")) if tpl else \
        open(os.path.join(tree, "bootstrap.example.sh"), "w").write(TEMPLATE)
    open(os.path.join(tree, "warehouse", "s3_push.py"), "w").write(S3PUSH)
    c = sqlite3.connect(os.path.join(tree, "trades.db"))
    c.execute("CREATE TABLE trades (trade_id TEXT, status TEXT)")
    for k in range(open_trades):
        c.execute("INSERT INTO trades VALUES (?, 'open')", ("t%d" % k,))
    c.commit()
    c.close()
    run = lambda *a: subprocess.run(["git", "-C", tree, *a], check=True, capture_output=True, text=True).stdout.strip()
    run("init", "-q", "-b", "main")
    run("add", "-A")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "pin")
    pin = run("rev-parse", "HEAD")
    if not head_is_pin:
        open(os.path.join(tree, "x"), "w").write("x")
        run("add", "-A")
        run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "later")
    keys = dict(SECRETS, OT_INSTRUMENT="NVDA") if unit_keys is None else unit_keys
    with open(os.path.join(fake, "etc", "optionsbot.service"), "w") as f:
        f.write("[Service]\nUser=ubuntu\n")
        for i, (k, v) in enumerate(keys.items()):
            f.write(('Environment="%s=%s"\n' if i % 2 else "Environment=%s=%s\n") % (k, v))
    for name, body in (("sudo", SUDO), ("systemctl", SYSTEMCTL), ("curl", CURL), ("tmux", TMUX)):
        p = os.path.join(fake, "bin", name)
        open(p, "w").write(body)
        os.chmod(p, 0o755)
    return tmp, home, fake, pin


def run_box(home, fake, pin, **env):
    import fleet
    script = fleet._reinstall_cmd(pin[:7])
    e = {"HOME": home, "FAKE": fake, "PATH": os.path.join(fake, "bin") + ":/usr/bin:/bin"}
    e.update({k: str(v) for k, v in env.items()})
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=e, timeout=120)
    return r.returncode, r.stdout + r.stderr


def main():
    import fleet

    tmp, home, fake, pin = box()
    rc, out = run_box(home, fake, pin, BOT_STATE="active")
    check("I1 a running bot is refused (rc 10), no bootstrap built",
          rc == 10 and not os.path.exists(os.path.join(home, "bootstrap.sh")), f"rc {rc} {out[-200:]}")
    shutil.rmtree(tmp, True)

    tmp, home, fake, pin = box(open_trades=1)
    rc, out = run_box(home, fake, pin)
    check("I2 an open trade is refused (rc 10)", rc == 10 and "open trade" in out, f"rc {rc} {out[-200:]}")
    shutil.rmtree(tmp, True)

    tmp, home, fake, pin = box(head_is_pin=False)
    rc, out = run_box(home, fake, pin)
    check("I3 a HEAD that is not the pin is refused (rc 7)", rc == 7, f"rc {rc} {out[-200:]}")
    shutil.rmtree(tmp, True)

    tmp, home, fake, pin = box()
    rc, out = run_box(home, fake, pin)
    seen = open(os.path.join(fake, "seen")).read().splitlines() if os.path.exists(os.path.join(fake, "seen")) else []
    want = sorted(["%s=%s" % kv for kv in SECRETS.items()] + ["OT_INSTRUMENT=NVDA", "OT_GIT_REF=" + pin,
                                                               "OT_CLAUDE_AT_BOOT=0", "OT_CLAUDE_SETTINGS=pull-only"])
    check("I4 the install gets exactly the unit's symbol and credentials, the full pin, Claude off at boot, pull-only",
          rc == 0 and seen == want and fleet._SENTINEL_REINSTALL_OK in out, f"rc {rc}\n{seen}\n{out[-400:]}")
    log = open(os.path.join(home, "reinstall.log")).read() if os.path.exists(os.path.join(home, "reinstall.log")) else ""
    mode = open(os.path.join(fake, "mode")).read().strip() if os.path.exists(os.path.join(fake, "mode")) else "?"
    leaked = [k for k, v in SECRETS.items() if v in out or v in log]
    check("I5 no credential in the output or the log; TT Account redacted; bootstrap gone, mode 600 while it existed",
          not leaked and "TT Account:  <redacted>" in log and not os.path.exists(os.path.join(home, "bootstrap.sh"))
          and mode == "600", f"leaked={leaked} mode={mode}")
    shutil.rmtree(tmp, True)

    keys = dict(SECRETS, OT_INSTRUMENT="NVDA")
    keys.pop("TT_REFRESH_TOKEN")
    tmp, home, fake, pin = box(unit_keys=keys)
    rc, out = run_box(home, fake, pin)
    check("I6 a unit without a TastyTrade credential is refused (rc 16), nothing left behind",
          rc == 16 and not os.path.exists(os.path.join(home, "bootstrap.sh")) and not os.path.exists(os.path.join(fake, "seen")),
          f"rc {rc} {out[-200:]}")
    shutil.rmtree(tmp, True)

    tmp, home, fake, pin = box()
    rc_bad, out_bad = run_box(home, fake, pin, PUSH_ON=1)
    built_bad = os.path.exists(os.path.join(fake, "seen"))
    rc_ok, out_ok = run_box(home, fake, pin, PUSH_ON=1, DRAIN_OK=1)
    check("I7 an installed push is drained first; a drain that is not OK refuses (rc 15) before any bootstrap",
          rc_bad == 15 and not built_bad and rc_ok == 0 and "drained NVDA" in out_ok, f"{rc_bad} {rc_ok}\n{out_ok[-300:]}")
    shutil.rmtree(tmp, True)

    calls = []
    real = fleet.cmd_repoint
    fleet.cmd_repoint = lambda *a, **k: calls.append(k) or 1
    try:
        r_a = fleet.cmd_reinstall("https://github.com/TX-9AI/OTV5.git", only=None, sha="054f431")
        r_b = fleet.cmd_reinstall("https://github.com/TX-9AI/OTV5.git", only=["NVDA", "SOFI"], sha="054f431")
        r_c = fleet.cmd_reinstall("https://github.com/TX-9AI/OTV5.git", only=["NVDA"], sha=None)
        ran = []
        real_exec = fleet._exec
        fleet._exec = lambda *a, **k: ran.append(a) or (0, "", "")
        try:
            r_d = fleet.cmd_reinstall("https://github.com/TX-9AI/OTV5.git", only=["NVDA"], sha="054f431")
        finally:
            fleet._exec = real_exec
    finally:
        fleet.cmd_repoint = real
    check("I8 refused without one --only or --sha (rc 2); a failed repoint stops before the install",
          (r_a, r_b, r_c) == (2, 2, 2) and r_d == 1 and not ran and calls and calls[-1].get("sha") == "054f431",
          f"{r_a} {r_b} {r_c} {r_d} ran={len(ran)}")

    scr = fleet._reinstall_cmd("054f431")
    check("I9 the install runs detached in tmux session 'reinstall', and the box waits for its rc",
          'tmux new-session -d -s reinstall' in scr and "while [ ! -f ~/reinstall.rc ]" in scr)

    print("\n%s" % ("GREEN — I1-I9" if not PROBLEMS else "RED — " + ", ".join(p.split()[0] for p in PROBLEMS)))
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
