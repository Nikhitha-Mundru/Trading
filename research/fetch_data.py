"""Save intraday candles so your own history keeps growing.

    python -m research.fetch_data INFY SBIN ITC

Free sources only keep about 60 days of 5-minute data, so run this every
evening. Each run merges new candles into data/<SYMBOL>.csv without duplicates.
"""
import sys

import pandas as pd

from research.common import COLUMNS, DATA_DIR, IST, prepare


def merge_candles(existing, new):
    """Combine two candle tables, keep one row per timestamp, oldest first."""
    both = pd.concat([existing, new], ignore_index=True)
    both["datetime"] = pd.to_datetime(both["datetime"], utc=True)
    both = both.drop_duplicates(subset="datetime", keep="last").sort_values("datetime")
    return both[COLUMNS].reset_index(drop=True)


def fetch(symbol, period="5d", interval="5m"):
    """Download candles for an NSE symbol from Yahoo Finance (free, may be delayed)."""
    import yfinance as yf  # imported here so tests never need the network

    raw = yf.download(f"{symbol}.NS", period=period, interval=interval, progress=False, auto_adjust=False)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=COLUMNS)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.reset_index()
    raw = raw.rename(columns={raw.columns[0]: "datetime", "Open": "open", "High": "high",
                              "Low": "low", "Close": "close", "Volume": "volume"})
    raw["datetime"] = pd.to_datetime(raw["datetime"], utc=True).dt.tz_convert(IST)
    return raw[COLUMNS]


def save(symbol, new, data_dir=None):
    folder = data_dir or DATA_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{symbol}.csv"
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=COLUMNS)
    merged = merge_candles(existing, new)
    merged["datetime"] = merged["datetime"].dt.tz_convert(IST)
    merged.to_csv(path, index=False)
    return len(merged)


def main(argv=None):
    symbols = [s.upper() for s in (argv if argv is not None else sys.argv[1:])]
    if not symbols:
        print("Usage: python -m research.fetch_data INFY SBIN ITC")
        return 1
    failures = 0
    for s in symbols:
        try:
            df = fetch(s)
            print(f"{s}: downloaded {len(df)} candles, file now has {save(s, df)}" if len(df) else f"{s}: nothing returned (market closed or wrong symbol)")
        except Exception as e:  # network or symbol problems should not stop the other symbols
            failures += 1
            print(f"{s}: failed ({e})")
    # Exit code 1 only when EVERY symbol failed, so the nightly job shows a red cross for a broken night
    return 1 if failures == len(symbols) else 0


if __name__ == "__main__":
    raise SystemExit(main())
