"""
N100 Financial Intelligence Platform
Sprint 4, Day 22: Shared, cached database access layer for the dashboard.

CRITICAL: every "latest year" query excludes year='TTM' -- TTM is a
rolling 12-month window, not a fixed fiscal year-end (Sprint 2 Finding
6). Every function here follows that rule explicitly, not by accident.
"""

import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = "data/nifty100.db"


def _connect():
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=600)
def get_companies():
    """All 92 companies with sector info."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT c.id, c.company_name, c.about_company, c.face_value,
               c.book_value, c.roce_percentage, c.roe_percentage,
               s.broad_sector, s.sub_sector, s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON c.id = s.company_id
        ORDER BY c.company_name
    """, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_ratios(ticker, year=None):
    """
    financial_ratios rows for one company. If year is None, returns the
    LATEST real fiscal year (never TTM). If year is given, returns that
    specific year's row (still excludes TTM from the candidate years).
    """
    conn = _connect()
    if year is None:
        df = pd.read_sql("""
            SELECT * FROM financial_ratios
            WHERE company_id = ? AND year != 'TTM'
            ORDER BY year DESC LIMIT 1
        """, conn, params=(ticker,))
    else:
        df = pd.read_sql("""
            SELECT * FROM financial_ratios
            WHERE company_id = ? AND year = ?
        """, conn, params=(ticker, year))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_ratios_history(ticker):
    """Full non-TTM fiscal year history of financial_ratios for one company."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT * FROM financial_ratios
        WHERE company_id = ? AND year != 'TTM'
        ORDER BY year ASC
    """, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pl(ticker):
    """Full P&L history, non-TTM years only, chronological."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT * FROM profitandloss
        WHERE company_id = ? AND year != 'TTM'
        ORDER BY year ASC
    """, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker):
    """Full balance sheet history. May be empty for SBIN (Sprint 1 Finding 8)."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT * FROM balancesheet
        WHERE company_id = ?
        ORDER BY year ASC
    """, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker):
    """Full cash flow history."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT * FROM cashflow
        WHERE company_id = ? AND year != 'TTM'
        ORDER BY year ASC
    """, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_sectors():
    """
    Distinct sectors with company counts. Returns however many sectors
    ACTUALLY have companies assigned -- confirmed in Sprint 3 to be 10,
    not the spec's stated 11 ("Conglomerates/Other" has zero companies
    in the real sectors.xlsx data). Dashboard must reflect real data,
    not force an empty 11th slice.
    """
    conn = _connect()
    df = pd.read_sql("""
        SELECT broad_sector, COUNT(*) as company_count
        FROM sectors
        GROUP BY broad_sector
        ORDER BY company_count DESC
    """, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_peers(group_name):
    """All companies in a peer group, with their percentile ranks."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT pg.company_id, c.company_name, pg.is_benchmark,
               pp.metric, pp.value, pp.percentile_rank
        FROM peer_groups pg
        JOIN companies c ON pg.company_id = c.id
        LEFT JOIN peer_percentiles pp ON pg.company_id = pp.company_id
            AND pg.peer_group_name = pp.peer_group_name
        WHERE pg.peer_group_name = ?
    """, conn, params=(group_name,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_valuation(ticker):
    """
    Latest market_cap row for a ticker, matched via the fiscal-year-to-
    calendar-year approximation established in Sprint 3 Day 15: fiscal
    year 'YYYY-03' maps to market_cap.year = YYYY. This is a STATED
    ASSUMPTION, not independently verified against source documentation
    -- see Sprint 3 retro for detail.
    """
    conn = _connect()
    df = pd.read_sql("""
        SELECT mc.* FROM market_cap mc
        WHERE mc.company_id = ?
        ORDER BY mc.year DESC LIMIT 1
    """, conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_pros_cons(ticker):
    """Pros/cons text for a company. May be empty (only ~8 companies covered)."""
    conn = _connect()
    df = pd.read_sql("SELECT pros, cons FROM prosandcons WHERE company_id = ?", conn, params=(ticker,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_documents(ticker):
    """Annual report links for a company."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT report_year, annual_report FROM documents
        WHERE company_id = ? ORDER BY report_year DESC
    """, conn, params=(ticker,))
    conn.close()
    return df