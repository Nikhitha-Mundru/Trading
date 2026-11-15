"""Shared helpers: loading candle files and splitting them into trading days."""
from datetime import date as _date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
IST = "Asia/Kolkata"
COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


def prepare(df):
    """Make sure candles have an IST datetime, a 'date' string and a 'minute' (minutes since midnight)."""
    df = df.copy()
    dt = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(IST)
    df["datetime"] = dt
    df["date"] = dt.dt.strftime("%Y-%m-%d")
    df["minute"] = dt.dt.hour * 60 + dt.dt.minute
    return df.sort_values("datetime").reset_index(drop=True)


def load_candles(path):
    return prepare(pd.read_csv(path))


def load_all(data_dir=None):
    """Load every CSV in the data folder into {symbol: candles}."""
    folder = Path(data_dir or DATA_DIR)
    return {p.stem: load_candles(p) for p in sorted(folder.glob("*.csv"))}


def days(df):
    """Yield (date, that day's candles with a fresh 0..n index)."""
    for d, g in df.groupby("date", sort=True):
        yield d, g.reset_index(drop=True)


def week_start(date_str):
    d = _date.fromisoformat(date_str)
    return (d - timedelta(days=d.weekday())).isoformat()
