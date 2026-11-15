"""Backtest engine. It asks the real gatekeeper before every trade, so the
backtest obeys the same rules as you do.

Honest-testing choices (all visible as arguments):
- Enter on the next candle's open, never on the signal candle.
- If a candle touches both stop and target, assume the STOP hit first.
- A gap through the stop exits at the open (worse than the stop).
- Slippage and full charges are applied to every trade.
- One position at a time. Quantity comes from your per-trade risk limit.
"""
import math

import pandas as pd

from gatekeeper import evaluate, to_min
from research import costs as costs_module
from research.common import days, week_start

CANDLE = 5


def simulate(day, entry_idx, stop, target, exit_minute, slippage=0.0005):
    """Walk candles from the entry candle. Returns (exit_price, exit_minute, reason)."""
    for j in range(entry_idx, len(day)):
        m = day["minute"][j]
        if m >= exit_minute and j > entry_idx:
            return day["open"][j] * (1 - slippage), m, "time"
        lo, hi, op = day["low"][j], day["high"][j], day["open"][j]
        if lo <= stop:
            price = min(op, stop)
            return price * (1 - slippage), m + CANDLE, "stop"
        if hi >= target:
            price = max(op, target)
            return price * (1 - slippage), m + CANDLE, "target"
    last = len(day) - 1
    return day["close"][last] * (1 - slippage), day["minute"][last] + CANDLE, "time"


def _candidate(day, signal, rules, slippage, leverage):
    """Turn a signal into a sized trade, or None if it cannot be sized within the rules."""
    idx = signal["index"] + 1
    entry = float(day["open"][idx]) * (1 + slippage)
    stop = float(signal["stop"])
    per_share = entry - stop
    if per_share <= 0:
        return None
    qty = math.floor(rules["max_loss_per_trade"] / per_share)
    qty = min(qty, math.floor(rules["capital"] * leverage / entry))
    if qty < 1:
        return None
    target = entry + rules["min_reward_risk"] * per_share
    return {"entry_idx": idx, "entry": entry, "stop": stop, "target": target, "qty": qty,
            "entry_minute": int(day["minute"][idx])}


def run_backtest(data, setup, rules, slippage=0.0005, leverage=1.0, costs_fn=None):
    """data = {symbol: candles}. Returns (trades DataFrame, list of blocked trades)."""
    costs_fn = costs_fn or costs_module.round_trip
    exit_minute = to_min(rules["close_all_by"])
    dates = sorted({d for df in data.values() for d in df["date"].unique()})
    history, trades, blocked = [], [], []
    by_day = {sym: {d: g for d, g in days(df)} for sym, df in data.items()}

    for date in dates:
        cands = []
        for sym, per_day in by_day.items():
            day = per_day.get(date)
            if day is None:
                continue
            sig = setup(day, rules)
            if sig is None:
                continue
            c = _candidate(day, sig, rules, slippage, leverage)
            if c:
                cands.append((c["entry_minute"], sym, day, c))
        busy_until = 0
        for entry_minute, sym, day, c in sorted(cands, key=lambda x: (x[0], x[1])):
            if entry_minute < busy_until:
                blocked.append({"date": date, "symbol": sym, "reasons": ["position still open"]})
                continue
            now = {"date": date, "minutes": entry_minute, "weekStart": week_start(date)}
            state = {"morning": {"date": date, "slept": True, "calm": True, "watchlist": []}, "trades": history}
            trade = {"segment": "equity", "side": "buy", "entry": c["entry"], "stop": c["stop"],
                     "target": c["target"], "qty": c["qty"], "paper": False}
            verdict = evaluate(rules, state, trade, now)
            if not verdict["pass"]:
                blocked.append({"date": date, "symbol": sym,
                                "reasons": [r["id"] for r in verdict["results"] if not r["ok"]]})
                continue
            exit_price, exit_at, reason = simulate(day, c["entry_idx"], c["stop"], c["target"], exit_minute, slippage)
            gross = (exit_price - c["entry"]) * c["qty"]
            charges = costs_fn(c["entry"], exit_price, c["qty"])
            pnl = gross - charges
            risk = (c["entry"] - c["stop"]) * c["qty"]
            trades.append({"date": date, "symbol": sym, "entry_minute": entry_minute, "exit_minute": exit_at,
                           "entry": round(c["entry"], 2), "exit": round(exit_price, 2), "stop": c["stop"],
                           "target": round(c["target"], 2), "qty": c["qty"], "risk": round(risk, 2),
                           "gross": round(gross, 2), "charges": round(charges, 2), "pnl": round(pnl, 2),
                           "r": round(pnl / risk, 2), "reason": reason})
            history.append({"date": date, "minutes": exit_at, "pnl": pnl, "paper": False})
            busy_until = exit_at
    columns = ["date", "symbol", "entry_minute", "exit_minute", "entry", "exit", "stop", "target", "qty",
               "risk", "gross", "charges", "pnl", "r", "reason"]
    return pd.DataFrame(trades, columns=columns), blocked


def metrics(trades):
    """Summary numbers. Expectancy = average rupees per trade after costs."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "win_rate": 0.0, "expectancy": 0.0, "total": 0.0, "max_drawdown": 0.0,
                "avg_r": 0.0, "profit_factor": 0.0, "charges": 0.0}
    pnl = trades["pnl"]
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    cum = pnl.cumsum()
    peak = cum.cummax().clip(lower=0)
    return {"trades": n, "win_rate": round(len(wins) / n, 3), "expectancy": round(float(pnl.mean()), 2),
            "total": round(float(pnl.sum()), 2), "max_drawdown": round(float((peak - cum).max()), 2),
            "avg_r": round(float(trades["r"].mean()), 2),
            "profit_factor": round(float(wins.sum() / -losses.sum()), 2) if losses.sum() < 0 else float("inf"),
            "charges": round(float(trades["charges"].sum()), 2)}


def split_design_test(trades, all_dates, design_fraction=0.7):
    """Design on the first part of the days, test on the rest the setup never saw."""
    dates = sorted(set(all_dates))
    cut = dates[max(1, int(len(dates) * design_fraction)) - 1] if dates else ""
    return trades[trades["date"] <= cut], trades[trades["date"] > cut]


def warnings_for(design, test):
    out = []
    if len(design) + len(test) < 30:
        out.append("Fewer than 30 trades in total: results are mostly luck. Collect more days.")
    if design["trades"] and test["trades"] and (design["expectancy"] > 0) != (test["expectancy"] > 0):
        out.append("Design and test sets disagree on whether the setup makes money. Do not trust it.")
    if design["expectancy"] > 0 and test["trades"] == 0:
        out.append("No test-set trades yet, so nothing has been checked out of sample.")
    return out
