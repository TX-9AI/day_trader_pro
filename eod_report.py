# day_trader_pro/eod_report.py — v0.3
# v0.3 (2026-09-05) — dtp r287 / TZ.1 — the naive `today` here asked a UTC box and rolled at 20:00 ET
#   (19:00 in winter), so anything run after that silently asked for TOMORROW and came
#   back empty. It now goes through `ettime`, the one ET/UTC boundary.
"""
v0.2 — 2026-08-13 — WH.4: THE TRADED BOXES ARE VERIFIED BEFORE THEY GO DARK.
       These are the boxes holding chains, the signal journal, shadow and
       trades — far more, and far less recoverable, than the sat-out boxes'
       candles. Each is asked to prove it filled the warehouse (box-side
       `s3_push.py --verify`, one line) immediately before the stop. The stop
       is NOT blocked on it: a stopped box's data is stranded until its next
       wake, not lost, whereas a box left running past EOD is its own problem.
       Any box that cannot confirm is named in the Telegram warnings, so a
       silent gap becomes a visible one.

End-of-day aggregator, run on the control server (~15:55 ET) on a systemd
timer, AFTER every bot has flattened (15:45) and written its P&L (15:50).

Flow:
  0. Master switch — if control is DISABLED, no-op.
  1. Scan the environment: every RUNNING box tagged Project=day_trader.
     No manifest, no ownership tracking — whatever is up gets captured and
     swept, including boxes you hand-started mid-day.
  2. SSH-pull each box's ~/eod/pnl_today.json (private IP, keyed).
  3. Aggregate into ONE message: per-symbol P&L + net + orphan/missing flags.
  4. Stop every running box (orderly stop, never terminate).
  5. Send the single unified message: P&L rollup + "N/N stopped".

Because bots are 0DTE-flat by 15:45, the 15:55 pull is always final — no
risk of reading mid-trade numbers.

CLI:
  python eod_report.py --mock       # offline demo (fake fleet + fake P&L)
  python eod_report.py --dry-run     # real pull, but do NOT stop boxes
"""

import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import control_state
import ec2ops
import instance_registry
import notify
import ssh_util
import ettime                                            # noqa: E402

_ET = ZoneInfo("US/Eastern")


def _today_et():
    return ettime.today_et()


# --------------------------------------------------------------------------
# Pull one box's P&L file
# --------------------------------------------------------------------------
def _ssh_pull(ip):
    """Return (data_dict, error_str). data_dict is None on failure."""
    rc, out, err = ssh_util.ssh_run(ip, f"cat ~/{config.EOD_REMOTE_PNL_PATH}")
    if rc != 0:
        return None, (err.strip().splitlines() or ["ssh failed"])[-1][:100]
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        return None, "bad/empty P&L file"


def _mock_pull(symbol):
    """Deterministic fake P&L so the unified message can be previewed offline."""
    h = abs(hash(symbol))
    net = round(((h % 400) - 150) + (h % 100) / 100.0, 2)
    n = h % 9
    wins = n * (1 if net >= 0 else 0)
    return {
        "date_et": _today_et(), "instrument": symbol, "paper": True,
        "n_trades": n, "wins": min(wins, n), "losses": n - min(wins, n),
        "gross_pnl": net, "fees": 0.0, "fees_tracked": False, "net_pnl": net,
        "best": round(abs(net) / 2, 2), "worst": -round(abs(net) / 3, 2),
        "orphans": 1 if symbol.endswith("U") else 0, "note": "",
    }, None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def run(dry_run=False):
    if not control_state.is_enabled():
        print("Control is DISABLED — EOD report no-op. "
              "(you manage shutdown yourself in deco mode)")
        return 0

    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r for s, r in mapping.items() if r.get("state") == "running"}

    if not running:
        notify.send("*day_trader_pro — EOD*\nNo tagged boxes running. "
                    "Nothing to pull or stop.")
        print("Nothing running.")
        return 0

    today = _today_et()
    rows = []          # (symbol, net, n_trades, flag)  flag: ok|missing|stale|error
    warnings = []
    total_net = 0.0
    total_trades = 0

    for sym in sorted(running):
        rec = running[sym]
        ip = rec.get("private_ip") or ""
        if config.MOCK_AWS:
            data, err = _mock_pull(sym)
        elif not ip:
            data, err = None, "no private IP"
        else:
            data, err = _ssh_pull(ip)

        if data is None:
            rows.append((sym, None, 0, "missing"))
            warnings.append(f"⚠️ {sym}: P&L missing ({err})")
            continue

        if data.get("date_et") != today:
            rows.append((sym, None, 0, "stale"))
            warnings.append(f"⚠️ {sym}: P&L file stale "
                            f"(dated {data.get('date_et')}, box may have crashed)")
            continue

        net = float(data.get("net_pnl", 0.0))
        n = int(data.get("n_trades", 0))
        total_net += net
        total_trades += n
        rows.append((sym, net, n, "ok"))
        if int(data.get("orphans", 0)) > 0:
            warnings.append(f"⚠️ {sym}: {data['orphans']} orphan(s) flagged — check box.")

    # --- Prove the warehouse is filled BEFORE the lights go out ----------
    # Chains are not reconstructible after the session; a box stopped with an
    # undrained archive keeps it until its next wake, which may be weeks.
    if not dry_run:
        for sym, rec in sorted(running.items()):
            ip = rec.get("private_ip", "")
            if not ip:
                continue
            cmd = ("/usr/bin/python3 ~/options-trader/warehouse/s3_push.py "
                   "--verify 2>&1 | tail -3")
            try:
                _, so, se = ssh_util.ssh_run(ip, cmd, timeout=300)
                line = ((so or se or "").strip().splitlines() or [""])[0]
            except Exception as exc:
                line = f"(verify raised: {exc})"
            if " OK" in line:
                print(f"[DRAIN] {sym} OK")
            else:
                print(f"[DRAIN] {sym} SHORT: {line}")
                warnings.append(
                    f"⚠️ {sym}: warehouse NOT confirmed before stop — "
                    f"data stranded on box until its next wake.")

    # --- Stop every running box (unless dry run) -------------------------
    ids = [r["instance_id"] for r in running.values()]
    if dry_run:
        stopped_ok = {i: True for i in ids}
        print(f"[DRY-RUN] would stop {len(ids)}: {sorted(running)}")
    else:
        ec2ops.stop(ids)
        stopped_ok = ec2ops.wait_state(ids, "stopped")
    n_stopped = sum(1 for ok in stopped_ok.values() if ok)

    notify.send(_format(today, rows, warnings, total_net, total_trades,
                        n_stopped, len(ids), dry_run))
    # Non-zero exit if any box failed to stop, so a wrapping timer can alert.
    return 0 if n_stopped == len(ids) else 1


def _money(v):
    return f"{'+' if v >= 0 else '-'}${abs(v):.2f}"


def _format(today, rows, warnings, total_net, total_trades,
            n_stopped, n_total, dry_run):
    lines = [f"*VERTIGO EOD — {datetime.now(_ET).strftime('%a %b %d')}*"]
    if dry_run:
        lines.append("_(dry run — nothing was actually stopped)_")
    for sym, net, n, flag in rows:
        if flag == "ok":
            lines.append(f"`{sym:<5}` {_money(net):>10}  ({n}t)")
        else:
            lines.append(f"`{sym:<5}` {'—':>10}  ({flag})")
    lines.append("──────────────")
    reporting = sum(1 for _, _, _, f in rows if f == "ok")
    lines.append(f"*Net: {_money(total_net)}*  ({reporting} boxes · {total_trades} trades)")
    for w in warnings:
        lines.append(w)
    verb = "would stop" if dry_run else "stopped"
    seal = " ✅" if n_stopped == n_total else " 🚨"
    lines.append(f"🔴 {n_stopped}/{n_total} servers {verb}{seal}")
    return "\n".join(lines)


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro EOD aggregator")
    p.add_argument("--mock", action="store_true", help="offline demo")
    p.add_argument("--dry-run", action="store_true",
                   help="real pull, but do not stop boxes")
    args = p.parse_args(argv[1:])
    if args.mock:
        config.set_mock(True)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
