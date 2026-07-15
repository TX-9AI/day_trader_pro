#!/usr/bin/env python3
# ohlc_fetch.py — Vertigo Capital data utility
# Pulls 1-minute OHLCV for the last 30 days via yfinance and writes a CSV.
#
# Usage:
#   python3 ohlc_fetch.py                 # prompts for a ticker (default QQQ)
#   python3 ohlc_fetch.py --symbol MU     # scripted, no prompt
#   python3 ohlc_fetch.py -s SPY --prepost --out spy.csv
#
# Why chunked: Yahoo/yfinance limits 1m data to the LAST 30 DAYS, and to a
# MAX 7 DAYS per request. A single 30d/1m call fails. This fetches in 7-day
# windows, stitches them, dedupes the seams, sorts, and normalizes timestamps
# to America/New_York so session times line up with your ORB logic.

import argparse
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ---- Dependency bootstrap (Ubuntu system Python friendly) ----
try:
    import pandas as pd
    import yfinance as yf
except ImportError:
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--quiet",
        "--break-system-packages", "yfinance", "pandas",
    ])
    import pandas as pd
    import yfinance as yf


def parse_args():
    p = argparse.ArgumentParser(description="Pull 1m OHLCV (last 30 days) via yfinance.")
    p.add_argument("-s", "--symbol", help="Ticker (e.g. QQQ, MU). Prompts if omitted.")
    p.add_argument("--days", type=int, default=30, help="Days back (max 30 for 1m).")
    p.add_argument("--interval", default="1m", help="Bar interval (default 1m).")
    p.add_argument("--prepost", action="store_true", help="Include pre/post-market bars.")
    p.add_argument("--out", help="Output CSV path (default <SYMBOL>_1m_30d.csv).")
    return p.parse_args()


def resolve_symbol(arg_symbol):
    sym = arg_symbol
    if not sym:
        try:
            sym = input("Enter ticker symbol [QQQ]: ")
        except EOFError:
            sym = ""
    sym = (sym or "QQQ").upper().strip()
    return sym


def fetch(symbol, interval, days, prepost):
    if days > 30:
        days = 30
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    chunk = timedelta(days=7)  # Yahoo 1m per-request limit
    frames = []
    cur = start
    tk = yf.Ticker(symbol)
    while cur < end:
        c_end = min(cur + chunk, end)
        df = tk.history(start=cur, end=c_end, interval=interval,
                        prepost=prepost, auto_adjust=False, actions=False)
        if df is not None and not df.empty:
            frames.append(df)
        cur = c_end

    if not frames:
        return None

    data = pd.concat(frames)
    data = data[~data.index.duplicated(keep="first")].sort_index()

    # Normalize to US/Eastern so timestamps match the trading session.
    idx = data.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    data.index = idx.tz_convert("America/New_York")
    return data


def main():
    args = parse_args()
    symbol = resolve_symbol(args.symbol)
    outfile = args.out or f"{symbol}_1m_30d.csv"

    print(f"Fetching {args.days}d of {args.interval} {symbol} "
          f"(prepost={args.prepost}) -> {outfile}")

    data = fetch(symbol, args.interval, args.days, args.prepost)
    if data is None:
        print(f"No data returned for '{symbol}'. Check the symbol format, or "
              f"Yahoo may be rate-limiting. (Indices need ^, crypto needs -USD, "
              f"futures need =F.)", file=sys.stderr)
        sys.exit(1)

    out = data[["Open", "High", "Low", "Close", "Volume"]].copy()
    out.columns = ["open", "high", "low", "close", "volume"]
    out.insert(0, "timestamp", out.index.strftime("%Y-%m-%d %H:%M:%S"))
    out.to_csv(outfile, index=False)

    print(f"Wrote {len(out)} rows to {outfile}")
    print(f"Range: {out['timestamp'].iloc[0]} -> {out['timestamp'].iloc[-1]} "
          f"(America/New_York)")


if __name__ == "__main__":
    main()
