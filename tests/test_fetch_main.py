import pandas as pd
from research import fetch_data
from research.common import COLUMNS


def _frame():
    return pd.DataFrame({"datetime": pd.to_datetime(["2026-11-16 09:15"]).tz_localize("Asia/Kolkata"),
                         "open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]})[COLUMNS]


def test_all_symbols_failing_returns_error(monkeypatch):
    def boom(symbol, **kw):
        raise RuntimeError("network down")
    monkeypatch.setattr(fetch_data, "fetch", boom)
    assert fetch_data.main(["AAA", "BBB"]) == 1


def test_one_failure_is_not_a_failed_night(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)

    def fake(symbol, **kw):
        if symbol == "BAD":
            raise RuntimeError("bad symbol")
        return _frame()
    monkeypatch.setattr(fetch_data, "fetch", fake)
    assert fetch_data.main(["GOOD", "BAD"]) == 0
    assert (tmp_path / "GOOD.csv").exists()


def test_empty_result_on_a_holiday_is_not_an_error(monkeypatch):
    monkeypatch.setattr(fetch_data, "fetch", lambda symbol, **kw: pd.DataFrame(columns=COLUMNS))
    assert fetch_data.main(["AAA"]) == 0
