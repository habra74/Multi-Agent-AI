"""
tests/test_phase6.py
--------------------
Phase 6 기능 단위 테스트.

커버리지:
  1. SettingsRepository  – get / set / get_all / get_recipients / set_recipients
  2. init_db             – app_settings 시드 데이터 확인
  3. _format_price       – KR(원) / US($) 포맷
  4. build_ticker_card   – 뉴스 섹션 (link / interpretation 포함)
  5. build_html_email    – base_url 파라미터 반영
  6. send_daily_report   – DB 설정에서 수신자 조회
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path):
    """Initialize a fresh test DB and return its path."""
    db = tmp_path / "test_phase6.db"
    from db.database import init_db
    init_db(db)
    return db


# ===========================================================================
# 1. SettingsRepository
# ===========================================================================

class TestSettingsRepository:

    # ── get ──────────────────────────────────────────────────────────────────

    def test_get_seeded_default_base_url(self, tmp_path):
        """init_db 후 base_url 기본값이 http://localhost:8501 이어야 한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        assert s.get("base_url") == "http://localhost:8501"

    def test_get_seeded_default_scheduler_time(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        assert s.get("scheduler_time") == "07:00"

    def test_get_missing_key_uses_builtin_default(self, tmp_path):
        """DB에 없는 키는 _DEFAULTS 값으로 폴백해야 한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        assert s.get("primary_recipient") == ""

    def test_get_missing_key_uses_caller_default(self, tmp_path):
        """DB에도, _DEFAULTS에도 없는 키는 caller 기본값을 반환해야 한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        result = s.get("nonexistent_key", default="fallback_value")
        assert result == "fallback_value"

    # ── set ──────────────────────────────────────────────────────────────────

    def test_set_and_get_roundtrip(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set("base_url", "http://myserver:9000")
        assert s.get("base_url") == "http://myserver:9000"

    def test_set_upsert_overwrites(self, tmp_path):
        """같은 키에 두 번 set하면 마지막 값이 남아야 한다 (upsert)."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set("scheduler_time", "08:00")
        s.set("scheduler_time", "09:30")
        assert s.get("scheduler_time") == "09:30"

    def test_set_new_custom_key(self, tmp_path):
        """사전에 정의되지 않은 키도 저장·조회 가능해야 한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set("custom_flag", "enabled")
        assert s.get("custom_flag") == "enabled"

    # ── get_all ──────────────────────────────────────────────────────────────

    def test_get_all_returns_dict(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        result = s.get_all()
        assert isinstance(result, dict)

    def test_get_all_contains_seeded_keys(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        result = s.get_all()
        for key in ("primary_recipient", "cc_recipients", "base_url", "scheduler_time"):
            assert key in result

    def test_get_all_reflects_updates(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set("base_url", "http://updated:8888")
        result = s.get_all()
        assert result["base_url"] == "http://updated:8888"

    # ── get_recipients ────────────────────────────────────────────────────────

    def test_get_recipients_empty_by_default(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        r = s.get_recipients()
        assert r["primary"] == ""
        assert r["cc_list"] == []

    def test_get_recipients_after_set(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set("primary_recipient", "user@example.com")
        r = s.get_recipients()
        assert r["primary"] == "user@example.com"

    def test_get_recipients_cc_list_parsed(self, tmp_path):
        """cc_recipients 는 쉼표 구분 문자열로 저장되고 리스트로 파싱돼야 한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set("cc_recipients", "a@x.com, b@x.com, c@x.com")
        r = s.get_recipients()
        assert r["cc_list"] == ["a@x.com", "b@x.com", "c@x.com"]

    # ── set_recipients ────────────────────────────────────────────────────────

    def test_set_recipients_roundtrip(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set_recipients("main@example.com", ["cc1@x.com", "cc2@x.com"])
        r = s.get_recipients()
        assert r["primary"] == "main@example.com"
        assert "cc1@x.com" in r["cc_list"]
        assert "cc2@x.com" in r["cc_list"]

    def test_set_recipients_empty_cc(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set_recipients("only@example.com", [])
        r = s.get_recipients()
        assert r["primary"] == "only@example.com"
        assert r["cc_list"] == []

    def test_set_recipients_strips_whitespace(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        s.set_recipients("  main@example.com  ", ["  cc@x.com  "])
        r = s.get_recipients()
        assert r["primary"] == "main@example.com"
        assert r["cc_list"] == ["cc@x.com"]


# ===========================================================================
# 2. init_db – app_settings 시드 데이터
# ===========================================================================

class TestInitDbAppSettings:

    def test_app_settings_table_created(self, tmp_path):
        db = _make_db(tmp_path)
        import sqlite3
        conn = sqlite3.connect(str(db))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "app_settings" in tables

    def test_seed_keys_present(self, tmp_path):
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        s = SettingsRepository(db)
        for key in ("primary_recipient", "cc_recipients", "base_url", "scheduler_time"):
            # Should not raise; each key should return some string
            val = s.get(key)
            assert isinstance(val, str)

    def test_init_db_idempotent(self, tmp_path):
        """init_db를 두 번 호출해도 중복 오류 없이 동작해야 한다."""
        db = _make_db(tmp_path)
        from db.database import init_db
        init_db(db)   # second call
        from db.repository import SettingsRepository
        assert SettingsRepository(db).get("base_url") == "http://localhost:8501"


# ===========================================================================
# 3. _format_price – KR(원) / US($)
# ===========================================================================

class TestFormatPrice:

    def setup_method(self):
        from report.report_generator import _format_price
        self._fmt = _format_price

    def test_us_format_dollar_sign(self):
        assert self._fmt(195.5, "US") == "$195.50"

    def test_us_format_two_decimals(self):
        assert self._fmt(1000.0, "US") == "$1000.00"

    def test_kr_format_won_suffix(self):
        result = self._fmt(216000, "KR")
        assert result.endswith("원")
        assert "216,000" in result

    def test_kr_format_no_decimal(self):
        result = self._fmt(75500, "KR")
        assert "." not in result.replace("원", "")

    def test_none_price_returns_na(self):
        assert self._fmt(None, "US") == "N/A"
        assert self._fmt(None, "KR") == "N/A"

    def test_us_is_default_market(self):
        result = self._fmt(100.0)
        assert result.startswith("$")

    def test_large_us_price(self):
        result = self._fmt(1234.56, "US")
        assert result == "$1234.56"

    def test_large_kr_price_comma(self):
        result = self._fmt(1234567, "KR")
        assert "1,234,567" in result


# ===========================================================================
# 4. build_ticker_card – 뉴스 섹션 (link / interpretation)
# ===========================================================================

_SAMPLE_WITH_NEWS = {
    "ticker":           "TSLA",
    "display_name":     "Tesla Inc.",
    "market":           "US",
    "final_decision":   "HOLD",
    "confidence":       0.55,
    "risk_score":       0.60,
    "executive_summary": "전기차 시장 경쟁 심화로 단기 불확실성 존재.",
    "json_report": json.dumps({
        "decision": {
            "bull_points":  ["자율주행 기술 선도"],
            "bear_points":  ["마진 압박"],
            "action_items": ["Q2 실적 확인"],
        },
        "news_analysis": {
            "evidence": [
                {
                    "headline":       "Tesla cuts prices again amid competition",
                    "sentiment":      "negative",
                    "category":       "product",
                    "interpretation": "가격 인하로 마진 압박 우려가 커지고 있습니다.",
                    "link":           "https://news.example.com/tesla-price-cut",
                },
                {
                    "headline":       "Tesla FSD milestone reached",
                    "sentiment":      "positive",
                    "category":       "product",
                    "interpretation": "자율주행 기술 진전으로 장기 성장 기대감이 높아집니다.",
                    "link":           "https://news.example.com/tesla-fsd",
                },
            ]
        }
    }),
}


class TestBuildTickerCardNews:

    def test_news_section_present(self):
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(_SAMPLE_WITH_NEWS)
        assert "주요 뉴스" in card

    def test_news_headline_rendered(self):
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(_SAMPLE_WITH_NEWS)
        assert "Tesla cuts prices again" in card

    def test_news_interpretation_rendered(self):
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(_SAMPLE_WITH_NEWS)
        assert "마진 압박 우려" in card

    def test_news_link_rendered(self):
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(_SAMPLE_WITH_NEWS)
        assert "https://news.example.com/tesla-price-cut" in card

    def test_news_sentiment_tag_negative(self):
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(_SAMPLE_WITH_NEWS)
        assert "부정" in card

    def test_news_sentiment_tag_positive(self):
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(_SAMPLE_WITH_NEWS)
        assert "긍정" in card

    def test_max_3_news_items(self):
        """evidence가 3개를 초과해도 최대 3개만 렌더링된다."""
        import copy
        row = copy.deepcopy(_SAMPLE_WITH_NEWS)
        data = json.loads(row["json_report"])
        # _SAMPLE_WITH_NEWS already has 2 items; add 2 more to reach 4 total
        data["news_analysis"]["evidence"].append({
            "headline": "Third news item ok",
            "sentiment": "neutral",
            "category": "general",
            "interpretation": "세 번째 뉴스.",
            "link": "https://news.example.com/3",
        })
        data["news_analysis"]["evidence"].append({
            "headline": "Fourth news item should be hidden",
            "sentiment": "neutral",
            "category": "general",
            "interpretation": "네 번째 뉴스는 보이면 안됩니다.",
            "link": "https://news.example.com/4",
        })
        row["json_report"] = json.dumps(data)
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(row)
        # 3rd headline should appear, 4th should NOT
        assert "Third news item ok" in card
        assert "Fourth news item should be hidden" not in card

    def test_no_news_no_section(self):
        """news_analysis가 없으면 주요 뉴스 섹션이 렌더링되지 않아야 한다."""
        row = {
            "ticker": "AAPL",
            "display_name": "Apple",
            "market": "US",
            "final_decision": "BUY",
            "confidence": 0.7,
            "risk_score": 0.3,
            "executive_summary": "",
            "json_report": json.dumps({
                "decision": {"bull_points": [], "bear_points": [], "action_items": []}
            }),
        }
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(row)
        assert "주요 뉴스" not in card

    def test_xss_escaped_in_headline(self):
        import copy
        row = copy.deepcopy(_SAMPLE_WITH_NEWS)
        data = json.loads(row["json_report"])
        data["news_analysis"]["evidence"][0]["headline"] = "<script>alert(1)</script>"
        row["json_report"] = json.dumps(data)
        from email_service.email_sender import build_ticker_card
        card = build_ticker_card(row)
        assert "<script>" not in card
        assert "&lt;script&gt;" in card


# ===========================================================================
# 5. build_html_email – base_url 파라미터
# ===========================================================================

class TestBuildHtmlEmailBaseUrl:

    _ROW = {
        "ticker":           "AAPL",
        "display_name":     "Apple Inc.",
        "market":           "US",
        "final_decision":   "BUY",
        "confidence":       0.72,
        "risk_score":       0.30,
        "executive_summary": "강한 서비스 성장.",
        "json_report": json.dumps({
            "decision": {"bull_points": ["서비스"], "bear_points": [], "action_items": []}
        }),
    }

    def test_custom_base_url_appears_in_output(self):
        from email_service.email_sender import build_html_email
        html = build_html_email([self._ROW], base_url="http://myserver:9999")
        assert "http://myserver:9999" in html

    def test_default_base_url_when_none(self):
        """base_url=None 이면 config/DB 기본값(localhost)이 사용된다."""
        from email_service.email_sender import build_html_email
        html = build_html_email([self._ROW], base_url=None)
        assert "localhost" in html or "http" in html

    def test_ticker_count_in_summary_bar(self):
        from email_service.email_sender import build_html_email
        html = build_html_email([self._ROW, self._ROW])
        assert "2개 종목" in html

    def test_report_date_korean_format(self):
        from email_service.email_sender import build_html_email
        from datetime import date
        html = build_html_email([self._ROW])
        year_str = date.today().strftime("%Y년")
        assert year_str in html


# ===========================================================================
# 6. send_daily_report – DB 설정에서 수신자 조회
# ===========================================================================

class TestSendDailyReportSettings:

    _ROW = {
        "ticker":           "AAPL",
        "display_name":     "Apple Inc.",
        "market":           "US",
        "final_decision":   "BUY",
        "confidence":       0.72,
        "risk_score":       0.30,
        "executive_summary": "강한 서비스 성장.",
        "json_report": json.dumps({
            "decision": {"bull_points": [], "bear_points": [], "action_items": []}
        }),
    }

    @patch("email_service.email_sender.EmailSender.send", return_value=(True, ""))
    def test_reads_recipient_from_db_settings(self, mock_send, tmp_path):
        """recipient 파라미터 없이 호출하면 DB에 저장된 primary_recipient 를 사용한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        SettingsRepository(db).set("primary_recipient", "db_user@example.com")

        from email_service.email_sender import send_daily_report
        result = send_daily_report([self._ROW], db_path=db)

        assert result is True
        call_args = mock_send.call_args
        # 2nd positional arg to send() is html_body; 3rd is recipient
        recipient_passed = call_args[0][2] if call_args[0] else call_args[1].get("recipient")
        assert recipient_passed == "db_user@example.com"

    @patch("email_service.email_sender.EmailSender.send", return_value=(True, ""))
    def test_explicit_recipient_overrides_db(self, mock_send, tmp_path):
        """명시적 recipient 가 DB 설정보다 우선한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        SettingsRepository(db).set("primary_recipient", "db_user@example.com")

        from email_service.email_sender import send_daily_report
        send_daily_report([self._ROW], recipient="override@example.com", db_path=db)

        call_args = mock_send.call_args
        recipient_passed = call_args[0][2] if call_args[0] else call_args[1].get("recipient")
        assert recipient_passed == "override@example.com"

    @patch("email_service.email_sender.EmailSender.send", return_value=(True, ""))
    def test_cc_list_from_db_settings(self, mock_send, tmp_path):
        """DB에 cc_recipients 가 있으면 send()의 cc_recipients 인자로 전달된다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        sr = SettingsRepository(db)
        sr.set("primary_recipient", "main@example.com")
        sr.set("cc_recipients", "cc1@example.com,cc2@example.com")

        from email_service.email_sender import send_daily_report
        send_daily_report([self._ROW], db_path=db)

        call_kwargs = mock_send.call_args[1] if mock_send.call_args[1] else {}
        call_args   = mock_send.call_args[0] if mock_send.call_args[0] else ()
        # cc_recipients is a keyword arg
        cc = call_kwargs.get("cc_recipients") or (call_args[3] if len(call_args) > 3 else None)
        assert cc is not None
        assert "cc1@example.com" in cc
        assert "cc2@example.com" in cc

    @patch("email_service.email_sender.EmailSender.send", return_value=(True, ""))
    def test_base_url_from_db_settings(self, mock_send, tmp_path):
        """DB의 base_url 설정이 이메일 HTML에 반영되어야 한다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository
        sr = SettingsRepository(db)
        sr.set("primary_recipient", "user@example.com")
        sr.set("base_url", "http://custom-server:1234")

        from email_service.email_sender import send_daily_report
        send_daily_report([self._ROW], db_path=db)

        call_args = mock_send.call_args[0]
        html_body = call_args[1]   # 2nd positional arg
        assert "http://custom-server:1234" in html_body

    def test_empty_rows_skipped_and_logged(self, tmp_path):
        """report_rows가 비어 있으면 False를 반환하고 DB에 skipped 로그를 남긴다."""
        db = _make_db(tmp_path)
        from db.repository import SettingsRepository, EmailLogRepository
        SettingsRepository(db).set("primary_recipient", "user@example.com")

        from email_service.email_sender import send_daily_report
        result = send_daily_report([], db_path=db)
        assert result is False

        logs = EmailLogRepository(db).get_all()
        assert len(logs) == 1
        assert logs[0]["status"] == "skipped"
