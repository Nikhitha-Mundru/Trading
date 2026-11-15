# Research scripts (weeks 4 to 8)

Run everything from the repo root in your Codespace terminal.

| Week | Command | What it does |
| --- | --- | --- |
| 4 | `python -m research.fetch_data INFY SBIN ITC` | Saves 5-minute candles to `data/<SYMBOL>.csv`. Run it every evening so your history grows past the free 60-day limit. |
| 5 | `python -m research.run_backtest orb` | Opening Range Breakout over every file in `data/`. |
| 6 | `python -m research.run_backtest vwap` | VWAP Bounce, same costs and rules. |
| 7 | (built in) | Each run prints the first 70% of days (design) and last 30% (test) separately, with warnings. |
| 8 | `python -m research.premarket --open INFY=1502.5` | Levels, gaps and a watchlist of at most 3. |

Run `pytest` any time. All 21 research tests use hand-made candles, so they need no internet.

## How the backtest stays honest

- **No lookahead:** a signal is decided on a candle's close, and the trade enters on the next candle's open.
- **Pessimistic fills:** if one candle touches both stop and target, the stop counts as hit first. A gap through the stop exits at the open.
- **Real costs:** brokerage, STT, exchange, SEBI, stamp duty and GST, plus 0.05% slippage per side. Check the rates in `research/costs.py` against your broker's charge calculator.
- **Your rules apply:** every trade goes through the same `gatekeeper.py` you use live: 3 trades a day, ₹300 daily limit, 2 losses in a row, 15-minute wait, entry window, and 2 to 1 reward vs risk.
- **Sizing:** quantity = ₹150 divided by the stop distance, with cash only (no leverage) by default. If the stop is too wide for even one share within ₹150, the trade is skipped.
- **One position at a time.**

## Read the results like a skeptic

1. Under 30 trades means luck. With 60 days of free data you may only get 20 to 40 trades, so treat early results as a demo.
2. If Design is positive and Test is negative, the setup was fitted to the past. Drop it.
3. Open `research/output/trades_orb.csv`, pick 3 trades and check each against a broker chart by eye. If a number looks wrong, the code has a bug, not the market.
4. Change one thing at a time (slippage, opening range length) and see how fragile the result is. A setup that only works at exactly one setting is overfitted.
5. Even a good backtest is a hypothesis. Paper trade it for 4 to 8 weeks through the gatekeeper before any real money.

## What the two setups mean

- **ORB:** after the first 15 minutes (09:15 to 09:30), buy when a 5-minute candle closes above the opening-range high. Stop at the range low. Target at 2 times risk.
- **VWAP Bounce:** the price was above VWAP, a candle dips to VWAP, then closes back above it on a green candle. Stop at that candle's low. Target at 2 times risk.

## Good exercises

1. Change the opening range from 15 to 30 minutes in `orb_signal` and compare. Which gives fewer trades?
2. Raise `slippage` to 0.002 and see which setup breaks first.
3. Add a third setup in `research/setups.py` (for example, prior-day-high breakout), add it to `SETUPS`, and write a hand-made test first.
4. Ask Copilot: "Explain `simulate` in `research/backtest.py` line by line and tell me which assumption could flatter the results."

## Known limits

- Yahoo data can be delayed, have gaps, or not exist for some symbols. Spot-check against your broker chart.
- Volume-weighted VWAP from free data is approximate.
- Costs and rates are estimates and change.
- Backtests ignore partial fills, circuit limits and your own hesitation.
