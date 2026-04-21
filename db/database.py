"""
db/database.py
--------------
SQLite connection management and schema initialisation.

Usage:
    from db.database import get_connection, init_db
    from config import DB_PATH

    init_db(DB_PATH)          # create tables + seed data (idempotent)

    with get_connection(DB_PATH) as conn:
        conn.execute("SELECT ...")
"""

import sqlite3
import logging
from pathlib import Path
from typing import Union

from db.models import (
    CREATE_WATCHLIST_TABLE,
    CREATE_REPORTS_TABLE,
    CREATE_REPORTS_INDEX,
    CREATE_EMAIL_LOGS_TABLE,
    CREATE_EMAIL_LOGS_INDEX,
    CREATE_APP_SETTINGS_TABLE,
    CREATE_APP_SETTINGS_INDEX,
    SEED_WATCHLIST,
    SEED_APP_SETTINGS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    """
    Return a sqlite3 connection with row_factory set to sqlite3.Row
    (enables column-name access) and foreign keys enabled.

    The caller is responsible for closing / using as context manager.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: Union[str, Path]) -> None:
    """
    Create tables and insert seed data if they don't already exist.
    Safe to call multiple times (idempotent).
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db_path) as conn:
        # Create tables
        conn.execute(CREATE_WATCHLIST_TABLE)
        conn.execute(CREATE_REPORTS_TABLE)
        conn.execute(CREATE_EMAIL_LOGS_TABLE)
        conn.execute(CREATE_APP_SETTINGS_TABLE)

        # Create indexes
        conn.execute(CREATE_REPORTS_INDEX)
        conn.execute(CREATE_EMAIL_LOGS_INDEX)
        conn.execute(CREATE_APP_SETTINGS_INDEX)

        # Insert seed watchlist entries (skip if ticker already exists)
        for ticker, display_name, market, style, horizon, language in SEED_WATCHLIST:
            conn.execute(
                """
                INSERT OR IGNORE INTO watchlist
                    (ticker, display_name, market, style, horizon, language, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (ticker, display_name, market, style, horizon, language),
            )

        # Insert seed app_settings (skip if key already exists)
        for key, value in SEED_APP_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        conn.commit()

    logger.info(f"Database initialised at: {db_path}")
