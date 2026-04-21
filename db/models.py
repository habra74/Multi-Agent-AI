"""
db/models.py
------------
SQLite schema DDL for the investment analysis system.

Tables:
  - watchlist   : tickers the user wants to track
  - reports     : analysis results, one row per run
  - email_logs  : email send history and status
"""

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

CREATE_WATCHLIST_TABLE = """
CREATE TABLE IF NOT EXISTS watchlist (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL UNIQUE,
    display_name TEXT    NOT NULL DEFAULT '',
    market       TEXT    NOT NULL DEFAULT 'US',
    style        TEXT    NOT NULL DEFAULT 'neutral',
    horizon      TEXT    NOT NULL DEFAULT 'mid',
    language     TEXT    NOT NULL DEFAULT 'ko',
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

CREATE_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker            TEXT    NOT NULL,
    display_name      TEXT    NOT NULL DEFAULT '',
    market            TEXT    NOT NULL DEFAULT 'US',
    style             TEXT    NOT NULL DEFAULT 'neutral',
    horizon           TEXT    NOT NULL DEFAULT 'mid',
    language          TEXT    NOT NULL DEFAULT 'ko',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    final_decision    TEXT,
    executive_summary TEXT,
    markdown_report   TEXT,
    json_report       TEXT,
    confidence        REAL    DEFAULT 0.0,
    risk_score        REAL    DEFAULT 0.0
);
"""

CREATE_EMAIL_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS email_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT    NOT NULL DEFAULT '',
    sent_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    recipient     TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'pending',
    error_message TEXT    DEFAULT ''
);
"""

# Indexes
CREATE_REPORTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reports_ticker_date
    ON reports (ticker, created_at DESC);
"""

CREATE_EMAIL_LOGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at
    ON email_logs (sent_at DESC);
"""

CREATE_APP_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

CREATE_APP_SETTINGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_app_settings_key
    ON app_settings (key);
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_WATCHLIST = [
    ("AAPL",      "Apple Inc.",    "US", "neutral", "mid", "ko"),
    ("NVDA",      "NVIDIA",        "US", "neutral", "mid", "ko"),
    ("005930.KS", "삼성전자",       "KR", "neutral", "mid", "ko"),
]

SEED_APP_SETTINGS = [
    ("primary_recipient", ""),
    ("cc_recipients",     ""),
    ("base_url",          "http://localhost:8501"),
    ("scheduler_time",    "07:00"),
]
