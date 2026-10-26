#!/usr/bin/env python3
# day_trader_pro/pager.py — v0.1.0
# v0.1.0 (2026-10-26) — PAGE.1 — CONTROL FOLLOWS THE BOTS' PAGES. The operator's design: every bot alert also writes
#   ONE short INFO line to bot.log that is the page (OTV5 notifications/pager.py v5.0:
#   `<YYYY-MM-DD HH:MM:SS> [INFO ] notifications.pager: [page] <CODE> [ref]`, managed boxes only), and its timestamp is
#   the reference. This holds ONE ssh stream per running box (ec2ops.describe_by_tag, state running; the argv is
#   ssh_util.ssh_argv, the same key/user/host-key policy as every fleet command) running
#   `tail -n0 -F ~/options-trader/bot.log | grep --line-buffered -F '[page] '` on the box, and prints each page to
#   stdout, flushed: `<SYM> <CODE> [ref] @HH:MM:SS ET` (the box clock is UTC). A code outside PAGE_CODES is dropped
#   and counted; (box, timestamp, code, ref) is printed once. A dropped stream reconnects with backoff 2 s -> 60 s and
#   CATCHES UP first: the same remote command greps bot.log.1 and bot.log for page lines once the new tail is running,
#   and the pages after the last one seen for that box are printed before the tail resumes. EC2 is re-read every
#   5 minutes, so a box that starts gets a stream and one that stops loses it. SIGTERM / SIGINT kill every child ssh
#   and exit 0. `--once` prints today's (ET) pages from every running box and exits. No credentials: ssh only.
#   Gate: tests/check_pager.py.
"""Follow the fleet's `[page]` lines in bot.log over ssh and print one line per page.

    python pager.py            # follow every running box until SIGTERM / SIGINT
    python pager.py --once     # today's pages from every running box, then exit

stdout carries ONLY page lines; connects, drops and the dropped-code count go to stderr.

⚠️ THE REMOTE SIDE DIES WITH THE CONNECTION. A remote `tail | grep` with nobody reading it would otherwise live on
until its next write (grep only writes on a page), so every reconnect would leave one behind: the remote command
reads its stdin (`cat`), which reaches EOF when the ssh channel closes, and then kills its own process group.
⚠️ NO GAP BETWEEN THE CATCH-UP AND THE TAIL. The tail starts first; the catch-up grep runs a second later and its
lines are marked (`=C `) and ended (`=CDONE`), so pages written while the stream was being set up arrive through one
or both and are printed once, in order.
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

import config
import ettime
import ssh_util

__version__ = "0.1.0"

# The fixed code table — OTV5 notifications/pager.py PAGE_CODES; anything else is dropped here.
PAGE_CODES = frozenset({"UP", "DN", "ENT", "EXT", "SUM", "HCF", "BLD", "SEE", "RCU", "EXR", "SLC", "ADP", "ORF",
                        "PHN", "RCV", "MSG"})
REMOTE_LOG = "$HOME/options-trader/bot.log"
BACKOFF_MIN_S = 2.0
BACKOFF_MAX_S = 60.0
RESCAN_S = 300.0
CATCHUP_DELAY_S = 1        # the tail is given this long to open bot.log before the catch-up grep runs
STREAM_OPTS = ("ServerAliveInterval=30", "ServerAliveCountMax=3")    # a half-open connection is noticed, not waited on
ONCE_TIMEOUT_S = 60

# `2026-10-26 13:31:05 [INFO ] notifications.pager: [page] ENT abcd1234` (",mmm" after the seconds is accepted)
PAGE_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(?:,(\d{3}))? \[INFO\s*\] notifications\.pager: "
                     r"\[page\] (\S+)(?: (\S+))?\s*$")
CATCH_MARK = "=C "
CATCH_DONE = "=CDONE"


def parse(line):
    """A bot.log line -> (ts, code, ref) or None. ts is the stamp as written (sortable), ref '' when absent."""
    m = PAGE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    ts = m.group(1) + ("," + m.group(2) if m.group(2) else "")
    return ts, m.group(3), m.group(4) or ""


def to_et(ts):
    """The bot.log stamp (box clock = UTC) -> `HH:MM:SS` ET."""
    d = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ettime.UTC)
    return d.astimezone(ettime.ET).strftime("%H:%M:%S")


def et_date(ts):
    d = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ettime.UTC)
    return d.astimezone(ettime.ET).date().isoformat()


def render(box, code, ref, ts):
    return "%s %s%s @%s ET" % (box, code, (" " + ref) if ref else "", to_et(ts))


def remote_command(follow=True):
    """The shell the box runs. follow=False is the catch-up alone (--once)."""
    grep = "grep -hF '[page] ' \"$L.1\" \"$L\" 2>/dev/null"
    if not follow:
        return "L=%s; %s; true" % (REMOTE_LOG, grep)
    # ⚠️ fd 3, NOT plain `cat &`: a non-interactive shell gives a background job /dev/null as its stdin, so `cat`
    # would read EOF at once and `kill 0` would end the stream the moment it started.
    return ("L=%s; exec 3<&0; (cat <&3 >/dev/null; kill 0) & "
            "tail -n0 -F \"$L\" 2>/dev/null | grep --line-buffered -F '[page] ' & "
            "sleep %d; %s | sed 's/^/%s/'; echo %s; wait"
            % (REMOTE_LOG, CATCHUP_DELAY_S, grep, CATCH_MARK, CATCH_DONE))


def stream_argv(box, ip, command):
    """The child that runs `command` on `box`. Tests replace this with a local process."""
    return ssh_util.ssh_argv(ip, command, extra_opts=STREAM_OPTS)


def discover():
    """{SYM: private_ip} for every RUNNING box carrying the fleet tag."""
    import ec2ops
    return {name: rec.get("private_ip", "") for name, rec in ec2ops.describe_by_tag().items()
            if rec.get("state") == "running" and rec.get("private_ip")}


def _utc_now_stamp():
    return datetime.now(ettime.UTC).strftime("%Y-%m-%d %H:%M:%S")


class Pager:
    """The printer: dedupe, drop unknown codes, one lock around stdout."""

    def __init__(self, out=None):
        self.out = out or sys.stdout
        self.lock = threading.Lock()
        self.seen = set()
        self.last = {}            # box -> newest ts printed or skipped as a dupe
        self.dropped = 0
        self.stop = threading.Event()
        self.children = {}        # box -> Popen
        self.streams = {}         # box -> (thread, ip, own stop event)
        self.started = _utc_now_stamp()     # the first connection's catch-up starts here, not at the log's head

    def emit(self, box, ts, code, ref):
        """Print one page once. True if printed."""
        with self.lock:
            if code not in PAGE_CODES:
                self.dropped += 1
                return False
            if ts > self.last.get(box, ""):
                self.last[box] = ts
            key = (box, ts, code, ref)
            if key in self.seen:
                return False
            self.seen.add(key)
            self.out.write(render(box, code, ref, ts) + "\n")
            self.out.flush()
            return True

    def emit_line(self, box, line, since=None):
        p = parse(line)
        if p is None:
            return False
        if since is not None and p[0] < since:
            return False
        return self.emit(box, *p)

    # ── one box ──────────────────────────────────────────────────────────────
    def _run_child(self, box, argv, own_stop):
        """One connection: catch-up, then tail, until EOF. True if the catch-up completed (the stream was up)."""
        since = self.last.get(box) or self.started
        try:
            p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 start_new_session=True, text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as exc:
            _note("%s: could not start the stream (%s)" % (box, exc))
            return False
        self.children[box] = p
        caught, catch, held = False, [], []
        try:
            if self.stop.is_set() or own_stop.is_set():
                return False
            for line in p.stdout:
                line = line.rstrip("\r\n")
                if not caught:
                    if line == CATCH_DONE:
                        caught = True
                        for ln in sorted(catch, key=lambda x: (parse(x) or ("",))[0]):
                            self.emit_line(box, ln, since=since)
                        for ln in held:
                            self.emit_line(box, ln)
                        catch, held = [], []
                    elif line.startswith(CATCH_MARK):
                        catch.append(line[len(CATCH_MARK):])
                    else:
                        held.append(line)
                else:
                    self.emit_line(box, line)
        finally:
            _kill(p)
            self.children.pop(box, None)
        return caught

    def follow_box(self, box, ip, own_stop):
        backoff = BACKOFF_MIN_S
        n = 0
        while not (self.stop.is_set() or own_stop.is_set()):
            n += 1
            up = self._run_child(box, stream_argv(box, ip, remote_command(True)), own_stop)
            if self.stop.is_set() or own_stop.is_set():
                break
            if up:
                backoff = BACKOFF_MIN_S          # it was a working stream that dropped: start the ladder again
            _note("%s: stream dropped (connection %d); reconnecting in %.1fs" % (box, n, backoff))
            if own_stop.wait(backoff) or self.stop.is_set():
                break
            backoff = min(backoff * 2, BACKOFF_MAX_S)

    # ── the fleet ────────────────────────────────────────────────────────────
    def sync(self, boxes):
        """Start a stream for every box in `boxes` ({SYM: ip}); stop the ones no longer there or moved."""
        for box in list(self.streams):
            th, ip, ev = self.streams[box]
            if boxes.get(box) != ip or not th.is_alive():
                ev.set()
                p = self.children.get(box)
                if p is not None:
                    _kill(p)
                th.join(timeout=5)
                del self.streams[box]
                if box not in boxes:
                    _note("%s: no longer running — stream closed" % box)
        for box, ip in sorted(boxes.items()):
            if box not in self.streams:
                ev = threading.Event()
                th = threading.Thread(target=self.follow_box, args=(box, ip, ev), name="pager-" + box, daemon=True)
                self.streams[box] = (th, ip, ev)
                th.start()
                _note("%s: following %s" % (box, ip))

    def shutdown(self):
        self.stop.set()
        for _box, (_th, _ip, ev) in list(self.streams.items()):
            ev.set()
        for _box, p in list(self.children.items()):
            _kill(p)
        for _box, (th, _ip, _ev) in list(self.streams.items()):
            th.join(timeout=5)

    def follow(self, discover_fn=None, rescan_s=None):
        discover_fn = discover_fn or discover
        rescan_s = RESCAN_S if rescan_s is None else rescan_s
        while not self.stop.is_set():
            try:
                self.sync(discover_fn())
            except Exception as exc:                            # noqa: BLE001
                _note("EC2 scan failed (%s: %s); keeping the current streams" % (type(exc).__name__, exc))
            self.stop.wait(rescan_s)
        self.shutdown()

    def once(self, boxes, day=None):
        """Today's (ET) pages from every box in `boxes`, in time order per box. The catch-up alone, no tail."""
        day = day or ettime.today_et()
        self.started = ""
        for box, ip in sorted(boxes.items()):
            argv = stream_argv(box, ip, remote_command(False))
            try:
                p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=ONCE_TIMEOUT_S)
                out = p.stdout
            except (subprocess.TimeoutExpired, OSError) as exc:
                _note("%s: could not read bot.log (%s)" % (box, type(exc).__name__))
                continue
            rows = [r for r in (parse(ln) for ln in out.splitlines()) if r and et_date(r[0]) == day]
            for ts, code, ref in sorted(rows):
                self.emit(box, ts, code, ref)


def _kill(p):
    """Kill a child's whole session (ssh, or the local stand-in and everything it started). Never raises."""
    try:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(timeout=3)
    except Exception:                                           # noqa: BLE001
        pass


def _note(msg):
    print("pager: %s" % msg, file=sys.stderr, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Follow the fleet's [page] lines in bot.log over ssh.")
    ap.add_argument("--once", action="store_true", help="print today's pages from every running box and exit")
    a = ap.parse_args(argv)
    pg = Pager()

    def _stop(_sig, _frm):
        pg.stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    if config.MOCK_AWS:
        _note("DTP_MOCK_AWS is set — mock instances have no address; nothing to follow")
    if a.once:
        pg.once(discover())
    else:
        pg.follow()
    if pg.dropped:
        _note("dropped %d page(s) with a code outside the table" % pg.dropped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
