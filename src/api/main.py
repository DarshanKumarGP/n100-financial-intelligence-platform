"""
N100 Financial Intelligence Platform
Sprint 6, Day 38: FastAPI Server Scaffold
Sprint 6, Day 40: HTTP 400 validation handler added

Location: src/api/main.py

Run with: uvicorn src.api.main:app --port 8000 --reload
Docs at:  http://localhost:8000/docs

Spec says "health endpoint returns db_row_counts for all 10 tables" --
confirmed 2026-09 the database actually has 14 tables:
companies, profitandloss, balancesheet, cashflow, analysis, documents,
prosandcons, sectors, stock_prices, market_cap, financial_ratios_source,
peer_groups, financial_ratios, peer_percentiles.
/health reports row counts for all 14 real tables, not a picked subset
of 10 -- same "verify against reality, don't force the spec's number"
approach as the sector-count finding from Sprints 1-5.

Day 38 scope (scaffold): app instance, CORS, request-logging middleware,
routers/ package with 8 router files registered under /api/v1.

Day 40 addition: FastAPI's default response to a malformed query param
(e.g. min_roe=notanumber) is HTTP 422. The screener spec explicitly
wants HTTP 400 ("return HTTP 400 for invalid parameter values"), so a
global exception handler converts 422 validation errors to 400 to match
the literal spec ask, rather than leaving FastAPI's default.
"""

import sqlite3
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.api.routers import (
    companies,
    documents,
    health,
    peers,
    portfolio,
    screener,
    sectors,
    valuation,
)

DB_PATH = "data/nifty100.db"
APP_VERSION = "1.0.0-sprint6"
_start_time = time.monotonic()


def get_db_connection():
    """Opens a fresh SQLite connection per call -- simple, stateless,
    matches the pattern every other script in this project already
    uses (sqlite3.connect() per script run), rather than introducing
    a connection pool this project has never needed before."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


app = FastAPI(
    title="N100 Financial Intelligence Platform API",
    description="REST API over the Nifty 100 financial intelligence warehouse.",
    version=APP_VERSION,
)

# CORS: allow all origins -- internal use only, per spec instruction.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs method, path, and response time for every request, per spec."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    print(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    FastAPI's default response to a malformed query param is HTTP 422.
    Spec explicitly wants 400 ("return HTTP 400 for invalid parameter
    values") -- converting here rather than leaving 422, since the spec
    text is specific about the code.
    """
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


# Make shared helpers available to routers without circular imports
app.state.get_db_connection = get_db_connection
app.state.start_time = _start_time
app.state.version = APP_VERSION

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(companies.router, prefix="/api/v1", tags=["companies"])
app.include_router(screener.router, prefix="/api/v1", tags=["screener"])
app.include_router(sectors.router, prefix="/api/v1", tags=["sectors"])
app.include_router(peers.router, prefix="/api/v1", tags=["peers"])
app.include_router(valuation.router, prefix="/api/v1", tags=["valuation"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
