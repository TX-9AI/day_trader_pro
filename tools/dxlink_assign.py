#!/usr/bin/env python3
"""
day_trader_pro/tools/dxlink_assign.py — v1.2
v1.2  2026-11-08  dtp r539 / TIMER.1 — the summary line goes to control's alert router through dxlink_probe.enqueue
      (alert_router.post_status "info"); tools/feed_triage.py and its outbox are deleted (the operator, 2026-11-08:
      "It should be reactionary, by event type—not run every minute looking for problems").
v1.1  2026-11-07  dtp r525 / FEED.15b — THE ASSIGNMENT GOES LIVE, DELIVERED AS EACH BOX COMES UP. The operator,
      2026-11-07: "Yes" to switching it on (and "Try not to suggest 'log only' as the proposed fix"). The timer moves
      from 09:17 to 09:16 ET and the service runs --apply --until 09:25. A box that is stopped cannot be written to
      (the fleet sleeps until the 09:15 wake, orchestrator.py ec2ops.start), so a pre-wake run would find no running
      box and write nothing: the file is delivered AFTER the wake, and OTV5 r74 candle_feed reads it on its ~15 s
      flush cadence and switches to it once before ASSIGN_SWITCH_BY_ET 09:27 (PlannedNodeSwitch, 1-5 s, pre-open).
      run_window() repeats the pass every --every seconds (20) until every running fleet box has its file or the
      --until deadline: a box whose ssh is not up yet, or that reaches running late, is planned and written on a
      later pass; a box already written keeps its node (plan(pinned=), counted first, so it never moves twice) and is
      not written again. A non-trading day writes nothing. One outbox line at the end. Same NEVERs as v1.0.
v1.0  2026-11-04  dtp r523 / FEED.15 — CONTROL ASSIGNS EACH BOX ITS DXLINK NODE BEFORE THE OPEN.
      The operator, 2026-11-02: "if we have control over the connections, then spread them out"; "Yes, connect to a
      known new server & if we can probe to spread out our connections prior to the open, it might be worth looking
      into"; 2026-11-03: "Yes to the proposal". On 2026-11-02 the 09:30 mass reconnect herded ten boxes onto one dxFeed
      node (129.153.134.53), which refused new sessions, and from 14:19 ET answered 502; the AWS nodes refused after
      ~4-6 boxes each. OTV5 r70 (FEED.13) spreads boxes by a symbol hash on each box; this lets control, which probes
      every node from outside (tools/dxlink_probe.py), do the spreading with one view of the whole fleet.

WHAT IT DOES (one pass; --apply to write, otherwise a dry run that writes nothing):
  1. The nodes: tools/dxlink_probe.py's status file, nodes whose CONFIRMED state is up, probed within STATUS_FRESH_S.
     A stale or absent file is re-probed here, read-only (dxlink_probe.candidates + probe; no status file written).
  2. The boxes: every running fleet box (instance_registry.fleet_members(), fleet.get_fleet - the tagged fleet only),
     read over ssh with READ_SCRIPT: the open-trade count (trades.db ?mode=ro) and the node its candle feed last
     connected on (the candle-feed journal's "connected on dxlink node" line). Nothing is printed from the box but
     those two facts.
  3. The plan (plan(), pure): holding boxes (open > 0, or unknown) first, then the rest, each in symbol order; a box
     already on an up node keeps it while that node is under the cap; otherwise the least-loaded up node (ties in
     node order). cap = ceil(boxes / up nodes), so the fleet is spread as evenly as the nodes allow. With no node up
     nothing is assigned and nothing is written.
  4. --apply: WRITE_SCRIPT writes ~/options-trader/data/dxlink_assign.json on that box (tmp + rename), with the box's
     symbol, today's ET date, the node, written_at and by, and reads it back. OTV5 candle_feed v5.9 reads it at every
     connect (the assigned node first; pre-open only after its own probe answers 101) and, before 09:27 ET, a box
     connected elsewhere switches to it once. One line per box to stdout; one summary line to control's alert router
     (dxlink_probe.enqueue -> control's alert router) when anything was written.

NEVER: a restart, a service stop/start, an instance action, a token, an environment read, or a write outside that one
file. The file is ignored by the box when it is for another day or symbol, older than 12 h or names a non-IPv4 node.

    venv/bin/python tools/dxlink_assign.py            # dry run: the plan, nothing written
    venv/bin/python tools/dxlink_assign.py --apply    # write each running box's assignment

    venv/bin/python tools/dxlink_assign.py --apply --until 09:25    # the morning service: repeat until every box has it

Schedule (tools/dtp-dxlink-assign.{service,timer}, installed by tools/install_dxlink_assign.sh): 09:16 ET weekdays,
after the 09:15 wake, --apply --until 09:25 (v1.1; v1.0 shipped 09:17 --dry-run).
"""
import argparse
import base64
import json
import math
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

__version__ = "1.2"
EVERY_S = 20

ET = ZoneInfo("America/New_York")
STATUS_FRESH_S = 15 * 60
ASSIGN_REL_PATH = "options-trader/data/dxlink_assign.json"
BY = "dtp dxlink_assign v%s" % __version__

READ_SCRIPT = r'''
import json, os, re, sqlite3, subprocess
H = os.path.expanduser("~/options-trader")
out = {"v": 1}
try:
    c = sqlite3.connect("file:" + os.path.join(H, "trades.db") + "?mode=ro", uri=True, timeout=5)
    out["open"] = int(c.execute("SELECT COUNT(*) FROM trades WHERE status='open'").fetchone()[0])
    c.close()
except Exception as e:
    out["open"] = None
try:
    j = subprocess.run(["journalctl", "-u", "candle-feed", "--since", "-12h", "--no-pager", "-q", "-o", "cat"],
                       capture_output=True, text=True, timeout=20).stdout
    m = re.findall(r"connected on dxlink node (\d+\.\d+\.\d+\.\d+)", j)
    out["node"] = m[-1] if m else None
except Exception:
    out["node"] = None
print("ASSIGN_READ " + json.dumps(out))
'''

WRITE_SCRIPT = r'''
import json, os, sys, base64
d = json.loads(base64.b64decode(sys.argv[1]).decode())
p = os.path.expanduser("~/%s")
os.makedirs(os.path.dirname(p), exist_ok=True)
tmp = p + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(d, fh, sort_keys=True)
os.replace(tmp, p)
with open(p, encoding="utf-8") as fh:
    back = json.load(fh)
print("ASSIGN_WROTE " + json.dumps({"ok": back == d, "node": back.get("node"), "symbol": back.get("symbol")}))
''' % ASSIGN_REL_PATH


def _cmd(script, *args):
    b64 = base64.b64encode(script.encode()).decode()
    return "echo %s | base64 -d | python3 - %s" % (b64, " ".join(args))


def _tagged(text, tag):
    for line in (text or "").splitlines():
        if line.startswith(tag + " "):
            try:
                return json.loads(line[len(tag) + 1:])
            except ValueError:
                return None
    return None


# ── the plan (pure) ───────────────────────────────────────────────────────────────────────────────────────
def plan(boxes, nodes, pinned=None):
    """boxes: [{"sym", "open" (int|None), "node" (ip|None)}]; nodes: the up nodes. -> ({sym: node}, cap).

    Holding (open > 0) or unknown (None) boxes first, then flat ones, each in symbol order. A box already on an up
    node keeps it while that node is under the cap; else the least-loaded node (ties in sorted node order).
    v1.1: pinned {sym: node} - boxes already written this morning keep their node and count toward its load first,
    so a later pass never moves a box twice."""
    nodes = sorted(set(n for n in nodes if n))
    if not nodes or not boxes:
        return {}, 0
    cap = int(math.ceil(len(boxes) / float(len(nodes))))
    load = {n: 0 for n in nodes}
    out = {}
    syms = {b["sym"] for b in boxes}
    for sym, n in sorted((pinned or {}).items()):
        if sym in syms and n in load:
            out[sym] = n
            load[n] += 1
    order = sorted((b for b in boxes if b["sym"] not in out),
                   key=lambda b: (0 if (b.get("open") is None or (b.get("open") or 0) > 0) else 1, str(b.get("sym"))))
    for b in order:
        cur = b.get("node")
        if cur in load and load[cur] < cap:
            pick = cur
        else:
            pick = min(nodes, key=lambda n: (load[n], nodes.index(n)))
        out[b["sym"]] = pick
        load[pick] += 1
    return out, cap


def up_nodes(status, now):
    """The confirmed-up nodes of a fresh probe status, else None (stale or absent)."""
    if not status or now - float(status.get("probed_at") or 0) > STATUS_FRESH_S:
        return None
    return sorted(ip for ip, n in (status.get("nodes") or {}).items() if n.get("state") == "up")


def probe_now():
    """A read-only probe of every candidate node (no status file written)."""
    import dxlink_probe as P
    found, _notes = P.candidates(P.load_status())
    return sorted(ip for ip in found if P.probe(ip)["state"] == "up")


def payload(sym, node, now):
    return {"date": datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d"), "symbol": sym, "node": node,
            "written_at": round(now, 3), "by": BY}


# ── the real world ────────────────────────────────────────────────────────────────────────────────────────
def observe(timeout=60):
    import fleet
    import ssh_util
    import instance_registry
    rows = fleet.get_fleet(instance_registry.fleet_members())
    running = [(s, ip) for s, ip, st in rows if st == "running" and ip]
    res = ssh_util.ssh_map(running, _cmd(READ_SCRIPT), timeout=timeout) if running else {}
    boxes = []
    for s, ip in running:
        rc, so, _se = res.get(s, (255, "", ""))
        d = _tagged(so, "ASSIGN_READ") or {}
        boxes.append({"sym": s, "ip": ip, "open": d.get("open"), "node": d.get("node"), "read": bool(d)})
    return boxes


def write(box, node, now, ssh_run=None):
    if ssh_run is None:
        import ssh_util
        ssh_run = ssh_util.ssh_run
    d = payload(box["sym"], node, now)
    rc, so, _se = ssh_run(box["ip"], _cmd(WRITE_SCRIPT, base64.b64encode(json.dumps(d).encode()).decode()),
                          timeout=30)
    back = _tagged(so, "ASSIGN_WROTE") or {}
    return bool(rc == 0 and back.get("ok") and back.get("node") == node and back.get("symbol") == box["sym"])


def resolve_nodes(status=None, now=None):
    now = now or time.time()
    if status is None:
        import dxlink_probe as P
        status = P.load_status()
    nodes = up_nodes(status, now)
    if nodes is None:
        print("[assign] probe status stale or absent - probing now (read-only)")
        nodes = probe_now()
    return nodes


def run(apply=False, now=None, boxes=None, status=None, nodes=None, ssh_run=None, enqueue=None, done=None):
    """One pass. done: {sym: node} already written this morning (v1.1) - those boxes are planned at that node (so
    they keep it) and not written again."""
    now = now or time.time()
    done = done or {}
    if nodes is None:
        nodes = resolve_nodes(status, now)
    boxes = observe() if boxes is None else boxes
    picks, cap = plan(boxes, nodes, pinned=done)
    if not picks:
        print("[assign] nothing to assign (%d up node(s), %d running box(es)) - nothing written"
              % (len(nodes), len(boxes)))
        return 0, picks, []
    wrote = []
    for b in sorted(boxes, key=lambda x: x["sym"]):
        n = picks[b["sym"]]
        if b["sym"] in done and done[b["sym"]] == n:
            continue
        tag = "keeps" if b.get("node") == n else "moves from %s" % (b.get("node") or "unknown")
        if apply:
            ok = write(b, n, now, ssh_run=ssh_run)
            if ok:
                wrote.append(b["sym"])
            print("[assign] %-6s -> %-16s (%s; open=%s) %s" % (b["sym"], n, tag, b.get("open"),
                                                               "written" if ok else "WRITE FAILED"))
        else:
            print("[assign] %-6s -> %-16s (%s; open=%s) DRY RUN" % (b["sym"], n, tag, b.get("open")))
    per = {n: sum(1 for v in picks.values() if v == n) for n in sorted(set(picks.values()))}
    line = ("DXLINK ASSIGNMENT %s | %d box(es) over %d node(s), cap %d: %s"
            % ("written" if apply else "planned (dry run)", len(picks), len(nodes), cap,
               ", ".join("%s x%d" % kv for kv in per.items())))
    print("[assign] " + line)
    if apply and wrote and enqueue is not False:
        if enqueue is None:
            import dxlink_probe
            enqueue = dxlink_probe.enqueue
        enqueue(line, source="dxlink_assign")
    return 0, picks, wrote


def _hm_epoch(hm, now):
    h, m = (int(x) for x in hm.split(":"))
    d = datetime.fromtimestamp(now, ET)
    return d.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def run_window(apply=True, until="09:25", every=EVERY_S, clock=time.time, sleep=time.sleep, observe_fn=None,
               ssh_run=None, enqueue=None, status=None, nodes=None, expected=None):
    """v1.1 — repeat run() every `every` s until every running fleet box (and every `expected` symbol, the tagged
    fleet) has today's file, or the `until` ET deadline. The nodes are resolved once. One outbox line at the end."""
    observe_fn = observe_fn or observe
    start = clock()
    deadline = _hm_epoch(until, start)
    if nodes is None:
        nodes = resolve_nodes(status, start)
    if expected is None:
        try:
            import instance_registry
            expected = sorted(instance_registry.fleet_members())
        except Exception:                                                   # noqa: BLE001
            expected = None
    done, passes, picks = {}, 0, {}
    while True:
        passes += 1
        boxes = observe_fn()
        _rc, picks, wrote = run(apply=apply, now=clock(), boxes=boxes, nodes=nodes, ssh_run=ssh_run,
                                enqueue=False, done=done)
        for s in wrote:
            done[s] = picks[s]
        want = set(expected or []) | {b["sym"] for b in boxes}
        missing = sorted(want - set(done)) if apply else []
        if not apply or not nodes or not missing or clock() + every > deadline:
            break
        print("[assign] pass %d: %d written, waiting on %s - next pass in %ds" % (passes, len(done),
                                                                                  " ".join(missing), every))
        sleep(every)
    per = {n: sum(1 for v in done.values() if v == n) for n in sorted(set(done.values()))}
    want = set(expected or []) | set(picks)
    missing = sorted(want - set(done)) if apply else []
    line = ("DXLINK ASSIGNMENT %s %d/%d box(es) over %d node(s) in %d pass(es): %s%s"
            % ("written" if apply else "planned (dry run, nothing written)", len(done), len(want), len(nodes or []),
               passes, ", ".join("%s x%d" % kv for kv in per.items()) or "-",
               (" | NOT WRITTEN by %s: %s" % (until, " ".join(missing))) if missing else ""))
    print("[assign] " + line)
    if apply and done and enqueue is not False:
        if enqueue is None:
            import dxlink_probe
            enqueue = dxlink_probe.enqueue
        enqueue(line, source="dxlink_assign")
    return (0 if not missing else 1), done, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description="control-assigned dxlink node per box (FEED.15)")
    ap.add_argument("--apply", action="store_true", help="write each running box's assignment (default: dry run)")
    ap.add_argument("--dry-run", action="store_true", help="the default; print the plan, write nothing")
    ap.add_argument("--until", metavar="HH:MM", help="v1.1: repeat the pass until every box has its file or this ET "
                                                     "time (the morning service: --apply --until 09:25)")
    ap.add_argument("--every", type=int, default=EVERY_S, help="seconds between passes with --until (20)")
    a = ap.parse_args(argv)
    apply = a.apply and not a.dry_run
    if a.until:
        import market_calendar
        if not market_calendar.is_trading_day():
            print("[assign] not a trading day - nothing to assign")
            return 0
        return run_window(apply=apply, until=a.until, every=a.every)[0]
    return run(apply=apply)[0]


if __name__ == "__main__":
    sys.exit(main())
