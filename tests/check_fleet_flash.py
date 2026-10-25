#!/usr/bin/env python3
"""
tests/check_fleet_flash.py  v1.0
v1.0  2026-10-25  dtp r506 / OPS.71 — `fleet.py flash`: OTV5 ONTO A BLANK TAGGED INSTANCE, RUN END TO END ON FAKE BOXES.
      A fake `ssh` routes each IP to its own scratch HOME and runs the command there with bash, so the REAL credential
      pipe (_pipe_creds: seed unit -> new box) and the REAL new-box script (_flash_cmd) run between a fake SEED box (a
      unit holding FAKE credentials) and a fake BLANK instance; sudo maps /etc/systemd/system into that HOME; curl serves
      the bootstrap template and an install.sh that records the environment it was given and answers like setup_ec2 v5.2
      in controller mode. No real box, unit, credential or network is touched. BORN RED on dtp 82dc238 (no flash).

  F1  refused (rc 2): not exactly one --only; no --seed; the seed is the target; a bad --symbol; an unresolvable pin
  F2  a blank instance is flashed: the install gets EXACTLY the seed unit's five credentials, OT_INSTRUMENT = --symbol,
      OT_INSTALL_MODE=controller, OT_CLAUDE_AT_BOOT=0, OT_CLAUDE_SETTINGS=pull-only and OT_GIT_REF = the full pin; rc 0
  F3  no credential value reaches control's output; ~/.flash_creds and ~/bootstrap.sh are gone from the new box;
      the seed's unit is unchanged
  F4  an instance that already has ~/options-trader is refused and nothing is installed; its credentials are shredded
  F5  a seed whose unit lacks a TastyTrade credential: nothing installed, no credential file left
  F6  a pinned template without OT_INSTALL_MODE (before OTV5 r17) is refused, nothing installed
  F7  the pipe never reads the seed's stdout into control's Python: the seed's stdout is the receiver's stdin
Run:  python3 tests/check_fleet_flash.py
"""
import contextlib
import inspect
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PROBLEMS = []
SHA = "c0ffee" + "0" * 34


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    if not ok:
        PROBLEMS.append(name)


SECRETS = {"TT_CLIENT_SECRET": "cs-SECRET-111", "TT_REFRESH_TOKEN": "rt-SECRET-222",
           "TT_ACCOUNT_NUMBER": "5WTSECRET3", "TELEGRAM_TOKEN": "tg-SECRET-444", "TELEGRAM_CHAT_ID": "SECRET555"}
TEMPLATE = """#!/bin/bash
export OT_INSTALL_MODE="unattended"
export OT_INSTRUMENT="QQQ"
export OT_GIT_REF="main"
export TT_CLIENT_SECRET=""
export TT_REFRESH_TOKEN=""
export TT_ACCOUNT_NUMBER=""
export TELEGRAM_TOKEN=""
export TELEGRAM_CHAT_ID=""
export GITHUB_REPO="TX-9AI/OTV5"
export OT_CLAUDE_AT_BOOT="1"
export OT_CLAUDE_SETTINGS=""
curl -fsSL "https://raw.githubusercontent.com/${GITHUB_REPO}/${OT_GIT_REF}/deploy/install.sh" -o install.sh \\
    && bash install.sh
"""
SSH = r'''#!/bin/bash
host=""; for a in "$@"; do case "$a" in *@*) host="${a#*@}";; esac; done
cmd="${@: -1}"
home=$(echo "$FAKE_HOMES" | tr ',' '\n' | grep "^$host=" | cut -d= -f2)
[ -n "$home" ] || { echo "no fake box at $host" >&2; exit 255; }
cd "$home" && HOME="$home" exec bash -c "$cmd"
'''
SUDO = '#!/bin/bash\nargs=(); for a in "$@"; do args+=("${a//\\/etc\\/systemd\\/system\\//$HOME/etc/}"); done\nexec "${args[@]}"\n'
SYSTEMCTL = '#!/bin/bash\n[ "$1" = is-enabled ] && { echo disabled; exit 1; }\n[ "$1" = is-active ] && { echo inactive; exit 3; }\nexit 0\n'
TMUX = '#!/bin/bash\n[ "$1" = new-session ] && { TMUX=stub bash -c "${@: -1}"; exit $?; }\nexit 0\n'
CURL = r'''#!/bin/bash
url=""; out=""; while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; http*) url="$1";; esac; shift; done
case "$url" in
  *bootstrap.example.sh) cp "$FAKE_TPL" "$out" ;;
  *install.sh) cat > "$out" <<'INST'
#!/bin/bash
env | grep -E '^(OT_INSTALL_MODE|OT_INSTRUMENT|TT_CLIENT_SECRET|TT_REFRESH_TOKEN|TT_ACCOUNT_NUMBER|TELEGRAM_TOKEN|TELEGRAM_CHAT_ID|OT_GIT_REF|OT_CLAUDE_AT_BOOT|OT_CLAUDE_SETTINGS)=' | sort > "$HOME/seen"
mkdir -p "$HOME/options-trader"
echo "  TT Account:  $TT_ACCOUNT_NUMBER"
[ "$OT_INSTALL_MODE" = controller ] && echo "INSTALL OK $OT_GIT_REF"
exit 0
INST
  ;;
  *) exit 22 ;;
esac
'''


def world(seed_keys=None, blank=True, template=TEMPLATE):
    tmp = tempfile.mkdtemp(prefix="flash_")
    bin_ = os.path.join(tmp, "bin")
    os.makedirs(bin_)
    for n, b in (("ssh", SSH), ("sudo", SUDO), ("systemctl", SYSTEMCTL), ("tmux", TMUX), ("curl", CURL)):
        open(os.path.join(bin_, n), "w").write(b)
        os.chmod(os.path.join(bin_, n), 0o755)
    seed, new = os.path.join(tmp, "seed"), os.path.join(tmp, "new")
    os.makedirs(os.path.join(seed, "etc"))
    os.makedirs(new)
    if not blank:
        os.makedirs(os.path.join(new, "options-trader"))
    keys = dict(SECRETS, OT_INSTRUMENT="SOFI", OT_RISK_USD="1050") if seed_keys is None else seed_keys
    unit = os.path.join(seed, "etc", "optionsbot.service")
    with open(unit, "w") as f:
        f.write("[Service]\n" + "".join(('Environment="%s=%s"\n' if i % 2 else "Environment=%s=%s\n") % kv
                                         for i, kv in enumerate(keys.items())))
    tpl = os.path.join(tmp, "tpl.sh")
    open(tpl, "w").write(template)
    env = {"PATH": bin_ + ":" + os.environ["PATH"], "FAKE_HOMES": "10.0.0.1=%s,10.0.0.2=%s" % (seed, new),
           "FAKE_TPL": tpl}
    return tmp, seed, new, unit, env


def flash(fleet, env, **kw):
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    real = fleet.get_fleet
    fleet.get_fleet = lambda only=None: [("SOFI", "10.0.0.1", "running"), ("NEWBOX", "10.0.0.2", "running")]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = fleet.cmd_flash("https://github.com/TX-9AI/FAKEREPO.git", assume_yes=True, **kw)
    finally:
        fleet.get_fleet = real
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return rc, buf.getvalue()


def main():
    import fleet
    ok_args = dict(only=["NEWBOX"], sha=SHA, seed="SOFI", symbol="IWM")
    with contextlib.redirect_stdout(io.StringIO()):
        bad = [fleet.cmd_flash("https://github.com/TX-9AI/FAKEREPO.git", **dict(ok_args, **d))
               for d in ({"only": None}, {"only": ["A", "B"]}, {"seed": None}, {"seed": "NEWBOX"},
                         {"symbol": "no good!"}, {"sha": "abc1234"})]
    check("F1 refused (rc 2): --only, --seed, seed = target, bad symbol, unresolvable short pin", bad == [2] * 6, str(bad))

    tmp, seed, new, unit, env = world()
    before = open(unit).read()
    rc, out = flash(fleet, env, **ok_args)
    seen = open(os.path.join(new, "seen")).read().splitlines() if os.path.exists(os.path.join(new, "seen")) else []
    want = sorted(["%s=%s" % kv for kv in SECRETS.items()] + ["OT_INSTRUMENT=IWM", "OT_GIT_REF=" + SHA,
                                                               "OT_INSTALL_MODE=controller", "OT_CLAUDE_AT_BOOT=0",
                                                               "OT_CLAUDE_SETTINGS=pull-only"])
    check("F2 the blank instance is flashed with exactly the seed's credentials, the symbol, controller mode, the pin",
          rc == 0 and seen == want and fleet._SENTINEL_REINSTALL_OK in out, f"rc {rc}\n{seen}\n{out[-500:]}")
    leaked = [k for k, v in SECRETS.items() if v in out]
    check("F3 no credential in control's output; creds and bootstrap gone from the new box; seed unit unchanged",
          not leaked and not os.path.exists(os.path.join(new, ".flash_creds"))
          and not os.path.exists(os.path.join(new, "bootstrap.sh")) and open(unit).read() == before,
          f"leaked={leaked}")
    shutil.rmtree(tmp, True)

    tmp, seed, new, unit, env = world(blank=False)
    rc, out = flash(fleet, env, **ok_args)
    check("F4 an instance that already has ~/options-trader is refused; nothing installed; creds shredded",
          rc == 1 and "not a blank instance" in out and not os.path.exists(os.path.join(new, "seen"))
          and not os.path.exists(os.path.join(new, ".flash_creds")), f"rc {rc}\n{out[-300:]}")
    shutil.rmtree(tmp, True)

    keys = dict(SECRETS, OT_INSTRUMENT="SOFI")
    keys.pop("TT_REFRESH_TOKEN")
    tmp, seed, new, unit, env = world(seed_keys=keys)
    rc, out = flash(fleet, env, **ok_args)
    check("F5 a seed lacking a TastyTrade credential: nothing installed, no credential file left",
          rc == 1 and not os.path.exists(os.path.join(new, "seen")) and not os.path.exists(os.path.join(new, ".flash_creds"))
          and not os.path.exists(os.path.join(new, "bootstrap.sh")), f"rc {rc}\n{out[-300:]}")
    shutil.rmtree(tmp, True)

    tmp, seed, new, unit, env = world(template=TEMPLATE.replace('export OT_INSTALL_MODE="unattended"\n', ""))
    rc, out = flash(fleet, env, **ok_args)
    check("F6 a pinned template without OT_INSTALL_MODE is refused, nothing installed",
          rc == 1 and "predates OTV5 r17" in out and not os.path.exists(os.path.join(new, "seen")), f"rc {rc}\n{out[-300:]}")
    shutil.rmtree(tmp, True)

    src = inspect.getsource(fleet._pipe_creds)
    check("F7 the seed's stdout is the receiver's stdin; control's Python never reads it",
          "stdin=p1.stdout" in src and "p1.stdout.read" not in src and "p1.communicate" not in src)

    print("\n%s" % ("GREEN — F1-F7" if not PROBLEMS else "RED — " + ", ".join(p.split()[0] for p in PROBLEMS)))
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
