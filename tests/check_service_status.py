#!/usr/bin/env python3
"""
day_trader_pro/tests/check_service_status.py  v1.0
v1.0  2026-10-25  DEV.3 — the land gate for SERVICE STATUS on an OTV5 fleet.

  V1  the item is registered and names a function that EXISTS
  V2  on a box where every OTV5 unit is up, the item reports NO unit inactive
  V3  every unit it queries is a unit OTV5 installs (optionsbot, candle-feed, OTV5 deploy/*.service|*.timer)
  V4  it reports the warehouse push (s3-push.timer)
  V5  a dead unit still reads `inactive` and the remote command exits 0 (the `|| true`, r303)
  V6  the label does not name a unit OTV5 does not run (shadow)

The REAL mi_service_status_bot_candle_feed is driven with a stub fleet.py that records the remote
command, and that command is then executed by bash against a fake `systemctl` on PATH. Nothing
reaches a box.

BORN RED on dtp 4fec59e: V2 V3 V4 V6
"""
import glob
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OTV5 = os.environ.get("OTV5_REPO", os.path.expanduser("~/OTV5"))
FN = "mi_service_status_bot_candle_feed"
FAILS = []


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def otv5_units():
    units = {"optionsbot"}                     # setup_ec2.sh SERVICE_NAME
    for f in glob.glob(os.path.join(OTV5, "deploy", "*.service")) + glob.glob(os.path.join(OTV5, "deploy", "*.timer")):
        b = os.path.basename(f)
        units.add(b)
        if b.endswith(".service"):
            units.add(b[:-len(".service")])
    if len(units) == 1:                        # no OTV5 checkout here: the units its deploy/ ships at r19
        units |= {"candle-feed", "candle-feed.service", "s3-push.service", "s3-push", "s3-push.timer",
                  "candle-logger.service", "candle-logger", "candle-logger.timer"}
    return units


def captured_command(d):
    log = os.path.join(d, "args")
    stub = os.path.join(d, "py")
    open(stub, "w").write('#!/bin/bash\nprintf "%%s\\0" "$@" > "%s"\n' % log)
    os.chmod(stub, 0o755)
    harness = ('pause(){ :; }; ask_scope(){ :; }; PY=%s; '
               'eval "$(sed -n \'/^%s() {/,/^}/p\' %s)"; %s' % (stub, FN, os.path.join(ROOT, "menu_functions.sh"), FN))
    subprocess.run(["bash", "-c", harness], input="", capture_output=True, text=True, timeout=30)
    if not os.path.exists(log):
        return None
    args = open(log).read().split("\0")
    if len(args) >= 3 and args[0] == "fleet.py" and args[1] == "run":
        return args[2]
    return None


def run_remote(cmd, d, up):
    bindir = os.path.join(d, "bin")
    os.makedirs(bindir, exist_ok=True)
    queried = os.path.join(d, "queried")
    fake = os.path.join(bindir, "systemctl")
    open(fake, "w").write(
        '#!/bin/bash\n[ "$1" = is-active ] || exit 1\necho "$2" >> "%s"\n'
        'case " %s " in *" $2 "*) echo active; exit 0;; *) echo inactive; exit 3;; esac\n' % (queried, " ".join(sorted(up))))
    os.chmod(fake, 0o755)
    if os.path.exists(queried):
        os.remove(queried)
    env = dict(os.environ, PATH=bindir + ":" + os.environ.get("PATH", ""))
    p = subprocess.run(["bash", "-c", cmd], env=env, capture_output=True, text=True, timeout=30)
    q = open(queried).read().split() if os.path.exists(queried) else []
    return p.returncode, p.stdout.strip(), q


def main():
    reg = open(os.path.join(ROOT, "menu_registry.sh")).read()
    fns = open(os.path.join(ROOT, "menu_functions.sh")).read()
    items = [m for m in re.findall(r'"ITEM\|([^"]*)"', reg) if m.rsplit("|", 1)[-1] == FN]
    check("V1", len(items) == 1 and (FN + "() {") in fns, "registered={} defined={}".format(len(items), (FN + "() {") in fns))

    units = otv5_units()
    d = tempfile.mkdtemp(prefix="svcstatus_")
    cmd = captured_command(d)
    if cmd is None:
        check("V2", False, "the item did not call `fleet.py run <cmd>`")
        rc, out, q = 1, "", []
    else:
        rc, out, q = run_remote(cmd, d, units)
    check("V2", cmd is not None and rc == 0 and "inactive" not in out and out != "", "healthy OTV5 box -> {!r}".format(out))
    alien = [u for u in q if u not in units]
    check("V3", bool(q) and not alien, "queried={} not-OTV5={}".format(q, alien))
    check("V4", "s3-push.timer" in q or "s3-push" in q, "queried={}".format(q))
    if cmd is not None:
        rc5, out5, _ = run_remote(cmd, d, {"optionsbot", "s3-push.timer"})
    else:
        rc5, out5 = 1, ""
    check("V5", rc5 == 0 and "candle-feed=inactive" in out5, "candle-feed down -> rc={} {!r}".format(rc5, out5))
    label = items[0].split("|")[0] if items else ""
    check("V6", label and "shadow" not in label.lower(), "label={!r}".format(label))

    import shutil
    shutil.rmtree(d, ignore_errors=True)
    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (6)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
