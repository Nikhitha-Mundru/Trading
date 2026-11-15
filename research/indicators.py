"""VWAP and opening range, kept simple so you can check them by hand."""
OPEN_MINUTE = 9 * 60 + 15  # 09:15


def add_vwap(day):
    """Add a 'vwap' column: running (typical price x volume) / running volume, restarting each day."""
    day = day.copy()
    typical = (day["high"] + day["low"] + day["close"]) / 3
    cum_value = (typical * day["volume"]).cumsum()
    cum_volume = day["volume"].cumsum()
    day["vwap"] = cum_value / cum_volume.where(cum_volume > 0)
    return day


def opening_range(day, minutes=15, candle_minutes=5):
    """High and low of the first `minutes` after 09:15, or None if candles are missing."""
    part = day[(day["minute"] >= OPEN_MINUTE) & (day["minute"] < OPEN_MINUTE + minutes)]
    if len(part) < minutes // candle_minutes:
        return None
    return float(part["high"].max()), float(part["low"].min())
