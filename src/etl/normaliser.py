"""
N100 Financial Intelligence Platform
Sprint 1, Day 2: Excel Loader & Normaliser

Two normalisation functions used across every downstream module:
- normalize_year(): converts every year-label format found in the raw
  Excel files into a single consistent 'YYYY-MM' string.
- normalize_ticker(): cleans company_id values so the same company
  is never accidentally treated as two different keys (e.g. "tcs "
  vs "TCS").
"""

import re

# Maps month names/abbreviations (lowercase) to their 2-digit number.
# Covers both 3-letter abbreviations (Mar, Dec) and full names (March).
MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

# Known ticker typos/corrections found in specific source files during
# Day 5 loading. Each entry is a confirmed, verified correction -- not
# a guess -- documented with the evidence that justified it.
KNOWN_TICKER_CORRECTIONS = {
    # cashflow.xlsx only: 7 rows under "AGTL", which does not exist in
    # companies.xlsx or anywhere else. "ATGL" (a real, valid company)
    # has 8 rows in profitandloss.xlsx and balancesheet.xlsx, but ZERO
    # rows in cashflow.xlsx -- strong evidence this is a transposed-
    # letter typo in that one file, not a missing company. Verified
    # 2026-08-22 via diagnose_cashflow_silent_filter.py.
    "AGTL": "ATGL",
}


def normalize_year(raw_value) -> str:
    """
    Convert any recognised year-label format into 'YYYY-MM'.
    Returns 'PARSE_ERROR' if the input doesn't match any known pattern.
    Returns 'TTM' unchanged for Trailing Twelve Months rows (a real,
    standard reporting period not tied to a single fiscal year-end).

    Recognised formats (see spec Section 23, plus real data found
    during Day 2 loading that the spec didn't originally document):
        'Mar-23'      -> '2023-03'
        'Mar 23'      -> '2023-03'   (space instead of hyphen)
        'March-2023'  -> '2023-03'   (full month name, full year)
        '2023'        -> '2023-03'   (bare year, assume March FY close)
        'FY23'        -> '2023-03'   (FY prefix)
        'Dec-22'      -> '2022-12'   (December year-end company)
        '2023-03'     -> '2023-03'   (already normalised, pass through)
        'TTM'         -> 'TTM'       (Trailing Twelve Months, pass through)
        anything else -> 'PARSE_ERROR'  (e.g. stub periods like 'Mar 2016 9m',
                                          ambiguous values like 'Mar 2023 15' --
                                          too rare/unclear to guess at; reject
                                          and log rather than silently corrupt)
    """
    if raw_value is None:
        return "PARSE_ERROR"

    text = str(raw_value).strip()
    if not text:
        return "PARSE_ERROR"

    # Trailing Twelve Months -- a real, standard reporting period, but NOT
    # tied to one specific fiscal year-end. Recognised explicitly rather
    # than forced into a fake YYYY-MM. Downstream modules (Ratio Engine,
    # CAGR calculations) must exclude 'TTM' rows from year-over-year
    # comparisons, since it's a rolling window, not a fixed year.
    if text.upper() == "TTM":
        return "TTM"

    # Pattern 1: already normalised, e.g. "2023-03"
    if re.match(r"^\d{4}-\d{2}$", text):
        return text

    # Pattern 2: FY prefix, e.g. "FY23" or "FY2023"
    fy_match = re.match(r"^FY(\d{2}|\d{4})$", text, re.IGNORECASE)
    if fy_match:
        year_part = fy_match.group(1)
        year = f"20{year_part}" if len(year_part) == 2 else year_part
        return f"{year}-03"

    # Pattern 3: "Mon-YY", "Mon YY", "Month-YYYY", "Month YYYY"
    # e.g. "Mar-23", "Mar 23", "March-2023", "December 2022"
    month_match = re.match(r"^([A-Za-z]{3,9})[-\s](\d{2}|\d{4})$", text)
    if month_match:
        month_name = month_match.group(1).lower()
        year_part = month_match.group(2)
        if month_name in MONTH_MAP:
            month_num = MONTH_MAP[month_name]
            year = f"20{year_part}" if len(year_part) == 2 else year_part
            return f"{year}-{month_num}"
        return "PARSE_ERROR"  # unrecognised month name

    # Pattern 4: bare 4-digit year, e.g. "2023" -- assume March FY close
    if re.match(r"^\d{4}$", text):
        return f"{text}-03"

    # Nothing matched
    return "PARSE_ERROR"


def normalize_ticker(raw_value) -> str | None:
    """
    Clean a company_id (NSE ticker) value: strip whitespace, uppercase.
    Hyphens and ampersands are preserved since they're valid characters
    in real NSE tickers (e.g. 'BAJAJ-AUTO', 'M&M').

    After cleaning, applies KNOWN_TICKER_CORRECTIONS -- a small, explicit
    map of confirmed source-data typos (see comment above the dict).
    This is NOT fuzzy matching or guessing; only tickers verified against
    real evidence in other tables are corrected here.

    Returns None if the value is missing/empty after cleaning --
    signals to the caller that this row should be rejected (no valid FK).
    """
    if raw_value is None:
        return None

    text = str(raw_value).strip().upper()
    if not text:
        return None

    return KNOWN_TICKER_CORRECTIONS.get(text, text)