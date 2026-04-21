"""
tests/test_scheduler.py
------------------------
스케줄러 로직 단위 테스트.
APScheduler 실제 실행은 하지 않고, run_daily_analysis() 함수만 테스트.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock, call

from db.database import init_db
from db.repository import WatchlistRepository, EmailLogRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db(tmp_path):
    db = tmp_path / "sched.db"
    init_db(db)
    return db


# ---------------------------------------------------------------------------
# 1. EmailLogRepository (DB 레이어 검증)
# ---------------------------------------------------------------------------

class TestEmailLogRepository:

    def test_log_success(self, test_db):
        repo = EmailLogRepository(test_db)
        log_id = repo.log("AAPL", "recv@test.com", "success")
        assert isinstance(log_id, int) and log_id > 0

    def test_log_failed_stores_error(self, test_db):
        repo = EmailLogRepository(test_db)
        log_id = repo.log("NVDA", "recv@test.com", "failed", "SMTP error")
        entry = repo.get_by_id(log_id)
        assert entry["status"] == "failed"
        assert entry["error_message"] == "SMTP error"

    def test_get_today_returns_todays_logs(self, test_db):
        repo = EmailLogRepository(test_db)
        repo.log("AAPL", "a@b.com", "success")
        repo.log("NVDA", "a@b.com", "failed", "err")
        assert len(repo.get_today()) == 2

    def test_get_all(self, test_db):
        repo = EmailLogRepository(test_db)
        repo.log("A", "a@b.com", "success")
        repo.log("B", "a@b.com", "success")
        assert len(repo.get_all()) == 2

    def test_count_today_success_only_counts_success(self, test_db):
        repo = EmailLogRepository(test_db)
        repo.log("AAPL", "a@b.com", "success")
        repo.log("NVDA", "a@b.com", "failed", "err")
        assert repo.count_today_success() == 1

    def test_schema_has_required_columns(self, test_db):
        repo = EmailLogRepository(test_db)
        log_id = repo.log("AAPL", "a@b.com", "success")
        entry = repo.get_by_id(log_id)
        required = {"id", "ticker", "sent_at", "recipient", "status", "error_message"}
        assert required.issubset(set(entry.keys()))


# ---------------------------------------------------------------------------
# 2. run_daily_analysis() 로직 테스트 (모든 외부 의존성 mock)
# ---------------------------------------------------------------------------

def _fake_result(ticker="AAPL", decision="BUY", report_id=1):
    return {
        "report_id": report_id,
        "results": {
            "ticker": ticker,
            "decision": {"final_decision": decision, "confidence": 0.70},
            "risk_analysis": {"risk_score": 0.30},
        },
        "markdown_report": "# Report",
        "json_data": {},
    }


def _fake_report_row(report_id=1, ticker="AAPL"):
    return {
        "id": report_id, "ticker": ticker, "display_name": ticker,
        "final_decision": "BUY", "confidence": 0.70, "risk_score": 0.30,
        "executive_summary": "요약", "json_report": "{}", "created_at": "2026-04-07",
    }


class TestRunDailyAnalysis:
    """
    스케줄러의 run_daily_analysis() 를 직접 import 하지 않고
    scheduler.scheduler 모듈을 매번 reload 하는 방식으로 격리.
    """

    def _run(self, test_db, analyze_results, email_ok=True):
        """
        run_daily_analysis() 실행을 위한 헬퍼.
        - analyze_and_store : analyze_results 리스트 순서대로 반환/raise
        - send_daily_report : email_ok 반환
        - DB 경로 : test_db
        """
        import sys
        import importlib

        wl_repo = WatchlistRepository(test_db)

        mock_analyze = MagicMock(side_effect=analyze_results)
        mock_email   = MagicMock(return_value=email_ok)
        mock_rp_inst = MagicMock()
        mock_rp_inst.get_by_id.side_effect = (
            lambda rid: _fake_report_row(rid)
        )

        # Stub out apscheduler if not installed so the import doesn't fail
        _apscheduler_stubs = {}
        _aps_mods = [
            "apscheduler",
            "apscheduler.schedulers",
            "apscheduler.schedulers.blocking",
            "apscheduler.triggers",
            "apscheduler.triggers.cron",
            "apscheduler.events",
        ]
        for _m in _aps_mods:
            if _m not in sys.modules:
                _apscheduler_stubs[_m] = MagicMock()
                sys.modules[_m] = _apscheduler_stubs[_m]

        # Ensure scheduler.scheduler is imported (Python 3.13+: patch needs it
        # already in sys.modules before the context manager is entered).
        if "scheduler.scheduler" in sys.modules:
            del sys.modules["scheduler.scheduler"]
        import scheduler.scheduler as mod  # noqa: E402

        with patch("scheduler.scheduler.DB_PATH",             test_db), \
             patch("scheduler.scheduler.init_db",             MagicMock()), \
             patch("scheduler.scheduler.WatchlistRepository", return_value=wl_repo), \
             patch("scheduler.scheduler.ReportRepository",    return_value=mock_rp_inst), \
             patch("scheduler.scheduler.analyze_and_store",   mock_analyze), \
             patch("scheduler.scheduler.send_daily_report",   mock_email):

            mod.run_daily_analysis()

        # Clean up stubs so they don't leak into other tests
        for _m in _apscheduler_stubs:
            sys.modules.pop(_m, None)
        if "scheduler.scheduler" in sys.modules:
            del sys.modules["scheduler.scheduler"]

        return mock_analyze, mock_email

    def test_analyzes_all_active_tickers(self, test_db):
        results = [
            _fake_result("AAPL",      report_id=1),
            _fake_result("NVDA",      report_id=2),
            _fake_result("005930.KS", report_id=3),
        ]
        mock_analyze, _ = self._run(test_db, results)
        assert mock_analyze.call_count == 3

    def test_one_failure_continues_others(self, test_db):
        results = [
            Exception("오류"),
            _fake_result("NVDA",      report_id=2),
            _fake_result("005930.KS", report_id=3),
        ]
        mock_analyze, _ = self._run(test_db, results)
        # 3번 모두 시도해야 함
        assert mock_analyze.call_count == 3

    def test_all_fail_no_email_sent(self, test_db):
        results = [Exception("e1"), Exception("e2"), Exception("e3")]
        _, mock_email = self._run(test_db, results)
        mock_email.assert_not_called()

    def test_email_called_with_successful_reports(self, test_db):
        results = [_fake_result("AAPL", report_id=1)]
        _, mock_email = self._run(test_db, results)
        mock_email.assert_called_once()

    def test_email_failure_does_not_crash(self, test_db):
        results = [_fake_result("AAPL", report_id=1)]
        # email_ok=False → 발송 실패
        self._run(test_db, results, email_ok=False)
        # 예외 없이 완료되어야 함

    def test_empty_watchlist_skips_everything(self, test_db):
        # 전부 비활성화
        wl = WatchlistRepository(test_db)
        for entry in wl.list_active():
            wl.deactivate(entry["ticker"])

        mock_analyze, mock_email = self._run(test_db, [])
        mock_analyze.assert_not_called()
        mock_email.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Config 검증
# ---------------------------------------------------------------------------

class TestSchedulerConfig:

    def test_scheduler_time_is_valid_hhmm(self):
        from config import SCHEDULER_TIME
        parts = SCHEDULER_TIME.split(":")
        assert len(parts) == 2 and all(p.isdigit() for p in parts)
        h, m = int(parts[0]), int(parts[1])
        assert 0 <= h <= 23 and 0 <= m <= 59

    def test_scheduler_default_is_0700(self):
        """환경 변수 미설정 시 기본값은 07:00."""
        saved = os.environ.pop("SCHEDULER_TIME", None)
        try:
            import importlib, config
            importlib.reload(config)
            assert config.SCHEDULER_TIME == "07:00"
        finally:
            if saved is not None:
                os.environ["SCHEDULER_TIME"] = saved
            import importlib, config
            importlib.reload(config)

    def test_smtp_config_keys_exist(self):
        import config
        assert hasattr(config, "SMTP_HOST")
        assert hasattr(config, "SMTP_PORT")
        assert hasattr(config, "SMTP_USER")
        assert hasattr(config, "SMTP_PASSWORD")
        assert hasattr(config, "SENDER_EMAIL")
        assert hasattr(config, "RECIPIENT_EMAIL")

    def test_base_url_exists(self):
        import config
        assert hasattr(config, "BASE_URL")
        assert config.BASE_URL.startswith("http")
