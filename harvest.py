# day_trader_pro/harvest.py — v0.6.3
# v0.6.3 — 2026-08-05 — TRIM THE PULLED trades.db TO ONE TRADING DAY.
#   The box DB is cumulative by design; the fault was copying the whole file
#   into a DATED folder, so every dated artifact contained all history. Reading
#   22 dated folders read the same trades 22 times. 2026-08-05: 76% of all rows
#   read by conditional_tables were duplicates, and the inflated n made every
#   Wilson interval ~1.7x too narrow. Trim runs on OUR COPY only — the box's
#   own record, which position reconciliation and the daily-loss halt depend
#   on, is never touched.
# v0.6.2 — 2026-07-30 — TWO CHANGES.
#   (a) backharvest() takes `artifacts=(...)` so a caller can pull ONLY what is
#       missing. The conductor's gap recovery passes ("journal","chains"): OHLC
#       has never had a gap, and re-pulling 29 candle files per date rewrites
#       mtimes on correct data for nothing — which is what the 07-29 recovery
#       did, and the user rightly objected.
#   (b) --date now ACCEPTS today (this was v0.6.1, built 07-29 and never landed).
#       v0.6.0 rejected it as "use run() for a live session", which was wrong on
#       the first real use: the day's EOD had already collected no journal and no
#       chains, so today WAS the date needing recovery.
# v0.6.0 — 2026-07-29 — THE MISSING mkdir (root cause), honest pull states, and
#   --date back-harvest.
#   ROOT CAUSE FIXED: scp does not create its destination directory, and run()
#   only ever mkdir'd ohlc_dir/trades_dir/REPORTS_DIR. v0.5.0 added
#   BASE_DIR/signal_journal/<date>/ and v0.5.1 added
#   BASE_DIR/chain_snapshots/<date>/ as destinations WITHOUT adding the matching
#   os.makedirs, so every journal and chain pull failed with "No such file or
#   directory" from 2026-07-27 onward while harvest reported a clean run. Both
#   roots are now created before the pull.
#   WHY IT WENT UNSEEN FOR THREE SESSIONS: both pulls discarded their return
#   value ("absence is normal"), making a FAILED pull and a genuinely absent file
#   indistinguishable. Now classified three ways -- ok / absent / failed -- and
#   reported per box in a `manifest` block on daily_trades, so the conductor can
#   page on `failed` alone without crying wolf over quiet days.
#   NEW --date YYYY-MM-DD: recovers a PAST session's date-addressed artifacts
#   (OHLC, journal, chains) and deliberately nothing else -- trades_today.json is
#   always the current day and trades.db is cumulative, so re-pulling either for
#   a past date would corrupt a correct snapshot. Writes
#   reports/backharvest_<date>.json.
# v0.5.1 — 2026-07-27 — also pull data/chain_snapshots/<date>/<SYM>.jsonl.gz
#   into BASE_DIR/chain_snapshots/<date>/ (P5 step 1: chains are unrecoverable
#   after 16:00 and previously existed only box-local). Lands exactly where
#   chain_reconstruction_check.py already looks (~/day_trader_pro/chain_snapshots).
# v0.5.0 — 2026-07-27 — also pull data/signal_journal/<date>/<SYM>.jsonl into
#   BASE_DIR/signal_journal/<date>/ (closes the 07-18 journal-harvest deferral;
#   conductor phases 8+9 consume it). Best-effort per box, absence is normal.
# v0.4.1 — 2026-07-23 — correct stale data/harvest path references (layout retired; now reports/ + ohlc/ + trades/)
# v0.4.1 — 2026-07-23 — correct stale data/harvest path references (layout retired; now reports/ + ohlc/ + trades/)
# v0.4.0 (2026-07-11) — canonical layout: raw OHLC -> ohlc/<date>/<SYM>_ohlc_<date>.csv,
#   raw trades.db -> trades/<date>/<SYM>_trades_<date>.db, aggregates (daily_trades,
#   fleet_trades) -> reports/ (flat). Replaces the old data/harvest/<date>/ tree so the
#   analysis harness reads the same tape we collect. Paths come from config.*.
"""
Trade-anatomy + raw-artifact harvester. Runs on the control server AFTER each bot
has written trades_today.json (15:50) and the per-box candle-logger has written
its full-session OHLC (16:05), and BEFORE the EOD sweep stops the fleet (16:15).
Scheduled at 16:10 ET (dtp-harvest.timer).

It is the fleet's single forensic collector (pure read — it never stops a box):

  1. Trade anatomy — SSH-pull every running box's ~/eod/trades_today.json and fold
     it into ONE analysis file, daily_trades_<date>.json (fleet stats, by_setup /
     by_grade, morning selection). This is the file you hand to Claude.
  2. Raw OHLC — scp each box's full-session 1-min CSV
     (options-trader/data/OHLC/<date>/<SYM>.csv).
  3. Raw trades.db — WAL-checkpoint then scp each box's SQLite ground-truth db.

Everything for a day lands in the consolidated roots (data/harvest RETIRED):
     daily_trades_<date>.json
     <SYM>_OHLC_<date>.csv
     <SYM>_trades_<date>.db
Raw per-box files carry BOTH symbol and date, so 29 boxes never collide.

Every box is PINGED first; unreachable boxes are skipped and reported, never block
the others. trades.db is safe to copy here — bots flatten at 15:45, so it is
quiescent by 16:10, and the checkpoint folds the WAL into the main file.

CLI:
  python harvest.py            # pull anatomy + raw OHLC + raw trades.db + Telegram note
  python harvest.py --quiet     # no Telegram
  python harvest.py --mock       # offline demo (fake fleet, placeholder raw files)

Changelog:
  v0.3.0 (2026-07-10) — after the sweep, auto-runs consolidate_trades to merge the
    pulled per-box trades.db into ONE full-fidelity fleet_trades_<date>.json (+ .csv)
    — the single deliverable for the trades-analysis thread. Never fatal to harvest.
  v0.2.0 (2026-07-10) — added the raw sweep (OHLC CSV + trades.db) with a ping-first
    gate and symbol+date filenames; consolidated all of a day's artifacts (incl. the
    daily_trades JSON, now landing flat in reports/). Paired
    with dtp-harvest.timer moving 15:55 -> 16:10 so the 16:05 OHLC exists to collect.
  v0.1.0 — trade-anatomy JSON aggregation only.
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import consolidate_trades
import instance_registry
import notify
import ssh_util

_ET = ZoneInfo("US/Eastern")
SELECTION_LOG = os.path.join(config.DATA_DIR, "selection_log.jsonl")

# Repo dir on each bot box (relative to the box's home — resolves under scp too).
REMOTE_REPO = "options-trader"


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _pull(ip):
    rc, out, err = ssh_util.ssh_run(ip, "cat ~/eod/trades_today.json")
    if rc != 0:
        return None, (err.strip().splitlines() or ["ssh failed"])[-1][:100]
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        return None, "bad/empty trades file"


def _ping(ip):
    """True if the box answers a keyed SSH echo."""
    rc, _out, _err = ssh_util.ssh_run(ip, "echo OK")
    return rc == 0


def _classify_pull(result, local_path):
    """v0.6.0 — turn an scp result into one of three HONEST states.

    v0.5.0/v0.5.1 discarded the return value of the journal and chain pulls
    entirely, on the reasoning that "many boxes have quiet days; absence is
    normal". True — but it made a FAILED pull and a NONEXISTENT file
    indistinguishable, and that is exactly how a missing os.makedirs went
    unnoticed for three sessions: every one of those pulls was failing with
    "No such file or directory" (the LOCAL directory, which nothing created)
    while harvest reported a clean run.

      "ok"      — file landed, non-empty
      "absent"  — box answered, file genuinely not there (a quiet day: NORMAL)
      "failed"  — anything else: permissions, timeout, missing local dir,
                  truncated transfer. This is the state that must be LOUD.
    """
    rc, _out, err = result
    if rc == 0 and os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return "ok"
    blob = (err or "").lower()
    if "no such file or directory" in blob or "not found" in blob:
        return "absent"
    return "failed"


def _pull_raw(ip, sym, today):
    """Pull this box's OHLC CSV -> ohlc/<date>/ and (WAL-checkpointed) trades.db ->
    trades/<date>/, with symbol+date names. Returns (ohlc_ok, db_ok)."""
    ohlc_ok = db_ok = False

    remote_csv = f"{REMOTE_REPO}/data/OHLC/{today}/{sym}.csv"
    local_csv = os.path.join(config.OHLC_DIR, today, f"{sym}_ohlc_{today}.csv")
    rc, _out, _err = ssh_util.scp_pull(ip, remote_csv, local_csv)
    ohlc_ok = rc == 0 and os.path.exists(local_csv) and os.path.getsize(local_csv) > 0

    # Checkpoint the WAL into the main db so the copy is a complete snapshot
    # (best-effort — bots are flat by now, so this is quiescent).
    ssh_util.ssh_run(
        ip, f"sqlite3 ~/{REMOTE_REPO}/trades.db 'PRAGMA wal_checkpoint(TRUNCATE);' 2>/dev/null || true")
    remote_db = f"{REMOTE_REPO}/trades.db"
    local_db = os.path.join(config.TRADES_DIR, today, f"{sym}_trades_{today}.db")
    rc, _out, _err = ssh_util.scp_pull(ip, remote_db, local_db)
    db_ok = rc == 0 and os.path.exists(local_db) and os.path.getsize(local_db) > 0

    # v0.6.3 — TRIM THE COPY TO ONE TRADING DAY.
    # The box's trades.db is CUMULATIVE and correctly so: it is the bot's own
    # working record (position reconciliation across restarts, the daily-loss
    # halt, the circuit breaker). Nothing on the box appends old sessions.
    # What was wrong is HERE: this copied the whole growing file into a DATED
    # folder, so the date in the path meant "when it was pulled", not "what is
    # inside". Reading 22 folders read the same trades 22 times.
    # Measured 2026-08-05: 2,502 of 3,298 rows (76%) were duplicates, and the
    # inflated n made every Wilson interval ~1.7x too narrow — the ORB grade
    # A/B split read as decisive and dissolved once de-duplicated.
    # The trim runs on OUR COPY, never on the box, so the bot's record is
    # untouched. Best-effort: a failure leaves the full copy, which is the old
    # behaviour and still readable.
    if db_ok:
        try:
            _con = sqlite3.connect(local_db)
            _before = _con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            _con.execute("DELETE FROM trades WHERE entry_time IS NULL "
                         "OR substr(entry_time,1,10) <> ?", (today,))
            _con.commit()
            _after = _con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            _con.execute("VACUUM")
            _con.close()
            if _before != _after:
                print(f"    {sym}: trimmed trades.db copy {_before} -> {_after} "
                    f"row(s) for {today}")
        except Exception as exc:                                 # noqa: BLE001
            print(f"    {sym}: trades.db trim skipped ({type(exc).__name__}: "
                f"{exc}) — full copy kept")

    # v0.5.0: signal journal (scored/disposition/readiness rows). Lands under
    # BASE_DIR/signal_journal/<date>/<SYM>.jsonl — EXACTLY where conductor
    # phase 8 (--journal-root) and phase 9 (readiness digest) already look, so
    # pulling it here lights both up with no other change. Best-effort: many
    # boxes have quiet days with no file; absence is normal, never a failure.
    remote_j = f"{REMOTE_REPO}/data/signal_journal/{today}/{sym}.jsonl"
    local_j = os.path.join(config.BASE_DIR, "signal_journal", today, f"{sym}.jsonl")
    os.makedirs(os.path.dirname(local_j), exist_ok=True)     # v0.6.0 — scp does NOT mkdir
    j_state = _classify_pull(ssh_util.scp_pull(ip, remote_j, local_j), local_j)

    # v0.5.1: chain snapshots (P5 step 1 — the TIME-CRITICAL one). The full
    # 0DTE chain archive (main v4.2) is the single dataset in the system that
    # CANNOT be reconstructed after 16:00; until tonight it lived only on the
    # box that wrote it, so any rebuilt box lost that symbol's history
    # permanently. ~1.4MB/box/day gzipped. Best-effort like the journal.
    remote_c = f"{REMOTE_REPO}/data/chain_snapshots/{today}/{sym}.jsonl.gz"
    local_c = os.path.join(config.BASE_DIR, "chain_snapshots", today,
                           f"{sym}.jsonl.gz")
    os.makedirs(os.path.dirname(local_c), exist_ok=True)     # v0.6.0 — scp does NOT mkdir
    c_state = _classify_pull(ssh_util.scp_pull(ip, remote_c, local_c), local_c)

    return ohlc_ok, db_ok, j_state, c_state


def _mock_pull(sym):
    h = abs(hash(sym))
    n = h % 5
    trades = []
    for i in range(n):
        pnl = round(((h >> i) % 300) - 120 + i * 3.5, 2)
        trades.append({
            "trade_id": f"{sym}-{i}", "status": "closed",
            "setup_type": ["ORB", "IronCondor", "Butterfly", "SweepRev"][(h + i) % 4],
            "setup_grade": ["A", "B", "C"][(h + i) % 3],
            "option_side": "call" if (h + i) % 2 else "put",
            "contracts": 1 + (h + i) % 4, "pnl_usd": pnl,
            "exit_reason": ["target", "stop", "trail_stop", "eod"][(h + i) % 4],
        })
    return {"date_et": _today_et(), "instrument": sym, "paper": True,
            "trades": trades, "open_positions": []}, None


def _load_selection():
    """Most recent selection-log entry for today (what Claude picked)."""
    try:
        today = _today_et()
        latest = None
        with open(SELECTION_LOG) as fh:
            for line in fh:
                e = json.loads(line)
                if e.get("ts_utc", "").startswith(today) or True:
                    latest = e  # keep last; today filter is soft
        return latest
    except Exception:  # noqa: BLE001
        return None


def _stats(all_trades):
    def num(t):
        try:
            return float(t.get("pnl_usd") or 0)
        except (TypeError, ValueError):
            return 0.0
    pnls = [num(t) for t in all_trades]
    wins = [p for p in pnls if p > 0]
    by_setup = defaultdict(lambda: {"n": 0, "net": 0.0})
    by_grade = defaultdict(lambda: {"n": 0, "net": 0.0})
    for t in all_trades:
        p = num(t)
        by_setup[t.get("setup_type", "?")]["n"] += 1
        by_setup[t.get("setup_type", "?")]["net"] += p
        by_grade[t.get("setup_grade", "?")]["n"] += 1
        by_grade[t.get("setup_grade", "?")]["net"] += p
    return {
        "n_trades": len(pnls),
        "wins": len(wins),
        "losses": len(pnls) - len(wins),
        "win_rate": round(len(wins) / len(pnls), 3) if pnls else 0.0,
        "net_pnl": round(sum(pnls), 2),
        "best": round(max(pnls), 2) if pnls else 0.0,
        "worst": round(min(pnls), 2) if pnls else 0.0,
        "by_setup": {k: {"n": v["n"], "net": round(v["net"], 2)}
                     for k, v in by_setup.items()},
        "by_grade": {k: {"n": v["n"], "net": round(v["net"], 2)}
                     for k, v in by_grade.items()},
    }


def run(quiet=False):
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r for s, r in mapping.items() if r.get("state") == "running"}
    today = _today_et()
    ohlc_dir = os.path.join(config.OHLC_DIR, today)
    trades_dir = os.path.join(config.TRADES_DIR, today)
    os.makedirs(ohlc_dir, exist_ok=True)
    os.makedirs(trades_dir, exist_ok=True)
    os.makedirs(config.REPORTS_DIR, exist_ok=True)

    per_symbol = {}
    all_trades = []
    missing = []              # trade-anatomy JSON missing (but box reachable)
    unreachable = []          # failed the ping — skipped entirely
    n_ohlc = 0
    n_db = 0
    journal_states = {}       # v0.6.0 — per-box ok/absent/failed, no longer discarded
    chain_states = {}
    pull_failures = []        # only the FAILED state; "absent" is a quiet day
    raw_gaps = []             # per-box notes on which raw artifact didn't come back

    for sym in sorted(running):
        ip = running[sym].get("private_ip", "")

        if config.MOCK_AWS:
            data, _err = _mock_pull(sym)
            # placeholder raw files so the offline demo shows the layout
            open(os.path.join(ohlc_dir, f"{sym}_ohlc_{today}.csv"), "w").write(
                "timestamp,open,high,low,close,volume\n")
            open(os.path.join(trades_dir, f"{sym}_trades_{today}.db"), "wb").write(b"SQLite mock")
            n_ohlc += 1
            n_db += 1
        else:
            if not ip:
                unreachable.append(f"{sym} (no ip)")
                continue
            if not _ping(ip):
                unreachable.append(f"{sym} (ssh)")
                continue
            data, err = _pull(ip)
            if data is None:
                missing.append(f"{sym} ({err})")
            ohlc_ok, db_ok, j_state, c_state = _pull_raw(ip, sym, today)
            n_ohlc += 1 if ohlc_ok else 0
            n_db += 1 if db_ok else 0
            journal_states[sym] = j_state
            chain_states[sym] = c_state
            if j_state == "failed":
                pull_failures.append(f"{sym} journal")
            if c_state == "failed":
                pull_failures.append(f"{sym} chains")
            if not ohlc_ok or not db_ok:
                gap = []
                if not ohlc_ok:
                    gap.append("OHLC")
                if not db_ok:
                    gap.append("trades.db")
                raw_gaps.append(f"{sym}: no {'/'.join(gap)}")
            if data is None:
                continue

        trades = data.get("trades", [])
        for t in trades:
            t["symbol"] = sym          # tag each trade with its box
            all_trades.append(t)
        per_symbol[sym] = {
            "instrument": data.get("instrument", sym),
            "paper": data.get("paper"),
            "n_trades": len(trades),
            "net_pnl": round(sum(float(t.get("pnl_usd") or 0) for t in trades), 2),
            "open_positions": data.get("open_positions", []),
            "trades": trades,
        }

    reachable = len(running) - len(unreachable)

    report = {
        "date_et": today,
        "generated_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "fleet": {
            "running": len(running),
            "reachable": reachable,
            "reporting": len(per_symbol),
            "missing": missing,
            "unreachable": unreachable,
            "raw_pulled": {"ohlc": n_ohlc, "trades_db": n_db, "gaps": raw_gaps},
            # v0.6.0 — completeness manifest. Counts are per STATE so a quiet
            # day (absent) never masquerades as a broken pull (failed), and the
            # conductor can page on `pull_failures` alone.
            "manifest": {
                "journal": {st: sorted(k for k, v in journal_states.items() if v == st)
                            for st in ("ok", "absent", "failed")},
                "chains": {st: sorted(k for k, v in chain_states.items() if v == st)
                           for st in ("ok", "absent", "failed")},
                "pull_failures": sorted(pull_failures),
            },
        },
        "selection": _load_selection(),   # what Claude picked this morning
        "fleet_stats": _stats(all_trades),
        "by_symbol": per_symbol,
        "all_trades": all_trades,         # flat, each tagged with "symbol"
    }

    out = os.path.join(config.REPORTS_DIR, f"daily_trades_{today}.json")
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    os.replace(tmp, out)

    # Consolidate the raw per-box trades.db into the single full-fidelity
    # deliverable for the analysis thread. Non-fatal: the sweep + daily_trades
    # are already saved, so a hiccup here never loses the collected data.
    fleet_json = None
    try:
        _b, fleet_json, _c = consolidate_trades.consolidate(date=today)
    except Exception as exc:  # noqa: BLE001
        print(f"consolidate_trades failed (non-fatal): {exc}")

    st = report["fleet_stats"]
    print(f"harvest {today}: {len(per_symbol)}/{len(running)} boxes reporting, "
          f"{st['n_trades']} trades, net {st['net_pnl']:+.2f}, "
          f"win rate {st['win_rate']:.0%}")
    print(f"raw: OHLC {n_ohlc}/{reachable} -> {ohlc_dir}, trades.db {n_db}/{reachable} -> {trades_dir}")
    print(f"wrote {out}")
    if fleet_json:
        print(f"deliverable: {fleet_json}")
    if unreachable:
        print(f"unreachable: {', '.join(unreachable)}")
    if missing:
        print(f"no trade JSON: {', '.join(missing)}")
    if raw_gaps:
        print(f"raw gaps: {', '.join(raw_gaps)}")

    if not quiet:
        msg = (f"*trade harvest {today}*\n"
               f"{len(per_symbol)}/{len(running)} boxes · {st['n_trades']} trades · "
               f"net {st['net_pnl']:+.2f} · win {st['win_rate']:.0%}\n"
               f"raw: OHLC {n_ohlc}/{reachable} · db {n_db}/{reachable}\n"
               + (f"deliverable: fleet_trades_{today}.json\n" if fleet_json else "")
               + f"saved daily_trades_{today}.json")
        flags = []
        if unreachable:
            flags.append(f"unreachable: {', '.join(unreachable)}")
        if raw_gaps:
            flags.append(f"gaps: {', '.join(raw_gaps)}")
        if missing:
            flags.append(f"no trade JSON: {', '.join(missing)}")
        if flags:
            msg += "\n⚠️ " + " | ".join(flags)
        notify.send(msg)
    return 0


def backharvest(date, quiet=False, artifacts=("ohlc", "journal", "chains")):
    """v0.6.0 — recover DATE-ADDRESSED artifacts for a PAST session.

    WHY THIS IS A SEPARATE FUNCTION AND NOT `run(date=...)`:
    only three artifacts are addressed by date on the box, and only those can be
    re-pulled safely --

        data/OHLC/<date>/<SYM>.csv                 <- date-addressed  OK
        data/signal_journal/<date>/<SYM>.jsonl     <- date-addressed  OK
        data/chain_snapshots/<date>/<SYM>.jsonl.gz <- date-addressed  OK

        ~/eod/trades_today.json    <- ALWAYS the CURRENT day. Re-pulling it for a
                                      past date would fold today's trades into
                                      that date's daily_trades JSON.
        ~/options-trader/trades.db <- cumulative, not date-addressed. Re-pulling
                                      would overwrite a correct past snapshot
                                      with a later state of the same database.

    So a back-harvest NEVER touches trade anatomy, trades.db, the daily_trades
    report, or consolidation. It fills the gap and nothing else.

    Which boxes hold a given date's journal/chains is NOT knowable from the box
    list: the trading cohort is scored and assigned each morning, so it differs
    day to day and is nobody's choice. We therefore ask EVERY running box and let
    the three-state classifier sort it out -- "absent" is the expected answer
    from the majority that did not trade that date. Where that date's
    daily_trades report survives, its by_symbol keys give the set that DID trade,
    which is the only honest yardstick for what we should have got.
    """
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r for s, r in mapping.items() if r.get("state") == "running"}
    if not running:
        print("no boxes are running — wake them first (a stopped box's disk is "
              "intact, but it cannot be read)")
        return None

    expected = None
    rep = os.path.join(config.REPORTS_DIR, f"daily_trades_{date}.json")
    if os.path.exists(rep):
        try:
            with open(rep) as fh:
                expected = sorted(json.load(fh).get("by_symbol", {}).keys())
        except Exception:  # noqa: BLE001
            expected = None

    _names = {"ohlc": "OHLC", "journal": "journal", "chains": "chains"}
    print(f"back-harvest {date} — asking {len(running)} running box(es) for "
          f"{' + '.join(_names[a] for a in artifacts)}")
    if expected:
        print(f"  that session's trading cohort ({len(expected)}): {' '.join(expected)}")
    else:
        print("  no daily_trades report for that date — cannot state the expected "
              "cohort, so treat 'absent' as unproven rather than normal")

    if "journal" in artifacts:
        os.makedirs(os.path.join(config.BASE_DIR, "signal_journal", date), exist_ok=True)
    if "chains" in artifacts:
        os.makedirs(os.path.join(config.BASE_DIR, "chain_snapshots", date), exist_ok=True)
    if "ohlc" in artifacts:
        os.makedirs(os.path.join(config.OHLC_DIR, date), exist_ok=True)

    # v0.6.2 — `artifacts` lets a caller pull ONLY what is missing. The gap
    # recovery in eod_conductor passes ("journal","chains") because OHLC has
    # never had a gap; re-pulling 29 candle files per date rewrites mtimes on
    # correct data for nothing, which is exactly what happened on 2026-07-29.
    j_states, c_states, o_states = {}, {}, {}
    for sym in sorted(running):
        ip = running[sym].get("private_ip", "")
        if not ip or not _ping(ip):
            j_states[sym] = c_states[sym] = o_states[sym] = "failed"
            continue

        if "ohlc" in artifacts:
            lo = os.path.join(config.OHLC_DIR, date, f"{sym}_ohlc_{date}.csv")
            o_states[sym] = _classify_pull(
                ssh_util.scp_pull(ip, f"{REMOTE_REPO}/data/OHLC/{date}/{sym}.csv", lo), lo)

        if "journal" in artifacts:
            lj = os.path.join(config.BASE_DIR, "signal_journal", date, f"{sym}.jsonl")
            j_states[sym] = _classify_pull(
                ssh_util.scp_pull(ip, f"{REMOTE_REPO}/data/signal_journal/{date}/{sym}.jsonl", lj), lj)

        if "chains" in artifacts:
            lc = os.path.join(config.BASE_DIR, "chain_snapshots", date, f"{sym}.jsonl.gz")
            c_states[sym] = _classify_pull(
                ssh_util.scp_pull(ip, f"{REMOTE_REPO}/data/chain_snapshots/{date}/{sym}.jsonl.gz", lc), lc)

    def _grp(d, st):
        return sorted(k for k, v in d.items() if v == st)

    manifest = {
        "date_et": date,
        "mode": "backharvest (date-addressed artifacts only)",
        "generated_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "boxes_asked": sorted(running),
        "expected_cohort": expected,
        "artifacts_requested": list(artifacts),
        "ohlc": {st: _grp(o_states, st) for st in ("ok", "absent", "failed")},
        "journal": {st: _grp(j_states, st) for st in ("ok", "absent", "failed")},
        "chains": {st: _grp(c_states, st) for st in ("ok", "absent", "failed")},
    }

    print("")
    # v0.6.2 — report ONLY what was requested. Printing "ohlc 0/0/0" when OHLC
    # was deliberately not asked for reads as a failed pull; a line that claims
    # work it never attempted is the same class of lie as a green canary on a
    # stale file.
    _panes = [("ohlc", o_states), ("journal", j_states), ("chains", c_states)]
    for label, d in [(l, d) for l, d in _panes if l in artifacts]:
        got, absent, failed = _grp(d, "ok"), _grp(d, "absent"), _grp(d, "failed")
        print(f"  {label:<9} recovered {len(got):>2}   absent {len(absent):>2}   FAILED {len(failed):>2}")
        if failed:
            print(f"            failed: {' '.join(failed)}")
        if expected:
            gap = [x for x in expected if x not in got]
            if gap:
                print(f"            traded that day but nothing recovered: {' '.join(gap)}")

    out = os.path.join(config.REPORTS_DIR, f"backharvest_{date}.json")
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    print(f"\n  manifest -> {out}")

    if not quiet:
        try:
            notify.send(f"\U0001F4E6 back-harvest {date} | "
                        f"journal {len(_grp(j_states, 'ok'))} | "
                        f"chains {len(_grp(c_states, 'ok'))} | "
                        f"failed {len(_grp(j_states, 'failed')) + len(_grp(c_states, 'failed'))}")
        except Exception:  # noqa: BLE001
            pass
    return manifest


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro trade + raw-artifact harvester")
    p.add_argument("--mock", action="store_true", help="offline demo")
    p.add_argument("--quiet", action="store_true", help="no Telegram note")
    p.add_argument("--date", metavar="YYYY-MM-DD",
                   help="BACK-HARVEST a past session: pulls only the "
                        "date-addressed artifacts (OHLC, signal_journal, "
                        "chain_snapshots). Never touches trade anatomy, "
                        "trades.db, daily_trades or consolidation.")
    args = p.parse_args(argv[1:])
    if args.mock:
        config.set_mock(True)
    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"--date must be YYYY-MM-DD, got {args.date!r}")
            return 2
        if args.date == _today_et():
            # v0.6.2 — TODAY IS A LEGITIMATE TARGET. v0.6.0 refused it on the
            # assumption that a live session is always run()'s job. Wrong on the
            # very first real use: the day's EOD had already run and collected NO
            # journal and NO chains, so today was exactly the date needing
            # recovery. Re-running full run() then is the DANGEROUS option — it
            # re-pulls ~/eod/trades_today.json from bots that may have restarted
            # and can overwrite a good daily_trades with an empty one. The
            # artifacts-only path structurally cannot.
            print(f"--date {args.date} is TODAY — artifacts-only path "
                  f"(OHLC + journal + chains). Trade anatomy, trades.db, "
                  f"daily_trades and consolidation are NOT touched; use plain "
                  f"`harvest.py` for a full live-session harvest.")
        return 0 if backharvest(args.date, quiet=args.quiet) is not None else 1
    return run(quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
