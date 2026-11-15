"""Tests for the statement and screenshot reader. All data is invented."""
import json
import shutil
from pathlib import Path

import pytest

from research.sip_import import (build_import, expected_invested, extract_pdf_text, ocr_image, parse_cas_text, parse_date,
                                 parse_screenshot_text, scheme_to_sip, screenshot_to_sip, to_num)

FIXTURE = Path(__file__).parent / "sip_import_sample.json"

CAS_TEXT = """
Consolidated Account Statement
Folio No: 12345678 / 90        PAN: ABCDE1234F
Example Mutual Fund
Nifty 50 Index Fund - Direct Plan - Growth - ISIN: INF000A01AB1(Advisor: DIRECT)
Opening Unit Balance: 0.000
05-Jan-2025   Purchase - SIP        2,000.00   20.123   99.38   20.123
05-Jan-2025   *** Stamp Duty ***    0.10
05-Feb-2025   Systematic Investment - SIP   2,000.00   19.800   101.00   39.923
05-Mar-2025   Switch In - From Other Fund   5,000.00   48.000   104.00   87.923
05-Mar-2025   Dividend Reinvestment        100.00   0.950   105.00   88.873
05-Apr-2025   Purchase - SIP        2,500.00   23.400   106.84   112.273
Closing Unit Balance: 112.273   NAV on 14-Nov-2026: INR 120.5000   Total Cost Value: 6,500.00   Market Value on 14-Nov-2026: INR 13,529.00

Example Flexi Cap Fund - Regular Plan - Growth - ISIN: INF000B02CD2
10-Jan-2025   Purchase            10,000.00   100.000   100.00   100.000
20-Mar-2025   Redemption          (10,000.00)   (90.000)   111.11   10.000
Closing Unit Balance: 0.000   Market Value on 14-Nov-2026: INR 0.00

Example Small Cap Fund - Direct Plan - Growth - ISIN: INF000C03EF3
30-Jun-2025   Purchase - SIP        1,000.00   10.000   100.00   10.000
30-Jul-2025   Purchase - SIP        1,000.00   9.800   102.04   19.800
30-Aug-2025   Purchase - SIP        1,000.00   9.900   101.01   29.700
"""


def write(tmp_path, name="statement.txt", text=CAS_TEXT):
    p = tmp_path / name
    p.write_text(text)
    return p


# ---- small parsers ----
def test_dates_and_numbers():
    assert parse_date("05-Jan-2025") == "2025-01-05" and parse_date("31-dec-2026 ") == "2026-12-31"
    assert to_num("1,234.50") == 1234.5 and to_num("(2,000.00)") == -2000.0 and to_num("-5") == -5.0
    with pytest.raises(ValueError):
        parse_date("2025-01-05")


# ---- statement text ----
def test_scheme_found_with_exact_flows_and_value():
    schemes, warnings = parse_cas_text(CAS_TEXT)
    assert [s["name"] for s in schemes] == ["Nifty 50 Index Fund - Direct Plan - Growth", "Example Flexi Cap Fund - Regular Plan - Growth", "Example Small Cap Fund - Direct Plan - Growth"]
    a = schemes[0]
    assert a["flows"] == [{"date": "2025-01-05", "amount": 2000.0}, {"date": "2025-02-05", "amount": 2000.0}, {"date": "2025-04-05", "amount": 2500.0}]
    assert a["value"] == {"date": "2026-11-14", "value": 13529.0}
    assert a["skipped"] == {"switch": 1, "dividend": 1} and a["sip_count"] == 3
    assert warnings == []  # stamp duty is expected noise, not a warning


def test_redemption_is_money_out_and_closing_value_zero():
    b = parse_cas_text(CAS_TEXT)[0][1]
    assert b["flows"] == [{"date": "2025-01-10", "amount": 10000.0}, {"date": "2025-03-20", "amount": -10000.0}]
    assert b["value"]["value"] == 0.0


def test_scheme_to_sip_picks_the_usual_amount_and_day():
    sip = scheme_to_sip(parse_cas_text(CAS_TEXT)[0][0])
    assert (sip["amount"], sip["day"], sip["start"]) == (2000, 5, "2025-01")  # most common amount, not the one-off 2,500
    assert sip["value"]["value"] == 13529.0 and len(sip["flows"]) == 3
    late = scheme_to_sip(parse_cas_text(CAS_TEXT)[0][2])
    assert late["day"] == 28 and late["start"] == "2025-06"  # the 30th is clamped so every month has it
    assert scheme_to_sip({"name": "x", "flows": [{"date": "2025-01-01", "amount": -5}], "value": None}) is None


def test_unreadable_lines_are_reported_not_hidden():
    _, warnings = parse_cas_text("Fund X - ISIN: INF000A01AB1\n05-Jan-2025 Purchase 2,000.00 20.1\n")
    assert len(warnings) == 1 and "could not read a line starting 05-Jan-2025" in warnings[0]


# ---- building the import ----
def test_build_import_filters_and_explains(tmp_path):
    r = build_import([write(tmp_path)], today="2026-11-15")
    assert [s["name"] for s in r["sips"]] == ["Nifty 50 Index Fund - Direct Plan - Growth", "Example Small Cap Fund - Direct Plan - Growth"]
    text = "\n".join(r["warnings"])
    assert "fully redeemed" in text and "left out 1 switch line" in text and "left out 1 dividend line" in text
    assert "no closing value found" in text and "Small Cap" in text
    kept = build_import([write(tmp_path)], include_closed=True, today="2026-11-15")
    assert len(kept["sips"]) == 3


def test_sip_only_drops_one_off_purchases(tmp_path):
    r = build_import([write(tmp_path)], sip_only=True, include_closed=True, today="2026-11-15")
    assert [s["name"] for s in r["sips"]] == ["Nifty 50 Index Fund - Direct Plan - Growth", "Example Small Cap Fund - Direct Plan - Growth"]
    assert any("fewer than 2 SIP-type" in w for w in r["warnings"])


def test_no_personal_details_leak_into_the_output(tmp_path):
    out = json.dumps(build_import([write(tmp_path)], include_closed=True, today="2026-11-15"))
    for secret in ("ABCDE1234F", "12345678", "Folio", "PAN"):
        assert secret not in out


def test_empty_or_wrong_file(tmp_path):
    r = build_import([write(tmp_path, text="nothing useful here")], today="2026-11-15")
    assert r["sips"] == [] and "no funds found" in r["warnings"][0]
    missing = build_import([tmp_path / "gone.pdf"], today="2026-11-15")
    assert missing["sips"] == [] and "gone.pdf" in missing["warnings"][0]


def test_output_matches_the_fixture_the_app_tests_use(tmp_path):
    result = build_import([write(tmp_path)], today="2026-11-15")
    assert result == json.loads(FIXTURE.read_text())


# ---- screenshots ----
SHOT = "Nifty 50 Index Fund Direct Growth\nInvested %24,000\nCurrent value =28,150\nXIRR 14.2%\nSIP 1,000 monthly on 5th of every month\nSince Jan 2025\n"


def test_screenshot_labels_survive_a_garbled_rupee_sign():
    p = parse_screenshot_text(SHOT, "shot1")
    assert p == {"name": "Nifty 50 Index Fund Direct Growth", "current": 28150.0, "invested": 24000.0, "sip_amount": 1000.0, "day": 5, "start": "2025-01", "xirr": 14.2}
    assert parse_screenshot_text("nothing here", "shot9")["name"] == "shot9"


def test_screenshot_builds_a_sip_and_cross_checks_invested():
    sip, w = screenshot_to_sip(parse_screenshot_text(SHOT, "s"), "2026-11-14")
    assert (sip["amount"], sip["day"], sip["start"]) == (1000, 5, "2025-01") and sip["value"] == {"date": "2026-11-14", "value": 28150.0}
    assert not any(x.startswith("CHECK") for x in w) and any("OCR" in x for x in w)  # 23,000 expected vs 24,000 shown: within 5%
    bad, w2 = screenshot_to_sip({**parse_screenshot_text(SHOT, "s"), "invested": 90000.0}, "2026-11-14")
    assert any(x.startswith("CHECK") and "90,000" in x and "23,000" in x for x in w2)


def test_screenshot_without_enough_detail_makes_no_guesses():
    sip, w = screenshot_to_sip(parse_screenshot_text("Some Fund\nCurrent value 5,000\nInvested 4,000", "s"), "2026-11-14")
    assert sip is None and "current value 5000.0" in w[0] and "statement PDF" in w[0]


def test_expected_invested_by_hand():
    assert expected_invested(1000, 5, "2025-01", "2026-11-14") == 23000   # Jan 2025 to Nov 2026, all on or before the 5th
    assert expected_invested(1000, 20, "2025-01", "2026-11-14") == 22000  # November's 20th has not happened yet
    assert expected_invested(1000, 5, "2026-12", "2026-11-14") == 0


def test_real_ocr_on_a_generated_screenshot(tmp_path):
    PIL = pytest.importorskip("PIL")
    pytest.importorskip("pytesseract")
    if not shutil.which("tesseract"):
        pytest.skip("tesseract is not installed")
    from PIL import Image, ImageDraw, ImageFont
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not Path(font_path).exists():
        pytest.skip("no test font")
    f = ImageFont.truetype(font_path, 34)
    img = Image.new("RGB", (900, 420), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(["Nifty 50 Index Fund Direct Growth", "Invested \u20B924,000", "Current value \u20B928,150", "SIP \u20B91,000 monthly on 5th of every month", "Since Jan 2025"]):
        d.text((30, 20 + 62 * i), line, font=f, fill="black")
    path = tmp_path / "shot.png"
    img.save(path)
    p = parse_screenshot_text(ocr_image(path), "shot")
    assert (p["invested"], p["current"], p["sip_amount"], p["day"], p["start"]) == (24000.0, 28150.0, 1000.0, 5, "2025-01")


# ---- PDF ----
def make_pdf(path, lines, password=None):
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.setFont("Helvetica", 9)
        c.drawString(40, y, line)
        y -= 14
    c.save()
    if password:
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter()
        for page in PdfReader(str(path)).pages:
            w.add_page(page)
        w.encrypt(password, algorithm="AES-256")
        with open(path, "wb") as fh:
            w.write(fh)


def test_pdf_text_to_sips(tmp_path):
    pytest.importorskip("pypdf")
    pdf = tmp_path / "cas.pdf"
    make_pdf(pdf, [l for l in CAS_TEXT.splitlines() if l.strip()])
    r = build_import([pdf], today="2026-11-15")
    assert [s["name"] for s in r["sips"]][0] == "Nifty 50 Index Fund - Direct Plan - Growth"
    assert r["sips"][0]["flows"][0] == {"date": "2025-01-05", "amount": 2000.0} and r["sips"][0]["value"]["value"] == 13529.0


def test_password_protected_pdf(tmp_path):
    pytest.importorskip("pypdf")
    pytest.importorskip("cryptography")
    pdf = tmp_path / "locked.pdf"
    make_pdf(pdf, [l for l in CAS_TEXT.splitlines() if l.strip()], password="ABCDE1234F")
    assert "password" in build_import([pdf], today="2026-11-15")["warnings"][0].lower()
    assert "did not open" in build_import([pdf], password="WRONG", today="2026-11-15")["warnings"][0]
    ok = build_import([pdf], password="ABCDE1234F", today="2026-11-15")
    assert len(ok["sips"]) == 2 and "Nifty" in ok["sips"][0]["name"]
    assert "Market Value" in extract_pdf_text(pdf, "ABCDE1234F")
