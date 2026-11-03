#!/usr/bin/env python3
"""
day_trader_pro/tests/check_alert_router.py  v1.1
v1.1  2026-11-03  FEED.14 R5 (operator "Yes to the proposal"): A14 a connection-triage take-down mutes the box's own
      STOPPED/STARTED - a DN after a stand_down line is taken and never sent while another box's DN in the same
      second is; a DN that arrives BEFORE the action line is muted at its group flush; an UP after a wake is muted,
      one 3 h later is not; a dry-run action line marks nothing; a direct (critical) DN is never muted; the triage
      outbox line is sent once as a Control line and its backlog at first start is not; offsets survive a restart;
      run()'s loop polls the triage files
v1.0  2026-11-02  PAGE.2 — CONTROL'S ALERT ROUTER (alert_router.py v0.1.0) AND THE PAGER'S ACK MODE (pager.py v0.2.0).

No network, no Telegram. The router runs on a fake clock with a fake post(); the stream checks run pager.py's OWN
remote command in a local bash against a temp $HOME (only the ssh hop is replaced), as tests/check_pager.py does.

  A1  grouping: 8 BLIND alerts of one cause inside the hold make ONE message naming all 8; nothing before the hold
  A2  open-position boxes are named first (an ENT-tracked box and a box whose BLIND reports open positions)
  A3  critical / direct: a via=direct alert is never sent by control and not acked; one id taken twice sends once;
      an `[alerted]` drops the queued copy; a direct BLIND member is listed "paged by box"
  A4  pacing: >= MIN_GAP_S between sends, <= PER_MIN in any 60 s, a 429's retry_after holds the queue and the same
      message goes first after it
  A5  recovery: a partial recovery names who is still blind (open first); the last SEE gives "All N boxes see again"
      and closes the episode
  A6  a group of one is the box's own words (BLD and its SEE), as before the router
  A7  the recovery side's hook: post_status("working") inside the hold rides the episode message; after it, it is its
      own "Working on it" line; "recovered" marks boxes back; router_alive() reads health.json
  A8  fallback contract: failing sends past UNHEALTHY_AFTER_S or a stalled loop make healthy() false; an unhealthy
      router takes no routed alert and the pager writes no heartbeat/ack; a too-old routed alert is not taken
  A9  the stream, end to end: an [alert] line in bot.log reaches the router and its id lands in the box's
      ~/.optbot/control_ack; the heartbeat refreshes it; when the stream dies it goes stale; plain pager.py
      (no ack) never writes the file
  A10 no token in any log line, error or spool file (a raising POST carrying the URL, a 401 echoing it)
  A11 an acked alert survives a router restart (spool replay); a delivered one is not replayed
  A12 one router at a time (the lock); no credentials -> run() refuses with 2 unless --dry-run
  A13 under a test runner the real post path captures instead of sending (notify's guard)

BORN RED on dtp 0015ff4: A1 (alert_router.py absent; every later check fails with it)
"""
import io
import json
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
TMP = tempfile.mkdtemp(prefix="check_alert_router-")
LOG = os.path.join(TMP, "options-trader", "bot.log")
ACKF = os.path.join(TMP, ".optbot", "control_ack")
TOKEN = "987654321:FAKE-router-token-check"
T0 = 1793647140.0            # 2026-11-02 14:19:00 ET (EST)


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", "" if ok else detail))
    if not ok:
        FAILS.append(name)


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


class Post:
    def __init__(self, verdicts=None):
        self.sent, self.calls, self.verdicts = [], [], list(verdicts or [])

    def __call__(self, text):
        self.calls.append((CLK.t, text))
        v = self.verdicts.pop(0) if self.verdicts else ("ok", None, "200")
        if v[0] == "ok":
            self.sent.append((CLK.t, text))
        return v


CLK = Clock()
LOGS = []


def mk(post=None, state=None, spool=False):
    import alert_router as ar
    CLK.t = T0
    return ar.Router(post or Post(), state_dir=state or os.path.join(TMP, "state"), clock=CLK,
                     log=LOGS.append, spool=spool)


N = [0]


def rec(box, code="BLD", via="control", **kw):
    N[0] += 1
    r = {"id": "src%s.%d" % (box.lower(), N[0]), "code": code, "ref": kw.pop("ref", ""), "sym": box, "via": via,
         "crit": via == "direct", "ts": CLK.t, "text": kw.pop("text", "%s %s alert" % (box, code))}
    r.update(kw)
    return r


def blind(box, open_n=0, paper=True, via="control"):
    return rec(box, "BLD", via=via, cause="BARS_STALE on 1m", open=open_n, paper=paper, detail="newest_bar=14:18",
               text="\U0001F534 [PAPER] BOT IS BLIND | %s | BARS_STALE on 1m | blind 40s | %s" % (box, "no open"))


def see(box):
    return rec(box, "SEE", cause="BARS_STALE", blind_for_s=300.0,
               text="✅ Sight restored (was BARS_STALE) | %s | was blind 300s" % box)


def run_until(r, t_end, step=0.1):
    while CLK.t < t_end:
        CLK.t = round(CLK.t + step, 3)
        r.tick()


FLEET8 = ["AMD", "AVGO", "GOOGL", "META", "MSFT", "NVDA", "QQQ", "TSLA"]


def main():
    try:
        import alert_router as ar
        import pager
    except Exception as e:                                          # noqa: BLE001
        check("A1", False, "import alert_router raised %s: %s" % (type(e).__name__, e))
        for g in ("A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12", "A13"):
            check(g, False, "no alert_router.py")
        return 1

    # A1 / A2 — the 14:19 storm: 8 boxes inside 40 s; TSLA holds an ENT, AMD's BLIND reports 1 open
    p = Post()
    r = mk(p)
    r.ingest_alert("TSLA", rec("TSLA", "ENT", ref="aaaa1111", text="\U0001F4C8 [PAPER] TSLA CALL 250 x2"))
    run_until(r, T0 + 3)
    entry_sent = len(p.sent)
    for i, box in enumerate(["NVDA", "AVGO", "AMD", "GOOGL", "META", "MSFT", "QQQ", "TSLA"]):
        run_until(r, T0 + 5 + i * 2)
        r.ingest_alert(box, blind(box, open_n=1 if box == "AMD" else 0))
    run_until(r, T0 + 5 + ar.GROUP_HOLD_S - 0.5)
    before = len(p.sent) - entry_sent
    run_until(r, T0 + 5 + ar.GROUP_HOLD_S + 30)
    bl = [t for _, t in p.sent if "BLIND" in t]
    ok1 = before == 0 and len(bl) == 1 and bl[0].startswith("\U0001F534 8 boxes BLIND since 14:19 ET") and \
        all(b in bl[0] for b in FLEET8)
    check("A1", ok1, "before=%d blind_msgs=%r" % (before, bl))
    lines = bl[0].splitlines() if bl else []
    ok2 = len(lines) >= 3 and lines[1].startswith("OPEN POSITIONS: AMD (1 open, paper), TSLA (1 open, paper)") \
        and lines[2] == "Also: AVGO, GOOGL, META, MSFT, NVDA, QQQ"
    check("A2", ok2, "lines=%r" % lines)
    print("      example (A1/A2):\n        " + "\n        ".join(lines))

    # A5 — partial then full recovery (continues A1's router)
    for box in ["NVDA", "AVGO", "GOOGL", "META", "MSFT"]:
        CLK.t += 1
        r.ingest_alert(box, see(box))
    n_before = len(p.sent)
    run_until(r, CLK.t + ar.RECOVERY_HOLD_S + 3)
    rec1 = [t for _, t in p.sent[n_before:]]
    for box in ["AMD", "QQQ", "TSLA"]:
        CLK.t += 1
        r.ingest_alert(box, see(box))
    n2 = len(p.sent)
    run_until(r, CLK.t + ar.RECOVERY_HOLD_S + 3)
    rec2 = [t for _, t in p.sent[n2:]]
    ok5 = (len(rec1) == 1 and rec1[0].startswith("✅ 5 of 8 recovered - BARS_STALE on 1m since 14:19 ET")
           and "STILL BLIND: AMD (1 open, paper), TSLA (1 open, paper), QQQ" in rec1[0]
           and len(rec2) == 1 and rec2[0].startswith("✅ All 8 boxes see again - BARS_STALE on 1m episode since "
                                                     "14:19 ET") and not r.episodes)
    check("A5", ok5, "rec1=%r rec2=%r episodes=%r" % (rec1, rec2, list(r.episodes)))
    print("      example (A5):\n        " + "\n        ".join((rec1 + rec2)[0].splitlines() + (rec1 + rec2)[1:2]))

    # A3 — direct / critical / dedup / alerted
    p = Post()
    r = mk(p)
    hcf = rec("SPX", "HCF", via="direct", text="\U0001F6A8 HARD CLOSE INCOMPLETE | SPX")
    took = r.ingest_alert("SPX", hcf)
    e1 = rec("QQQ", "ENT", ref="bbbb2222", text="QQQ CALL x1")
    a, b = r.ingest_alert("QQQ", e1), r.ingest_alert("QQQ", dict(e1))
    e2 = rec("QQQ", "EXT", ref="bbbb2222", text="QQQ CLOSED pnl=+$12")
    e3 = rec("QQQ", "EXT", ref="cccc3333", text="QQQ CLOSED pnl=-$4")
    r.ingest_alert("QQQ", e2)
    r.ingest_alert("QQQ", e3)
    r.ingest_alerted("QQQ", e3["id"])                               # the box sent this one itself
    run_until(r, T0 + 10)
    texts = [t for _, t in p.sent]
    # a direct BLIND (live open) inside a routed episode
    for box, via, n in (("AMD", "control", 0), ("SPX", "direct", 2), ("NVDA", "control", 0)):
        r.ingest_alert(box, blind(box, open_n=n, paper=via != "direct", via=via))
    run_until(r, CLK.t + ar.GROUP_HOLD_S + 5)
    ep = [t for _, t in p.sent if "BLIND" in t]
    ok3 = (took is False and "HARD CLOSE" not in " ".join(texts) and a is True and b is True
           and texts.count("QQQ CALL x1") == 1 and "QQQ CLOSED pnl=+$12" in texts and "QQQ CLOSED pnl=-$4" not in texts
           and len(ep) == 1 and "SPX (2 open, LIVE, paged by box)" in ep[0])
    check("A3", ok3, "took=%r a=%r b=%r texts=%r ep=%r" % (took, a, b, texts, ep))

    # A4 — pacing and 429
    p = Post(verdicts=[("ok", None, "200")] * 3 + [("retry", 7.0, "429 Too Many Requests")])
    r = mk(p)
    for i in range(40):
        r.ingest_alert("B%02d" % i, rec("B%02d" % i, "ENT", ref="t%04d" % i, text="entry %02d" % i))
    run_until(r, T0 + 200, step=0.05)
    times = [t for t, _ in p.calls]
    gaps = [b_ - a_ for a_, b_ in zip(times, times[1:])]
    maxwin = max(sum(1 for u in times if t <= u < t + 60) for t in times)
    after429 = [(t, x) for t, x in p.calls if t > p.calls[3][0]]
    ok4 = (len(p.sent) == 40 and min(gaps) >= 1.0 - 1e-6 and maxwin <= 20
           and after429 and after429[0][0] - p.calls[3][0] >= 7.0 - 1e-6 and after429[0][1] == p.calls[3][1]
           and [x for _, x in p.sent] == ["entry %02d" % i for i in range(40)])
    check("A4", ok4, "sent=%d min_gap=%.2f max_per_60s=%d after429=%r" % (len(p.sent), min(gaps or [0]), maxwin,
                                                                          after429[:1]))

    # A6 — a group of one
    p = Post()
    r = mk(p)
    one = blind("CVX")
    r.ingest_alert("CVX", one)
    run_until(r, T0 + ar.GROUP_HOLD_S + 2)
    run_until(r, CLK.t + 30)
    s1 = see("CVX")
    r.ingest_alert("CVX", s1)
    run_until(r, CLK.t + ar.RECOVERY_HOLD_S + 2)
    check("A6", [t for _, t in p.sent] == [one["text"], s1["text"]], "sent=%r" % [t for _, t in p.sent])

    # A7 — the recovery side's hook
    state = os.path.join(TMP, "state7")
    p = Post()
    r = mk(p, state=state)
    for box in ("AMD", "AVGO", "GOOGL"):
        r.ingest_alert(box, blind(box))
    ar.post_status("working", "feed 502 on dxlink node 129.153.134.53; restarting the feed on the flat boxes",
                   cause="BARS_STALE", state_dir=state)
    r.poll_outbox()
    run_until(r, T0 + ar.GROUP_HOLD_S + 2)
    first = [t for _, t in p.sent]
    ar.post_status("working", "AVGO feed restarted", boxes=["AVGO"], cause="BARS_STALE", state_dir=state)
    ar.post_status("recovered", "AMD and AVGO back after the feed restart", boxes=["AMD", "AVGO"],
                   cause="BARS_STALE", state_dir=state)
    r.poll_outbox()
    run_until(r, CLK.t + ar.RECOVERY_HOLD_S + 3)
    later = [t for _, t in p.sent][len(first):]
    r.write_health()
    real_now = ar._now
    ar._now = CLK                                                       # router_alive reads health.json's ts
    alive = ar.router_alive(state_dir=state)
    ar._now = real_now
    ok7 = (len(first) == 1 and "Control: feed 502 on dxlink node 129.153.134.53" in first[0]
           and "Control is on it" not in first[0] and len(later) == 2
           and later[0].startswith("\U0001F6E0 Working on it: AVGO feed restarted | cause BARS_STALE | AVGO")
           and later[1].startswith("✅ 2 of 3 recovered") and "STILL BLIND: GOOGL" in later[1]
           and "Control: AMD and AVGO back" in later[1] and alive and not os.listdir(os.path.join(state, "outbox")))
    check("A7", ok7, "first=%r later=%r alive=%r" % (first, later, alive))
    print("      example (A7):\n        " + "\n        ".join(first[0].splitlines() if first else []))

    # A8 — health and the fallback contract
    p = Post(verdicts=[("retry", None, "502 Bad Gateway")] * 500)
    r = mk(p)
    r.ingest_alert("AMD", rec("AMD", "ENT", ref="dddd4444"))
    h0 = r.healthy()
    run_until(r, T0 + ar.UNHEALTHY_AFTER_S + 5, step=0.5)
    h1 = r.healthy()
    refused = r.ingest_alert("NVDA", rec("NVDA", "ENT", ref="eeee5555"))
    direct_still = r.ingest_alert("SPX", rec("SPX", "HCF", via="direct"))

    class _Child:
        def __init__(self):
            self.stdin = io.StringIO()
    pg_ = pager.Pager(out=io.StringIO(), on_alert=r.ingest_alert, ack=True, healthy_fn=r.healthy)
    ch = _Child()
    wrote_unhealthy = pg_.write_ack("NVDA", ch)
    r2 = mk(Post())
    stall = r2.healthy(now=T0 + ar.LOOP_STALL_S + 1)
    CLK.t = T0 + 100
    r2.tick()                                                           # a live loop: only the age refuses it
    old = rec("QQQ", "ENT", ref="ffff6666")
    old["ts"] = CLK.t - ar.ACCEPT_WINDOW_S - 5
    late = r2.ingest_alert("QQQ", old)
    pg_ok = pager.Pager(out=io.StringIO(), on_alert=lambda b, x: True, ack=True)
    ch2 = _Child()
    pg_ok.take_line("AMD", '2026-11-02 19:19:00 [INFO ] notifications.pager: [alert] {"id":"ab12.7","code":"ENT"}',
                    child=ch2)
    ack_txt = ch2.stdin.getvalue()
    ok8 = (h0 and not h1 and refused is False and direct_still is False and wrote_unhealthy is False
           and ch.stdin.getvalue() == "" and stall is False and late is False
           and ack_txt.startswith("HB ") and ack_txt.rstrip().endswith("ab12:7"))
    check("A8", ok8, "h0=%r h1=%r refused=%r unhealthy_write=%r stall=%r late=%r ack=%r"
          % (h0, h1, refused, wrote_unhealthy, stall, late, ack_txt))

    # A9 — the stream end to end
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    open(LOG, "a").close()
    pager.stream_argv = lambda _b, _i, c: ["env", "HOME=%s" % TMP, "bash", "-c", c]
    pager.HB_S = 0.5
    got = []
    pg9 = pager.Pager(out=io.StringIO(), on_alert=lambda b, x: got.append((b, x)) or True, ack=True)
    th = threading.Thread(target=pg9.follow, kwargs={"discover_fn": lambda: {"AMD": "127.0.0.1"}, "rescan_s": 3600},
                          daemon=True)
    th.start()
    wait_for(lambda: "AMD" in pg9.children, 5)
    time.sleep(pager.CATCHUP_DELAY_S + 1.0)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    line = '%s [INFO ] notifications.pager: [alert] {"id":"9f3a1c2b.4","code":"BLD","sym":"AMD","via":"control",' \
           '"ts":%.3f,"text":"BOT IS BLIND"}' % (stamp, time.time())
    with open(LOG, "a") as fh:
        fh.write(line + "\n")
    has_id = wait_for(lambda: os.path.exists(ACKF) and "9f3a1c2b:4" in open(ACKF).read(), 8)
    m1 = os.stat(ACKF).st_mtime if os.path.exists(ACKF) else 0
    time.sleep(1.6)
    m2 = os.stat(ACKF).st_mtime if os.path.exists(ACKF) else 0
    child = pg9.children.get("AMD")
    pg9.shutdown()
    th.join(timeout=10)
    time.sleep(1.5)
    m3 = os.stat(ACKF).st_mtime if os.path.exists(ACKF) else 0
    time.sleep(1.5)
    m4 = os.stat(ACKF).st_mtime if os.path.exists(ACKF) else 0
    # plain mode never writes it
    os.unlink(ACKF) if os.path.exists(ACKF) else None
    pg_plain = pager.Pager(out=io.StringIO())
    th = threading.Thread(target=pg_plain.follow, kwargs={"discover_fn": lambda: {"AMD": "127.0.0.1"},
                                                          "rescan_s": 3600}, daemon=True)
    th.start()
    time.sleep(pager.CATCHUP_DELAY_S + 2.0)
    plain_wrote = os.path.exists(ACKF)
    pg_plain.shutdown()
    th.join(timeout=10)
    ok9 = (has_id and len(got) == 1 and got[0][1]["id"] == "9f3a1c2b.4" and m2 > m1 and m4 == m3
           and child is not None and not plain_wrote)
    check("A9", ok9, "has_id=%r got=%r m1<m2=%r m3==m4=%r plain_wrote=%r" % (has_id, got, m2 > m1, m4 == m3,
                                                                           plain_wrote))

    # A10 — no token anywhere
    import requests
    real_post = requests.post
    state10 = os.path.join(TMP, "state10")
    seen = []

    def raising(url, **kw):
        seen.append(url)
        raise requests.ConnectionError("HTTPSConnectionPool(host='api.telegram.org'): Max retries exceeded with "
                                       "url: %s" % url)

    class _R:
        status_code = 401
        text = '{"ok":false,"description":"Unauthorized bot%s"}' % TOKEN

        def json(self):
            return json.loads(self.text)
    LOGS.clear()
    requests.post = raising
    tp = ar.telegram_post(TOKEN, "42")
    r = mk(tp, state=state10, spool=True)
    r.log = lambda m: LOGS.append(ar.scrub(m, ""))                     # what a logger with no scrub would print
    r.ingest_alert("AMD", rec("AMD", "ENT", ref="gggg7777"))
    run_until(r, T0 + 5)
    requests.post = lambda url, **kw: _R()
    run_until(r, T0 + 20)
    requests.post = real_post
    spool_txt = "".join(open(os.path.join(state10, f)).read() for f in os.listdir(state10) if f.startswith("spool"))
    leaks = [x for x in LOGS if TOKEN in x] + ([spool_txt] if TOKEN in spool_txt else [])
    ok10 = seen and TOKEN in seen[0] and LOGS and not leaks and r.dropped == 1
    check("A10", ok10, "posted=%d logs=%r leaks=%d dropped=%d" % (len(seen), LOGS[-2:], len(leaks), r.dropped))

    # A11 — spool replay
    state11 = os.path.join(TMP, "state11")
    p = Post()
    r = mk(p, state=state11, spool=True)
    kept, sent_ = rec("QQQ", "ENT", ref="hhhh8888", text="kept for replay"), rec("SPX", "ENT", ref="iiii9999",
                                                                               text="already sent")
    r.ingest_alert("SPX", sent_)
    run_until(r, T0 + 2)
    r.ingest_alert("QQQ", kept)                                     # acked, then the router dies before sending
    p2 = Post()
    CLK.t = T0 + 30
    r2 = ar.Router(p2, state_dir=state11, clock=CLK, log=LOGS.append)
    n = r2.replay()
    run_until(r2, CLK.t + 5)
    again = r2.ingest_alert("QQQ", dict(kept))
    run_until(r2, CLK.t + 5)
    ok11 = n == 1 and [t for _, t in p2.sent] == ["kept for replay"] and again is True
    check("A11", ok11, "replayed=%r sent=%r again=%r" % (n, [t for _, t in p2.sent], again))

    # A12 — the lock; no credentials
    import fcntl
    state12 = os.path.join(TMP, "state12")
    os.makedirs(state12, exist_ok=True)
    hold = open(os.path.join(state12, "router.lock"), "w")
    fcntl.flock(hold, fcntl.LOCK_EX | fcntl.LOCK_NB)
    rc_locked = ar.run(dry_run=True, state_dir=state12, discover_fn=lambda: {})
    fcntl.flock(hold, fcntl.LOCK_UN)
    hold.close()
    import config
    saved = {k: os.environ.pop(k, None) for k in (config.ENV_TELEGRAM_TOKEN, config.ENV_TELEGRAM_CHAT)}
    rc_nocred = ar.run(dry_run=False, state_dir=os.path.join(TMP, "state12b"), discover_fn=lambda: {})
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
    check("A12", rc_locked == 3 and rc_nocred == 2, "locked=%r nocred=%r" % (rc_locked, rc_nocred))

    # A14 — FEED.14 R5: triage take-downs
    tdir = os.path.join(TMP, "triage")
    os.makedirs(tdir, exist_ok=True)
    acts, obx = os.path.join(tdir, "actions.jsonl"), os.path.join(tdir, "outbox.jsonl")
    st14 = os.path.join(TMP, "state14")

    def put(path, row):
        with open(path, "a") as fh:
            fh.write(json.dumps(row) + "\n")
    put(obx, {"ts": T0 - 60, "source": "feed_triage", "text": "OLD BACKLOG LINE"})
    p14 = Post()
    r14 = mk(p14, state=st14, spool=True)
    r14.poll_triage(acts, obx)                                  # first start: the outbox backlog is skipped
    put(acts, {"kind": "takedown_intent", "sym": "CCC", "reason": "stopping", "at": T0, "dry": False})
    put(acts, {"kind": "stand_down", "sym": "CCC", "reason": "for SPX", "at": T0 + 2, "dry": False})
    put(acts, {"kind": "stand_down", "sym": "EEE", "reason": "dry", "at": T0, "dry": True})
    put(obx, {"ts": T0 + 2, "source": "feed_triage", "text": "FEED TRIAGE | STOOD DOWN CCC | for SPX"})
    r14.poll_triage(acts, obx)
    CLK.t = T0 + 10
    own_c = r14.ingest_alert("CCC", rec("CCC", "DN", cause="instance stop", text="🔴 CCC STOPPED"))
    r14.ingest_alert("AAA", rec("AAA", "DN", cause="instance stop", text="🔴 AAA STOPPED"))
    r14.ingest_alert("EEE", rec("EEE", "DN", cause="x", text="🔴 EEE STOPPED"))
    r14.ingest_alert("FFF", rec("FFF", "DN", via="direct", cause="x", text="🔴 FFF STOPPED"))
    r14.ingest_alert("DDD", rec("DDD", "DN", cause="instance stop", text="🔴 DDD STOPPED"))
    put(acts, {"kind": "stand_down", "sym": "DDD", "reason": "late line", "at": T0 + 12, "dry": False})
    CLK.t = T0 + 13
    r14.poll_triage(acts, obx)
    run_until(r14, T0 + 60)
    put(acts, {"kind": "wake", "sym": "CCC", "reason": "slot", "at": T0 + 1200, "dry": False})
    CLK.t = T0 + 1201
    r14.poll_triage(acts, obx)
    CLK.t = T0 + 1500
    r14.tick()
    r14.ingest_alert("CCC", rec("CCC", "UP", text="🚀 CCC STARTED"))
    run_until(r14, T0 + 1560)
    CLK.t = T0 + 4 * 3600
    r14.tick()
    r14.ingest_alert("CCC", rec("CCC", "UP", text="🚀 CCC STARTED again"))
    run_until(r14, T0 + 4 * 3600 + 60)
    texts = [t for _ts, t in p14.sent]
    blob = "\n".join(texts)
    muted = sorted((b, c) for b, c, _i in r14.muted)
    r14b = mk(Post(), state=st14, spool=True)
    n_restart = r14b.poll_triage(acts, obx)
    ok14 = (own_c is True and muted == [("CCC", "DN"), ("CCC", "UP"), ("DDD", "DN")]
            and "CCC STOPPED" not in blob and "DDD STOPPED" not in blob and "AAA STOPPED" in blob
            and "EEE STOPPED" in blob and "FFF STOPPED" not in blob and "CCC STARTED again" in blob
            and "CCC STARTED\n" not in blob + "\n" and sum("STOOD DOWN CCC" in t for t in texts) == 1
            and "OLD BACKLOG LINE" not in blob and n_restart == 0)
    import inspect
    ok14 = ok14 and "r.poll_triage()" in inspect.getsource(ar.run)
    check("A14", ok14, "muted=%r sent=%r restart re-read=%r" % (muted, texts, n_restart))

    # A13 — the guard
    import notify
    hits = []
    g = ar._guarded(lambda text: hits.append(text) or ("ok", None, "200"))
    v = g("would page the operator")
    check("A13", v[0] == "ok" and not hits and "would page the operator" in notify.captured(),
          "v=%r hits=%r" % (v, hits))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (14)")
    return 0


def wait_for(fn, timeout=12.0):
    t = time.time()
    while time.time() - t < timeout:
        try:
            if fn():
                return True
        except Exception:                                           # noqa: BLE001
            pass
        time.sleep(0.1)
    return fn()


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        subprocess.run(["pkill", "-f", TMP], capture_output=True)
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(rc)
