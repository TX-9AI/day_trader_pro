#!/usr/bin/env python3
"""
tests/check_repoint_install.py  v1.0
v1.0  2026-10-25  dtp r507 / OPS.72 — MENU 43 IS THE FLEET REPOINT TO OTV5: THE MANAGED REPOINT, THEN THE FULL INSTALL ON
      EVERY BOX. The operator: "If 43 can't do it, we should fix it. This is the use-case for it." fleet.cmd_repoint is
      driven with the fleet, the ssh layer and the pin's template stubbed (nothing touches a box); mi_repoint (the real
      bash function from menu_functions.sh) is driven with a stub fleet.py that records its arguments.
      BORN RED on dtp 2cb7a49 (r506: a pinned repoint never installed; 43 never asked for a pin).

  R1  a pinned repoint whose tree supports the controller install runs PHASE 3 on every box that repointed cleanly -
      reinstall's own box script, at most INSTALL_WORKERS at a time - and a box whose repoint failed is NOT installed
  R2  --no-install (install=False): no phase 3
  R3  a pin whose tree predates the controller install: the git-only managed repoint, said; with install=True, refused
  R4  a pin whose template cannot be read: refused (rc 2) unless --no-install, before any box is touched
  R5  one box's install failing is named; the others' results still print; the run returns 1
  R6  reinstall is the same path for one box (install=True)
  R7  menu 43 with a pin calls `fleet.py repoint URL ... --sha PIN` (and --no-install on "n"), never --no-restart;
      ENTER at the pin keeps the old unpinned prompts
Run:  python3 tests/check_repoint_install.py
"""
import contextlib
import io
import os
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


BOXES = [("AMD", "10.0.0.1", "running"), ("AMZN", "10.0.0.2", "running"), ("AVGO", "10.0.0.3", "running"),
         ("CRM", "10.0.0.4", "running"), ("CVX", "10.0.0.5", "running"), ("META", "10.0.0.6", "running")]


def drive(fleet, support=True, install=None, fail_repoint=(), fail_install=(), only=None):
    sent, maps = [], []
    saved = {k: getattr(fleet, k) for k in ("get_fleet", "survey_remotes", "_exec", "_pin_supports_controller")}
    saved_map = fleet.ssh_util.ssh_map
    fleet.get_fleet = lambda o=None: [b for b in BOXES if not o or b[0] in o]
    fleet.survey_remotes = lambda running, exec_fn=None: {s: "options_trader_v4" for s, _, _ in running}
    fleet._pin_supports_controller = lambda repo, sha: support

    def _ex(sym, ip, cmd, timeout=None):
        sent.append((sym, cmd))
        if "reset --hard" in cmd:
            return (1, "boom", "") if sym in fail_repoint else (0, f"{fleet._SENTINEL_OK} a -> b\n", "")
        return (0, "", "")
    fleet._exec = _ex

    def _map(targets, command, timeout=None, workers=None, on_result=None):
        targets = list(targets)
        maps.append((targets, command, workers))
        res = {}
        for n, (k, ip) in enumerate(targets, 1):
            r = (18, "install rc=1", "") if k in fail_install else (0, f"{fleet._SENTINEL_REINSTALL_OK} x\n", "")
            res[k] = r
            on_result and on_result(k, r, n, len(targets))
        return res
    fleet.ssh_util.ssh_map = _map
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = fleet.cmd_repoint("https://github.com/TX-9AI/OTV5.git", only=only, assume_yes=True,
                                   sha="6dc63e2", install=install)
    finally:
        for k, v in saved.items():
            setattr(fleet, k, v)
        fleet.ssh_util.ssh_map = saved_map
    return rc, buf.getvalue(), sent, maps


def main():
    import fleet
    rc, out, sent, maps = drive(fleet, fail_repoint=("CRM",))
    targets = [k for k, _ in maps[0][0]] if maps else []
    check("R1 phase 3 installs every cleanly repointed box (reinstall's script, <= INSTALL_WORKERS), not the failed one",
          len(maps) == 1 and sorted(targets) == ["AMD", "AMZN", "AVGO", "CVX", "META"]
          and maps[0][1] == fleet._reinstall_cmd("6dc63e2") and maps[0][2] <= fleet.INSTALL_WORKERS
          and rc == 1 and "PHASE 3" in out, f"rc={rc} targets={targets}\n{out[-400:]}")
    rc, out, sent, maps = drive(fleet, install=False)
    check("R2 --no-install: no phase 3", rc == 0 and not maps and "PHASE 3" not in out, out[-300:])
    rc, out, sent, maps = drive(fleet, support=False)
    rc2, out2, sent2, maps2 = drive(fleet, support=False, install=True)
    check("R3 a pre-r17 pin: git-only repoint, said; install=True refused",
          rc == 0 and not maps and "predates the controller install" in out and rc2 == 2 and not sent2,
          f"rc={rc} rc2={rc2}")
    rc, out, sent, maps = drive(fleet, support=None)
    rc2, out2, sent2, maps2 = drive(fleet, support=None, install=False)
    check("R4 an unreadable template: refused before any box is touched, unless --no-install",
          rc == 2 and not sent and "cannot read the pin" in out and rc2 == 0, f"rc={rc} sent={len(sent)} rc2={rc2}")
    rc, out, sent, maps = drive(fleet, fail_install=("AVGO",))
    check("R5 one failed install is named; the rest still report; rc 1",
          rc == 1 and "AVGO: INSTALL FAILED" in out and out.count(": INSTALLED") == 5 and "FAILED: AVGO" in out,
          out[-500:])
    calls = []
    real = fleet.cmd_repoint
    fleet.cmd_repoint = lambda *a, **k: calls.append(k) or 0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            r6 = fleet.cmd_reinstall("https://github.com/TX-9AI/OTV5.git", only=["AMD"], sha="6dc63e2")
    finally:
        fleet.cmd_repoint = real
    check("R6 reinstall is the same path for one box (install=True)",
          r6 == 0 and calls and calls[0].get("install") is True and calls[0].get("only") == ["AMD"], str(calls))

    # R7 — the real mi_repoint, with a stub fleet.py
    d = tempfile.mkdtemp(prefix="menu43_")
    log = os.path.join(d, "args")
    stub = os.path.join(d, "py")
    open(stub, "w").write('#!/bin/bash\necho "$@" >> "%s"\n' % log)
    os.chmod(stub, 0o755)
    harness = ('pause(){ :; }; _yes(){ case "${1:-}" in y|Y|yes) return 0;; *) return 1;; esac; }; '
               'ask_url(){ echo https://github.com/TX-9AI/OTV5.git; }; PY=%s; '
               'eval "$(sed -n \'/^mi_repoint() {/,/^}/p\' %s)"; mi_repoint' % (stub, os.path.join(ROOT, "menu_functions.sh")))

    def menu(inputs):
        if os.path.exists(log):
            os.remove(log)
        subprocess.run(["bash", "-c", harness], input=inputs, capture_output=True, text=True, timeout=30)
        return open(log).read().strip() if os.path.exists(log) else ""
    a = menu("\ny\n6dc63e2\n\n")
    b = menu("AMD\n\n6dc63e2\nn\n")
    c = menu("\n\n\n\n")
    check("R7 menu 43: a pin -> repoint --sha (n -> --no-install), never --no-restart; ENTER keeps the old prompts",
          a.startswith("fleet.py repoint https://github.com/TX-9AI/OTV5.git") and "--sha 6dc63e2" in a
          and "--wake" in a and "--no-install" not in a and "--no-restart" not in a
          and "--only AMD" in b and "--no-install" in b and "--sha" not in c and c.startswith("fleet.py repoint"),
          f"a={a!r} b={b!r} c={c!r}")

    print("\n%s" % ("GREEN — R1-R7" if not PROBLEMS else "RED — " + ", ".join(p.split()[0] for p in PROBLEMS)))
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
