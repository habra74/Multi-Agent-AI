"""
tests/test_watchlist.py
------------------------
WatchlistRepository 및 ReportRepository CRUD 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest
from db.database import init_db
from db.repository import WatchlistRepository, ReportRepository


@pytest.fixture
def wl_repo(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return WatchlistRepository(db_path)


@pytest.fixture
def rp_repo(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return ReportRepository(db_path)


# ---------------------------------------------------------------------------
# WatchlistRepository tests
# ---------------------------------------------------------------------------

class TestWatchlistRepository:

    def test_list_all_returns_seed_data(self, wl_repo):
        entries = wl_repo.list_all()
        assert len(entries) == 3

    def test_list_active_all_active_by_default(self, wl_repo):
        active = wl_repo.list_active()
        assert len(active) == 3

    def test_get_existing_ticker(self, wl_repo):
        entry = wl_repo.get("AAPL")
        assert entry is not None
        assert entry["ticker"] == "AAPL"

    def test_get_nonexistent_ticker(self, wl_repo):
        entry = wl_repo.get("ZZZNOTREAL")
        assert entry is None

    def test_add_new_ticker(self, wl_repo):
        result = wl_repo.add("TSLA", "Tesla", "US", "aggressive", "short", "ko")
        assert result is True
        entry = wl_repo.get("TSLA")
        assert entry is not None
        assert entry["display_name"] == "Tesla"

    def test_add_duplicate_reactivates(self, wl_repo):
        # Deactivate first, then re-add
        wl_repo.deactivate("AAPL")
        assert wl_repo.get("AAPL")["is_active"] == 0
        wl_repo.add("AAPL")  # should reactivate
        assert wl_repo.get("AAPL")["is_active"] == 1

    def test_deactivate(self, wl_repo):
        wl_repo.deactivate("NVDA")
        entry = wl_repo.get("NVDA")
        assert entry["is_active"] == 0

    def test_deactivate_removes_from_active_list(self, wl_repo):
        wl_repo.deactivate("NVDA")
        active_tickers = [w["ticker"] for w in wl_repo.list_active()]
        assert "NVDA" not in active_tickers

    def test_activate_restores(self, wl_repo):
        wl_repo.deactivate("NVDA")
        wl_repo.activate("NVDA")
        assert wl_repo.get("NVDA")["is_active"] == 1

    def test_update_style(self, wl_repo):
        wl_repo.update("AAPL", style="aggressive")
        assert wl_repo.get("AAPL")["style"] == "aggressive"

    def test_update_language(self, wl_repo):
        wl_repo.update("AAPL", language="en")
        assert wl_repo.get("AAPL")["language"] == "en"

    def test_kr_ticker_in_seed(self, wl_repo):
        entry = wl_repo.get("005930.KS")
        assert entry is not None
        assert entry["market"] == "KR"

    def test_add_kr_ticker(self, wl_repo):
        wl_repo.add("000660.KS", "SK하이닉스", "KR", "neutral", "mid", "ko")
        entry = wl_repo.get("000660.KS")
        assert entry is not None
        assert entry["market"] == "KR"

    def test_remove_ticker(self, wl_repo):
        wl_repo.add("MSFT", "Microsoft", "US")
        assert wl_repo.get("MSFT") is not None
        wl_repo.remove("MSFT")
        assert wl_repo.get("MSFT") is None


# ---------------------------------------------------------------------------
# ReportRepository tests
# ---------------------------------------------------------------------------

_SAMPLE_JSON = {"ticker": "AAPL", "decision": {"final_decision": "BUY"}}
_SAMPLE_MD   = "# AAPL Report\n\nVerdict: BUY\n"


def _save_sample(repo: ReportRepository, ticker="AAPL", decision="BUY", confidence=0.70, risk=0.30):
    return repo.save(
        ticker           = ticker,
        display_name     = "Apple Inc.",
        market           = "US",
        style            = "neutral",
        horizon          = "mid",
        language         = "ko",
        final_decision   = decision,
        executive_summary= "Test summary",
        markdown_report  = _SAMPLE_MD,
        json_report      = _SAMPLE_JSON,
        confidence       = confidence,
        risk_score       = risk,
    )


class TestReportRepository:

    def test_save_returns_int_id(self, rp_repo):
        rid = _save_sample(rp_repo)
        assert isinstance(rid, int)
        assert rid > 0

    def test_get_by_id(self, rp_repo):
        rid = _save_sample(rp_repo)
        report = rp_repo.get_by_id(rid)
        assert report is not None
        assert report["ticker"] == "AAPL"

    def test_get_by_id_missing(self, rp_repo):
        assert rp_repo.get_by_id(99999) is None

    def test_get_by_ticker_returns_list(self, rp_repo):
        _save_sample(rp_repo, "AAPL")
        _save_sample(rp_repo, "AAPL")
        reports = rp_repo.get_by_ticker("AAPL")
        assert len(reports) == 2

    def test_get_by_ticker_newest_first(self, rp_repo):
        id1 = _save_sample(rp_repo, "AAPL", "BUY")
        id2 = _save_sample(rp_repo, "AAPL", "HOLD")
        reports = rp_repo.get_by_ticker("AAPL")
        assert reports[0]["id"] == id2  # newest first

    def test_get_by_ticker_empty_for_unknown(self, rp_repo):
        assert rp_repo.get_by_ticker("ZZZNOTREAL") == []

    def test_get_latest_by_ticker(self, rp_repo):
        _save_sample(rp_repo, "NVDA", "BUY")
        _save_sample(rp_repo, "NVDA", "STRONG BUY")
        latest = rp_repo.get_latest_by_ticker("NVDA")
        assert latest["final_decision"] == "STRONG BUY"

    def test_list_tickers(self, rp_repo):
        _save_sample(rp_repo, "AAPL")
        _save_sample(rp_repo, "NVDA")
        tickers = rp_repo.list_tickers()
        assert "AAPL" in tickers
        assert "NVDA" in tickers

    def test_json_stored_and_retrievable(self, rp_repo):
        rid = _save_sample(rp_repo)
        report = rp_repo.get_by_id(rid)
        json_raw = report["json_report"]
        data = json.loads(json_raw) if isinstance(json_raw, str) else json_raw
        assert data["ticker"] == "AAPL"

    def test_confidence_stored(self, rp_repo):
        rid = _save_sample(rp_repo, confidence=0.82)
        report = rp_repo.get_by_id(rid)
        assert abs(report["confidence"] - 0.82) < 0.001

    def test_risk_score_stored(self, rp_repo):
        rid = _save_sample(rp_repo, risk=0.55)
        report = rp_repo.get_by_id(rid)
        assert abs(report["risk_score"] - 0.55) < 0.001

    def test_kr_ticker_save(self, rp_repo):
        rid = rp_repo.save(
            ticker="005930.KS", display_name="삼성전자",
            market="KR", style="neutral", horizon="mid", language="ko",
            final_decision="BUY", executive_summary="삼성전자 분석",
            markdown_report="# 삼성전자\n", json_report={},
            confidence=0.65, risk_score=0.40,
        )
        report = rp_repo.get_by_id(rid)
        assert report["ticker"] == "005930.KS"
        assert report["market"] == "KR"
        assert report["display_name"] == "삼성전자"

    def test_delete_report(self, rp_repo):
        rid = _save_sample(rp_repo)
        assert rp_repo.delete(rid) is True
        assert rp_repo.get_by_id(rid) is None

    def test_get_all_summary(self, rp_repo):
        _save_sample(rp_repo, "AAPL")
        _save_sample(rp_repo, "NVDA")
        summaries = rp_repo.get_all_summary()
        assert len(summaries) == 2
        # Should NOT include markdown_report (that's a large field)
        # Actually get_all_summary returns lightweight rows without markdown
        for s in summaries:
            assert "ticker" in s
            assert "final_decision" in s
