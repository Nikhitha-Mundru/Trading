# SIP analysis tab

Analyses your existing mutual fund SIP from the numbers you type in. There are no reminders, no prices fetched, and no AI. It sits outside your trading limits, and the gatekeeper never reads it.

## Set it up (2 minutes)
1. **SIP tab, Add your SIP.** Two ways:
   - **Quick:** fund name, monthly amount, day of the month it is debited (1 to 28), and the month you started. If your SIP goes up each year, add the yearly step-up %. If you skipped months, list them like `2025-03, 2025-04`.
   - **Most accurate:** paste your transactions from your fund app, one per line (`2025-01-05, 2000` or `05-01-2025 2,000`). Pasted lines override the quick fields, so real amounts and dates are used.
2. **On its card, type today's value** from your fund app and tap **Save value**. Do this again whenever you want a fresh analysis, about once a month is plenty.

## What you get
- **Invested, value, gain.** Simple gain and percent.
- **XIRR.** Your yearly return, counting when each payment went in. This is the honest number for a SIP. A plain percent gain hides that money put in last month has had no time to grow.
- **Benchmark.** What the same payments, on the same dates, would be worth at a fixed return you choose (7% by default, like a fixed deposit). It tells you whether the fund has earned its risk. You are told in rupees whether you are ahead or behind.
- **Direct plan saving (optional).** If you hold a regular plan, enter how much a direct plan would save per year (the expense ratio difference, in your fund's factsheet). It shows the rupees that difference would have added.
- **If you keep going.** What the SIP could be worth in N years at 8%, 10% and 12% a year, with an optional yearly increase. These are assumptions, not predictions.
- **Consistency.** Months with no payment between your first and last. Gaps hurt more than people expect.
- **Saved values over time,** with XIRR on each date, so you can see the trend.
- **Ask tab.** "How is my SIP doing?" gives the same numbers.

## How to read it honestly
- **Under a year of data:** XIRR can swing wildly, so the app tells you to treat it as rough.
- **Beating 7% is not skill.** In a rising market, almost any equity fund will. Judge over several years and a full market cycle, including a fall.
- **Past returns do not predict future ones.** The projections only show what steady returns would do. Real returns are lumpy.
- **Values are what you typed.** A stale or mistyped value gives a wrong answer, so type it from the fund app's own portfolio screen.
- This is information, not financial advice. For decisions about switching funds, compare against the fund's category average and costs, and consider a SEBI-registered advisor.

## Notes
- Existing SIP data from the earlier reminder version is not carried over. Add your SIP again.
- To change a SIP, delete it and add it again. Deleting also removes its saved values, after a confirmation.
- Backup: SIP tab, Export, Build CSV, Copy. Do it monthly.
- It does not fetch NAVs. Every figure comes from what you enter.

## Run the tests
```
node tests/test_sip.js
node tests/test_ask.js
```

## Learn by changing it
1. XIRR is solved by bisection in `xirr()` (repeatedly halving a range). Change the search limits and see which tests fail.
2. Add the SIP's best and worst single month to the analysis, with the test first.
3. Ask Copilot: "Explain `xirr()` in `sip.js` and why bisection works for this shape of cash flows, including its limit."
