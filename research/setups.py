"""Setup rules. Each returns a signal or None.

A signal is decided on a candle's CLOSE, and the trade enters on the NEXT
candle's open. That one-candle delay is what prevents lookahead bias.
These are hypotheses to test, not edges.
"""
from research.indicators import OPEN_MINUTE, add_vwap, opening_range
from gatekeeper import to_min


def _last_signal_start(rules):
    """Latest signal-candle start so the next candle opens inside the entry window."""
    return to_min(rules["entry_window"]["end"]) - 5


def orb_signal(day, rules, or_minutes=15):
    """Opening Range Breakout: first close above the opening-range high. Stop = opening-range low."""
    rng = opening_range(day, or_minutes)
    if rng is None:
        return None
    high, low = rng
    first = OPEN_MINUTE + or_minutes
    for i in range(len(day) - 1):
        m = day["minute"][i]
        if m < first or m > _last_signal_start(rules):
            continue
        if day["close"][i] > high:
            return {"index": i, "stop": low}
    return None


def vwap_bounce_signal(day, rules, tolerance=0.001):
    """VWAP Bounce: price was above VWAP, a candle dips to VWAP, then closes back above it
    on a green candle. Stop = that candle's low."""
    d = add_vwap(day)
    first = OPEN_MINUTE + 15
    for i in range(1, len(d) - 1):
        m = d["minute"][i]
        if m < first or m > _last_signal_start(rules):
            continue
        v = d["vwap"][i]
        if v != v or d["vwap"][i - 1] != d["vwap"][i - 1]:  # NaN check
            continue
        was_above = d["close"][i - 1] > d["vwap"][i - 1]
        touched = d["low"][i] <= v * (1 + tolerance)
        back_above = d["close"][i] > v and d["close"][i] > d["open"][i]
        if was_above and touched and back_above:
            return {"index": i, "stop": float(d["low"][i])}
    return None


SETUPS = {"orb": orb_signal, "vwap": vwap_bounce_signal}
