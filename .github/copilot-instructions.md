# Instructions for Copilot

This is a beginner's learning project: a rules-first trading helper. Explain what you write in plain language, and keep code short and readable.

## Hard constraints (never break these)
- The agent never connects to a broker and never places orders. The user places every order by hand.
- The rules engine must not depend on any AI service or network call.
- Every limit lives in `rules.json`. Never hard-code a number that belongs there.
- `gatekeeper.py` and `gatekeeper.js` must stay identical in behaviour. Any rule change updates both, plus a case in `tests/make_cases.py`, then `python tests/make_cases.py`, `pytest` and `node tests/test_gatekeeper.js` must all pass.
- Write the test case before the rule.

## Trading context
- Capital under 50,000 INR, intraday equity, trading window 09:15 to 12:00 IST.
- Backtests must include brokerage, STT and other charges, avoid lookahead bias, and keep an out-of-sample test set.
- Options, futures and stock options are paper only. No short selling, no selling options.
- Setups are hypotheses to test, never promised edges. Do not give financial advice.
