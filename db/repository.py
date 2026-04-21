"""
db/repository.py
----------------
Repository pattern for database access.

Classes:
  WatchlistRepository  – CRUD for the watchlist table
  ReportRepository     – CRUD for the reports table
  EmailLogRepository   – CRUD for the email_logs table
"""

import json
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _rows_to_list(rows) -> List[Dict[str, Any]]:
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# WatchlistRepository
# ---------------------------------------------------------------------------

class WatchlistRepository:
    """Manages the watchlist table."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)

    def _conn(self):
        from db.database import get_connection
        return get_connection(self.db_path)

    # ---- Read ---------------------------------------------------------------

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all watchlist entries (active + inactive)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist ORDER BY is_active DESC, ticker ASC"
            ).fetchall()
        return _rows_to_list(rows)

    def list_active(self) -> List[Dict[str, Any]]:
        """Return only active watchlist entries."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE is_active = 1 ORDER BY ticker ASC"
            ).fetchall()
        return _rows_to_list(rows)

    def get(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Return watchlist entry for a given ticker, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE ticker = ?", (ticker,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    # ---- Write --------------------------------------------------------------

    def add(
        self,
        ticker: str,
        display_name: str = "",
        market: str = "US",
        style: str = "neutral",
        horizon: str = "mid",
        language: str = "ko",
    ) -> bool:
        """
        Add ticker to watchlist.
        Returns True if inserted, False if ticker already exists (upsert skipped).
        """
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO watchlist
                        (ticker, display_name, market, style, horizon, language, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (ticker, display_name, market, style, horizon, language),
                )
                conn.commit()
            logger.info(f"Watchlist: added {ticker}")
            return True
        except sqlite3.IntegrityError:
            # UNIQUE constraint → already exists, reactivate instead
            with self._conn() as conn:
                conn.execute(
                    "UPDATE watchlist SET is_active = 1 WHERE ticker = ?", (ticker,)
                )
                conn.commit()
            logger.info(f"Watchlist: reactivated {ticker}")
            return False

    def update(
        self,
        ticker: str,
        display_name: Optional[str] = None,
        market: Optional[str] = None,
        style: Optional[str] = None,
        horizon: Optional[str] = None,
        language: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """Update one or more fields for an existing ticker. Returns True if updated."""
        fields = []
        params: List[Any] = []

        if display_name is not None:
            fields.append("display_name = ?"); params.append(display_name)
        if market is not None:
            fields.append("market = ?"); params.append(market)
        if style is not None:
            fields.append("style = ?"); params.append(style)
        if horizon is not None:
            fields.append("horizon = ?"); params.append(horizon)
        if language is not None:
            fields.append("language = ?"); params.append(language)
        if is_active is not None:
            fields.append("is_active = ?"); params.append(1 if is_active else 0)

        if not fields:
            return False

        params.append(ticker)
        sql = f"UPDATE watchlist SET {', '.join(fields)} WHERE ticker = ?"

        with self._conn() as conn:
            cur = conn.execute(sql, params)
            conn.commit()

        updated = cur.rowcount > 0
        if updated:
            logger.info(f"Watchlist: updated {ticker} ({', '.join(fields)})")
        return updated

    def deactivate(self, ticker: str) -> bool:
        """Set is_active=0 for a ticker. Returns True if updated."""
        return self.update(ticker, is_active=False)

    def activate(self, ticker: str) -> bool:
        """Set is_active=1 for a ticker. Returns True if updated."""
        return self.update(ticker, is_active=True)

    def remove(self, ticker: str) -> bool:
        """Permanently delete ticker from watchlist."""
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
            conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# ReportRepository
# ---------------------------------------------------------------------------

class ReportRepository:
    """Manages the reports table."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)

    def _conn(self):
        from db.database import get_connection
        return get_connection(self.db_path)

    # ---- Write --------------------------------------------------------------

    def save(
        self,
        ticker: str,
        display_name: str,
        market: str,
        style: str,
        horizon: str,
        language: str,
        final_decision: str,
        executive_summary: str,
        markdown_report: str,
        json_report: Dict[str, Any],
        confidence: float,
        risk_score: float,
    ) -> int:
        """
        Insert a new report row.
        Returns the new row's id.
        """
        json_str = json.dumps(json_report, ensure_ascii=False, default=str)

        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO reports
                    (ticker, display_name, market, style, horizon, language,
                     final_decision, executive_summary, markdown_report,
                     json_report, confidence, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker, display_name, market, style, horizon, language,
                    final_decision, executive_summary, markdown_report,
                    json_str, confidence, risk_score,
                ),
            )
            conn.commit()
            new_id = cur.lastrowid

        logger.info(f"Report saved: id={new_id} ticker={ticker} decision={final_decision}")
        return new_id

    # ---- Read ---------------------------------------------------------------

    def get_by_id(self, report_id: int) -> Optional[Dict[str, Any]]:
        """Return single report by primary key."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE id = ?", (report_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def get_today(self) -> List[Dict[str, Any]]:
        """Return all reports created today (local date)."""
        today = date.today().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, ticker, display_name, market, style, horizon,
                       language, created_at, final_decision, confidence, risk_score
                FROM reports
                WHERE DATE(created_at) = ?
                ORDER BY created_at DESC
                """,
                (today,),
            ).fetchall()
        return _rows_to_list(rows)

    def get_by_ticker(
        self,
        ticker: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return reports for a ticker, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, ticker, display_name, market, style, horizon,
                       language, created_at, final_decision, confidence, risk_score
                FROM reports
                WHERE ticker = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (ticker, limit),
            ).fetchall()
        return _rows_to_list(rows)

    def get_latest_by_ticker(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Return the most recent report for a ticker (full row including markdown)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE ticker = ? ORDER BY id DESC LIMIT 1",
                (ticker,),
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_tickers(self) -> List[str]:
        """Return distinct tickers that have at least one saved report."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM reports ORDER BY ticker ASC"
            ).fetchall()
        return [r["ticker"] for r in rows]

    def get_all_summary(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return lightweight summary rows for all reports."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, ticker, display_name, market, style, horizon,
                       language, created_at, final_decision, confidence, risk_score
                FROM reports
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return _rows_to_list(rows)

    def delete(self, report_id: int) -> bool:
        """Delete a report by id."""
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
            conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# EmailLogRepository
# ---------------------------------------------------------------------------

class EmailLogRepository:
    """Manages the email_logs table."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)

    def _conn(self):
        from db.database import get_connection
        return get_connection(self.db_path)

    # ---- Write --------------------------------------------------------------

    def log(
        self,
        ticker: str,
        recipient: str,
        status: str,
        error_message: str = "",
    ) -> int:
        """
        Insert a new email log row.

        Parameters
        ----------
        ticker        : ticker symbol (or '' for a batch/summary email)
        recipient     : recipient email address
        status        : 'success' | 'failed' | 'skipped'
        error_message : error detail if status == 'failed'

        Returns the new row's id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO email_logs (ticker, recipient, status, error_message)
                VALUES (?, ?, ?, ?)
                """,
                (ticker, recipient, status, error_message),
            )
            conn.commit()
            new_id = cur.lastrowid

        logger.info(f"Email log saved: id={new_id} ticker={ticker} status={status}")
        return new_id

    # ---- Read ---------------------------------------------------------------

    def get_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM email_logs WHERE id = ?", (log_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def get_today(self) -> List[Dict[str, Any]]:
        """Return all email log entries from today."""
        today = date.today().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM email_logs
                WHERE DATE(sent_at) = ?
                ORDER BY sent_at DESC
                """,
                (today,),
            ).fetchall()
        return _rows_to_list(rows)

    def get_all(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return recent email log entries, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM email_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return _rows_to_list(rows)

    def count_today_success(self) -> int:
        """Return count of successfully sent emails today."""
        today = date.today().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM email_logs
                WHERE DATE(sent_at) = ? AND status = 'success'
                """,
                (today,),
            ).fetchone()
        return row["c"] if row else 0


# ---------------------------------------------------------------------------
# SettingsRepository
# ---------------------------------------------------------------------------

class SettingsRepository:
    """
    Key-value settings store backed by the app_settings table.

    Supported keys (seeded on init_db):
        primary_recipient  – main email recipient
        cc_recipients      – comma-separated additional recipients
        base_url           – dashboard URL (default: http://localhost:8501)
        scheduler_time     – daily analysis time in HH:MM (default: 07:00)
    """

    _DEFAULTS: Dict[str, str] = {
        "primary_recipient": "",
        "cc_recipients":     "",
        "base_url":          "http://localhost:8501",
        "scheduler_time":    "07:00",
    }

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = str(db_path)

    def _conn(self):
        from db.database import get_connection
        return get_connection(self.db_path)

    # ---- Read ---------------------------------------------------------------

    def get(self, key: str, default: Optional[str] = None) -> str:
        """Return the stored value for key, or default (falls back to built-in default)."""
        fallback = default if default is not None else self._DEFAULTS.get(key, "")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return fallback
        return row["value"] if row["value"] is not None else fallback

    def get_all(self) -> Dict[str, str]:
        """Return all settings as a dict."""
        with self._conn() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        result = dict(self._DEFAULTS)
        result.update({r["key"]: r["value"] for r in rows})
        return result

    def get_recipients(self) -> Dict[str, Any]:
        """
        Return recipient info as:
            { "primary": str, "cc_list": List[str] }
        """
        primary = self.get("primary_recipient", "")
        cc_raw  = self.get("cc_recipients", "")
        cc_list = [e.strip() for e in cc_raw.split(",") if e.strip()] if cc_raw else []
        return {"primary": primary, "cc_list": cc_list}

    # ---- Write --------------------------------------------------------------

    def set(self, key: str, value: str) -> None:
        """Insert or update a setting value."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, datetime('now','localtime'))
                ON CONFLICT(key) DO UPDATE SET
                    value      = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value),
            )
            conn.commit()
        logger.info(f"Settings: {key} = {value!r}")

    def set_recipients(self, primary: str, cc_list: List[str]) -> None:
        """Convenience: save primary + cc recipients in one call."""
        self.set("primary_recipient", primary.strip())
        self.set("cc_recipients", ",".join(e.strip() for e in cc_list if e.strip()))
