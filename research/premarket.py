"""Pre-market brief: yesterday's levels, gaps if you give today's opening prices,
and a watchlist of at most 3.

    python -m research.premarket
    python -m research.premarket --open INFY=1502.5 SBIN=801

NSE does not show a real open before 9:15. Around 9:08 the pre-open session shows
an indicative price: type it in with --open to get gaps. Without it you only get levels.
"""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from gatekeeper import load_rules
from research.common import IST, days, load_all


def levels(df, before_date):
    """High, low and close of the latest full day before `before_date`."""
    previous = [(d, g) for d, g in days(df) if d < before_date]
    if not previous:
        return None
    d, g = previous[-1]
    high, low, close = float(g["high"].max()), float(g["low"].min()), float(g["close"].iloc[-1])
    return {"date": d, "high": high, "low": low, "close": close, "range_pct": round((high - low) / close * 100, 2)}


def build_brief(data, opens, today, limit=3):
    rows = []
    for sym, df in data.items():
        lv = levels(df, today)
        if lv is None:
            continue
        lv["symbol"] = sym
        lv["gap_pct"] = round((opens[sym] / lv["close"] - 1) * 100, 2) if sym in opens else None
        rows.append(lv)
    key = (lambda r: abs(r["gap_pct"]) if r["gap_pct"] is not None else -1) if opens else (lambda r: r["range_pct"])
    rows.sort(key=key, reverse=True)
    return rows, [r["symbol"] for r in rows[:limit]]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--open", nargs="*", default=[], help="SYMBOL=price pairs")
    args = p.parse_args(argv)
    opens = {k.upper(): float(v) for k, v in (x.split("=") for x in args.open)}
    data = load_all()
    if not data:
        print("No CSV files in data/. Run: python -m research.fetch_data INFY SBIN ITC")
        return 1
    today = datetime.now(ZoneInfo(IST)).strftime("%Y-%m-%d")
    rows, watch = build_brief(data, opens, today, load_rules()["watchlist_max"])
    print(f"Pre-market brief for {today}")
    for r in rows:
        gap = f"gap {r['gap_pct']:+}%" if r["gap_pct"] is not None else "gap n/a"
        print(f"{r['symbol']:<10} prev close {r['close']:<9} high {r['high']:<9} low {r['low']:<9} range {r['range_pct']}%  {gap}")
    how = "largest gaps" if opens else "widest previous-day range"
    print(f"Watchlist (at most 3, ranked by {how}): {', '.join(watch) if watch else 'none'}")
    print("Copy these into the Morning tab on your phone. Ranking is a learning heuristic, not advice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
