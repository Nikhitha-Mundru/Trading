"""Tests for the research scripts. All data is tiny and hand-made so every number can be checked by hand."""
import pandas as pd
import pytest

from gatekeeper import load_rules
from research import costs
from research.backtest import metrics, run_backtest, simulate, split_design_test, warnings_for
from research.common import load_candles, prepare
from research.fetch_data import merge_candles, save
from research.indicators import add_vwap, opening_range
from research.premarket import build_brief
from research.setups import orb_signal

RULES = load_rules()


def candles(date, rows, start=555):
    """rows = (open, high, low, close, volume), one per 5-minute candle starting 09:15."""
    out = []
    for i, (o, h, l, c, v) in enumerate(rows):
        m = start + 5 * i
        out.append({"datetime": f"{date} {m // 60:02d}:{m % 60:02d}:00+05:30", "open": o, "high": h, "low": l, "close": c, "volume": v})
    return prepare(pd.DataFrame(out))


def scripted_day(date, signal_start):
    """Flat day, opening range 99 to 101, breakout close 102 at `signal_start`, then a drop that hits the stop."""
    rows = []
    for m in range(555, 716, 5):
        if m < 570:
            rows.append((100, 101, 99, 100, 1000))
        elif m == signal_start:
            rows.append((100, 102, 100, 102, 1000))
        elif m == signal_start + 5:
            rows.append((102, 102, 98.5, 99, 1000))
        elif m > signal_start + 5:
            rows.append((99, 99.5, 98.8, 99, 1000))
        else:
            rows.append((100, 100.5, 99.5, 100, 1000))
    return candles(date, rows)


# ---- indicators -------------------------------------------------------------
def test_vwap_by_hand():
    day = candles("2026-11-16", [(100, 102, 98, 100, 100), (100, 106, 100, 104, 200)])
    v = add_vwap(day)["vwap"]
    assert v[0] == pytest.approx(100.0)                       # (102+98+100)/3
    assert v[1] == pytest.approx((100 * 100 + (310 / 3) * 200) / 300)  # 102.2222


def test_opening_range():
    day = candles("2026-11-16", [(100, 101, 99, 100, 1), (100, 103, 98, 100, 1), (100, 102, 99.5, 100, 1), (100, 110, 90, 100, 1)])
    assert opening_range(day) == (103.0, 98.0)  # the 4th candle is after 09:30 start of range end
    assert opening_range(day.iloc[:2].reset_index(drop=True)) is None  # not enough candles


# ---- costs ------------------------------------------------------------------
def test_costs_small_order():
    c = costs.round_trip(100, 102, 50)
    buy, sell = 5000, 5100
    brokerage = min(20, buy * 0.0003) + min(20, sell * 0.0003)
    expected = brokerage + (buy + sell) * (costs.EXCHANGE_PCT + costs.SEBI_PCT) + sell * costs.STT_SELL_PCT + buy * costs.STAMP_BUY_PCT
    expected += 0.18 * (brokerage + (buy + sell) * (costs.EXCHANGE_PCT + costs.SEBI_PCT))
    assert c == pytest.approx(expected)


def test_costs_brokerage_is_capped_at_20_per_order():
    big = costs.round_trip(1000, 1000, 1000)  # 10 lakh each side
    assert costs._brokerage(1_000_000) == 20
    assert big > 0


# ---- setups: no lookahead ---------------------------------------------------
def test_orb_signal_and_stop():
    day = scripted_day("2026-11-16", 575)  # 09:35 candle closes above 101
    sig = orb_signal(day, RULES)
    assert sig == {"index": 4, "stop": 99.0}


def test_entry_is_next_candle_open_not_signal_close():
    day = scripted_day("2026-11-16", 575)
    trades, _ = run_backtest({"AAA": day}, orb_signal, RULES, slippage=0.0, costs_fn=costs.no_costs)
    assert trades.iloc[0]["entry"] == 102.0  # open of the 09:40 candle
    assert trades.iloc[0]["entry_minute"] == 580


# ---- simulation -------------------------------------------------------------
def test_stop_wins_when_candle_touches_both():
    day = candles("2026-11-16", [(100, 110, 90, 100, 1), (100, 110, 90, 100, 1)])
    price, minute, why = simulate(day, 0, stop=95, target=105, exit_minute=700, slippage=0.0)
    assert (price, why) == (95, "stop")


def test_gap_down_through_stop_exits_at_open():
    day = candles("2026-11-16", [(100, 101, 99, 100, 1), (90, 91, 89, 90, 1)])
    price, _, why = simulate(day, 0, stop=98, target=110, exit_minute=700, slippage=0.0)
    assert (price, why) == (90, "stop")


def test_time_exit_at_1145():
    rows = [(100, 101, 99.5, 100, 1)] * 40  # 09:15 to 12:30, never touches stop or target
    day = candles("2026-11-16", rows)
    price, minute, why = simulate(day, 0, stop=90, target=120, exit_minute=11 * 60 + 45, slippage=0.0)
    assert why == "time" and minute == 11 * 60 + 45


# ---- sizing and rules inside the backtest -----------------------------------
def test_position_sized_from_risk_limit():
    day = scripted_day("2026-11-16", 575)
    trades, _ = run_backtest({"AAA": day}, orb_signal, RULES, slippage=0.0, costs_fn=costs.no_costs)
    t = trades.iloc[0]
    assert t["qty"] == 50 and t["risk"] == 150.0          # 150 / (102 - 99)
    assert t["exit"] == 99.0 and t["pnl"] == -150.0 and t["r"] == -1.0


def test_backtest_obeys_gatekeeper_daily_limit():
    # three signals 09:35, 10:15, 10:45, all stopped out. Third must be blocked.
    data = {"AAA": scripted_day("2026-11-16", 575), "BBB": scripted_day("2026-11-16", 615), "CCC": scripted_day("2026-11-16", 645)}
    trades, blocked = run_backtest(data, orb_signal, RULES, slippage=0.0, costs_fn=costs.no_costs)
    assert list(trades["symbol"]) == ["AAA", "BBB"]
    assert [b["symbol"] for b in blocked] == ["CCC"]
    assert "daily" in blocked[0]["reasons"] and "streak" in blocked[0]["reasons"]


def test_backtest_obeys_cooldown():
    # first loss exits 09:45; second entry at 09:55 is only 10 minutes later: cooldown must block it
    data = {"AAA": scripted_day("2026-11-16", 575), "BBB": scripted_day("2026-11-16", 590)}
    trades, blocked = run_backtest(data, orb_signal, RULES, slippage=0.0, costs_fn=costs.no_costs)
    assert list(trades["symbol"]) == ["AAA"]
    assert blocked[0]["reasons"] == ["cooldown"]


# ---- metrics and honest testing ---------------------------------------------
def test_metrics_by_hand():
    t = pd.DataFrame({"pnl": [100.0, -50.0, -50.0, 100.0], "r": [2, -1, -1, 2], "charges": [1, 1, 1, 1]})
    m = metrics(t)
    assert m["win_rate"] == 0.5 and m["expectancy"] == 25.0 and m["total"] == 100.0
    assert m["max_drawdown"] == 100.0  # cumulative 100, 50, 0, 100: peak 100 down to 0
    assert m["profit_factor"] == 2.0


def test_split_keeps_test_days_unseen():
    t = pd.DataFrame({"date": [f"2026-11-{d:02d}" for d in range(1, 11)], "pnl": [1.0] * 10})
    design, test = split_design_test(t, list(t["date"]))
    assert len(design) == 7 and len(test) == 3 and design["date"].max() < test["date"].min()


def test_warnings():
    bad = warnings_for({"trades": 5, "expectancy": 10}, {"trades": 5, "expectancy": -10})
    assert any("Fewer than 30" in w for w in bad) and any("disagree" in w for w in bad)


# ---- data files -------------------------------------------------------------
def test_merge_removes_duplicates_and_sorts():
    a = pd.DataFrame({"datetime": ["2026-11-16 09:20:00+05:30", "2026-11-16 09:15:00+05:30"], "open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1, 1], "volume": [1, 1]})
    b = pd.DataFrame({"datetime": ["2026-11-16 09:20:00+05:30", "2026-11-16 09:25:00+05:30"], "open": [2, 2], "high": [2, 2], "low": [2, 2], "close": [2, 2], "volume": [2, 2]})
    m = merge_candles(a, b)
    assert len(m) == 3 and list(m["close"]) == [1, 2, 2]  # newest copy of 09:20 wins


def test_save_and_load_roundtrip(tmp_path):
    day = candles("2026-11-16", [(100, 101, 99, 100, 5), (100, 102, 99, 101, 6)])
    save("TEST", day[["datetime", "open", "high", "low", "close", "volume"]], tmp_path)
    save("TEST", day[["datetime", "open", "high", "low", "close", "volume"]], tmp_path)  # saving twice must not duplicate
    back = load_candles(tmp_path / "TEST.csv")
    assert len(back) == 2 and list(back["minute"]) == [555, 560]


# ---- pre-market brief -------------------------------------------------------
def test_brief_levels_gap_and_watchlist_limit():
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D"]):
        d1 = candles("2026-11-13", [(100, 100 + i, 99, 100, 1)])
        d2 = candles("2026-11-16", [(100, 101, 99, 100, 1)])
        data[sym] = pd.concat([d1, d2], ignore_index=True)
    rows, watch = build_brief(data, {"A": 103.0, "B": 100.0, "C": 98.0, "D": 100.0}, "2026-11-16")
    assert rows[0]["symbol"] == "A" and rows[0]["gap_pct"] == 3.0  # largest absolute gap first
    assert len(watch) == 3 and watch[0] == "A" and watch[1] == "C"
    assert rows[0]["close"] == 100.0  # yesterday only, never today's candle


def test_cooldown_ends_after_15_minutes():
    # second entry at 10:00 is exactly 15 minutes after the 09:45 exit: allowed
    data = {"AAA": scripted_day("2026-11-16", 575), "BBB": scripted_day("2026-11-16", 595)}
    trades, blocked = run_backtest(data, orb_signal, RULES, slippage=0.0, costs_fn=costs.no_costs)
    assert list(trades["symbol"]) == ["AAA", "BBB"] and blocked == []


def test_vwap_bounce_signal_by_hand():
    from research.setups import vwap_bounce_signal
    rows = [(100, 101, 99, 100.5, 1000), (100.5, 102, 100, 101.5, 1000), (101.5, 102.5, 101, 102, 1000),
            (102, 103, 101.5, 102.5, 1000),
            (101.4, 102.6, 101.3, 102.2, 1000),   # dips to VWAP (~101.5), closes above it, green
            (102.2, 103, 102, 102.8, 1000)]
    sig = vwap_bounce_signal(candles("2026-11-16", rows), RULES)
    assert sig == {"index": 4, "stop": 101.3}


def test_vwap_bounce_needs_a_dip():
    from research.setups import vwap_bounce_signal
    rows = [(100, 101, 99, 100.5, 1000), (100.5, 102, 100, 101.5, 1000), (101.5, 102.5, 101, 102, 1000),
            (102, 103, 101.5, 102.5, 1000), (103, 104, 103, 103.8, 1000), (103.8, 105, 103.5, 104.5, 1000)]
    assert vwap_bounce_signal(candles("2026-11-16", rows), RULES) is None
