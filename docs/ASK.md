# Ask tab

The fourth tab on the phone answers questions from your own rules and journal. It has no AI and needs no internet, so it works in airplane mode and never hits a usage limit.

## What it can answer

| Ask | You get |
| --- | --- |
| "Can I trade now?" | Yes or not now, with the reasons (morning check, window, limits, cooldown), using the same checks as the gatekeeper |
| "How much can I risk?" | Your cap for the next trade, after today's losses |
| "Today's P&L" / "this week" | Real-money result, trades used, and your limits |
| "How many shares entry 100 stop 98" | The most shares that keep risk inside your cap, plus a 2 to 1 target |
| "What are my rules?" | The full list from `rules.json`. Narrow it: "what is the entry window", "what is my max loss", "cooldown rule" |
| "Why was I blocked?" | The last blocked check today |
| "How am I doing?" | Win rate, expectancy and total, real and paper separately |
| "How long until the window closes?" | Minutes left to entry cut-off and the 11:45 close |
| "What is VWAP?" | Plain definitions of about 20 trading terms (R-multiple, slippage, expiry, SIP, margin and more) |

Anything else gets a short list of things to try. It never guesses.

## How it works (for learning)
- `ask.js` matches keywords to an intent, then runs a small function for that intent. There is no AI: it is a lookup with regular expressions.
- "Can I trade now?" asks the real `Gatekeeper.evaluate` about a harmless made-up trade, so only state-based rules can fail. That means the answer can never disagree with the Check tab.
- Numbers come from `rules.json`, so if you change a limit, the answers change too.
- Rules questions win over glossary questions: "what is the expiry rule" gives your rule, "what is expiry" gives the definition.

## Run the tests
```
node tests/test_ask.js
```

## Learn by changing it
1. Add a glossary term (look at the `GLOSSARY` list). Write the test first.
2. Add a new intent, for example "how many trades left". Add its test and then the function.
3. Find a question it answers badly, add it to the tests, and fix the keywords.
4. Ask Copilot: "Explain how `answer()` in `ask.js` picks an intent, and where this approach breaks down."

## Limits
Keyword matching is brittle: phrasing it doesn't recognise falls through to the help message. That is deliberate, because a wrong answer about your money limits is worse than no answer. If you later want free-form questions, that is where the optional LLM layer (phase 8) fits, and it must never sit in the path of a rule.
