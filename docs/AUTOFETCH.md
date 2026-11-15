# Automatic nightly data

A free GitHub Action fetches 5-minute candles every weekday at 16:30 IST and saves them in `data/`. It runs on GitHub's servers, so it does not use your Codespace hours and works even if you forget.

## Set up (once)
1. Unzip this add-on in your Codespace, then save it:
   ```
   unzip -o autofetch-addon.zip
   rm autofetch-addon.zip
   git add -A
   git commit -m "Add nightly candle fetch"
   git push
   ```
2. On github.com open your repo, then the **Actions** tab. If it asks, click the green button to enable workflows.
3. Test it now: Actions, then "Fetch candles", then **Run workflow**. After a minute you should see a green tick. A new commit called "Add candles for ..." appears if there were new candles.

## Change your symbols
Edit `symbols.txt`, one NSE symbol per line (INFY, SBIN, ITC), then commit and push. You can list more than 3 symbols for research. The pre-market brief still picks at most 3.

## Important habits
- **Pull before you push.** The bot adds commits, so in Codespaces run `git pull` first. If you forget and `git push` is rejected, run `git pull` then `git push` again.
- **Market holidays:** nothing new is saved and no commit is made. That is normal.
- **GitHub timing:** scheduled runs can start 10 to 30 minutes late, and occasionally skip. Check the Actions tab each week for red crosses.
- **Public repos:** GitHub pauses scheduled workflows after 60 days with no repo activity. Any commit restarts them. A private repo is not affected.
- **Free data limits:** Yahoo keeps about 60 days of 5-minute candles, which is why saving them yourself matters. Spot-check a candle against your broker chart now and then.

## If it fails
Open the failed run in Actions, click the red step, and read the message. Most failures are a temporary Yahoo error: click **Re-run jobs**. If a symbol is wrong (typo or delisted), the log says "nothing returned".

## What changed in `research/fetch_data.py`
It now exits with an error only when every symbol fails, so a broken night shows a red cross in Actions instead of a green tick. One bad symbol, or a market holiday with no new candles, still counts as success. `tests/test_fetch_main.py` checks all three cases.
