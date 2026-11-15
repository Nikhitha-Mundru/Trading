# Gatekeeper

A rules-first trading helper. It does not place orders and never connects to a broker. It checks a planned trade against your rules and answers **PASS** or **BLOCKED** with reasons. It does not use AI, so it has no usage limit.

This is a learning project. Treat every setup as a hypothesis, and this is not financial advice.

## Files

| File | What it is |
| --- | --- |
| `rules.json` | The one place every limit lives. Change a number here and both engines follow. |
| `gatekeeper.py` | Rules engine in Python (laptop, tests, research). |
| `gatekeeper.js` | The same engine in JavaScript (the phone page). |
| `index.html`, `sw.js`, `manifest.json`, `icon-*.png` | The iPhone web app and its offline support. |
| `tests/cases.json` | 29 shared test cases. Both engines must give identical answers. |
| `tests/make_cases.py` | Generates `cases.json`. Add your own cases here. |
| `tests/test_gatekeeper.py` / `.js` | Test runners. |
| `.devcontainer/`, `.github/copilot-instructions.md`, `requirements.txt` | Codespaces setup and Copilot rules. |
| `docs/CODESPACES.md` | Step-by-step build guide and Copilot prompts. |

## Run the tests

    pip install pytest
    pytest                          # Python engine
    node tests/test_gatekeeper.js   # JavaScript engine
    python gatekeeper.py            # demo check

## Put it on your iPhone (free)

1. Create a GitHub repository and upload every file in this folder (keep `tests/`).
2. Repository Settings, Pages: deploy from the `main` branch, root folder.
3. Open the `https://<your-name>.github.io/<repo>/` link in Safari on the iPhone.
4. Share, then Add to Home Screen. Open it once online, then it works offline.

Your data stays on the phone. Use Journal, Export, to back it up weekly.

## The rules it enforces

Loss per trade 150, per day 300, per week 900; at most 3 trades a day; reward vs risk at least 2 to 1; entries 09:30 to 11:30, everything closed by 11:45; 2 losses in a row ends the day; 15 minutes wait after any loss; morning check (slept well, calm, watchlist of at most 3); options are paper only, buying only, never on expiry day; futures and stock options paper only; buy side only.

Design choices to know about:

- Paper trades must pass the time, price, risk and reward checks, but they do not count toward the daily and weekly limits.
- A trade must also fit what is left of today's loss budget, not just the 150 cap.
- The 11:45 close is a reminder banner. The app cannot close your positions.

## Learn by changing it

1. Change `max_loss_per_trade` to 100 and run the tests. Which fail, and why?
2. Add a rule: no entry in the 10 minutes after a win. Write the test case first.
3. Add the rule to both `gatekeeper.py` and `gatekeeper.js`, then check the tests agree.
