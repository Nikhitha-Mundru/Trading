"""Gatekeeper rules engine (Python). Mirrors gatekeeper.js exactly.

Run `python gatekeeper.py` for a demo, `pytest` for the tests.
"""
import json
import math
from pathlib import Path


def to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def rupees(n):
    return "\u20B9" + f"{round(n * 100) / 100:g}"


def summarize(trades, now):
    """Real-money trades only; paper trades never count toward the limits."""
    real = [t for t in trades if not t.get("paper")]
    today = [t for t in real if t["date"] == now["date"]]
    week = [t for t in real if now["weekStart"] <= t["date"] <= now["date"]]
    pnl = lambda lst: sum(t.get("pnl") or 0 for t in lst)
    streak = 0
    for t in reversed(today):
        if (t.get("pnl") or 0) < 0:
            streak += 1
        else:
            break
    last_loss = None
    for t in today:
        if (t.get("pnl") or 0) < 0:
            last_loss = t["minutes"]
    return {"netToday": pnl(today), "netWeek": pnl(week), "count": len(today),
            "streak": streak, "lastLossMinutes": last_loss}


def evaluate(rules, state, trade, now):
    out = []

    def add(id_, label, ok, reason):
        out.append({"id": id_, "label": label, "ok": bool(ok), "reason": reason})

    paper = trade.get("paper") is True
    s = summarize(state.get("trades") or [], now)

    # 1. Morning check
    m = state.get("morning")
    m_ok = bool(m and m["date"] == now["date"] and m["slept"] and m["calm"]
                and len(m.get("watchlist") or []) <= rules["watchlist_max"])
    why = "Morning check passed."
    if not m or m["date"] != now["date"]:
        why = "Do the morning check first."
    elif not m["slept"] or not m["calm"]:
        why = "You said you are not rested and calm. No trading today."
    elif len(m.get("watchlist") or []) > rules["watchlist_max"]:
        why = f"Watchlist has more than {rules['watchlist_max']} names."
    add("morning", "Morning check", m_ok, why)

    # 2. Entry window
    w0, w1 = to_min(rules["entry_window"]["start"]), to_min(rules["entry_window"]["end"])
    w_ok = w0 <= now["minutes"] <= w1
    add("window", "Entry window", w_ok,
        f"It is {clock(now['minutes'])}, inside {rules['entry_window']['start']} to {rules['entry_window']['end']}."
        if w_ok else
        f"It is {clock(now['minutes'])}. Entries are allowed only {rules['entry_window']['start']} to {rules['entry_window']['end']}.")

    # 3. Segment
    seg = trade.get("segment")
    if seg in rules["real_money_segments"]:
        seg_ok, why = True, f"Real money allowed for {seg}."
    elif seg in rules["paper_only_segments"]:
        seg_ok = paper
        why = f"{seg} is paper only, and this is a paper trade." if paper else f"{seg} is paper only. Log it as a paper trade."
    else:
        seg_ok, why = False, f"Unknown segment: {seg}."
    add("segment", "Segment", seg_ok, why)

    # 4. Side
    add("side", "Buy only", trade.get("side") == "buy",
        "Long trade." if trade.get("side") == "buy" else "Short selling and selling options are not allowed.")

    # 5. Prices
    e, st, tg, q = (trade.get(k) for k in ("entry", "stop", "target", "qty"))
    nums = all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0
               for x in (e, st, tg, q))
    geo_ok = bool(nums and int(q) == q and st < e < tg)
    add("prices", "Prices and quantity", geo_ok,
        "Stop is below entry and target is above it." if geo_ok else "Need whole quantity and stop < entry < target.")
    risk = (e - st) * q if geo_ok else None
    reward = (tg - e) * q if geo_ok else None

    # 6. Risk per trade
    r_ok = geo_ok and risk <= rules["max_loss_per_trade"] + 1e-9
    add("risk", "Risk per trade", r_ok,
        "Fix the prices first." if not geo_ok else
        f"Risk is {rupees(risk)}; limit is {rupees(rules['max_loss_per_trade'])}.")

    # 7. Reward vs risk
    rr_ok = geo_ok and reward / risk >= rules["min_reward_risk"] - 1e-9
    add("rr", "Reward vs risk", rr_ok,
        "Fix the prices first." if not geo_ok else
        f"Reward vs risk is {round(reward / risk * 100) / 100:g} to 1; need at least {rules['min_reward_risk']} to 1.")

    # 8-13. Real-money limits (skipped for paper trades)
    skip = "Paper trade: real-money limits do not apply."
    d_ok = paper or s["netToday"] > -rules["max_loss_per_day"]
    add("daily", "Daily loss limit", d_ok,
        skip if paper else
        (f"Today is {rupees(s['netToday'])}; limit is -{rupees(rules['max_loss_per_day'])}." if d_ok else
         f"Daily limit reached ({rupees(s['netToday'])}). Stop and close the app."))

    b_ok = paper or (geo_ok and risk <= rules["max_loss_per_day"] + s["netToday"] + 1e-9)
    if paper:
        why = skip
    elif not geo_ok:
        why = "Fix the prices first."
    elif b_ok:
        why = "Risk fits what is left of today's budget."
    else:
        why = f"Risk {rupees(risk)} is more than the {rupees(max(0, rules['max_loss_per_day'] + s['netToday']))} left today."
    add("budget", "Fits remaining daily budget", b_ok, why)

    wk_ok = paper or s["netWeek"] > -rules["max_loss_per_week"]
    add("week", "Weekly loss limit", wk_ok,
        skip if paper else
        (f"This week is {rupees(s['netWeek'])}; limit is -{rupees(rules['max_loss_per_week'])}." if wk_ok else
         f"Weekly limit reached ({rupees(s['netWeek'])}). No trading until Monday."))

    c_ok = paper or s["count"] < rules["max_trades_per_day"]
    add("count", "Trades per day", c_ok,
        skip if paper else
        (f"{s['count']} of {rules['max_trades_per_day']} trades used today." if c_ok else
         f"All {rules['max_trades_per_day']} trades used today."))

    st_ok = paper or s["streak"] < rules["max_consecutive_losses"]
    add("streak", "Losses in a row", st_ok,
        skip if paper else
        (f"{s['streak']} losses in a row." if st_ok else f"{s['streak']} losses in a row. Done for the day."))

    wait = 0 if s["lastLossMinutes"] is None else rules["cooldown_minutes_after_loss"] - (now["minutes"] - s["lastLossMinutes"])
    cd_ok = paper or wait <= 0
    add("cooldown", "Wait after a loss", cd_ok,
        skip if paper else ("No cooldown running." if cd_ok else f"Wait {wait} more minutes after your last loss."))

    # 14. Options: not on expiry day
    is_opt = seg in rules["option_segments"]
    x_ok = not (is_opt and trade.get("expiryDay") is True)
    add("expiry", "Expiry day", x_ok,
        ("Not an expiry day." if is_opt else "Not an option.") if x_ok else "No option trading on expiry day.")

    return {"pass": all(r["ok"] for r in out), "results": out, "risk": risk, "reward": reward,
            "rr": reward / risk if geo_ok else None, "summary": s}


def load_rules(path=None):
    return json.loads(Path(path or Path(__file__).with_name("rules.json")).read_text())


if __name__ == "__main__":
    rules = load_rules()
    state = {"morning": {"date": "2026-11-16", "slept": True, "calm": True, "watchlist": ["INFY", "SBIN"]}, "trades": []}
    trade = {"segment": "equity", "side": "buy", "entry": 100, "stop": 98, "target": 104, "qty": 50}
    now = {"date": "2026-11-16", "minutes": 10 * 60, "weekStart": "2026-11-16"}
    res = evaluate(rules, state, trade, now)
    print("PASS" if res["pass"] else "BLOCKED")
    for r in res["results"]:
        print(("  ok   " if r["ok"] else "  FAIL ") + r["label"] + ": " + r["reason"])
