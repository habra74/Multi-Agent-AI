"""
tests/test_database.py
-----------------------
SQLite DB 초기화 및 schema 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import tempfile
from pathlib import Path

import pytest
from db.database import init_db, get_connection


@pytest.fixture
def tmp_db(tmp_path):
    """각 테스트마다 임시 DB 파일을 생성한다."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


class TestInitDB:

    def test_creates_file(self, tmp_db):
        assert tmp_db.exists()

    def test_watchlist_table_exists(self, tmp_db):
        with get_connection(tmp_db) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        names = [t["name"] for t in tables]
        assert "watchlist" in names

    def test_reports_table_exists(self, tmp_db):
        with get_connection(tmp_db) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        names = [t["name"] for t in tables]
        assert "reports" in names

    def test_idempotent_double_init(self, tmp_db):
        """init_db를 두 번 호출해도 오류가 없어야 한다."""
        init_db(tmp_db)  # second call — should not raise

    def test_seed_watchlist_aapl(self, tmp_db):
        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE ticker = 'AAPL'"
            ).fetchone()
        assert row is not None
        assert row["is_active"] == 1

    def test_seed_watchlist_nvda(self, tmp_db):
        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE ticker = 'NVDA'"
            ).fetchone()
        assert row is not None

    def test_seed_watchlist_samsung(self, tmp_db):
        with get_connection(tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE ticker = '005930.KS'"
            ).fetchone()
        assert row is not None
        assert row["market"] == "KR"

    def test_seed_count_is_three(self, tmp_db):
        with get_connection(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM watchlist").fetchone()["c"]
        assert count == 3

    def test_watchlist_schema_columns(self, tmp_db):
        with get_connection(tmp_db) as conn:
            row = conn.execute("SELECT * FROM watchlist LIMIT 1").fetchone()
        keys = set(row.keys())
        expected = {"id", "ticker", "display_name", "market", "style",
                    "horizon", "language", "is_active", "created_at"}
        assert expected.issubset(keys)

    def test_reports_schema_columns(self, tmp_db):
        # Insert a dummy report to inspect schema
        with get_connection(tmp_db) as conn:
            conn.execute("""
                INSERT INTO reports (ticker, display_name, final_decision, markdown_report, json_report)
                VALUES ('TEST', 'Test Co', 'HOLD', '# test', '{}')
            """)
            conn.commit()
            row = conn.execute("SELECT * FROM reports LIMIT 1").fetchone()
        keys = set(row.keys())
        expected = {"id", "ticker", "display_name", "market", "style", "horizon",
                    "language", "created_at", "final_decision", "executive_summary",
                    "markdown_report", "json_report", "confidence", "risk_score"}
        assert expected.issubset(keys)
