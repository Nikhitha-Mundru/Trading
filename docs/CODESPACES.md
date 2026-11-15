# Build it in Codespaces with Copilot

## 1. One-time setup
1. On github.com create a new **private** repository named `trading-agent`.
2. Click Add file, Upload files, and drag in everything from the unzipped folder (keep the folders, including the hidden `.devcontainer` and `.github`). Commit.
3. Click Code, Codespaces, Create codespace on main. Wait for the build.
4. In the terminal: `pytest` then `node tests/test_gatekeeper.js`. Both should pass.

## 2. See the phone page
1. Run `python -m http.server 8000`.
2. Open the forwarded port 8000 from the Ports tab. Try the app in the browser.
3. For the iPhone and offline use, publish with GitHub Pages: Settings, Pages, deploy from `main`, root. Open the Pages link in Safari, then Share, Add to Home Screen.

## 3. Working with Copilot
Open Copilot Chat. It reads `.github/copilot-instructions.md` automatically, so it already knows your rules. Use Ask mode to learn and Agent mode to build. Always run the tests after it edits, and read the diff before you accept it.

Copy these prompts in order, one per session:

**Learn the core**
> Explain `gatekeeper.py` to me line by line like I am a beginner. Then show me which test in `tests/cases.json` covers each rule.

**Add a rule (practice)**
> Add a rule: no new entry within 10 minutes after a winning trade. Add a case to `tests/make_cases.py` first, then update `rules.json`, `gatekeeper.py` and `gatekeeper.js`, then run all tests.

**Data (week 4)**
> Create `research/fetch_data.py` that downloads 5-minute candles for up to 3 NSE symbols with yfinance and appends them to CSV files in `data/`, so my history grows each day. Skip days already saved. Explain each step.

**VWAP and opening range (week 4)**
> Create `research/indicators.py` with functions for VWAP and the opening range (high and low of the first 15 minutes) using pandas. Add pytest tests with a small hand-made example I can verify by hand.

**ORB backtest (week 5)**
> Create `research/backtest_orb.py`. Enter long when price closes above the opening range high between 09:30 and 11:30, stop at the opening range low capped at my per-trade risk from `rules.json`, target at 2 times risk, exit by 11:45. Use only information available at each candle (no lookahead). Print a trade list.

**Costs (week 6)**
> Add `research/costs.py` that estimates brokerage, STT, exchange charges, GST and stamp duty for an intraday equity round trip, with each rate as a named constant I can update. Apply it to the backtest results.

**Honest testing (week 7)**
> Add an out-of-sample split to the backtest: design on the first 70 percent of days, test on the last 30. Report expectancy, win rate and max drawdown for each part, and warn me if results differ a lot.

**Pre-market brief (week 8)**
> Create `research/premarket.py` that prints, for my watchlist, the gap versus yesterday's close, yesterday's high and low, and flags at most 3 names with the largest gaps.

## 4. Good habits
- Commit after every working step, with a clear message.
- Ask Copilot "why" before accepting code you do not understand.
- Never paste broker passwords or API keys into the repo. Use Codespaces secrets if you ever need keys.
- Stop the codespace when done (Code menu) to save your free hours.
