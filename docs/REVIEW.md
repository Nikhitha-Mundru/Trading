# Friday review (10 minutes)

## 1. Export from the phone
Open the app, Journal tab, tap **Build CSV**, then **Copy**. Send it to yourself (Notes, email or a message).

## 2. Put it in the repo
In Codespaces create `journal/week-47.csv` (use the week number or date), paste the text, save. Then:
```
python -m research.review journal/week-47.csv
```

## 3. How to read it
- **Real money vs paper:** for now, judge paper only. Real money stays off until the plan's gate is met.
- **Blocked checks:** the rule that blocks you most is your biggest habit to fix, not a bug in the app.
- **Stop-rule attempts:** checks run after the daily limit, trade count, losing streak or cooldown said you were done. These matter more than any profit number, because they are how a bad day becomes a very bad day.
- **By hour:** see whether your later trades do worse. That is the sleepy-and-stressed pattern the app exists to catch.
- **Under 20 results:** don't judge anything yet.

## 4. Then
Write one line in the Learning Log in your notes: what blocked you most, and one change for next week. Commit the CSV (`git add journal`) so your history is kept.

## Note on the update to `index.html`
The exported BLOCKED section now includes a `rules` column with each blocking rule's id, so the review doesn't have to guess from sentences. Older exports still work, using an approximate text match. Re-publish with `git push` and reopen the app on the phone to get the new version.
