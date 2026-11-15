# Import your SIPs from a statement or screenshot

You do not type anything. A PC tool in your Codespace reads your fund statement (or screenshots) and writes a file. The app imports that file in one tap, then analyses it. Nothing is uploaded anywhere and no AI is used.

## Which one to use
| Source | Accuracy | What it gives |
| --- | --- | --- |
| **Statement PDF** (CAMS / KFintech consolidated statement) | High: dates and amounts are read as text | Every purchase and redemption, plus the closing value, for every fund |
| **Screenshots** | Lower: OCR can misread numbers | Value, SIP amount, day and start month, if the screen shows them |

Use the statement whenever you can. Use screenshots for a quick fill.

## One-time setup
```
pip install -r requirements.txt
mkdir -p statements
```
For screenshots only: `sudo apt-get install -y tesseract-ocr`

## 1. Get your statement
Ask for a **consolidated account statement (CAS)** with all transactions from your first investment. CAMS, KFintech and MF Central all offer it free by email. The PDF is password protected. Use the password you chose when you requested it, or the one in the email. For depository statements it is usually your PAN in capitals. The tool never writes your PAN, folio number or name anywhere.

## 2. Run the tool
Drag the PDF into the `statements` folder in the Explorer, then:
```
python -m research.sip_import statements/cas.pdf --password YOURPASSWORD
```
It prints each fund it found with the number of transactions, the amount invested and the closing value, then notes on anything it left out. Read this summary and compare it with your fund app. Lines starting with `!` (CHECK) mean something does not add up.

Useful options:
- `--sip-only` keeps only funds with 2 or more SIP purchases. Without it, funds you bought by lump sum are included too.
- `--include-closed` keeps funds you have fully redeemed. By default they are skipped.

For screenshots, put the images in `statements` too, then:
```
python -m research.sip_import statements/shot1.png statements/shot2.png
```

## 3. Import into the app
The file is `journal/sip_import.json`. Apps keep data per device, so import it **on the phone**:
1. In Codespaces, right-click `journal/sip_import.json` and choose Download.
2. Get it to the phone (AirDrop, email or Notes). Save it to Files.
3. App, SIP tab, **Import from a statement**, choose the file.
4. Check the preview, then tap **Import**.

If choosing a file is awkward on the phone, open the JSON in Codespaces, copy all of the text, send it to yourself, and paste it into the box in the app.

Importing twice is safe: funds you already added are skipped.

## What gets imported
- Money in: SIP and lump-sum purchases. Money out: redemptions.
- Left out on purpose, and counted in the notes: switches between funds and dividend reinvestments, because they are not new money from you. Stamp duty lines are ignored.
- The value is the closing value on the statement date. If the statement is old, type a fresh value on the fund's card in the app. The analysis then uses the newer date.

## Screenshots: read this
- OCR often misreads the rupee sign (in my tests it came out as `%`, `=` or nothing). The digits survived on clean images, but real phone screenshots are smaller and fuzzier, so a digit can be wrong.
- The tool cross-checks the "Invested" figure it reads against what the SIP amount and start month would give, and raises a CHECK if they differ by more than 5%.
- If the screen does not show the SIP amount and start month, no schedule can be built. The tool says what it could read, and you add the fund with the quick form or use the statement.
- The value is dated today, because a screenshot has no reliable date.

## If it says "no funds found"
The reader expects the common CAMS/KFintech layout: a line with `ISIN: INF...` for each fund, then transaction lines like `05-Jan-2025 Purchase - SIP 2,000.00 20.123 99.38 20.123` (date, description, amount, units, price, balance). I could only test it on invented text in that shape, plus a generated PDF. Real statements vary. If yours is different, copy a few transaction lines and the fund heading line, remove your name, PAN, folio and email, and show them to me in the chat. I will adapt the reader.

## Privacy
- Statements contain your PAN, name and folio number. The `.gitignore` in this add-on keeps `statements/`, all PDFs and `journal/sip_import.json` out of git. Do not commit them. If your repository is public, anything you commit is public.
- Delete the PDF when you are done.
- Your SIP data lives only on your phone, in the app.

## Run the tests
```
pytest tests/test_sip_import.py
node tests/test_sip.js
```
Some tests are skipped if OCR or the PDF libraries are not installed.

## Learn by changing it
1. Add a new transaction word (for example "Bonus") to the classifier in `parse_cas_text` with a test first.
2. Run the tool on a statement with a fund you switched out of. Check the "left out" note matches your own count.
3. Ask Copilot: "Explain `parse_cas_text` in `research/sip_import.py` and which statement layouts would break it."
