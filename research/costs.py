"""Estimated charges for one intraday equity round trip (buy then sell).

These rates are APPROXIMATE and change over time. Check your broker's charge
calculator and update the constants below before you trust any result.
"""
BROKERAGE_FLAT = 20.0        # rupees per executed order, or the percent below if lower
BROKERAGE_PCT = 0.0003       # 0.03% of order value
STT_SELL_PCT = 0.00025       # securities transaction tax, sell side only
EXCHANGE_PCT = 0.0000307     # exchange transaction charge, both sides
SEBI_PCT = 0.000001          # SEBI turnover fee, both sides
STAMP_BUY_PCT = 0.00003      # stamp duty, buy side only
GST_PCT = 0.18               # on brokerage + exchange + SEBI charges


def _brokerage(value):
    return min(BROKERAGE_FLAT, value * BROKERAGE_PCT)


def round_trip(entry, exit_price, qty):
    """Total charges in rupees for buying at `entry` and selling at `exit_price`."""
    buy, sell = entry * qty, exit_price * qty
    brokerage = _brokerage(buy) + _brokerage(sell)
    exchange = (buy + sell) * EXCHANGE_PCT
    sebi = (buy + sell) * SEBI_PCT
    stt = sell * STT_SELL_PCT
    stamp = buy * STAMP_BUY_PCT
    gst = (brokerage + exchange + sebi) * GST_PCT
    return brokerage + exchange + sebi + stt + stamp + gst


def no_costs(entry, exit_price, qty):
    """Use this in tests, never in a real backtest."""
    return 0.0
