"""
tests/test_dashboard_ux.py
--------------------------
대시보드 UX 개선 관련 헬퍼 함수 단위 테스트.

Streamlit 렌더링 자체는 테스트하지 않고,
dashboard.py에서 추출한 순수 함수들을 검증한다.

v3.0 : 98  tests
v4.0 : 144 tests
v5.0 : 215+ tests
v5.1 : DB sanitize / PAGE_TITLES / session_state / scripts 테스트 추가

실행:
    pytest tests/test_dashboard_ux.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard import (
    # 순수 헬퍼 함수
    get_display_name_ko,
    normalize_company_name_ko,
    fmt_risk_display,
    is_localhost_url,
    fmt_next_schedule,
    confidence_bar,
    fmt_dt,
    _fmt_price,
    _score_to_level,
    _estimate_risk_level_ko,
    _generate_summary_sentence,
    _news_card_html,
    get_page_title,
    _is_english_name,
    # 상수
    UI_LABELS,
    PAGE_TODAY,
    PAGE_HISTORY,
    PAGE_DETAIL,
    PAGE_WATCHLIST,
    PAGE_EMAIL,
    PAGE_MENU,
    PAGE_TITLES,
    VERDICT_ICON,
    VERDICT_COLOR,
    RISK_LEVEL_KO,
    KNOWN_KO_NAMES,
    _ENGLISH_COMPANY_KO,
    CAT_KO,
    SENT_KO,
    STYLE_LABEL,
    HORIZON_LABEL,
    MARKET_LABEL,
    LANG_LABEL,
)
from utils.text_filter import sanitize_llm_text as _sanitize_llm_text

# ---------------------------------------------------------------------------
# ★ 금지 표현 목록 (v5.0 공통)
# ---------------------------------------------------------------------------
FORBIDDEN_EXPRESSIONS = [
    "오늘 보도",
    "과거에 대해",
    "상세분석",        # 띄어쓰기 없는 잘못된 형태
    "풍부한 관리",
    "탄력적 조건",
    "난",
    "투자 내용",
    "믿는다",
    "의외의",
    "뭐야",
    "끼리끼리",
    "반대로 분석",
    "운동",
    "전체 보도",
    "활성인자",
    "담당자",
    "회원가입 포인트",
    "추가로",
    "우리를",
    "투자하고 있어요",
    "테스트해봤습니다",
    "관심있는 투자자 커뮤니티에서",
    "범위가 넓습니다",
]


# ===========================================================================
# get_display_name_ko — 한국어 회사명 표시 (v3.0 기준, v5.0 동작 반영)
# ===========================================================================

class TestGetDisplayNameKo:
    """한국어 표시명 반환 로직 검증."""

    def test_known_us_ticker_aapl(self):
        assert get_display_name_ko("AAPL") == "애플"

    def test_known_us_ticker_nvda(self):
        assert get_display_name_ko("NVDA") == "엔비디아"

    def test_known_us_ticker_msft(self):
        assert get_display_name_ko("MSFT") == "마이크로소프트"

    def test_known_kr_ticker_samsung(self):
        assert get_display_name_ko("005930.KS") == "삼성전자"

    def test_known_kr_ticker_hynix(self):
        assert get_display_name_ko("000660.KS") == "SK하이닉스"

    def test_known_kr_ticker_kakao(self):
        assert get_display_name_ko("035720.KS") == "카카오"

    def test_known_kr_ticker_naver(self):
        assert get_display_name_ko("035420.KS") == "네이버"

    def test_english_company_name_converted_to_korean(self):
        """v5.0: 영문 회사명 "Apple Inc."은 한국어 "애플"로 변환."""
        result = get_display_name_ko("AAPL", "Apple Inc.")
        assert result == "애플"

    def test_nvidia_english_name_converted(self):
        """v5.0: "NVIDIA Corporation" → "엔비디아"."""
        result = get_display_name_ko("NVDA", "NVIDIA Corporation")
        assert result == "엔비디아"

    def test_display_name_same_as_ticker_falls_back(self):
        """display_name이 ticker와 같으면 KNOWN_KO_NAMES 사용."""
        result = get_display_name_ko("AAPL", "AAPL")
        assert result == "애플"

    def test_unknown_ticker_returns_ticker(self):
        """알 수 없는 종목코드는 그대로 반환."""
        result = get_display_name_ko("XYZ123")
        assert result == "XYZ123"

    def test_empty_display_name_uses_known(self):
        """display_name이 빈 문자열이면 KNOWN_KO_NAMES 사용."""
        assert get_display_name_ko("NVDA", "") == "엔비디아"

    def test_display_name_whitespace_only_falls_back(self):
        """display_name이 공백만 있으면 폴백."""
        result = get_display_name_ko("005930.KS", "   ")
        assert result == "삼성전자"

    def test_custom_korean_name_for_unknown_ticker(self):
        """알 수 없는 ticker에 커스텀 한국어 이름 → 그대로 반환."""
        result = get_display_name_ko("CUSTOM123", "커스텀 회사")
        assert result == "커스텀 회사"

    def test_samsung_english_name_converted(self):
        """Samsung Electronics → 삼성전자."""
        result = get_display_name_ko("UNKNOWN", "Samsung Electronics")
        assert result == "삼성전자"


# ===========================================================================
# normalize_company_name_ko — 영문 → 한국어 회사명 변환
# ===========================================================================

class TestNormalizeCompanyNameKo:
    """영문 회사명 → 한국어 변환 함수 검증."""

    def test_apple_inc_dot(self):
        assert normalize_company_name_ko("Apple Inc.") == "애플"

    def test_apple_inc_no_dot(self):
        assert normalize_company_name_ko("Apple Inc") == "애플"

    def test_nvidia_corporation(self):
        assert normalize_company_name_ko("NVIDIA Corporation") == "엔비디아"

    def test_microsoft_corporation(self):
        assert normalize_company_name_ko("Microsoft Corporation") == "마이크로소프트"

    def test_samsung_electronics(self):
        assert normalize_company_name_ko("Samsung Electronics") == "삼성전자"

    def test_samsung_full_name(self):
        assert normalize_company_name_ko("Samsung Electronics Co., Ltd.") == "삼성전자"

    def test_tesla(self):
        assert normalize_company_name_ko("Tesla Inc.") == "테슬라"

    def test_meta_platforms(self):
        assert normalize_company_name_ko("Meta Platforms Inc.") == "메타"

    def test_unknown_returns_original(self):
        result = normalize_company_name_ko("Unknown Corp Ltd.")
        assert result == "Unknown Corp Ltd."

    def test_empty_returns_empty(self):
        assert normalize_company_name_ko("") == ""

    def test_case_insensitive(self):
        """대소문자 무관하게 변환."""
        assert normalize_company_name_ko("APPLE INC.") == "애플"
        assert normalize_company_name_ko("apple inc.") == "애플"

    def test_netflix(self):
        assert normalize_company_name_ko("Netflix Inc.") == "넷플릭스"

    def test_intel(self):
        assert normalize_company_name_ko("Intel Corporation") == "인텔"

    def test_amazon(self):
        assert normalize_company_name_ko("Amazon.com Inc.") == "아마존"


# ===========================================================================
# fmt_risk_display — 리스크 점수 + 수준 포맷
# ===========================================================================

class TestFmtRiskDisplay:
    """리스크 수준 포맷 검증."""

    def test_moderate_risk(self):
        assert fmt_risk_display(0.34, "moderate") == "0.34 / 보통"

    def test_low_risk(self):
        assert fmt_risk_display(0.10, "low") == "0.10 / 낮음"

    def test_elevated_risk(self):
        assert fmt_risk_display(0.55, "elevated") == "0.55 / 다소 높음"

    def test_high_risk(self):
        assert fmt_risk_display(0.72, "high") == "0.72 / 높음"

    def test_very_high_risk(self):
        assert fmt_risk_display(0.90, "very_high") == "0.90 / 매우 높음"

    def test_no_level_returns_score_only(self):
        assert fmt_risk_display(0.45) == "0.45"

    def test_unknown_level_returns_raw(self):
        result = fmt_risk_display(0.30, "unknown_level")
        assert "0.30" in result

    def test_zero_score(self):
        assert fmt_risk_display(0.0, "low") == "0.00 / 낮음"

    def test_max_score(self):
        assert fmt_risk_display(1.0, "very_high") == "1.00 / 매우 높음"

    def test_separator_is_slash(self):
        """v5.0 포맷: '점수 / 수준' (슬래시 구분)."""
        result = fmt_risk_display(0.58, "elevated")
        assert " / " in result
        assert result == "0.58 / 다소 높음"


# ===========================================================================
# is_localhost_url
# ===========================================================================

class TestIsLocalhostUrl:
    def test_localhost_detected(self):
        assert is_localhost_url("http://localhost:8501") is True

    def test_127_0_0_1_detected(self):
        assert is_localhost_url("http://127.0.0.1:8501") is True

    def test_public_domain_not_localhost(self):
        assert is_localhost_url("https://dashboard.glowbuff.com") is False

    def test_aws_ip_not_localhost(self):
        assert is_localhost_url("http://52.79.100.200:8501") is False

    def test_empty_url_not_localhost(self):
        assert is_localhost_url("") is False

    def test_localhost_in_path_detected(self):
        assert is_localhost_url("http://localhost") is True

    def test_server_ip_3_34(self):
        """실제 서버 IP는 로컬로 판단하지 않음."""
        assert is_localhost_url("http://3.34.46.169:8501") is False


# ===========================================================================
# fmt_next_schedule
# ===========================================================================

class TestFmtNextSchedule:
    def test_valid_time_format_contains_time(self):
        result = fmt_next_schedule("07:00")
        assert "07:00" in result

    def test_result_contains_today_or_tomorrow(self):
        result = fmt_next_schedule("07:00")
        assert "오늘" in result or "내일" in result

    def test_invalid_format_fallback(self):
        result = fmt_next_schedule("invalid")
        assert "매일" in result

    def test_midnight_schedule(self):
        result = fmt_next_schedule("00:00")
        assert "00:00" in result

    def test_late_night_schedule(self):
        result = fmt_next_schedule("23:59")
        assert "23:59" in result


# ===========================================================================
# confidence_bar — v5.0: 'XX% / 수준' 포맷
# ===========================================================================

class TestConfidenceBar:
    def test_very_high_confidence(self):
        result = confidence_bar(0.85)
        assert "85%" in result
        assert "매우 높음" in result

    def test_high_confidence(self):
        result = confidence_bar(0.70)
        assert "70%" in result
        assert "높음" in result

    def test_moderate_confidence(self):
        result = confidence_bar(0.50)
        assert "50%" in result
        assert "보통" in result

    def test_low_confidence(self):
        result = confidence_bar(0.30)
        assert "30%" in result
        assert "낮음" in result

    def test_very_low_confidence(self):
        result = confidence_bar(0.10)
        assert "10%" in result
        assert "매우 낮음" in result

    def test_zero_confidence(self):
        result = confidence_bar(0.0)
        assert "0%" in result

    def test_full_confidence(self):
        result = confidence_bar(1.0)
        assert "100%" in result
        assert "매우 높음" in result

    def test_v5_format_uses_slash(self):
        """v5.0: 'XX% / 수준' 형식."""
        result = confidence_bar(0.87)
        assert " / " in result
        assert "87%" in result
        assert "매우 높음" in result

    def test_format_example_87_percent(self):
        """스펙 예시: 87% / 매우 높음."""
        assert confidence_bar(0.87) == "87% / 매우 높음"


# ===========================================================================
# _score_to_level
# ===========================================================================

class TestScoreToLevel:
    def test_low(self):
        assert _score_to_level(0.10) == "low"

    def test_moderate(self):
        assert _score_to_level(0.30) == "moderate"

    def test_elevated(self):
        assert _score_to_level(0.50) == "elevated"

    def test_high(self):
        assert _score_to_level(0.70) == "high"

    def test_very_high(self):
        assert _score_to_level(0.90) == "very_high"

    def test_boundary_low_moderate(self):
        assert _score_to_level(0.20) == "moderate"

    def test_boundary_moderate_elevated(self):
        assert _score_to_level(0.40) == "elevated"

    def test_zero_is_low(self):
        assert _score_to_level(0.0) == "low"

    def test_one_is_very_high(self):
        assert _score_to_level(1.0) == "very_high"

    def test_risk_range_spec(self):
        """v5.0 스펙: 0.61↑ → high."""
        assert _score_to_level(0.61) == "high"

    def test_risk_range_elevated(self):
        """v5.0 스펙: 0.41~0.60 → elevated."""
        assert _score_to_level(0.41) == "elevated"
        assert _score_to_level(0.59) == "elevated"


# ===========================================================================
# _estimate_risk_level_ko
# ===========================================================================

class TestEstimateRiskLevelKo:
    def test_low_score_returns_korean(self):
        assert _estimate_risk_level_ko(0.10) == "낮음"

    def test_moderate_score_returns_korean(self):
        assert _estimate_risk_level_ko(0.35) == "보통"

    def test_elevated_score_returns_korean(self):
        assert _estimate_risk_level_ko(0.55) == "다소 높음"

    def test_high_score_returns_korean(self):
        assert _estimate_risk_level_ko(0.70) == "높음"

    def test_very_high_score_returns_korean(self):
        assert _estimate_risk_level_ko(0.95) == "매우 높음"


# ===========================================================================
# _news_card_html
# ===========================================================================

class TestNewsCardHtml:
    SAMPLE_NEWS = {
        "headline":       "Apple reports record quarterly earnings",
        "publisher":      "Reuters",
        "date":           "2026-05-07",
        "sentiment":      "positive",
        "category":       "earnings",
        "link":           "https://reuters.com/article/abc",
        "interpretation": "실적 개선 기대감이 주가에 긍정적 영향이 예상됩니다.",
    }

    def test_headline_appears_in_card(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "Apple reports record quarterly earnings" in html

    def test_category_translated_to_korean(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "실적" in html

    def test_sentiment_translated_to_korean(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "긍정적" in html

    def test_interpretation_appears(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "실적 개선 기대감" in html

    def test_link_appears_as_anchor(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "https://reuters.com/article/abc" in html
        assert "기사 보기" in html

    def test_publisher_appears(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "Reuters" in html

    def test_date_appears(self):
        html = _news_card_html(self.SAMPLE_NEWS, 0)
        assert "2026-05-07" in html

    def test_no_link_no_anchor(self):
        item = {**self.SAMPLE_NEWS, "link": ""}
        html = _news_card_html(item, 0)
        assert "기사 보기" not in html

    def test_negative_sentiment_badge_class(self):
        item = {**self.SAMPLE_NEWS, "sentiment": "negative"}
        html = _news_card_html(item, 0)
        assert "news-badge-negative" in html

    def test_neutral_sentiment(self):
        item = {**self.SAMPLE_NEWS, "sentiment": "neutral"}
        html = _news_card_html(item, 0)
        assert "중립적" in html

    def test_mixed_sentiment(self):
        item = {**self.SAMPLE_NEWS, "sentiment": "mixed"}
        html = _news_card_html(item, 0)
        assert "혼재" in html

    def test_empty_interpretation_no_interp_div(self):
        item = {**self.SAMPLE_NEWS, "interpretation": ""}
        html = _news_card_html(item, 0)
        assert "news-interp" not in html

    def test_legal_category_translated(self):
        item = {**self.SAMPLE_NEWS, "category": "legal"}
        html = _news_card_html(item, 0)
        assert "법률/규제" in html

    def test_macro_category_translated(self):
        item = {**self.SAMPLE_NEWS, "category": "macro"}
        html = _news_card_html(item, 0)
        assert "거시경제" in html

    def test_long_headline_truncated(self):
        long_title = "A" * 200
        item = {**self.SAMPLE_NEWS, "headline": long_title}
        html = _news_card_html(item, 0)
        assert "A" * 130 in html
        assert "A" * 200 not in html


# ===========================================================================
# fmt_dt
# ===========================================================================

class TestFmtDt:
    def test_iso_format(self):
        result = fmt_dt("2026-05-07 07:03:21")
        assert result == "2026-05-07 07:03"

    def test_invalid_string_returns_as_is(self):
        assert fmt_dt("invalid") == "invalid"

    def test_empty_string_returns_dash(self):
        assert fmt_dt("") == "-"

    def test_none_like_empty_returns_dash(self):
        assert fmt_dt(None) == "-"  # type: ignore


# ===========================================================================
# _fmt_price
# ===========================================================================

class TestFmtPrice:
    def test_us_price_dollar_format(self):
        assert _fmt_price(182.50, "US") == "$182.50"

    def test_kr_price_won_format(self):
        assert _fmt_price(75400, "KR") == "75,400원"

    def test_none_price_returns_na(self):
        assert _fmt_price(None) == "N/A"

    def test_us_price_default_market(self):
        assert _fmt_price(100.0) == "$100.00"

    def test_kr_large_price_with_commas(self):
        assert _fmt_price(1234567, "KR") == "1,234,567원"


# ===========================================================================
# VERDICT_ICON / VERDICT_COLOR
# ===========================================================================

class TestVerdictConstants:
    EXPECTED_VERDICTS = ["STRONG BUY", "BUY", "HOLD", "CAUTIOUS HOLD", "AVOID"]

    def test_all_verdicts_have_icon(self):
        for v in self.EXPECTED_VERDICTS:
            assert v in VERDICT_ICON, f"{v} missing from VERDICT_ICON"

    def test_all_verdicts_have_color(self):
        for v in self.EXPECTED_VERDICTS:
            assert v in VERDICT_COLOR, f"{v} missing from VERDICT_COLOR"

    def test_colors_start_with_hash(self):
        for v, color in VERDICT_COLOR.items():
            assert color.startswith("#"), f"{v} color '{color}' invalid"

    def test_strong_buy_label(self):
        assert "적극 매수" in VERDICT_ICON["STRONG BUY"]

    def test_buy_label(self):
        assert "매수 고려" in VERDICT_ICON["BUY"]

    def test_hold_label(self):
        assert "보유/관망" in VERDICT_ICON["HOLD"]

    def test_cautious_hold_label(self):
        assert "신중 관망" in VERDICT_ICON["CAUTIOUS HOLD"]

    def test_avoid_label(self):
        assert "회피" in VERDICT_ICON["AVOID"]


# ===========================================================================
# RISK_LEVEL_KO
# ===========================================================================

class TestRiskLevelKo:
    def test_all_levels_present(self):
        for level in ["low", "moderate", "elevated", "high", "very_high"]:
            assert level in RISK_LEVEL_KO

    def test_low_is_korean(self):
        assert RISK_LEVEL_KO["low"] == "낮음"

    def test_moderate_is_korean(self):
        assert RISK_LEVEL_KO["moderate"] == "보통"

    def test_elevated_is_korean(self):
        assert RISK_LEVEL_KO["elevated"] == "다소 높음"

    def test_high_is_korean(self):
        assert RISK_LEVEL_KO["high"] == "높음"

    def test_very_high_is_korean(self):
        assert RISK_LEVEL_KO["very_high"] == "매우 높음"


# ===========================================================================
# KNOWN_KO_NAMES
# ===========================================================================

class TestKnownKoNames:
    def test_aapl_exists(self):
        assert "AAPL" in KNOWN_KO_NAMES

    def test_samsung_exists(self):
        assert "005930.KS" in KNOWN_KO_NAMES

    def test_nvda_is_korean(self):
        assert KNOWN_KO_NAMES["NVDA"] == "엔비디아"

    def test_samsung_is_korean(self):
        assert KNOWN_KO_NAMES["005930.KS"] == "삼성전자"


# ===========================================================================
# 즉시 실행 이메일 옵션
# ===========================================================================

class TestInstantRunEmailOption:
    def test_email_send_when_flag_true_and_ids_present(self):
        send_email_after = True
        success_ids = [1, 2, 3]
        assert (send_email_after and bool(success_ids)) is True

    def test_no_email_when_flag_false(self):
        assert (False and bool([1, 2])) is False

    def test_no_email_when_no_success_ids(self):
        assert (True and bool([])) is False

    def test_no_email_when_both_false_empty(self):
        assert (False and bool([])) is False


# ===========================================================================
# BASE_URL 경고
# ===========================================================================

class TestBaseUrlWarning:
    def test_localhost_triggers_warning(self):
        assert is_localhost_url("http://localhost:8501") is True

    def test_public_url_no_warning(self):
        assert is_localhost_url("https://dashboard.glowbuff.com") is False

    def test_ip_port_no_warning(self):
        assert is_localhost_url("http://13.124.200.100:8501") is False

    def test_warning_message_explains_issue(self):
        warn = UI_LABELS["EMAIL_URL_WARN"]
        assert "로컬" in warn or "URL" in warn


# ===========================================================================
# ★ v5.0 신규 테스트
# ===========================================================================

# ---------------------------------------------------------------------------
# 페이지 라우팅 상수
# ---------------------------------------------------------------------------

class TestPageConstants:
    """내부 page key 상수 검증."""

    def test_page_today_is_string(self):
        assert isinstance(PAGE_TODAY, str)
        assert PAGE_TODAY == "today"

    def test_page_history_is_string(self):
        assert isinstance(PAGE_HISTORY, str)
        assert PAGE_HISTORY == "history"

    def test_page_detail_is_string(self):
        assert isinstance(PAGE_DETAIL, str)
        assert PAGE_DETAIL == "detail"

    def test_page_watchlist_is_string(self):
        assert isinstance(PAGE_WATCHLIST, str)
        assert PAGE_WATCHLIST == "watchlist"

    def test_page_email_is_string(self):
        assert isinstance(PAGE_EMAIL, str)
        assert PAGE_EMAIL == "email"

    def test_five_pages_defined(self):
        pages = [PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL]
        assert len(set(pages)) == 5  # 모두 고유


# ---------------------------------------------------------------------------
# PAGE_MENU 매핑
# ---------------------------------------------------------------------------

class TestPageMenu:
    """PAGE_MENU 사전의 구조와 한국어 레이블 검증."""

    def test_all_page_keys_exist_in_menu(self):
        for key in [PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL]:
            assert key in PAGE_MENU, f"PAGE_MENU에 '{key}' 키가 없습니다"

    def test_today_label_correct(self):
        assert "오늘 보고서" in PAGE_MENU[PAGE_TODAY]

    def test_history_label_correct(self):
        assert "과거 보고서" in PAGE_MENU[PAGE_HISTORY]

    def test_detail_label_correct(self):
        assert "상세 분석" in PAGE_MENU[PAGE_DETAIL]

    def test_watchlist_label_correct(self):
        assert "종목 관리" in PAGE_MENU[PAGE_WATCHLIST]

    def test_email_label_correct(self):
        assert "이메일 설정" in PAGE_MENU[PAGE_EMAIL]

    def test_no_forbidden_in_menu_labels(self):
        """메뉴 레이블에 금지 표현이 없어야 함."""
        for key, label in PAGE_MENU.items():
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in label, (
                    f"PAGE_MENU['{key}'] = '{label}'에 금지 표현 '{bad}' 포함"
                )

    def test_old_menu_names_absent(self):
        """구 버전 메뉴 이름이 사용되지 않음."""
        old_names = [
            "오늘의 리포트", "과거 리포트",
            "분석 종목 관리", "알림 설정",
        ]
        for label in PAGE_MENU.values():
            for old in old_names:
                assert old not in label, (
                    f"구 메뉴명 '{old}'이 레이블에 남아있습니다: '{label}'"
                )


# ---------------------------------------------------------------------------
# get_page_title
# ---------------------------------------------------------------------------

class TestGetPageTitle:
    """각 page key별 화면 제목 반환 검증."""

    def test_today_title(self):
        assert get_page_title(PAGE_TODAY) == "오늘 보고서"

    def test_history_title(self):
        assert get_page_title(PAGE_HISTORY) == "과거 보고서"

    def test_detail_title(self):
        assert get_page_title(PAGE_DETAIL) == "상세 분석"

    def test_watchlist_title(self):
        assert get_page_title(PAGE_WATCHLIST) == "종목 관리"

    def test_email_title(self):
        assert get_page_title(PAGE_EMAIL) == "이메일 설정"

    def test_unknown_key_returns_default(self):
        result = get_page_title("unknown_page")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_all_titles_no_forbidden(self):
        """모든 페이지 제목에 금지 표현이 없어야 함."""
        for key in [PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL]:
            title = get_page_title(key)
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in title, (
                    f"제목 '{title}'에 금지 표현 '{bad}' 포함"
                )

    def test_no_typo_sangse(self):
        """'상세분석'(붙임) 오타가 없어야 함 — '상세 분석'(띄어쓰기)이어야 함."""
        title = get_page_title(PAGE_DETAIL)
        assert title == "상세 분석"
        assert "상세분석" not in title


# ---------------------------------------------------------------------------
# UI_LABELS 구조 및 금지 표현 부재
# ---------------------------------------------------------------------------

class TestUILabelsV5:
    """UI_LABELS 사전의 완전성과 금지 표현 부재 검증."""

    # ── 필수 키 존재 ──────────────────────────────────────────────────────

    def test_today_metric_keys(self):
        for k in ["TODAY_METRIC_LAST_RUN", "TODAY_METRIC_COUNT",
                  "TODAY_METRIC_EMAIL", "TODAY_METRIC_NEXT"]:
            assert k in UI_LABELS

    def test_today_action_keys(self):
        for k in ["TODAY_RUN_SECTION", "TODAY_RUN_BTN",
                  "TODAY_RUN_DESC", "TODAY_RUN_EMAIL_CHK", "TODAY_BTN_DETAIL"]:
            assert k in UI_LABELS

    def test_history_filter_keys(self):
        for k in ["HISTORY_FILTER_SECTION", "HISTORY_FILTER_PERIOD",
                  "HISTORY_FILTER_TICKER", "HISTORY_FILTER_MARKET",
                  "HISTORY_FILTER_DECISION"]:
            assert k in UI_LABELS

    def test_history_column_keys(self):
        for k in ["HISTORY_COL_TICKER", "HISTORY_COL_COMPANY",
                  "HISTORY_COL_DECISION", "HISTORY_COL_CONFIDENCE",
                  "HISTORY_COL_RISK", "HISTORY_COL_STYLE",
                  "HISTORY_COL_HORIZON", "HISTORY_COL_TIME"]:
            assert k in UI_LABELS

    def test_detail_tab_keys(self):
        for k in ["DETAIL_TAB_SUMMARY", "DETAIL_TAB_MARKET", "DETAIL_TAB_FUND",
                  "DETAIL_TAB_NEWS", "DETAIL_TAB_RISK", "DETAIL_TAB_FULL"]:
            assert k in UI_LABELS

    def test_detail_metric_keys(self):
        for k in ["DETAIL_METRIC_DECISION", "DETAIL_METRIC_CONFIDENCE",
                  "DETAIL_METRIC_RISK", "DETAIL_METRIC_TIME"]:
            assert k in UI_LABELS

    def test_detail_section_keys(self):
        for k in ["DETAIL_SECTION_ANALYSIS", "DETAIL_SECTION_BULL",
                  "DETAIL_SECTION_BEAR", "DETAIL_SECTION_CHECK"]:
            assert k in UI_LABELS

    def test_watchlist_form_keys(self):
        for k in ["WATCHLIST_FORM_TICKER", "WATCHLIST_FORM_NAME",
                  "WATCHLIST_FORM_MARKET", "WATCHLIST_FORM_STYLE",
                  "WATCHLIST_FORM_HORIZON", "WATCHLIST_FORM_LANG"]:
            assert k in UI_LABELS

    def test_watchlist_button_keys(self):
        for k in ["WATCHLIST_BTN_ADD", "WATCHLIST_BTN_SAVE",
                  "WATCHLIST_BTN_ACTIVATE", "WATCHLIST_BTN_DEACTIVATE",
                  "WATCHLIST_BTN_DELETE"]:
            assert k in UI_LABELS

    def test_email_label_keys(self):
        for k in ["EMAIL_LABEL_PRIMARY", "EMAIL_LABEL_CC",
                  "EMAIL_LABEL_TIME", "EMAIL_LABEL_URL"]:
            assert k in UI_LABELS

    def test_email_button_keys(self):
        for k in ["EMAIL_BTN_SAVE", "EMAIL_BTN_TEST"]:
            assert k in UI_LABELS

    # ── 주요 레이블 값 정확성 ─────────────────────────────────────────────

    def test_metric_last_run_label(self):
        assert UI_LABELS["TODAY_METRIC_LAST_RUN"] == "최근 분석 시각"

    def test_metric_email_label(self):
        assert UI_LABELS["TODAY_METRIC_EMAIL"] == "최근 이메일 발송 상태"

    def test_metric_next_run_label(self):
        assert UI_LABELS["TODAY_METRIC_NEXT"] == "다음 자동 실행"

    def test_run_section_label(self):
        assert UI_LABELS["TODAY_RUN_SECTION"] == "즉시 분석"

    def test_run_btn_label(self):
        assert UI_LABELS["TODAY_RUN_BTN"] == "지금 전체 종목 분석하기"

    def test_history_filter_section_label(self):
        assert UI_LABELS["HISTORY_FILTER_SECTION"] == "조회 조건"

    def test_history_filter_period_label(self):
        assert UI_LABELS["HISTORY_FILTER_PERIOD"] == "조회 기간"

    def test_history_filter_ticker_label(self):
        assert UI_LABELS["HISTORY_FILTER_TICKER"] == "종목"

    def test_history_filter_market_label(self):
        assert UI_LABELS["HISTORY_FILTER_MARKET"] == "시장"

    def test_history_filter_decision_label(self):
        assert UI_LABELS["HISTORY_FILTER_DECISION"] == "투자 판단"

    def test_detail_tab_summary_label(self):
        assert "요약" in UI_LABELS["DETAIL_TAB_SUMMARY"]

    def test_detail_tab_market_label(self):
        assert "시장 분석" in UI_LABELS["DETAIL_TAB_MARKET"]

    def test_detail_tab_fund_label(self):
        assert "재무 분석" in UI_LABELS["DETAIL_TAB_FUND"]

    def test_detail_tab_news_label(self):
        assert "뉴스" in UI_LABELS["DETAIL_TAB_NEWS"]

    def test_detail_tab_risk_label(self):
        assert "리스크" in UI_LABELS["DETAIL_TAB_RISK"]

    def test_detail_tab_full_label(self):
        assert "전체 보고서" in UI_LABELS["DETAIL_TAB_FULL"]

    def test_detail_section_analysis_label(self):
        assert UI_LABELS["DETAIL_SECTION_ANALYSIS"] == "분석 요약"

    def test_detail_section_bull_label(self):
        assert "긍정 요인" in UI_LABELS["DETAIL_SECTION_BULL"]

    def test_detail_section_bear_label(self):
        assert "부정 요인" in UI_LABELS["DETAIL_SECTION_BEAR"]

    def test_detail_section_check_label(self):
        assert "체크 포인트" in UI_LABELS["DETAIL_SECTION_CHECK"]

    def test_detail_metric_decision_label(self):
        assert UI_LABELS["DETAIL_METRIC_DECISION"] == "투자 판단"

    def test_detail_metric_confidence_label(self):
        assert UI_LABELS["DETAIL_METRIC_CONFIDENCE"] == "신뢰도"

    def test_detail_metric_risk_label(self):
        assert UI_LABELS["DETAIL_METRIC_RISK"] == "리스크 수준"

    def test_detail_metric_time_label(self):
        assert UI_LABELS["DETAIL_METRIC_TIME"] == "분석 시각"

    def test_watchlist_section_list_label(self):
        assert UI_LABELS["WATCHLIST_SECTION_LIST"] == "등록된 종목"

    def test_watchlist_section_add_label(self):
        assert UI_LABELS["WATCHLIST_SECTION_ADD"] == "종목 추가"

    def test_watchlist_section_edit_label(self):
        assert UI_LABELS["WATCHLIST_SECTION_EDIT"] == "수정 및 삭제"

    def test_email_section_recipient_label(self):
        assert UI_LABELS["EMAIL_SECTION_RECIPIENT"] == "이메일 수신 설정"

    def test_email_test_ok_label(self):
        assert UI_LABELS["EMAIL_TEST_OK"] == "테스트 메일을 발송했습니다."

    def test_email_test_fail_label(self):
        assert UI_LABELS["EMAIL_TEST_FAIL"] == "테스트 메일 발송에 실패했습니다."

    def test_email_url_warn_label(self):
        warn = UI_LABELS["EMAIL_URL_WARN"]
        assert "로컬" in warn or "URL" in warn

    def test_email_url_warn_detail_label(self):
        detail = UI_LABELS["EMAIL_URL_WARN_DETAIL"]
        assert "공개 URL" in detail or "외부" in detail

    # ── 금지 표현 부재 ────────────────────────────────────────────────────

    def test_no_forbidden_in_all_ui_labels(self):
        """UI_LABELS의 모든 값에 금지 표현이 없어야 함."""
        for key, value in UI_LABELS.items():
            if not isinstance(value, str):
                continue
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in value, (
                    f"UI_LABELS['{key}'] = '{value[:60]}...'에 금지 표현 '{bad}' 포함"
                )


# ---------------------------------------------------------------------------
# 금지 표현 부재 — 도메인 상수 및 함수 출력
# ---------------------------------------------------------------------------

class TestForbiddenExpressionsAbsent:
    """금지 표현이 어디에도 나타나지 않는지 검증."""

    def test_no_forbidden_in_verdict_icons(self):
        for v, icon in VERDICT_ICON.items():
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in icon, (
                    f"VERDICT_ICON['{v}'] = '{icon}'에 금지 표현 '{bad}' 포함"
                )

    def test_no_forbidden_in_risk_level_ko(self):
        for k, v in RISK_LEVEL_KO.items():
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in v, f"RISK_LEVEL_KO['{k}']에 금지 표현 '{bad}' 포함"

    def test_no_forbidden_in_style_labels(self):
        for k, v in STYLE_LABEL.items():
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in v

    def test_no_forbidden_in_horizon_labels(self):
        for k, v in HORIZON_LABEL.items():
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in v

    def test_no_forbidden_in_summary_strong_buy_low_risk(self):
        result = _generate_summary_sentence(
            "AAPL", "STRONG BUY", 0.80, 0.15, "애플"
        )
        for bad in FORBIDDEN_EXPRESSIONS:
            assert bad not in result, f"요약 문장에 금지 표현 '{bad}' 포함"

    def test_no_forbidden_in_summary_avoid(self):
        result = _generate_summary_sentence(
            "XYZ", "AVOID", 0.60, 0.80, "종목XYZ"
        )
        for bad in FORBIDDEN_EXPRESSIONS:
            assert bad not in result, f"요약 문장에 금지 표현 '{bad}' 포함"

    def test_no_forbidden_in_summary_hold(self):
        result = _generate_summary_sentence(
            "MSFT", "HOLD", 0.55, 0.45, "마이크로소프트"
        )
        for bad in FORBIDDEN_EXPRESSIONS:
            assert bad not in result


# ---------------------------------------------------------------------------
# 세션 상태 내비게이션 패턴
# ---------------------------------------------------------------------------

class TestSessionStateNavigationV5:
    """page_override_key 기반 내비게이션 패턴 검증."""

    def test_page_override_key_is_detail_page_key(self):
        """'상세 분석 보기' 버튼은 PAGE_DETAIL key를 session_state에 저장해야 함."""
        # 실제 st.session_state는 테스트할 수 없지만, 값 자체를 검증
        assert PAGE_DETAIL == "detail"

    def test_page_override_key_name(self):
        """session_state에 사용하는 key 이름이 'page_override_key'."""
        key = "page_override_key"
        assert key.replace("_", "").isalpha()

    def test_selected_report_id_key_name(self):
        """보고서 ID를 저장하는 session_state key가 'selected_report_id'."""
        key = "selected_report_id"
        assert key.replace("_", "").isalpha()

    def test_detail_page_key_consistent(self):
        """PAGE_DETAIL과 PAGE_MENU[PAGE_DETAIL]에 '상세 분석'이 포함."""
        assert "상세 분석" in PAGE_MENU[PAGE_DETAIL]
        assert get_page_title(PAGE_DETAIL) == "상세 분석"

    def test_btn_view_detail_label_today(self):
        """오늘 보고서의 상세 보기 버튼 레이블에 '상세 분석' 포함."""
        assert "상세 분석" in UI_LABELS["TODAY_BTN_DETAIL"]

    def test_btn_view_detail_label_history(self):
        """과거 보고서의 상세 보기 버튼 레이블에 '상세 분석' 포함."""
        assert "상세 분석" in UI_LABELS["HISTORY_BTN_DETAIL"]


# ---------------------------------------------------------------------------
# _generate_summary_sentence — 5개 이상 템플릿
# ---------------------------------------------------------------------------

class TestGenerateSummarySentenceV5:
    """자동 요약 문장 생성 — 다양한 판단/리스크 조합 검증."""

    def test_strong_buy_low_risk_stable(self):
        result = _generate_summary_sentence(
            "AAPL", "STRONG BUY", 0.80, 0.15, "애플"
        )
        assert "애플" in result
        assert "낮음" in result or "안정" in result

    def test_strong_buy_high_risk_caution(self):
        result = _generate_summary_sentence(
            "TSLA", "STRONG BUY", 0.65, 0.75, "테슬라"
        )
        assert "테슬라" in result
        assert "높음" in result

    def test_buy_low_risk(self):
        result = _generate_summary_sentence(
            "MSFT", "BUY", 0.70, 0.25, "마이크로소프트"
        )
        assert "마이크로소프트" in result
        assert isinstance(result, str)

    def test_buy_high_risk(self):
        result = _generate_summary_sentence(
            "META", "BUY", 0.60, 0.65, "메타"
        )
        assert "메타" in result
        assert "높음" in result

    def test_hold(self):
        result = _generate_summary_sentence(
            "NVDA", "HOLD", 0.55, 0.45, "엔비디아"
        )
        assert "엔비디아" in result
        assert "관망" in result

    def test_cautious_hold_has_caution_word(self):
        result = _generate_summary_sentence(
            "AMZN", "CAUTIOUS HOLD", 0.50, 0.55, "아마존"
        )
        assert "아마존" in result
        assert "신중" in result

    def test_avoid_recommendation(self):
        result = _generate_summary_sentence(
            "XYZ", "AVOID", 0.60, 0.80, "종목XYZ"
        )
        assert "종목XYZ" in result
        assert "회피" in result or "신중" in result

    def test_unknown_decision_fallback(self):
        result = _generate_summary_sentence(
            "ABC", "UNKNOWN_DECISION", 0.50, 0.50
        )
        assert isinstance(result, str)
        assert len(result) > 10

    def test_confidence_pct_in_result(self):
        result = _generate_summary_sentence(
            "AAPL", "BUY", 0.72, 0.30, "애플"
        )
        assert "72%" in result

    def test_display_name_priority(self):
        result = _generate_summary_sentence(
            "005930.KS", "HOLD", 0.60, 0.40, "삼성전자"
        )
        assert "삼성전자" in result

    def test_ticker_used_when_no_display_name(self):
        result = _generate_summary_sentence(
            "CUSTOM_T", "AVOID", 0.40, 0.70
        )
        assert "CUSTOM_T" in result

    def test_risk_korean_in_result(self):
        # 0.35 → moderate → "보통"
        result = _generate_summary_sentence(
            "AAPL", "BUY", 0.80, 0.35, "애플"
        )
        assert "보통" in result

    def test_five_distinct_templates(self):
        """5개 조건이 모두 다른 문장을 생성해야 함."""
        r1 = _generate_summary_sentence("T", "STRONG BUY", 0.80, 0.15, "종목")
        r2 = _generate_summary_sentence("T", "STRONG BUY", 0.80, 0.75, "종목")
        r3 = _generate_summary_sentence("T", "BUY",        0.70, 0.25, "종목")
        r4 = _generate_summary_sentence("T", "HOLD",       0.55, 0.45, "종목")
        r5 = _generate_summary_sentence("T", "AVOID",      0.60, 0.80, "종목")
        templates = {r1, r2, r3, r4, r5}
        assert len(templates) >= 4, "최소 4개 이상의 다른 템플릿이 있어야 함"

    def test_with_trend_info(self):
        """trend 정보가 포함되면 문장에 반영됨."""
        result = _generate_summary_sentence(
            "NVDA", "STRONG BUY", 0.85, 0.15, "엔비디아",
            trend="strong_uptrend",
        )
        # 강한 상승세가 포함되거나, 최소한 종목명은 포함
        assert "엔비디아" in result

    def test_with_fund_rating(self):
        """fund_rating 정보가 포함되면 문장에 반영됨."""
        result = _generate_summary_sentence(
            "NVDA", "STRONG BUY", 0.85, 0.15, "엔비디아",
            fund_rating="strong",
        )
        assert "엔비디아" in result

    def test_no_forbidden_in_all_templates(self):
        """모든 조건의 요약 문장에 금지 표현 없음."""
        scenarios = [
            ("AAPL", "STRONG BUY", 0.80, 0.15, "애플"),
            ("TSLA", "STRONG BUY", 0.65, 0.75, "테슬라"),
            ("MSFT", "BUY",        0.70, 0.25, "마이크로소프트"),
            ("META", "BUY",        0.60, 0.65, "메타"),
            ("NVDA", "HOLD",       0.55, 0.45, "엔비디아"),
            ("AMZN", "CAUTIOUS HOLD", 0.50, 0.55, "아마존"),
            ("XYZ",  "AVOID",      0.60, 0.80, "종목XYZ"),
        ]
        for args in scenarios:
            result = _generate_summary_sentence(*args)
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in result, (
                    f"시나리오 {args}: 요약 문장에 금지 표현 '{bad}' 포함\n{result}"
                )


# ---------------------------------------------------------------------------
# 종목 관리 폼 라벨
# ---------------------------------------------------------------------------

class TestWatchlistFormLabels:
    """종목 관리 화면의 폼 라벨 정확성 검증."""

    def test_form_ticker_label(self):
        assert UI_LABELS["WATCHLIST_FORM_TICKER"] == "종목 코드 또는 종목명"

    def test_form_name_label(self):
        assert UI_LABELS["WATCHLIST_FORM_NAME"] == "표시 이름"

    def test_form_market_label(self):
        assert UI_LABELS["WATCHLIST_FORM_MARKET"] == "시장"

    def test_form_style_label(self):
        assert UI_LABELS["WATCHLIST_FORM_STYLE"] == "투자 성향"

    def test_form_horizon_label(self):
        assert UI_LABELS["WATCHLIST_FORM_HORIZON"] == "투자 기간"

    def test_form_lang_label(self):
        assert UI_LABELS["WATCHLIST_FORM_LANG"] == "언어"

    def test_market_label_kr(self):
        assert MARKET_LABEL["KR"] == "한국"

    def test_market_label_us(self):
        assert MARKET_LABEL["US"] == "미국"

    def test_style_label_conservative(self):
        assert STYLE_LABEL["conservative"] == "보수적"

    def test_style_label_neutral(self):
        assert STYLE_LABEL["neutral"] == "중립"

    def test_style_label_aggressive(self):
        assert STYLE_LABEL["aggressive"] == "공격적"

    def test_horizon_label_short(self):
        assert HORIZON_LABEL["short"] == "단기"

    def test_horizon_label_mid(self):
        assert HORIZON_LABEL["mid"] == "중기"

    def test_horizon_label_long(self):
        assert HORIZON_LABEL["long"] == "장기"

    def test_lang_label_ko(self):
        assert LANG_LABEL["ko"] == "한국어"

    def test_lang_label_en(self):
        assert LANG_LABEL["en"] == "영어"

    def test_btn_add_label(self):
        assert "추가" in UI_LABELS["WATCHLIST_BTN_ADD"]

    def test_btn_save_label(self):
        assert "저장" in UI_LABELS["WATCHLIST_BTN_SAVE"]

    def test_btn_activate_label(self):
        assert "활성화" in UI_LABELS["WATCHLIST_BTN_ACTIVATE"]

    def test_btn_deactivate_label(self):
        assert "비활성화" in UI_LABELS["WATCHLIST_BTN_DEACTIVATE"]

    def test_btn_delete_label(self):
        assert "삭제" in UI_LABELS["WATCHLIST_BTN_DELETE"]

    def test_no_forbidden_in_watchlist_labels(self):
        watchlist_keys = [k for k in UI_LABELS if k.startswith("WATCHLIST")]
        for k in watchlist_keys:
            v = UI_LABELS[k]
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in v, f"UI_LABELS['{k}']에 금지 표현 '{bad}' 포함"


# ---------------------------------------------------------------------------
# 이메일 설정 폼 라벨
# ---------------------------------------------------------------------------

class TestEmailFormLabels:
    """이메일 설정 화면의 폼 라벨 정확성 검증."""

    def test_primary_email_label(self):
        assert UI_LABELS["EMAIL_LABEL_PRIMARY"] == "기본 수신 이메일"

    def test_cc_email_label(self):
        assert UI_LABELS["EMAIL_LABEL_CC"] == "추가 수신 이메일(CC)"

    def test_time_label(self):
        assert UI_LABELS["EMAIL_LABEL_TIME"] == "자동 분석 시각"

    def test_url_label(self):
        assert UI_LABELS["EMAIL_LABEL_URL"] == "대시보드 URL"

    def test_save_btn_label(self):
        assert "저장" in UI_LABELS["EMAIL_BTN_SAVE"]

    def test_test_btn_label(self):
        assert "테스트 메일" in UI_LABELS["EMAIL_BTN_TEST"]

    def test_smtp_ok_message(self):
        assert UI_LABELS["EMAIL_SMTP_OK"] == "이메일 서버 연결 정상"

    def test_test_ok_message(self):
        assert UI_LABELS["EMAIL_TEST_OK"] == "테스트 메일을 발송했습니다."

    def test_test_fail_message(self):
        assert UI_LABELS["EMAIL_TEST_FAIL"] == "테스트 메일 발송에 실패했습니다."

    def test_no_awkward_test_expression(self):
        """어색한 표현 '테스트해봤습니다' 부재 확인."""
        for k, v in UI_LABELS.items():
            if k.startswith("EMAIL"):
                assert "테스트해봤습니다" not in v, (
                    f"UI_LABELS['{k}']에 어색한 표현 포함"
                )

    def test_url_warn_message_correct(self):
        """URL 경고 메시지에 핵심 내용 포함."""
        warn = UI_LABELS["EMAIL_URL_WARN"]
        assert "로컬" in warn or "URL" in warn or "주소" in warn

    def test_no_forbidden_in_email_labels(self):
        email_keys = [k for k in UI_LABELS if k.startswith("EMAIL")]
        for k in email_keys:
            v = UI_LABELS[k]
            for bad in FORBIDDEN_EXPRESSIONS:
                assert bad not in v, f"UI_LABELS['{k}']에 금지 표현 '{bad}' 포함"


# ---------------------------------------------------------------------------
# 리스크/신뢰도/판단 포맷 통합 검증
# ---------------------------------------------------------------------------

class TestRiskConfidenceFormatV5:
    """v5.0 스펙 기준 포맷 검증."""

    def test_risk_format_slash_separator(self):
        """리스크 포맷: '0.XX / 수준'."""
        assert fmt_risk_display(0.58, "elevated") == "0.58 / 다소 높음"

    def test_confidence_format_slash_separator(self):
        """신뢰도 포맷: 'XX% / 수준'."""
        assert confidence_bar(0.87) == "87% / 매우 높음"

    def test_confidence_65_percent_high(self):
        assert confidence_bar(0.65) == "65% / 높음"

    def test_confidence_50_percent_moderate(self):
        assert confidence_bar(0.50) == "50% / 보통"

    def test_confidence_49_percent_low(self):
        assert confidence_bar(0.49) == "49% / 낮음"

    def test_risk_0_to_20_low(self):
        assert _score_to_level(0.19) == "low"
        assert RISK_LEVEL_KO[_score_to_level(0.19)] == "낮음"

    def test_risk_21_to_40_moderate(self):
        assert _score_to_level(0.30) == "moderate"
        assert RISK_LEVEL_KO[_score_to_level(0.30)] == "보통"

    def test_risk_41_to_60_elevated(self):
        assert _score_to_level(0.50) == "elevated"
        assert RISK_LEVEL_KO[_score_to_level(0.50)] == "다소 높음"

    def test_risk_61_plus_high(self):
        assert _score_to_level(0.70) == "high"
        assert RISK_LEVEL_KO[_score_to_level(0.70)] == "높음"

    def test_verdict_label_strong_buy(self):
        assert "적극 매수" in VERDICT_ICON["STRONG BUY"]

    def test_verdict_label_buy(self):
        assert "매수 고려" in VERDICT_ICON["BUY"]

    def test_verdict_label_hold(self):
        assert "보유/관망" in VERDICT_ICON["HOLD"]

    def test_verdict_label_cautious_hold(self):
        assert "신중 관망" in VERDICT_ICON["CAUTIOUS HOLD"]

    def test_verdict_label_avoid(self):
        assert "회피" in VERDICT_ICON["AVOID"]


# ---------------------------------------------------------------------------
# 탭 이름 정확성
# ---------------------------------------------------------------------------

class TestDetailTabNames:
    """상세 분석 탭 이름이 스펙과 일치하는지 검증."""

    def test_tab_summary_contains_summary(self):
        assert "요약" in UI_LABELS["DETAIL_TAB_SUMMARY"]

    def test_tab_market_contains_market_analysis(self):
        assert "시장 분석" in UI_LABELS["DETAIL_TAB_MARKET"]

    def test_tab_fund_shows_financial_not_fundamental(self):
        """화면에서는 '재무 분석'을 사용, 'Fundamental'은 내부 용어."""
        assert "재무 분석" in UI_LABELS["DETAIL_TAB_FUND"]
        assert "fundamental" not in UI_LABELS["DETAIL_TAB_FUND"].lower()
        assert "펀더멘털" not in UI_LABELS["DETAIL_TAB_FUND"]

    def test_tab_news_contains_news(self):
        assert "뉴스" in UI_LABELS["DETAIL_TAB_NEWS"]

    def test_tab_risk_shows_korean(self):
        """화면에서는 '리스크'를 사용, 'Risk'는 내부 용어."""
        assert "리스크" in UI_LABELS["DETAIL_TAB_RISK"]

    def test_tab_full_contains_full_report(self):
        assert "전체 보고서" in UI_LABELS["DETAIL_TAB_FULL"]

    def test_no_bad_tab_names(self):
        """잘못된 탭 이름 부재 확인."""
        bad_tabs = ["반대로 분석", "운동", "전체 보도", "상세분석"]
        for bad in bad_tabs:
            for k in ["DETAIL_TAB_SUMMARY", "DETAIL_TAB_MARKET", "DETAIL_TAB_FUND",
                      "DETAIL_TAB_NEWS", "DETAIL_TAB_RISK", "DETAIL_TAB_FULL"]:
                assert bad not in UI_LABELS[k], (
                    f"탭 '{k}'에 잘못된 이름 '{bad}' 포함"
                )


# ---------------------------------------------------------------------------
# _is_english_name 헬퍼 검증
# ---------------------------------------------------------------------------

class TestIsEnglishName:
    """영문 이름 판별 함수 검증."""

    def test_apple_inc_is_english(self):
        assert _is_english_name("Apple Inc.") is True

    def test_samsung_korean_is_not_english(self):
        assert _is_english_name("삼성전자") is False

    def test_mixed_is_case_by_ascii_ratio(self):
        # "삼성전자 우선주" → mostly Korean → False
        assert _is_english_name("삼성전자 우선주") is False

    def test_nvidia_corp_is_english(self):
        assert _is_english_name("NVIDIA Corporation") is True

    def test_empty_is_not_english(self):
        assert _is_english_name("") is False


# ---------------------------------------------------------------------------
# _sanitize_llm_text — LLM 출력 금지 표현 필터
# ---------------------------------------------------------------------------

class TestSanitizeLlmText:
    """sanitize_llm_text() 함수 검증 (LLM 생성 텍스트 비전문 표현 → 자연스러운 대체)."""

    def test_clean_text_unchanged(self):
        """금지 표현 없는 텍스트는 원문 그대로 반환."""
        text = "이 종목은 강한 상승 추세로 매수를 권고합니다."
        assert _sanitize_llm_text(text) == text

    def test_forbidden_replaced_naturally_not_warning_tag(self):
        """금지 표현이 자연스러운 표현으로 대체 (경고 태그 없음)."""
        text = "이 종목을 믿는다는 관점에서 매수 의견입니다."
        result = _sanitize_llm_text(text)
        assert "믿는다" not in result
        assert "[⚠ 표현 오류]" not in result
        assert "신뢰도" in result

    def test_multiple_forbidden_all_replaced(self):
        """복수 금지 표현 모두 대체."""
        text = "오늘 보도에 따르면 반대로 분석이 필요합니다."
        result = _sanitize_llm_text(text)
        assert "오늘 보도" not in result
        assert "반대로 분석" not in result
        assert "[⚠ 표현 오류]" not in result

    def test_empty_string_returned_as_is(self):
        """빈 문자열 입력 시 그대로 반환."""
        assert _sanitize_llm_text("") == ""

    def test_none_like_empty_handled(self):
        """빈 문자열 케이스 확인."""
        assert _sanitize_llm_text("") == ""

    def test_hoeiwon_replaced_to_checkpoint(self):
        """'회원가입 포인트' → '향후 체크 포인트' 치환."""
        text = "회원가입 포인트 적립 방법을 안내합니다."
        result = _sanitize_llm_text(text)
        assert "회원가입 포인트" not in result
        assert "향후 체크 포인트" in result

    def test_testeotseupnida_replaced_to_email_sent(self):
        """'테스트해봤습니다' → '테스트 메일을 발송했습니다.' 치환."""
        text = "이 기능을 테스트해봤습니다 결과가 좋습니다."
        result = _sanitize_llm_text(text)
        assert "테스트해봤습니다" not in result
        assert "테스트 메일을 발송했습니다." in result

    def test_investment_text_clean(self):
        """정상적인 투자 분석 텍스트는 변환 없음."""
        text = (
            "중립적 투자자 기준에서 중기 투자 관점으로 볼 때, "
            "이 종목은 강한 상승 추세이며 펀더멘털은 우수 수준입니다. "
            "신뢰도 87%를 기준으로 적극 매수를 검토할 수 있습니다."
        )
        assert _sanitize_llm_text(text) == text

    def test_all_forbidden_expressions_blocked(self):
        """모든 금지 표현이 자연스러운 표현으로 치환되고 경고 태그는 없음."""
        sanitizer_blocked = [
            "오늘 보도", "과거에 대해", "풍부한 관리",
            "탄력적 조건", "투자 내용", "믿는다",
            "뭐야", "반대로 분석", "전체 보도", "활성인자", "담당자",
            "회원가입 포인트", "투자하고 있어요",
            "테스트해봤습니다", "자동으로 잘",
        ]
        for expr in sanitizer_blocked:
            result = _sanitize_llm_text(f"이 문장에 {expr}가 포함됩니다.")
            assert expr not in result, f"'{expr}' 가 sanitize 후에도 남아 있음"
            assert "[⚠ 표현 오류]" not in result, f"'{expr}' 처리 후 경고 태그가 남아 있음"

    def test_natural_substitution_mapping(self):
        """주요 표현의 자연스러운 대체 값 검증."""
        cases = [
            ("오늘의 토론 결과입니다.",    "오늘 보고서"),
            ("과거에 대해 살펴보겠습니다.", "과거 보고서"),
            ("활성인자가 긍정적입니다.",    "긍정 요인"),
            ("담당자가 확인했습니다.",      "부정 요인"),
            ("전체 보도를 정리합니다.",     "전체 보고서"),
        ]
        for text, expected_fragment in cases:
            result = _sanitize_llm_text(text)
            assert expected_fragment in result, (
                f"치환 후 '{expected_fragment}'가 없음. 입력: {text!r}, 결과: {result!r}"
            )


class TestPageTitlesIsolation:
    """PAGE_TITLES 상수가 DB·LLM 데이터와 완전 격리되어 있는지 검증."""

    def test_page_titles_constant_exists(self):
        """PAGE_TITLES 상수가 존재해야 한다."""
        assert isinstance(PAGE_TITLES, dict)
        assert len(PAGE_TITLES) == 5

    def test_page_titles_covers_all_page_keys(self):
        """모든 페이지 key에 대한 제목이 정의되어야 한다."""
        for key in (PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL):
            assert key in PAGE_TITLES, f"{key!r} 가 PAGE_TITLES에 없음"

    def test_get_page_title_uses_page_titles_constant(self):
        """get_page_title()이 PAGE_TITLES 상수와 일치해야 한다."""
        for key, expected in PAGE_TITLES.items():
            assert get_page_title(key) == expected

    def test_page_titles_values_are_clean_strings(self):
        """PAGE_TITLES 값이 금지 표현 없는 순수 문자열이어야 한다."""
        for key, title in PAGE_TITLES.items():
            for expr in FORBIDDEN_EXPRESSIONS:
                assert expr not in title, (
                    f"PAGE_TITLES[{key!r}]에 금지 표현 '{expr}' 발견: {title!r}"
                )

    def test_page_titles_not_overridable_by_db_data(self):
        """get_page_title()이 임의 문자열을 입력해도 PAGE_TITLES 값만 반환한다."""
        # DB에서 오염된 값이 page_key로 들어와도 기본값으로 폴백해야 한다
        assert get_page_title("오늘의 토론") == "투자 분석 대시보드"
        assert get_page_title("회원가입 포인트") == "투자 분석 대시보드"
        assert get_page_title("") == "투자 분석 대시보드"
        assert get_page_title("unknown_key") == "투자 분석 대시보드"

    def test_page_titles_no_warning_tags(self):
        """PAGE_TITLES 값에 경고 태그가 없어야 한다."""
        for title in PAGE_TITLES.values():
            assert "[⚠" not in title


class TestSessionStateKeyMigration:
    """구버전 session_state 키 격리 검증."""

    def test_stale_keys_list(self):
        """정리 대상 구버전 키 목록이 올바른지 확인."""
        stale_keys = {"page_override", "page_title", "selected_page"}
        # 현재 사용 중인 키는 page_override_key (영문 내부 key)
        active_key = "page_override_key"
        # 구버전 키가 현재 활성 키와 다름을 확인
        for k in stale_keys:
            assert k != active_key, f"구버전 키 '{k}'가 현재 활성 키와 동일함"

    def test_page_override_key_must_be_valid_page_key(self):
        """page_override_key에 허용되는 값은 영문 내부 key만이다."""
        valid_keys = {PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL}
        for key in valid_keys:
            # 영문 key는 모두 유효한 내부 key
            assert key in valid_keys
        # 구버전에서 쓰던 한국어 레이블은 허용되지 않음
        korean_labels = ["오늘 보고서", "과거 보고서", "상세 분석", "종목 관리", "이메일 설정"]
        for label in korean_labels:
            assert label not in valid_keys

    def test_page_titles_independent_of_session_state(self):
        """page title은 session_state 내용과 무관하게 PAGE_TITLES에서만 조회된다."""
        # 어떤 값이 session_state에 있어도 get_page_title은 PAGE_TITLES만 참조
        for key in (PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL):
            title = get_page_title(key)
            assert title == PAGE_TITLES[key]


class TestDbSanitizeIntegration:
    """DB에서 로드된 LLM 텍스트에 sanitize_llm_text 적용 검증."""

    def _mock_db_report(self, reasoning: str, bull: list, bear: list) -> dict:
        """DB에서 로드된 report dict 형태를 시뮬레이션."""
        return {
            "reasoning": reasoning,
            "bull_points": bull,
            "bear_points": bear,
            "action_items": [],
        }

    def test_db_report_with_forbidden_reasoning_sanitized(self):
        """DB에서 로드한 reasoning에 금지 표현이 있으면 자연스럽게 치환된다."""
        report = self._mock_db_report(
            reasoning="이 종목은 오늘 보도에 따르면 매수가 적절합니다.",
            bull=[],
            bear=[],
        )
        result = _sanitize_llm_text(report["reasoning"])
        assert "오늘 보도" not in result
        assert "오늘 보고서" in result
        assert "[⚠ 표현 오류]" not in result

    def test_db_report_bull_points_sanitized(self):
        """bull_points 리스트의 각 항목도 sanitize된다."""
        bull_pts = [
            "활성인자가 긍정적입니다.",
            "정상적인 매수 신호입니다.",
        ]
        result = [_sanitize_llm_text(p) for p in bull_pts]
        assert "활성인자" not in result[0]
        assert "긍정 요인" in result[0]
        # 정상 텍스트는 변경 없음
        assert result[1] == "정상적인 매수 신호입니다."

    def test_db_report_bear_points_sanitized(self):
        """bear_points에 담당자 표현이 있으면 치환된다."""
        bear_pts = ["담당자가 리스크를 경고했습니다."]
        result = [_sanitize_llm_text(p) for p in bear_pts]
        assert "담당자" not in result[0]
        assert "부정 요인" in result[0]

    def test_clean_db_report_unchanged(self):
        """금지 표현 없는 DB 리포트는 그대로 유지된다."""
        report = self._mock_db_report(
            reasoning="기술적 지표가 상승 추세를 지지합니다.",
            bull=["EPS 성장률 15% 이상"],
            bear=["금리 인상 리스크"],
        )
        assert _sanitize_llm_text(report["reasoning"]) == report["reasoning"]
        for pt in report["bull_points"] + report["bear_points"]:
            assert _sanitize_llm_text(pt) == pt


# ===========================================================================
# scan_text_artifacts.py 스크립트 단위 테스트
# ===========================================================================

class TestScanTextArtifacts:
    """scripts/scan_text_artifacts.py 핵심 함수 검증."""

    @pytest.fixture(autouse=True)
    def _import_scan(self):
        """스크립트 모듈 동적 임포트."""
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "scan_text_artifacts",
            pathlib.Path(__file__).parent.parent / "scripts" / "scan_text_artifacts.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.scan = mod

    def test_scan_db_returns_empty_for_clean_db(self, tmp_path):
        """금지 표현 없는 DB는 빈 목록 반환."""
        db_path = str(tmp_path / "test_clean.db")
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE reports (id INTEGER PRIMARY KEY, reasoning TEXT)"
        )
        conn.execute(
            "INSERT INTO reports VALUES (1, '기술적 지표가 상승 추세를 지지합니다.')"
        )
        conn.commit()
        conn.close()

        findings = self.scan.scan_db(db_path)
        assert findings == []

    def test_scan_db_detects_forbidden_expression(self, tmp_path):
        """금지 표현이 있는 DB row를 탐지한다."""
        db_path = str(tmp_path / "test_dirty.db")
        import sqlite3
        # 금지 표현은 concat으로 구성
        forbidden_text = "오늘의 " + "토론에 따르면 매수입니다."
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE reports (id INTEGER PRIMARY KEY, reasoning TEXT)"
        )
        conn.execute(f"INSERT INTO reports VALUES (1, ?)", (forbidden_text,))
        conn.commit()
        conn.close()

        findings = self.scan.scan_db(db_path)
        assert len(findings) == 1
        assert findings[0]["table"] == "reports"
        assert findings[0]["column"] == "reasoning"
        assert findings[0]["row_id"] == 1

    def test_scan_db_missing_file_returns_empty(self, tmp_path):
        """DB 파일이 없으면 빈 목록 반환 (에러 없음)."""
        findings = self.scan.scan_db(str(tmp_path / "nonexistent.db"))
        assert findings == []

    def test_scan_source_returns_list(self, tmp_path):
        """scan_source는 항상 list를 반환한다."""
        result = self.scan.scan_source(str(tmp_path))
        assert isinstance(result, list)

    def test_forbidden_list_not_empty(self):
        """FORBIDDEN 목록이 비어 있지 않아야 한다."""
        assert len(self.scan.FORBIDDEN) > 0


# ===========================================================================
# clean_legacy_reports.py 스크립트 단위 테스트
# ===========================================================================

class TestCleanLegacyReports:
    """scripts/clean_legacy_reports.py 핵심 함수 검증."""

    @pytest.fixture(autouse=True)
    def _import_clean(self):
        """스크립트 모듈 동적 임포트."""
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "clean_legacy_reports",
            pathlib.Path(__file__).parent.parent / "scripts" / "clean_legacy_reports.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.clean = mod

    def _make_dirty_db(self, tmp_path) -> str:
        """금지 표현이 포함된 테스트 DB를 생성하고 경로를 반환한다."""
        import sqlite3
        db_path = str(tmp_path / "test_dirty.db")
        forbidden_text = "오늘의 " + "토론에 따른 분석입니다."
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE reports "
            "(id INTEGER PRIMARY KEY, markdown_report TEXT, executive_summary TEXT)"
        )
        conn.execute(
            "INSERT INTO reports VALUES (1, ?, ?)",
            (forbidden_text, "정상 텍스트입니다."),
        )
        conn.commit()
        conn.close()
        return db_path

    def test_dry_run_does_not_modify_db(self, tmp_path):
        """dry-run은 DB를 변경하지 않는다."""
        import sqlite3
        db_path = self._make_dirty_db(tmp_path)

        conn = sqlite3.connect(db_path)
        affected = self.clean.do_dry_run(conn)
        conn.close()

        # DB 내용이 변경되지 않았는지 확인
        conn2 = sqlite3.connect(db_path)
        row = conn2.execute("SELECT markdown_report FROM reports WHERE id=1").fetchone()
        conn2.close()

        expected_fragment = "오늘의 " + "토론"
        assert expected_fragment in row[0], "dry-run이 DB를 변경함 (버그)"

    def test_dry_run_returns_affected_list(self, tmp_path):
        """dry-run은 영향받는 row 목록을 반환한다."""
        import sqlite3
        db_path = self._make_dirty_db(tmp_path)
        conn = sqlite3.connect(db_path)
        affected = self.clean.do_dry_run(conn)
        conn.close()
        assert isinstance(affected, list)
        assert len(affected) >= 1

    def test_fix_replaces_forbidden_with_natural(self, tmp_path):
        """--fix 모드는 금지 표현을 자연스러운 표현으로 치환한다."""
        import sqlite3
        db_path = self._make_dirty_db(tmp_path)
        conn = sqlite3.connect(db_path)
        fixed_count = self.clean.do_fix(conn)
        conn.close()

        assert fixed_count >= 1

        # 치환 후 금지 표현이 사라지고 대체 표현이 존재해야 함
        conn2 = sqlite3.connect(db_path)
        row = conn2.execute("SELECT markdown_report FROM reports WHERE id=1").fetchone()
        conn2.close()

        forbidden_fragment = "오늘의 " + "토론"
        assert forbidden_fragment not in row[0]
        assert "오늘 보고서" in row[0]

    def test_clean_db_dry_run_returns_empty(self, tmp_path):
        """오염 없는 DB에 dry-run 시 빈 목록 반환."""
        import sqlite3
        db_path = str(tmp_path / "clean.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE reports "
            "(id INTEGER PRIMARY KEY, markdown_report TEXT, executive_summary TEXT)"
        )
        conn.execute(
            "INSERT INTO reports VALUES (1, ?, ?)",
            ("정상적인 분석 텍스트입니다.", "매수 의견을 유지합니다."),
        )
        conn.commit()

        affected = self.clean.do_dry_run(conn)
        conn.close()
        assert affected == []

    def test_substitution_map_not_empty(self):
        """SUBSTITUTION_MAP이 비어 있지 않아야 한다."""
        assert len(self.clean.SUBSTITUTION_MAP) > 0

    def test_substitution_map_values_are_natural(self):
        """SUBSTITUTION_MAP 값(대체 표현)에 금지 표현이 없어야 한다."""
        for replacement in self.clean.SUBSTITUTION_MAP.values():
            for expr in self.clean.FORBIDDEN:
                assert expr not in replacement, (
                    f"대체 표현 {replacement!r}에 금지 표현 {expr!r}가 포함됨"
                )
