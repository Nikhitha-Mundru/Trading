"""Read a mutual fund statement and write a SIP import file for the app.

    python -m research.sip_import statements/cas.pdf --password ABCDE1234F          (transaction history: best)
    python -m research.sip_import statements/Holdings_Statement.xlsx               (holdings summary, e.g. Groww)
    python -m research.sip_import statements/shot1.png statements/shot2.png        (screenshots, best effort)

Then, in the app: SIP tab, Import, choose journal/sip_import.json (or paste its text).

The statement route is accurate: dates and amounts are read from text, not guessed.
The screenshot route uses OCR, which can misread numbers (the rupee sign is often
read as a digit), so it is best effort and always cross-checked and flagged.
Nothing here uses AI or the internet, and no PAN, folio number or name is written out.
"""
import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RE = re.compile(r"^(\d{2})-([A-Za-z]{3})-(\d{4})\b")
NUM_RE = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
ISIN_RE = re.compile(r"^(.*?)\s*-?\s*ISIN\s*:\s*(IN[A-Z0-9]{9}\d)", re.I)
VALUE_RE = re.compile(r"(?:Market|Valuation)\s+Value\s+on\s+(\d{2}-[A-Za-z]{3}-\d{4})\s*:?\s*(?:INR|Rs\.?|\u20B9)?\s*([\d,]+(?:\.\d+)?)", re.I)
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
TABLE_TYPES = {".xlsx", ".xlsm", ".csv"}


# ---------- small parsers ----------
def parse_date(text):
    """'05-Jan-2025' -> '2025-01-05'."""
    m = DATE_RE.match(text.strip())
    if not m or m.group(2).lower() not in MONTHS:
        raise ValueError(f"not a statement date: {text!r}")
    return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{m.group(1)}"


def to_num(text):
    """'1,234.50' -> 1234.5, '(2,000.00)' -> -2000.0."""
    t = text.strip()
    neg = t.startswith("(") and t.endswith(")")
    value = float(t.strip("()").replace(",", ""))
    return -abs(value) if neg else value


def clean_name(text):
    name = re.sub(r"\(.*?(advisor|direct).*?\)", "", text, flags=re.I)  # "(Advisor: DIRECT)"
    return re.sub(r"\s*-\s*$", "", " ".join(name.split())).strip()


# ---------- statement (CAS) text ----------
def parse_cas_text(text):
    """Find each scheme, its money-in/money-out transactions, and its closing value.

    Counts, never silently drops: switches, dividend reinvestments and other lines are
    reported, because they are not new money from you.
    """
    schemes, current, warnings = [], None, []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        head = ISIN_RE.match(line)
        if head and not DATE_RE.match(line):
            current = {"name": clean_name(head.group(1)) or head.group(2), "flows": [], "skipped": Counter(), "value": None, "sip_count": 0}
            schemes.append(current)
            continue
        if current is None:
            continue
        found = VALUE_RE.search(line)
        if found:
            current["value"] = {"date": parse_date(found.group(1)), "value": to_num(found.group(2))}
        if not DATE_RE.match(line):
            continue
        parts = line.split()
        nums = []
        while parts[1:] and NUM_RE.match(parts[-1]) and len(nums) < 4:
            nums.insert(0, parts.pop())
        desc = " ".join(parts[1:]).lower()
        if desc.startswith("***") or "stamp duty" in desc or " stt" in f" {desc}":
            continue
        if len(nums) < 4:
            warnings.append(f"{current['name']}: could not read a line starting {parts[0]}")
            continue
        when, amount = parse_date(parts[0]), to_num(nums[0])
        if "switch" in desc:
            current["skipped"]["switch"] += 1
        elif "reinvest" in desc or "dividend" in desc:
            current["skipped"]["dividend"] += 1
        elif any(w in desc for w in ("redemption", "redeem", "withdrawal", "reversal", "rejection")):
            current["flows"].append({"date": when, "amount": -abs(amount)})
        elif any(w in desc for w in ("purchase", "sip", "systematic", "investment", "allotment")):
            current["flows"].append({"date": when, "amount": abs(amount)})
            if "sip" in desc or "systematic" in desc:
                current["sip_count"] += 1
        else:
            current["skipped"]["other"] += 1
    return schemes, warnings


def scheme_to_sip(scheme):
    """Turn a scheme into the app's SIP record. Its real transactions are kept exactly."""
    flows = sorted(scheme["flows"], key=lambda f: f["date"])
    buys = [f for f in flows if f["amount"] > 0]
    if not buys:
        return None
    amount = Counter(round(f["amount"]) for f in buys).most_common(1)[0][0]
    day = Counter(int(f["date"][8:]) for f in buys).most_common(1)[0][0]
    sip = {"name": scheme["name"], "amount": amount, "day": min(day, 28), "start": flows[0]["date"][:7],
           "stepUp": 0, "skipped": [], "flows": flows}
    if scheme["value"]:
        sip["value"] = scheme["value"]
    return sip


# ---------- screenshot text ----------
def parse_screenshot_text(text, fallback_name="Fund from screenshot"):
    """Pull labelled numbers out of OCR text. Anything not found is left out, never guessed."""
    flat = " ".join(text.split())
    money = r"[^\d\-]{0,14}(?:\u20B9|rs\.?|inr)?\s*(-?[\d,]+(?:\.\d+)?)"

    def find(label):
        m = re.search(label + money, flat, re.I)
        return to_num(m.group(1)) if m else None

    out = {"name": fallback_name,
           "current": find(r"(?:current|market|present)\s+value"),
           "invested": find(r"invested(?:\s+amount)?"),
           "sip_amount": find(r"sip(?:\s+amount)?"), "day": None, "start": None, "xirr": None}
    m = re.search(r"(?:\u20B9|rs\.?)\s*([\d,]+)\s*(?:/|per|a|every)\s*month", flat, re.I)
    if m and not out["sip_amount"]:
        out["sip_amount"] = to_num(m.group(1))
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s+(?:of\s+)?(?:every|each|the)\s+month", flat, re.I) or re.search(r"(?:every|on)\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)", flat, re.I)
    if m and 1 <= int(m.group(1)) <= 31:
        out["day"] = int(m.group(1))
    m = re.search(r"(?:since|started|start date|sip start)[:\s]+(?:\d{1,2}[\s-]+)?([A-Za-z]{3})[a-z]*[\s,-]+(\d{4})", flat, re.I)
    if m and m.group(1).lower() in MONTHS:
        out["start"] = f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"xirr[^\d\-]{0,8}(-?\d+(?:\.\d+)?)\s*%", flat, re.I)
    if m:
        out["xirr"] = float(m.group(1))
    for line in text.splitlines():
        if re.search(r"fund|direct.*growth|growth.*direct", line, re.I) and 8 <= len(line.strip()) <= 90:
            out["name"] = " ".join(line.split())
            break
    return out


def expected_invested(amount, day, start, as_of):
    """What a plain monthly SIP would have put in by `as_of`, to cross-check a screenshot."""
    y, m = int(start[:4]), int(start[5:7])
    ay, am, ad = int(as_of[:4]), int(as_of[5:7]), int(as_of[8:])
    count = 0
    while (y, m) < (ay, am) or ((y, m) == (ay, am) and day <= ad):
        count += 1
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return count * amount


def screenshot_to_sip(parsed, today):
    warnings, label = [], parsed["name"]
    if not (parsed["sip_amount"] and parsed["start"]):
        seen = ", ".join(f"{k} {v}" for k, v in (("current value", parsed["current"]), ("invested", parsed["invested"]), ("XIRR %", parsed["xirr"])) if v is not None)
        warnings.append(f"{label}: the screenshot does not show the SIP amount and start month, so no schedule can be built"
                        + (f" (it showed: {seen})" if seen else "") + ". Use the statement PDF, or the quick form in the app.")
        return None, warnings
    day = min(parsed["day"] or 1, 28)
    if not parsed["day"]:
        warnings.append(f"{label}: SIP day not shown, so day 1 is assumed. Transactions from the PDF would be exact.")
    sip = {"name": label, "amount": parsed["sip_amount"], "day": day, "start": parsed["start"], "stepUp": 0, "skipped": []}
    if parsed["current"] is not None:
        sip["value"] = {"date": today, "value": parsed["current"]}
        warnings.append(f"{label}: the value is dated {today} because a screenshot has no reliable date.")
    if parsed["invested"] is not None:
        mine = expected_invested(sip["amount"], day, sip["start"], today)
        if mine and abs(mine - parsed["invested"]) / parsed["invested"] > 0.05:
            warnings.append(f"CHECK {label}: the screenshot says invested {parsed['invested']:,.0f}, but a monthly SIP of {sip['amount']:,.0f} "
                            f"from {sip['start']} gives {mine:,.0f}. Either the SIP amount changed, months were skipped, or OCR misread a number.")
    warnings.append(f"{label}: read from a screenshot by OCR. Check every number against the app before trusting the analysis.")
    return sip, warnings


# ---------- holdings summary (xlsx / csv, e.g. Groww) ----------
def _text(cell):
    return " ".join(str(cell).split()).lower() if cell is not None else ""


def _num(cell):
    """29998.48, '29,998.48', '-8.25%' -> float. 'N/A', '' and None -> None."""
    if cell is None or isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    t = str(cell).strip().replace(",", "").replace("%", "").replace("\u20B9", "")
    try:
        return float(t)
    except ValueError:
        return None


def _as_on_date(rows, filename, today):
    for row in rows:
        for cell in row:
            m = re.search(r"as\s+on\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})", str(cell or ""), re.I)
            if m:
                d = m.group(1)
                return d if re.match(r"\d{4}", d) else f"{d[6:10]}-{d[3:5]}-{d[0:2]}", None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if m:
        return m.group(1), None
    return today, f"no statement date found, so values are dated {today}."


def parse_holdings_rows(rows, filename="", today=None):
    """A holdings summary has the total invested and the current value of each fund, but no payment dates.
    Returns (sips, warnings). Each sip carries a 'summary' instead of transactions.
    Folio numbers, units and your name are never copied out.
    """
    today = today or date.today().isoformat()
    head = None
    for i, row in enumerate(rows):
        cells = [_text(c) for c in row]
        if "scheme name" in cells and any(c.startswith("invested") for c in cells) and any(c in ("current value", "market value") for c in cells):
            head = i
            break
    if head is None:
        return [], []
    cols = {_text(c): j for j, c in enumerate(rows[head]) if c is not None}
    name_i = cols["scheme name"]
    inv_i = next(j for c, j in cols.items() if c.startswith("invested"))
    val_i = next(j for c, j in cols.items() if c in ("current value", "market value"))
    xirr_i = cols.get("xirr")
    asof, note = _as_on_date(rows[:head], filename, today)
    warnings = [note] if note else []

    reported = None  # the statement's own overall figures, used as a cross-check
    for i, row in enumerate(rows[:head]):
        if any("total investments" in _text(c) for c in row):
            labels = [_text(c) for c in row]
            nxt = next((r for r in rows[i + 1:head] if any(c is not None for c in r)), None)
            if nxt:
                pairs = dict(zip(labels, nxt))
                reported = {"invested": _num(pairs.get("total investments")), "value": _num(pairs.get("current portfolio value"))}

    sips, no_xirr = [], 0
    for row in rows[head + 1:]:
        name = " ".join(str(row[name_i]).split()) if len(row) > name_i and row[name_i] not in (None, "") else ""
        inv, val = (_num(row[inv_i]) if len(row) > inv_i else None), (_num(row[val_i]) if len(row) > val_i else None)
        if not name or (inv is None and val is None):
            continue
        if inv is None or val is None:
            warnings.append(f"{name}: invested or current value is missing, skipped.")
            continue
        x = _num(row[xirr_i]) if xirr_i is not None and len(row) > xirr_i else None
        no_xirr += x is None
        sips.append({"name": name, "summary": {"invested": round(inv, 2), "value": round(val, 2), "date": asof, "xirr": x}})
    if sips:
        warnings.insert(0, "This is a holdings summary: it has no payment dates. The app can show invested, value, gain and the XIRR your own app reported, "
                           "but cannot compare against a benchmark or find gaps. Download the transaction history for the full analysis.")
        if no_xirr:
            warnings.append(f"{no_xirr} fund{'s' if no_xirr != 1 else ''} had no XIRR in the statement (usually under a year old).")
        if reported and reported["invested"] is not None:
            tot_i, tot_v = sum(x["summary"]["invested"] for x in sips), sum(x["summary"]["value"] for x in sips)
            if abs(tot_i - reported["invested"]) > 1 or (reported["value"] is not None and abs(tot_v - reported["value"]) > 1):
                warnings.append(f"CHECK: the funds add up to invested {tot_i:,.0f} and value {tot_v:,.0f}, but the statement's own totals are "
                                f"{reported['invested']:,.0f} and {reported['value'] or 0:,.0f}. A fund may be missing or misread.")
    return sips, warnings


def load_table(path):
    """Rows of cells from an .xlsx or .csv file."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8-sig", errors="ignore") as fh:
            return [row or [] for row in csv.reader(fh)]
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        best = []
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            if any("scheme name" in [_text(c) for c in r] for r in rows):
                return rows
            best = best or rows
        return best
    finally:
        wb.close()


# ---------- files ----------
def extract_pdf_text(path, password=None):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        if not password:
            raise ValueError("This PDF is password protected. Run again with --password. For CAMS and KFintech statements it is usually your PAN in capitals.")
        if not reader.decrypt(password):
            raise ValueError("That password did not open the PDF.")
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def ocr_image(path):
    try:
        from PIL import Image, ImageOps, ImageStat
        import pytesseract
    except ImportError:
        raise RuntimeError("Screenshots need OCR. Run: pip install pillow pytesseract  and  sudo apt-get install -y tesseract-ocr")
    img = ImageOps.autocontrast(Image.open(path).convert("L"))
    if ImageStat.Stat(img).mean[0] < 110:  # dark mode screenshots read better inverted
        img = ImageOps.invert(img)
    if img.width < 1600:
        img = img.resize((img.width * 2, img.height * 2))
    try:
        return pytesseract.image_to_string(img, config="--psm 6")
    except Exception as e:
        raise RuntimeError(f"OCR could not run ({e}). Install it with: sudo apt-get install -y tesseract-ocr")


def resolve(path):
    """Accept a bare file name if the file is in the statements folder."""
    p = Path(path)
    alt = ROOT / "statements" / p.name
    return p if p.exists() or not alt.exists() else alt


def build_import(paths, password=None, include_closed=False, sip_only=False, today=None):
    today = today or date.today().isoformat()
    sips, warnings = [], []
    for given in paths:
        p = resolve(given)
        kind = p.suffix.lower()
        if not p.exists():
            warnings.append(f"{p.name}: file not found. Drag it into the statements folder in the Explorer, then run the command with statements/{p.name}")
            continue
        try:
            if kind in IMAGE_TYPES:
                sip, w = screenshot_to_sip(parse_screenshot_text(ocr_image(p), p.stem), today)
                warnings += w
                if sip:
                    sips.append(sip)
                continue
            if kind in TABLE_TYPES:
                found, w = parse_holdings_rows(load_table(p), p.name, today)
                warnings += w
                sips += found
                if not found:
                    warnings.append(f"{p.name}: no holdings table found. This reader expects columns named Scheme Name, Invested Value and Current Value.")
                continue
            text = extract_pdf_text(p, password) if kind == ".pdf" else p.read_text(errors="ignore")
        except (ValueError, RuntimeError, OSError, KeyError) as e:
            warnings.append(f"{p.name}: {e}")
            continue
        schemes, w = parse_cas_text(text)
        warnings += w
        if not schemes:
            warnings.append(f"{p.name}: no funds found. This reader expects a CAMS or KFintech consolidated statement with ISIN lines.")
        for s in schemes:
            sip = scheme_to_sip(s)
            if sip is None:
                warnings.append(f"{s['name']}: no purchases found, skipped.")
            elif sip_only and s["sip_count"] < 2:
                warnings.append(f"{s['name']}: fewer than 2 SIP-type purchases, skipped (--sip-only).")
            elif s["value"] and s["value"]["value"] == 0 and not include_closed:
                warnings.append(f"{s['name']}: fully redeemed (value 0), skipped. Use --include-closed to keep it.")
            else:
                sips.append(sip)
                if not s["value"]:
                    warnings.append(f"{s['name']}: no closing value found in the statement. Type today's value on its card.")
                for kind_, n in s["skipped"].items():
                    warnings.append(f"{s['name']}: left out {n} {kind_} line{'s' if n != 1 else ''} (not new money from you)." if kind_ != "other"
                                    else f"{s['name']}: {n} unrecognised line{'s' if n != 1 else ''} left out. Check the statement if totals look wrong.")
    return {"version": 1, "source_files": [Path(p).name for p in paths], "sips": sips, "warnings": warnings}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make a SIP import file from a statement PDF or screenshots.")
    ap.add_argument("files", nargs="+", help="statement PDF, holdings .xlsx/.csv, text copy of a statement, or screenshot images")
    ap.add_argument("--password", help="PDF password (for CAS files, usually your PAN in capitals)")
    ap.add_argument("--include-closed", action="store_true", help="keep funds you have fully redeemed")
    ap.add_argument("--sip-only", action="store_true", help="keep only funds with 2 or more SIP-type purchases")
    ap.add_argument("--out", default=str(ROOT / "journal" / "sip_import.json"))
    args = ap.parse_args(argv)

    result = build_import(args.files, args.password, args.include_closed, args.sip_only)
    for s in result["sips"]:
        if s.get("summary"):
            m = s["summary"]
            x = f", XIRR {m['xirr']}% (as reported)" if m["xirr"] is not None else ", no XIRR reported"
            print(f"  {s['name']}: invested {m['invested']:,.0f}, value {m['value']:,.0f} on {m['date']}{x}")
            continue
        shape = f"{len(s['flows'])} transactions, invested {sum(f['amount'] for f in s['flows']):,.0f}" if s.get("flows") else f"{s['amount']:,.0f} monthly from {s['start']}"
        val = f"value {s['value']['value']:,.0f} on {s['value']['date']}" if s.get("value") else "no value yet"
        print(f"  {s['name']}: {shape}; {val}")
    for w in result["warnings"]:
        print(("  ! " if w.startswith("CHECK") else "  - ") + w)
    if not result["sips"]:
        print("No SIPs found, nothing written.")
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1))
    print(f"\nWrote {len(result['sips'])} SIP(s) to {out}. Do not commit it: it holds your financial details.")
    print("Next: app, SIP tab, Import from a statement, choose that file, check the preview, tap Import.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
