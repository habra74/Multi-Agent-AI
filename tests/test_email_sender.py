"""
tests/test_email_sender.py
---------------------------
EmailSender 및 HTML 빌더 단위 테스트.
SMTP 실제 발송은 하지 않음 (mock 사용).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest
from unittest.mock import patch, MagicMock

from email_service.email_sender import (
    build_ticker_card,
    build_html_email,
    EmailSender,
    send_daily_report,
    _conf_label,
    _html_list,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ROW = {
    "id":               1,
    "ticker":           "AAPL",
    "display_name":     "Apple Inc.",
    "market":           "US",
    "style":            "neutral",
    "horizon":          "mid",
    "language":         "ko",
    "created_at":       "2026-04-07 07:00:00",
    "final_decision":   "BUY",
    "executive_summary": "애플은 강한 브랜드와 서비스 매출 성장을 바탕으로 안정적인 성장세를 유지하고 있습니다.",
    "confidence":       0.72,
    "risk_score":       0.35,
    "json_report": json.dumps({
        "decision": {
            "bull_points":  ["서비스 매출 고성장", "탄탄한 현금흐름"],
            "bear_points":  ["중국 시장 불확실성", "밸류에이션 부담"],
            "action_items": ["실적 발표 모니터링", "SMA50 지지 여부 확인"],
        }
    }),
}

SAMPLE_ROW_KR = {
    "id":               2,
    "ticker":           "005930.KS",
    "display_name":     "삼성전자",
    "market":           "KR",
    "style":            "neutral",
    "horizon":          "mid",
    "language":         "ko",
    "created_at":       "2026-04-07 07:05:00",
    "final_decision":   "HOLD",
    "executive_summary": "반도체 업황 회복 기대감은 있으나 단기 모멘텀은 약합니다.",
    "confidence":       0.58,
    "risk_score":       0.50,
    "json_report": json.dumps({
        "decision": {
            "bull_points":  ["HBM 수요 증가"],
            "bear_points":  ["환율 부담"],
            "action_items": ["실적 가이던스 확인"],
        }
    }),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_conf_label_very_high(self):
        assert "매우 높음" in _conf_label(0.85)

    def test_conf_label_high(self):
        assert "높음" in _conf_label(0.70)

    def test_conf_label_moderate(self):
        assert "보통" in _conf_label(0.50)

    def test_conf_label_low(self):
        assert "낮음" in _conf_label(0.30)

    def test_conf_label_very_low(self):
        assert "매우 낮음" in _conf_label(0.10)

    def test_html_list_normal(self):
        html = _html_list(["항목1", "항목2"])
        assert "<li>항목1</li>" in html
        assert "<li>항목2</li>" in html

    def test_html_list_empty(self):
        html = _html_list([])
        assert "없음" in html or "color:#aaa" in html

    def test_html_list_xss_escaped(self):
        html = _html_list(["<script>alert(1)</script>"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# build_ticker_card
# ---------------------------------------------------------------------------

class TestBuildTickerCard:

    def test_returns_string(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert isinstance(card, str)
        assert len(card) > 0

    def test_contains_ticker(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "AAPL" in card

    def test_contains_display_name(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "Apple Inc." in card

    def test_contains_verdict_ko(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "매수 고려" in card   # BUY → 매수 고려

    def test_contains_executive_summary(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "애플은 강한 브랜드" in card

    def test_contains_bull_points(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "서비스 매출 고성장" in card

    def test_contains_bear_points(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "중국 시장 불확실성" in card

    def test_contains_action_items(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "실적 발표 모니터링" in card

    def test_kr_ticker(self):
        card = build_ticker_card(SAMPLE_ROW_KR)
        assert "005930.KS" in card
        assert "삼성전자" in card

    def test_hold_verdict(self):
        card = build_ticker_card(SAMPLE_ROW_KR)
        assert "보유/관망" in card   # HOLD → 보유/관망

    def test_verdict_css_class_buy(self):
        card = build_ticker_card(SAMPLE_ROW)
        assert "verdict-BUY" in card

    def test_verdict_css_class_hold(self):
        card = build_ticker_card(SAMPLE_ROW_KR)
        assert "verdict-HOLD" in card

    def test_empty_json_report_safe(self):
        row = {**SAMPLE_ROW, "json_report": "{}"}
        card = build_ticker_card(row)
        assert "AAPL" in card   # Should not crash

    def test_invalid_json_report_safe(self):
        row = {**SAMPLE_ROW, "json_report": "not-json"}
        card = build_ticker_card(row)
        assert "AAPL" in card   # Should not crash


# ---------------------------------------------------------------------------
# build_html_email
# ---------------------------------------------------------------------------

class TestBuildHtmlEmail:

    def test_returns_string(self):
        html = build_html_email([SAMPLE_ROW, SAMPLE_ROW_KR])
        assert isinstance(html, str)
        assert len(html) > 100

    def test_contains_report_date(self):
        from datetime import date
        html = build_html_email([SAMPLE_ROW])
        today = date.today().strftime("%Y년")
        assert today in html

    def test_contains_ticker_count(self):
        html = build_html_email([SAMPLE_ROW, SAMPLE_ROW_KR])
        assert "2개 종목" in html

    def test_contains_dashboard_url(self):
        html = build_html_email([SAMPLE_ROW])
        assert "localhost" in html or "http" in html

    def test_empty_rows_safe(self):
        html = build_html_email([])
        assert "0개 종목" in html

    def test_utf8_encodable(self):
        html = build_html_email([SAMPLE_ROW, SAMPLE_ROW_KR])
        # Should not raise
        encoded = html.encode("utf-8")
        assert len(encoded) > 0

    def test_is_valid_html_structure(self):
        html = build_html_email([SAMPLE_ROW])
        assert "<!DOCTYPE html>" in html
        assert "<body>" in html
        assert "</body>" in html


# ---------------------------------------------------------------------------
# EmailSender
# ---------------------------------------------------------------------------

class TestEmailSender:

    def test_not_configured_without_credentials(self):
        sender = EmailSender(smtp_host="", smtp_user="", smtp_password="")
        assert sender.is_configured is False

    def test_configured_with_credentials(self):
        sender = EmailSender(
            smtp_host="smtp.gmail.com",
            smtp_user="test@gmail.com",
            smtp_password="secret",
        )
        assert sender.is_configured is True

    def test_send_unconfigured_returns_false(self):
        sender = EmailSender(smtp_host="", smtp_user="", smtp_password="")
        ok, err = sender.send("제목", "<p>본문</p>", "to@example.com")
        assert ok is False
        assert err  # error message not empty

    def test_send_no_recipient_returns_false(self):
        sender = EmailSender(
            smtp_host="smtp.gmail.com",
            smtp_user="user@example.com",
            smtp_password="pass",
        )
        ok, err = sender.send("제목", "<p>본문</p>", "")
        assert ok is False

    @patch("smtplib.SMTP")
    def test_send_success_mock(self, mock_smtp_cls):
        """Mock SMTP 연결로 발송 성공 시뮬레이션."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__  = MagicMock(return_value=False)

        sender = EmailSender(
            smtp_host="smtp.test.com",
            smtp_user="user@test.com",
            smtp_password="testpw",
            sender_email="user@test.com",
        )
        ok, err = sender.send("테스트 제목", "<p>테스트</p>", "recv@test.com")
        assert ok is True
        assert err == ""

    @patch("smtplib.SMTP", side_effect=ConnectionRefusedError("Connection refused"))
    def test_send_connection_error_returns_false(self, _):
        sender = EmailSender(
            smtp_host="smtp.test.com",
            smtp_user="user@test.com",
            smtp_password="testpw",
        )
        ok, err = sender.send("제목", "<p>내용</p>", "recv@test.com", retries=0)
        assert ok is False
        assert "Connection refused" in err or err


# ---------------------------------------------------------------------------
# send_daily_report (integration-level, mocked SMTP)
# ---------------------------------------------------------------------------

class TestSendDailyReport:

    def test_empty_rows_returns_false(self, tmp_path):
        db = tmp_path / "test.db"
        from db.database import init_db
        init_db(db)
        result = send_daily_report([], db_path=db)
        assert result is False

    @patch("email_service.email_sender.EmailSender.send", return_value=(True, ""))
    def test_sends_email_when_rows_present(self, mock_send, tmp_path):
        db = tmp_path / "test.db"
        from db.database import init_db
        init_db(db)
        result = send_daily_report([SAMPLE_ROW], recipient="to@test.com", db_path=db)
        assert result is True
        mock_send.assert_called_once()

    @patch("email_service.email_sender.EmailSender.send", return_value=(False, "SMTP error"))
    def test_logs_failure_to_db(self, mock_send, tmp_path):
        db = tmp_path / "test.db"
        from db.database import init_db
        from db.repository import EmailLogRepository
        init_db(db)
        send_daily_report([SAMPLE_ROW], recipient="to@test.com", db_path=db)
        logs = EmailLogRepository(db).get_all()
        assert len(logs) == 1
        assert logs[0]["status"] == "failed"

    @patch("email_service.email_sender.EmailSender.send", return_value=(True, ""))
    def test_logs_success_to_db(self, mock_send, tmp_path):
        db = tmp_path / "test.db"
        from db.database import init_db
        from db.repository import EmailLogRepository
        init_db(db)
        send_daily_report([SAMPLE_ROW, SAMPLE_ROW_KR], recipient="to@test.com", db_path=db)
        logs = EmailLogRepository(db).get_all()
        assert len(logs) == 1
        assert logs[0]["status"] == "success"
        assert "AAPL" in logs[0]["ticker"]
