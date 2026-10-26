#!/usr/bin/env python3
"""
day_trader_pro/tests/check_pager.py  v1.0
v1.0  2026-10-26  PAGE.1 — CONTROL FOLLOWS THE BOTS' `[page]` LINES (pager.py v0.1.0).

No network. The "box" is a local bash running pager.py's OWN remote command against a temp
$HOME/options-trader/bot.log, so the real tail | grep, the catch-up grep and its markers are what is driven; only
the ssh hop is replaced (pager.stream_argv). EC2 is replaced by a dict (discover_fn).

  G1  pager.py imports; PAGE_CODES is the fixed sixteen-code table
  G2  a page line parses and renders `<SYM> <CODE> [ref] @HH:MM:SS ET` from the UTC stamp (EDT, EST, ",mmm")
  G3  non-page lines are ignored (an ALERT line, another logger's "[page] " text, a bare line)
  G4  a code outside the table is dropped and counted, nothing printed
  G5  a duplicate (box, ts, code, ref) prints once; the same ts with another code prints
  G6  the stream: pages written to bot.log after the start print; pages already in it before the start do not
  G7  a dropped stream reconnects and catches up the pages written while down, without reprinting any
  G8  ...including a page that rotated into bot.log.1 while down
  G9  the remote command lives while its stdin is open and dies (tail with it) when the connection closes
  G10 --once prints only the given ET day's pages, oldest first, from bot.log.1 and bot.log, and returns
  G11 the reconnect backoff doubles from the floor and stops at the ceiling
  G12 the real argv is ssh_util.ssh_argv's (key, BatchMode, accept-new, ConnectTimeout) plus ServerAlive
  G13 SIGTERM: `pager.py` exits 0 promptly and leaves no child running
  G14 Pager.shutdown() ends the follow loop and leaves no stand-in, tail or grep running

BORN RED on dtp 2d8adf9: G1 (pager.py absent; every later check fails with it)
"""
import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []
TMP = tempfile.mkdtemp(prefix="check_pager-")
LOG = os.path.join(TMP, "options-trader", "bot.log")
CODES = {"UP", "DN", "ENT", "EXT", "SUM", "HCF", "BLD", "SEE", "RCU", "EXR", "SLC", "ADP", "ORF", "PHN", "RCV", "MSG"}


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", "" if ok else detail))
    if not ok:
        FAILS.append(name)


def pline(ts, code, ref=""):
    return "%s [INFO ] notifications.pager: [page] %s%s" % (ts, code, (" " + ref) if ref else "")


def append(path, *lines):
    with open(path, "a") as fh:
        for ln in lines:
            fh.write(ln + "\n")


def utc(offset_s=0):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + offset_s))


class Out(io.StringIO):
    def __init__(self):
        super().__init__()
        self.lk = threading.Lock()

    def write(self, s):
        with self.lk:
            return super().write(s)

    def lines(self):
        with self.lk:
            return [x for x in self.getvalue().splitlines() if x]


def wait_for(fn, timeout=12.0):
    t = time.time()
    while time.time() - t < timeout:
        if fn():
            return True
        time.sleep(0.1)
    return fn()


def local_argv(_box, _ip, command):
    return ["env", "HOME=%s" % TMP, "bash", "-c", command]


def strays():
    """Local processes still holding the fixture log (a tail the stream left behind)."""
    r = subprocess.run(["pgrep", "-af", TMP], capture_output=True, text=True)
    return [ln for ln in r.stdout.splitlines() if "drive.py" not in ln]


def main():
    try:
        import pager
    except Exception as e:                                          # noqa: BLE001
        check("G1", False, "import pager raised %s: %s" % (type(e).__name__, e))
        for g in ("G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13", "G14"):
            check(g, False, "no pager.py")
        return 1
    check("G1", set(pager.PAGE_CODES) == CODES, "PAGE_CODES=%r" % sorted(pager.PAGE_CODES))

    # G2 — parse + ET
    o = Out()
    pg = pager.Pager(out=o)
    pg.emit_line("QQQ", pline("2026-10-26 13:31:05", "ENT", "abcd1234"))        # EDT: UTC-4
    pg.emit_line("SPX", pline("2026-11-02 14:31:05,123", "UP"))                 # EST: UTC-5, with ms
    pg.emit_line("NVDA", "2026-10-26 23:59:59,999 [INFO ] notifications.pager: [page] SUM")
    want = ["QQQ ENT abcd1234 @09:31:05 ET", "SPX UP @09:31:05 ET", "NVDA SUM @19:59:59 ET"]
    check("G2", o.lines() == want, "got %r" % o.lines())

    # G3 — non-page lines
    o = Out()
    pg = pager.Pager(out=o)
    junk = ["2026-10-26 13:31:05 [INFO ] notifications.alert_manager: ALERT: OptionsBot STARTED | QQQ",
            "2026-10-26 13:31:05 [INFO ] __main__: operator typed [page] UP here",
            "[page] UP", "", "2026-10-26 13:31:05 [INFO ] notifications.pager: [page] UP extra token"]
    printed = [pg.emit_line("QQQ", ln) for ln in junk]
    check("G3", not any(printed) and o.lines() == [] and all(pager.parse(ln) is None for ln in junk),
          "printed=%r out=%r" % (printed, o.lines()))

    # G4 — unknown code
    o = Out()
    pg = pager.Pager(out=o)
    pg.emit_line("QQQ", pline("2026-10-26 13:31:05", "ZZZ", "x"))
    pg.emit_line("QQQ", pline("2026-10-26 13:31:06", "msg"))
    check("G4", o.lines() == [] and pg.dropped == 2, "out=%r dropped=%d" % (o.lines(), pg.dropped))

    # G5 — dupes
    o = Out()
    pg = pager.Pager(out=o)
    for _ in range(3):
        pg.emit_line("QQQ", pline("2026-10-26 13:31:05", "EXT", "t1"))
    pg.emit_line("QQQ", pline("2026-10-26 13:31:05", "SUM"))
    pg.emit_line("SPX", pline("2026-10-26 13:31:05", "EXT", "t1"))
    check("G5", o.lines() == ["QQQ EXT t1 @09:31:05 ET", "QQQ SUM @09:31:05 ET", "SPX EXT t1 @09:31:05 ET"],
          "got %r" % o.lines())

    # G6..G8 — the live stream, a drop, a catch-up
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    append(LOG, pline(utc(-3600), "UP"), "noise line")                  # before the start: never printed
    pager.stream_argv = local_argv
    pager.BACKOFF_MIN_S = 0.3
    o = Out()
    pg = pager.Pager(out=o)
    th = threading.Thread(target=pg.follow, kwargs={"discover_fn": lambda: {"QQQ": "127.0.0.1"}, "rescan_s": 3600},
                          daemon=True)
    th.start()
    wait_for(lambda: "QQQ" in pg.children, 5)
    time.sleep(pager.CATCHUP_DELAY_S + 1.0)                             # the catch-up has run; the tail is live
    t1 = utc()
    append(LOG, "%s [INFO ] __main__: tick" % t1, pline(t1, "ENT", "aaaa1111"), pline(t1, "ENT", "aaaa1111"),
           pline(t1, "BOGUS"))
    got6 = wait_for(lambda: len(o.lines()) >= 1, 8)
    time.sleep(0.5)
    check("G6", got6 and o.lines() == ["QQQ ENT aaaa1111 @%s ET" % pager.to_et(t1)], "got %r" % o.lines())

    # drop it: kill the stand-in's whole session, write while it is down
    first = pg.children.get("QQQ")
    if first is not None:
        os.killpg(first.pid, signal.SIGKILL)
    wait_for(lambda: pg.children.get("QQQ") is not first, 5)
    t2 = utc(1)
    append(LOG, pline(t2, "EXT", "aaaa1111"))                           # while down, in bot.log
    # rotate while down: bot.log -> bot.log.1, a new bot.log
    os.rename(LOG, LOG + ".1")
    t3 = utc(2)
    append(LOG, pline(t3, "SUM"))
    want7 = ["QQQ ENT aaaa1111 @%s ET" % pager.to_et(t1), "QQQ EXT aaaa1111 @%s ET" % pager.to_et(t2),
             "QQQ SUM @%s ET" % pager.to_et(t3)]
    wait_for(lambda: len(o.lines()) >= 3, 15)
    time.sleep(pager.CATCHUP_DELAY_S + 0.5)
    t4 = utc(3)
    append(LOG, pline(t4, "DN"))                                        # and the tail is live again
    wait_for(lambda: len(o.lines()) >= 4, 8)
    time.sleep(0.5)
    lines = o.lines()
    check("G7", lines[:2] == want7[:2] and lines[3:] == ["QQQ DN @%s ET" % pager.to_et(t4)] and len(lines) == 4
          and len(set(lines)) == len(lines), "got %r" % lines)
    check("G8", len(lines) >= 3 and lines[2] == want7[2], "got %r" % lines)
    pg.shutdown()
    th.join(timeout=10)
    time.sleep(0.5)
    left = strays()
    check("G14", not th.is_alive() and not left, "thread alive=%s strays=%r" % (th.is_alive(), left))

    # G9 — the remote command dies with its connection
    p = subprocess.Popen(local_argv("QQQ", "", pager.remote_command(True)), stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(2.0)
    alive_open = p.poll() is None
    p.stdin.close()                                                     # what the ssh channel closing looks like
    try:
        p.wait(timeout=5)
        died = True
    except subprocess.TimeoutExpired:
        died = False
        os.killpg(p.pid, signal.SIGKILL)
    time.sleep(0.5)
    left = strays()
    check("G9", alive_open and died and not left, "alive_while_open=%s died_on_close=%s strays=%r"
          % (alive_open, died, left))

    # G10 — --once
    os.unlink(LOG + ".1")
    os.unlink(LOG)
    append(LOG + ".1", pline("2026-10-25 15:00:00", "UP"), pline("2026-10-26 03:59:59", "SUM"),   # 10-25 ET both
           pline("2026-10-26 13:15:01", "UP"))
    append(LOG, pline("2026-10-27 01:00:00", "DN"), pline("2026-10-26 14:00:00", "ENT", "bbbb2222"),
           pline("2026-10-26 14:00:00", "WHAT"), "2026-10-26 14:00:01 [INFO ] __main__: not a page")
    o = Out()
    pg = pager.Pager(out=o)
    t = time.time()
    pg.once({"QQQ": "127.0.0.1"}, day="2026-10-26")
    check("G10", o.lines() == ["QQQ UP @09:15:01 ET", "QQQ ENT bbbb2222 @10:00:00 ET", "QQQ DN @21:00:00 ET"]
          and pg.dropped == 1 and time.time() - t < 10, "got %r dropped=%d" % (o.lines(), pg.dropped))

    # G11 — backoff ladder
    times = []

    def failing(_b, _i, _c):
        times.append(time.time())
        return ["false"]
    pager.stream_argv = failing
    pager.BACKOFF_MIN_S, pager.BACKOFF_MAX_S = 0.1, 0.4
    pg = pager.Pager(out=Out())
    ev = threading.Event()
    th = threading.Thread(target=pg.follow_box, args=("QQQ", "x", ev), daemon=True)
    th.start()
    wait_for(lambda: len(times) >= 6, 6)
    ev.set()
    th.join(timeout=3)
    gaps = [round(b - a, 2) for a, b in zip(times, times[1:])][:5]
    ok11 = len(gaps) == 5 and 0.08 <= gaps[0] < 0.18 and 0.18 <= gaps[1] < 0.3 and all(0.38 <= g < 0.55
                                                                                        for g in gaps[2:])
    check("G11", ok11, "gaps=%r" % gaps)
    pager.stream_argv = local_argv

    # G12 — the real argv
    import importlib
    import config
    real = importlib.reload(pager)
    argv = real.stream_argv("QQQ", "10.1.2.3", "CMD")
    ok12 = (argv[:2] == ["ssh", "-i"] and argv[2] == config.SSH_KEY_PATH and "BatchMode=yes" in argv
            and "StrictHostKeyChecking=accept-new" in argv and "ConnectTimeout=%d" % config.SSH_CONNECT_TIMEOUT in argv
            and "ServerAliveInterval=30" in argv and argv[-2:] == ["%s@10.1.2.3" % config.SSH_USER, "CMD"])
    check("G12", ok12, "argv=%r" % argv)

    # G13 — SIGTERM on the real entry point (EC2 and ssh replaced by a driver; no network)
    drv = os.path.join(TMP, "drive.py")
    with open(drv, "w") as fh:
        fh.write("import sys; sys.path.insert(0, %r)\n"
                 "import pager\n"
                 "pager.stream_argv = lambda b, i, c: ['env', 'HOME=%s', 'bash', '-c', c]\n"
                 "pager.discover = lambda: {'QQQ': '127.0.0.1', 'SPX': '127.0.0.2'}\n"
                 "sys.exit(pager.main([]))\n" % (ROOT, TMP))
    p = subprocess.Popen([sys.executable, drv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(3.0)
    p.send_signal(signal.SIGTERM)
    try:
        out, err = p.communicate(timeout=10)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        rc = "hung"
    time.sleep(0.5)
    left = strays()
    check("G13", rc == 0 and not left and "following" in err, "rc=%r strays=%r err=%r" % (rc, left, err[-200:]))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (14)")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        subprocess.run(["pkill", "-f", TMP], capture_output=True)
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(rc)
