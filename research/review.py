"""Weekly review of the CSV you export from the phone app (Journal tab, Build CSV, Copy).

    python -m research.review journal/week-47.csv

It shows your results and, more importantly, how you behaved: which rules blocked
you most, and whether you tried to trade after a stop rule said you were done.
"""
import argparse
import csv
import io
from collections import Counter
from pathlib import Path

import pandas as pd

from research.backtest import metrics

RULE_NAMES = {
    "morning": "morning check", "window": "entry window", "segment": "paper-only segment", "side": "buy only",
    "prices": "prices and quantity", "risk": "risk per trade", "rr": "reward vs risk", "daily": "daily loss limit",
    "budget": "remaining daily budget", "week": "weekly loss limit", "count": "trades per day",
    "streak": "losses in a row", "cooldown": "wait after a loss", "expiry": "expiry day",
}
STOP_RULES = {"daily", "week", "count", "streak", "cooldown"}  # rules that mean "you should be done"

# Older exports have only the reason sentences. These phrases map them back to rule ids (approximate).
TEXT_TO_RULE = [
    ("left today", "budget"), ("Do the morning check", "morning"), ("not rested", "morning"),
    ("Watchlist has more", "morning"), ("Entries are allowed only", "window"), ("is paper only", "segment"),
    ("Unknown segment", "segment"), ("Short selling", "side"), ("Need whole quantity", "prices"),
    ("Fix the prices first", "prices"), ("Risk is", "risk"), ("Reward vs risk is", "rr"),
    ("Daily limit reached", "daily"), ("Weekly limit reached", "week"), ("trades used today", "count"),
    ("losses in a row", "streak"), ("more minutes after your last loss", "cooldown"), ("expiry day", "expiry"),
]


def _sections(text):
    """Split the export into {'TRADES': [rows], 'BLOCKED': [rows]} using the csv module."""
    out, current = {}, None
    for row in csv.reader(io.StringIO(text.strip())):
        if not row or not any(c.strip() for c in row):
            continue
        if len(row) == 1 and row[0] in ("TRADES", "BLOCKED"):
            current = row[0]
            out[current] = []
        elif current:
            out[current].append(row)
    return out


def _frame(rows):
    if not rows:
        return pd.DataFrame()
    header, body = rows[0], rows[1:]
    return pd.DataFrame([r + [""] * (len(header) - len(r)) for r in body], columns=header)


def infer_rules(reasons_text):
    found = []
    for part in reasons_text.split(" | "):
        for phrase, rule in TEXT_TO_RULE:
            if phrase in part:
                found.append(rule)
                break
    return found


def parse(text):
    """Return (trades DataFrame, blocked DataFrame with a 'rule_list' column)."""
    sec = _sections(text)
    trades = _frame(sec.get("TRADES", []))
    if len(trades):
        trades["paper"] = trades["paper"].str.lower() == "true"
        for c in ("entry", "stop", "target", "qty", "risk", "pnl"):
            trades[c] = pd.to_numeric(trades[c], errors="coerce")
    blocked = _frame(sec.get("BLOCKED", []))
    if len(blocked):
        if "rules" in blocked.columns:
            blocked["rule_list"] = [[x for x in r.split(";") if x] or infer_rules(why)
                                    for r, why in zip(blocked["rules"], blocked["reasons"])]
        else:
            blocked["rule_list"] = [infer_rules(why) for why in blocked["reasons"]]
    return trades, blocked


def _m(df):
    d = df.copy()
    d["r"] = d["pnl"] / d["risk"]
    d["charges"] = 0.0
    return metrics(d.reset_index(drop=True))


def _line(label, m):
    if m["trades"] == 0:
        return f"{label}: no results yet"
    return (f"{label}: {m['trades']} trades, win rate {m['win_rate']:.0%}, expectancy {m['expectancy']} per trade, "
            f"total {m['total']}, worst drawdown {m['max_drawdown']}")


def by_hour(done):
    out = {}
    for hour, g in done.groupby(done["time"].str[:2]):
        out[hour] = {"trades": len(g), "total": round(float(g["pnl"].sum()), 2)}
    return out


def stop_rule_attempts(blocked):
    return int(sum(1 for rules in blocked["rule_list"] if STOP_RULES & set(rules))) if len(blocked) else 0


def report(text):
    trades, blocked = parse(text)
    lines = []
    dates = sorted(set(trades["date"] if len(trades) else []) | set(blocked["date"] if len(blocked) else []))
    lines.append(f"Weekly review: {dates[0]} to {dates[-1]}" if dates else "Weekly review: no data")
    if len(trades):
        done = trades[trades["pnl"].notna()]
        missing = int(trades["pnl"].isna().sum())
        lines.append(f"Trades logged: {len(trades)} ({int((~trades['paper']).sum())} real, {int(trades['paper'].sum())} paper)"
                     + (f". {missing} have no result: enter them in Journal." if missing else "."))
        lines.append(_line("Real money", _m(done[~done["paper"]])))
        lines.append(_line("Paper", _m(done[done["paper"]])))
        if len(done):
            lines.append("By hour (all trades with results): " + ", ".join(
                f"{h}:00 -> {v['trades']} trades, {v['total']}" for h, v in sorted(by_hour(done).items())))
        if len(done) < 20:
            lines.append("Note: under 20 results is far too few to judge a setup. Keep logging.")
    else:
        lines.append("No trades logged this period.")

    if len(blocked):
        counts = Counter(r for rules in blocked["rule_list"] for r in rules)
        lines.append(f"Blocked checks: {len(blocked)}")
        for rule, n in counts.most_common():
            lines.append(f"  {RULE_NAMES.get(rule, rule)}: {n}")
        attempts = stop_rule_attempts(blocked)
        if attempts:
            lines.append(f"You ran {attempts} checks after a stop rule said you were done. Talk to yourself about why.")
        top = counts.most_common(1)[0][0] if counts else None
        advice = {
            "window": "Most blocks are the time window: plan trades before 11:30, not after.",
            "morning": "Most blocks are the morning check: you are skipping it or not feeling ready. That is the rule working.",
            "risk": "Most blocks are risk per trade: your stops are too wide for your size. Use fewer shares or find tighter setups.",
            "rr": "Most blocks are reward vs risk: your targets are too close. Only take setups with room to run.",
        }
        if top in advice:
            lines.append(advice[top])
    else:
        lines.append("Nothing was blocked this period.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("csv_file", help="the file you pasted from the phone's Journal export")
    args = p.parse_args(argv)
    text = Path(args.csv_file).read_text()
    out = report(text)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
