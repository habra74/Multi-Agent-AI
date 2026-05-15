"""
dashboard.py — 투자 분석 대시보드 v5.0
UI 문구 전면 정리 및 페이지 라우팅 수정
---------------------------------------
Streamlit 기반 투자 분석 관리 화면

메뉴 (내부 key → 화면 표시):
  today      → 오늘 보고서
  history    → 과거 보고서
  detail     → 상세 분석
  watchlist  → 종목 관리
  email      → 이메일 설정
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime, date, timedelta

from config import (
    DB_PATH, INVESTMENT_STYLES, HORIZONS, MARKETS, LANGUAGES,
    DEFAULT_LANGUAGE, SMTP_HOST, SMTP_USER, SMTP_PASSWORD,
)
from db.database import init_db
from db.repository import (
    WatchlistRepository, ReportRepository,
    EmailLogRepository, SettingsRepository,
)
from utils.ticker_normalizer import normalize_ticker, get_display_name, infer_market
from utils.text_filter import sanitize_llm_text as _sanitize_llm_text

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="투자 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===========================================================================
# ★ 페이지 라우팅 상수 — 내부 key(영문)와 화면 표시(한국어) 분리
# ===========================================================================

PAGE_TODAY     = "today"
PAGE_HISTORY   = "history"
PAGE_DETAIL    = "detail"
PAGE_WATCHLIST = "watchlist"
PAGE_EMAIL     = "email"

# key → 화면 표시 레이블 (이모지 + 한국어)
PAGE_MENU: dict = {
    PAGE_TODAY:     "🏠 오늘 보고서",
    PAGE_HISTORY:   "📋 과거 보고서",
    PAGE_DETAIL:    "🔍 상세 분석",
    PAGE_WATCHLIST: "⭐ 종목 관리",
    PAGE_EMAIL:     "🔔 이메일 설정",
}

_MENU_ORDER  = [PAGE_TODAY, PAGE_HISTORY, PAGE_DETAIL, PAGE_WATCHLIST, PAGE_EMAIL]
_MENU_LABELS = [PAGE_MENU[k] for k in _MENU_ORDER]
_LABEL_TO_KEY: dict = {v: k for k, v in PAGE_MENU.items()}


# ★ 페이지 제목 상수 — DB·LLM 데이터와 완전 격리, 이 dict에서만 제목을 가져온다
PAGE_TITLES: dict[str, str] = {
    PAGE_TODAY:     "오늘 보고서",
    PAGE_HISTORY:   "과거 보고서",
    PAGE_DETAIL:    "상세 분석",
    PAGE_WATCHLIST: "종목 관리",
    PAGE_EMAIL:     "이메일 설정",
}


def get_page_title(page_key: str) -> str:
    """페이지 key → 화면 제목 반환 (PAGE_TITLES 상수에서만 조회)."""
    return PAGE_TITLES.get(page_key, "투자 분석 대시보드")


# ===========================================================================
# ★ UI 용어 사전 — 사용자에게 보이는 모든 문구는 이 사전에서만 가져온다
# ===========================================================================

UI_LABELS: dict = {

    # ── 사이드바 ────────────────────────────────────────────────────────────
    "SIDEBAR_TITLE":            "📈 투자 분석",
    "SIDEBAR_DATE_PREFIX":      "기준일",
    "SIDEBAR_OPS":              "🔧 운영 정보",
    "SIDEBAR_URL_LABEL":        "대시보드 URL",
    "SIDEBAR_DB_LABEL":         "DB 경로",
    "SIDEBAR_SCHED_LABEL":      "스케줄러 실행",

    # ── 오늘 보고서 ─────────────────────────────────────────────────────────
    "TODAY_METRIC_LAST_RUN":    "최근 분석 시각",
    "TODAY_METRIC_COUNT":       "오늘 분석 종목",
    "TODAY_METRIC_EMAIL":       "최근 이메일 발송 상태",
    "TODAY_METRIC_NEXT":        "다음 자동 실행",
    "TODAY_NO_ANALYSIS":        "아직 분석 결과가 없습니다",
    "TODAY_COUNT_NONE":         "없음",
    "TODAY_EMAIL_OK":           "✅ 발송 완료",
    "TODAY_EMAIL_FAIL":         "❌ 발송 실패",
    "TODAY_EMAIL_SKIP":         "⬜ 건너뜀",
    "TODAY_EMAIL_NONE":         "— 미발송",
    "TODAY_RUN_SECTION":        "즉시 분석",
    "TODAY_RUN_BTN":            "지금 전체 종목 분석하기",
    "TODAY_RUN_DESC":           "활성화된 종목을 즉시 분석하고 결과를 저장합니다.",
    "TODAY_RUN_EMAIL_CHK":      "분석 완료 후 이메일도 발송",
    "TODAY_NO_ACTIVE":          "활성화된 분석 종목이 없습니다.",
    "TODAY_ADD_WATCHLIST_HINT": "종목 관리 메뉴에서 종목을 추가하세요.",
    "TODAY_TARGET_LABEL":       "분석 대상",
    "TODAY_REPORT_SECTION":     "오늘 생성된 리포트",
    "TODAY_NO_REPORT":          "오늘 생성된 리포트가 없습니다.",
    "TODAY_RUN_HINT":           "위 버튼을 눌러 분석을 시작하세요.",
    "TODAY_SELECT_REPORT":      "보고서 선택 후 상세 보기",
    "TODAY_BTN_DETAIL":         "상세 분석 보기",
    "TODAY_ANALYZING":          "분석 중",
    "TODAY_ANALYSIS_OK":        "분석 완료",
    "TODAY_ANALYSIS_FAIL":      "분석 실패",
    "TODAY_EMAIL_SENDING":      "이메일 발송 중...",
    "TODAY_EMAIL_OK_MSG":       "📧 이메일 발송 완료",
    "TODAY_EMAIL_FAIL_MSG":     "📧 이메일 발송에 실패했습니다. 이메일 설정을 확인하세요.",
    "TODAY_EMAIL_ERR_PREFIX":   "📧 이메일 발송 오류",

    # ── 과거 보고서 ─────────────────────────────────────────────────────────
    "HISTORY_DESC":             "날짜와 종목별로 생성된 투자 분석 리포트를 조회합니다.",
    "HISTORY_NO_DATA":          "저장된 리포트가 없습니다. 오늘 보고서 화면에서 분석을 먼저 실행하세요.",
    "HISTORY_FILTER_SECTION":   "조회 조건",
    "HISTORY_FILTER_PERIOD":    "조회 기간",
    "HISTORY_FILTER_TICKER":    "종목",
    "HISTORY_FILTER_MARKET":    "시장",
    "HISTORY_FILTER_DECISION":  "투자 판단",
    "HISTORY_PERIOD_ALL":       "전체",
    "HISTORY_PERIOD_7D":        "최근 7일",
    "HISTORY_PERIOD_30D":       "최근 30일",
    "HISTORY_PERIOD_90D":       "최근 90일",
    "HISTORY_MARKET_ALL":       "전체",
    "HISTORY_DECISION_ALL":     "전체",
    "HISTORY_TICKER_ALL":       "전체",
    "HISTORY_RESULT_PREFIX":    "조회 결과",
    "HISTORY_NO_RESULT":        "조회 조건에 맞는 리포트가 없습니다.",
    "HISTORY_COL_TICKER":       "종목",
    "HISTORY_COL_COMPANY":      "회사명",
    "HISTORY_COL_DECISION":     "투자 판단",
    "HISTORY_COL_CONFIDENCE":   "신뢰도",
    "HISTORY_COL_RISK":         "리스크 수준",
    "HISTORY_COL_STYLE":        "투자 성향",
    "HISTORY_COL_HORIZON":      "투자 기간",
    "HISTORY_COL_TIME":         "분석 시각",
    "HISTORY_SELECT_REPORT":    "보고서 선택",
    "HISTORY_BTN_DETAIL":       "상세 분석 보기",

    # ── 상세 분석 ───────────────────────────────────────────────────────────
    "DETAIL_DESC":              "선택한 종목의 시장 흐름, 재무 상태, 뉴스, 리스크 요인을 종합적으로 확인합니다.",
    "DETAIL_NO_DATA":           "저장된 리포트가 없습니다.",
    "DETAIL_SELECT_REPORT":     "리포트 선택",
    "DETAIL_NOT_FOUND":         "리포트를 찾을 수 없습니다.",
    "DETAIL_METRIC_DECISION":   "투자 판단",
    "DETAIL_METRIC_CONFIDENCE": "신뢰도",
    "DETAIL_METRIC_RISK":       "리스크 수준",
    "DETAIL_METRIC_TIME":       "분석 시각",
    "DETAIL_TAB_SUMMARY":       "📌 요약",
    "DETAIL_TAB_MARKET":        "📊 시장 분석",
    "DETAIL_TAB_FUND":          "🏢 재무 분석",
    "DETAIL_TAB_NEWS":          "📰 뉴스/이슈",
    "DETAIL_TAB_RISK":          "⚠️ 리스크",
    "DETAIL_TAB_FULL":          "📄 전체 보고서",
    "DETAIL_SECTION_ANALYSIS":  "분석 요약",
    "DETAIL_SECTION_BULL":      "긍정 요인",
    "DETAIL_SECTION_BEAR":      "부정 요인",
    "DETAIL_SECTION_CHECK":     "향후 체크 포인트",
    "DETAIL_BULL_NONE":         "해당 없음",
    "DETAIL_BEAR_NONE":         "해당 없음",
    "DETAIL_SIGNAL_CONFLICT":   (
        "⚡ 신호 충돌 감지 — 기술적 지표와 펀더멘털이 상반된 신호를 보입니다. "
        "신중한 판단이 필요합니다."
    ),
    "DETAIL_CURRENT_PRICE":     "현재 가격",
    "DETAIL_TREND":             "추세",
    "DETAIL_CONFIDENCE":        "신뢰도",
    "DETAIL_BULL_SIGNAL":       "긍정 신호",
    "DETAIL_BEAR_SIGNAL":       "부정 신호",
    "DETAIL_TECH_DETAIL":       "📐 기술적 지표 상세",
    "DETAIL_FUND_GRADE":        "재무 등급",
    "DETAIL_KEY_METRICS":       "주요 재무 지표",
    "DETAIL_FUND_DETAIL":       "📋 전체 재무 데이터",
    "DETAIL_NEWS_SENTIMENT":    "뉴스 심리",
    "DETAIL_NEWS_COUNT":        "수집 기사",
    "DETAIL_NEWS_CONFIDENCE":   "분석 신뢰도",
    "DETAIL_NEWS_CAT":          "주요 뉴스 카테고리",
    "DETAIL_NEWS_TOP5":         "핵심 뉴스 (최대 5건)",
    "DETAIL_NEWS_NO_CARD":      "표시할 뉴스 카드 데이터가 없습니다.",
    "DETAIL_NEWS_NO_DATA":      "수집된 뉴스 데이터가 없습니다.",
    "DETAIL_RISK_LEVEL":        "리스크 수준",
    "DETAIL_RISK_SCORE":        "리스크 점수",
    "DETAIL_RISK_FACTORS":      "주요 리스크 요인",
    "DETAIL_MITIG":             "완화 요인",
    "DETAIL_RISK_NONE":         "식별된 리스크 없음",
    "DETAIL_MITIG_NONE":        "해당 없음",
    "DETAIL_FULL_RAW":          "🔩 고급 보기 (원시 데이터)",
    "DETAIL_FULL_NO_REPORT":    "저장된 보고서가 없습니다.",
    "DETAIL_FULL_NO_RAW":       "원시 데이터 없음",
    "DETAIL_NO_ANALYSIS_DATA":  "데이터가 없습니다.",
    "DETAIL_MARKET_NONE":       "시장 분석 데이터가 없습니다.",
    "DETAIL_FUND_NONE":         "재무 분석 데이터가 없습니다.",
    "DETAIL_NEWS_NONE":         "뉴스 분석 데이터가 없습니다.",
    "DETAIL_RISK_NONE_DATA":    "리스크 분석 데이터가 없습니다.",

    # ── 종목 관리 ───────────────────────────────────────────────────────────
    "WATCHLIST_DESC":           "매일 자동 분석할 종목을 관리합니다. 활성화된 종목만 일일 리포트에 포함됩니다.",
    "WATCHLIST_SECTION_LIST":   "등록된 종목",
    "WATCHLIST_SECTION_ADD":    "종목 추가",
    "WATCHLIST_SECTION_EDIT":   "수정 및 삭제",
    "WATCHLIST_NO_DATA":        "등록된 종목이 없습니다. 아래에서 종목을 추가하세요.",
    "WATCHLIST_COL_CODE":       "종목코드",
    "WATCHLIST_COL_COMPANY":    "회사명",
    "WATCHLIST_COL_MARKET":     "시장",
    "WATCHLIST_COL_STYLE":      "투자 성향",
    "WATCHLIST_COL_HORIZON":    "투자 기간",
    "WATCHLIST_COL_STATUS":     "상태",
    "WATCHLIST_COL_DATE":       "등록일",
    "WATCHLIST_ACTIVE":         "✅ 활성",
    "WATCHLIST_INACTIVE":       "⬜ 비활성",
    "WATCHLIST_FORM_TICKER":    "종목 코드 또는 종목명",
    "WATCHLIST_TICKER_PH":      "예: AAPL, 005930, 삼성전자",
    "WATCHLIST_FORM_NAME":      "표시 이름",
    "WATCHLIST_NAME_PH":        "비워두면 자동 설정",
    "WATCHLIST_NAME_HINT":      "예: Apple, 삼성전자",
    "WATCHLIST_FORM_MARKET":    "시장",
    "WATCHLIST_FORM_STYLE":     "투자 성향",
    "WATCHLIST_FORM_HORIZON":   "투자 기간",
    "WATCHLIST_FORM_LANG":      "언어",
    "WATCHLIST_BTN_ADD":        "➕ 추가",
    "WATCHLIST_BTN_SAVE":       "💾 저장",
    "WATCHLIST_BTN_ACTIVATE":   "✅ 활성화",
    "WATCHLIST_BTN_DEACTIVATE": "⬜ 비활성화",
    "WATCHLIST_BTN_DELETE":     "🗑 삭제",
    "WATCHLIST_BTN_CONFIRM_DEL":"삭제 확인",
    "WATCHLIST_BTN_CANCEL":     "취소",
    "WATCHLIST_MANAGE_SELECT":  "관리할 종목",
    "WATCHLIST_EDIT_SECTION":   "✏️ 정보 수정 및 삭제",
    "WATCHLIST_NO_MANAGE":      "관리할 종목이 없습니다.",
    "WATCHLIST_ERR_NO_TICKER":  "종목 코드를 입력하세요.",
    "WATCHLIST_DELETE_WARN":    "을(를) 영구 삭제합니다. 이 작업은 되돌릴 수 없습니다.",

    # ── 이메일 설정 ─────────────────────────────────────────────────────────
    "EMAIL_DESC":               "일일 리포트 수신자, 자동 실행 시간, 대시보드 URL을 관리합니다.",
    "EMAIL_SMTP_OK":            "이메일 서버 연결 정상",
    "EMAIL_SMTP_FAIL":          "이메일 발송 설정이 없습니다. .env 파일에 SMTP 정보를 입력하세요.",
    "EMAIL_SECTION_RECIPIENT":  "이메일 수신 설정",
    "EMAIL_SECTION_SCHEDULE":   "자동 실행 및 대시보드 URL 설정",
    "EMAIL_SECTION_LOG":        "최근 이메일 발송 이력",
    "EMAIL_LABEL_PRIMARY":      "기본 수신 이메일",
    "EMAIL_LABEL_CC":           "추가 수신 이메일(CC)",
    "EMAIL_CC_HINT":            "한 줄에 하나씩 입력하세요.",
    "EMAIL_LABEL_TIME":         "자동 분석 시각",
    "EMAIL_TIME_HINT":          "HH:MM 형식 (KST 기준)",
    "EMAIL_LABEL_URL":          "대시보드 URL",
    "EMAIL_URL_HINT":           "이메일의 대시보드 열기 링크로 사용됩니다.",
    "EMAIL_BTN_SAVE":           "💾 저장",
    "EMAIL_BTN_TEST":           "📧 테스트 메일 보내기",
    "EMAIL_SAVE_OK":            "✅ 수신 이메일이 저장되었습니다.",
    "EMAIL_SCHED_SAVE_OK":      "✅ 설정이 저장되었습니다.",
    "EMAIL_TEST_OK":            "테스트 메일을 발송했습니다.",
    "EMAIL_TEST_FAIL":          "테스트 메일 발송에 실패했습니다.",
    "EMAIL_ERR_NO_ADDR":        "기본 수신 이메일을 먼저 입력하세요.",
    "EMAIL_ERR_NO_SMTP":        "이메일 서버 설정이 없어 테스트 메일을 보낼 수 없습니다.",
    "EMAIL_ERR_TIME_FMT":       "시각 형식이 잘못되었습니다. HH:MM 형식으로 입력하세요 (예: 07:00).",
    "EMAIL_URL_WARN":           "현재 대시보드 URL이 로컬 주소로 설정되어 있습니다.",
    "EMAIL_URL_WARN_DETAIL":    "외부 기기에서 이메일 버튼을 사용하려면 공개 URL을 입력하세요.",
    "EMAIL_URL_OK":             "대시보드 URL 설정 완료",
    "EMAIL_LOG_TIME":           "발송 시각",
    "EMAIL_LOG_RECIPIENT":      "수신자",
    "EMAIL_LOG_STATUS":         "상태",
    "EMAIL_LOG_ERROR":          "오류 내용",
    "EMAIL_LOG_SUCCESS":        "✅ 성공",
    "EMAIL_LOG_SKIP":           "⬜ 건너뜀",
    "EMAIL_LOG_FAIL":           "❌ 실패",
    "EMAIL_LOG_EMPTY":          "이메일 발송 이력이 없습니다.",
}

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@media (max-width: 768px) {
    div[data-testid="metric-container"] > div:first-child  { font-size: 11px !important; }
    div[data-testid="metric-container"] > div:nth-child(2) { font-size: 17px !important; }
    div[data-testid="column"]  { padding: 2px 3px !important; }
    section[data-testid="stSidebar"] { transform: translateX(-100%); }
    .report-header-card { flex-direction: column !important; }
}
.news-card {
    border: 1px solid #dde3ec;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 12px;
    background: #f8fafc;
    line-height: 1.6;
}
.news-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}
.news-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    background: #e8edf5;
    color: #3a4a6b;
}
.news-badge-positive { background: #d4edda; color: #155724; }
.news-badge-negative { background: #f8d7da; color: #721c24; }
.news-badge-neutral  { background: #e2e3e5; color: #383d41; }
.news-badge-mixed    { background: #fff3cd; color: #856404; }
.news-headline {
    font-weight: 600;
    font-size: 13.5px;
    color: #1a1a2e;
    margin-bottom: 4px;
}
.news-interp {
    font-size: 12.5px;
    color: #4a5568;
    border-left: 3px solid #a0aec0;
    padding-left: 8px;
    margin: 6px 0;
}
.news-meta { font-size: 11.5px; color: #718096; }
.verdict-badge {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 14px;
    color: #fff;
    margin-right: 4px;
}
.report-header-card {
    background: linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 100%);
    border: 1px solid #d0d9f0;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB 초기화
# ---------------------------------------------------------------------------
@st.cache_resource
def get_repos():
    init_db(DB_PATH)
    return (
        WatchlistRepository(DB_PATH),
        ReportRepository(DB_PATH),
        EmailLogRepository(DB_PATH),
        SettingsRepository(DB_PATH),
    )


wl_repo, rp_repo, email_repo, settings_repo = get_repos()

# ---------------------------------------------------------------------------
# 도메인 상수
# ---------------------------------------------------------------------------
VERDICT_ICON = {
    "STRONG BUY":    "🟢 적극 매수",
    "BUY":           "🟩 매수 고려",
    "HOLD":          "🟡 보유/관망",
    "CAUTIOUS HOLD": "🟠 신중 관망",
    "AVOID":         "🔴 회피",
}
VERDICT_COLOR = {
    "STRONG BUY":    "#1a7a1a",
    "BUY":           "#3da13d",
    "HOLD":          "#9c8c00",
    "CAUTIOUS HOLD": "#c06000",
    "AVOID":         "#c0392b",
}
STYLE_LABEL = {
    "conservative": "보수적",
    "neutral":      "중립",
    "aggressive":   "공격적",
}
HORIZON_LABEL = {
    "short": "단기",
    "mid":   "중기",
    "long":  "장기",
}
MARKET_LABEL = {
    "US": "미국",
    "KR": "한국",
}
LANG_LABEL = {
    "ko": "한국어",
    "en": "영어",
}
TREND_KO = {
    "strong_uptrend":   "강한 상승세",
    "uptrend":          "상승세",
    "sideways":         "횡보",
    "downtrend":        "하락세",
    "strong_downtrend": "강한 하락세",
    "unknown":          "불명확",
}
FUND_RATING_KO = {
    "strong":   "우수",
    "moderate": "보통",
    "weak":     "취약",
    "poor":     "불량",
}
RISK_LEVEL_KO = {
    "low":       "낮음",
    "moderate":  "보통",
    "elevated":  "다소 높음",
    "high":      "높음",
    "very_high": "매우 높음",
}
SENT_KO = {
    "positive": "긍정적",
    "negative": "부정적",
    "neutral":  "중립적",
    "mixed":    "혼재",
}
SENT_ICON = {
    "positive": "📈",
    "negative": "📉",
    "neutral":  "📊",
    "mixed":    "↕️",
}
SENT_BADGE_CLASS = {
    "positive": "news-badge news-badge-positive",
    "negative": "news-badge news-badge-negative",
    "neutral":  "news-badge news-badge-neutral",
    "mixed":    "news-badge news-badge-mixed",
}
CAT_KO = {
    "earnings":  "실적",
    "product":   "제품",
    "analyst":   "애널리스트",
    "legal":     "법률/규제",
    "macro":     "거시경제",
    "corporate": "기업이슈",
    "sentiment": "시장심리",
    "general":   "일반",
}

# ---------------------------------------------------------------------------
# 종목 한국어 표시명 사전
# ---------------------------------------------------------------------------
KNOWN_KO_NAMES: dict = {
    "AAPL":      "애플",
    "NVDA":      "엔비디아",
    "MSFT":      "마이크로소프트",
    "GOOGL":     "구글",
    "GOOG":      "구글",
    "AMZN":      "아마존",
    "META":      "메타",
    "TSLA":      "테슬라",
    "NFLX":      "넷플릭스",
    "AMD":       "AMD",
    "INTC":      "인텔",
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035720.KS": "카카오",
    "035420.KS": "네이버",
    "005380.KS": "현대차",
    "051910.KS": "LG화학",
    "207940.KS": "삼성바이오로직스",
    "068270.KS": "셀트리온",
    "000270.KS": "기아",
    "096770.KS": "SK이노베이션",
}

# 영문 회사명 → 한국어 (yfinance 등에서 받아오는 원문 회사명 처리)
_ENGLISH_COMPANY_KO: dict = {
    "apple inc.":                    "애플",
    "apple inc":                     "애플",
    "nvidia corporation":            "엔비디아",
    "nvidia corp.":                  "엔비디아",
    "nvidia corp":                   "엔비디아",
    "microsoft corporation":         "마이크로소프트",
    "microsoft corp.":               "마이크로소프트",
    "microsoft corp":                "마이크로소프트",
    "alphabet inc.":                 "구글",
    "alphabet inc":                  "구글",
    "amazon.com, inc.":              "아마존",
    "amazon.com inc.":               "아마존",
    "amazon.com inc":                "아마존",
    "meta platforms, inc.":          "메타",
    "meta platforms inc.":           "메타",
    "meta platforms inc":            "메타",
    "tesla, inc.":                   "테슬라",
    "tesla inc.":                    "테슬라",
    "tesla inc":                     "테슬라",
    "netflix, inc.":                 "넷플릭스",
    "netflix inc.":                  "넷플릭스",
    "netflix inc":                   "넷플릭스",
    "advanced micro devices, inc.":  "AMD",
    "advanced micro devices inc":    "AMD",
    "intel corporation":             "인텔",
    "intel corp.":                   "인텔",
    "intel corp":                    "인텔",
    "samsung electronics co., ltd.": "삼성전자",
    "samsung electronics":           "삼성전자",
    "sk hynix inc.":                 "SK하이닉스",
    "sk hynix":                      "SK하이닉스",
    "kakao corp.":                   "카카오",
    "kakao corp":                    "카카오",
    "naver corporation":             "네이버",
    "naver corp":                    "네이버",
    "hyundai motor company":         "현대차",
    "hyundai motor":                 "현대차",
    "lg chem, ltd.":                 "LG화학",
    "lg chem":                       "LG화학",
    "samsung biologics":             "삼성바이오로직스",
    "celltrion, inc.":               "셀트리온",
    "celltrion":                     "셀트리온",
    "kia corporation":               "기아",
    "kia corp":                      "기아",
    "sk innovation co., ltd.":       "SK이노베이션",
    "sk innovation":                 "SK이노베이션",
}


# ---------------------------------------------------------------------------
# 헬퍼 함수 — 순수 함수 (Streamlit 미사용, 단위 테스트 가능)
# ---------------------------------------------------------------------------

def normalize_company_name_ko(display_name: str) -> str:
    """영문 회사명을 한국어 표시명으로 변환.

    알 수 없는 이름은 원문 그대로 반환.
    예) "Apple Inc." → "애플", "NVIDIA Corporation" → "엔비디아"
    """
    if not display_name:
        return display_name
    lower = display_name.strip().lower()
    return _ENGLISH_COMPANY_KO.get(lower, display_name)


def _is_english_name(name: str) -> bool:
    """문자열이 주로 영문/ASCII로 구성되었는지 확인 (영문 회사명 판별용)."""
    if not name:
        return False
    ascii_count = sum(1 for c in name if c.isascii())
    return ascii_count / len(name) >= 0.7


def get_display_name_ko(ticker: str, display_name: str = "") -> str:
    """종목코드에서 최적의 한국어 표시명 반환.

    우선순위:
    1. 영문 display_name → 한국어 변환 성공 시 반환
    2. KNOWN_KO_NAMES에 ticker 존재 시 반환
    3. 비영문 커스텀 display_name 반환
    4. ticker 그대로 반환
    """
    dn = (display_name or "").strip()

    # 1. 영문 회사명이면 한국어 변환 시도
    if dn and dn != ticker and _is_english_name(dn):
        converted = normalize_company_name_ko(dn)
        if converted != dn:
            return converted

    # 2. KNOWN_KO_NAMES
    ko = KNOWN_KO_NAMES.get(ticker, KNOWN_KO_NAMES.get(ticker.upper(), ""))
    if ko:
        return ko

    # 3. 커스텀 한국어 display_name
    if dn and dn != ticker:
        return dn

    # 4. ticker 그대로
    return ticker


def fmt_risk_display(score: float, level: str = "") -> str:
    """리스크 점수와 한국어 수준을 함께 표시.

    예: fmt_risk_display(0.34, "moderate") → "0.34 / 보통"
    """
    level_ko  = RISK_LEVEL_KO.get(level, "")
    score_str = f"{score:.2f}"
    return f"{score_str} / {level_ko}" if level_ko else score_str


def is_localhost_url(url: str) -> bool:
    """URL이 로컬 주소인지 확인."""
    return "localhost" in url or "127.0.0.1" in url


def fmt_next_schedule(sched_time: str) -> str:
    """다음 자동 실행 시각을 '오늘 HH:MM' 또는 '내일 HH:MM'으로 반환."""
    try:
        now = datetime.now()
        h, m = map(int, sched_time.split(":"))
        scheduled_today = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < scheduled_today:
            return f"오늘 {sched_time}"
        return f"내일 {sched_time}"
    except Exception:
        return f"매일 {sched_time}"


def _fmt_price(price, market: str = "US") -> str:
    """시장별 가격 포맷 (US: $X.XX, KR: X,XXX원)."""
    if price is None:
        return "N/A"
    try:
        price = float(price)
    except (TypeError, ValueError):
        return str(price)
    if market == "KR":
        return f"{price:,.0f}원"
    return f"${price:.2f}"


def verdict_badge(decision: str) -> str:
    """판정 배지 HTML 반환."""
    icon  = VERDICT_ICON.get(decision, f"⬜ {decision}")
    color = VERDICT_COLOR.get(decision, "#555")
    return (
        f'<span class="verdict-badge" style="background:{color};">'
        f"{icon}</span>"
    )


def fmt_dt(dt_str) -> str:
    """ISO datetime → 'YYYY-MM-DD HH:MM' 형식."""
    try:
        return datetime.fromisoformat(str(dt_str)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt_str) if dt_str else "-"


def confidence_bar(conf: float) -> str:
    """신뢰도 → 'XX% / 수준' 형식 문자열.

    80%↑ 매우 높음 / 65%↑ 높음 / 50%↑ 보통 / 25%↑ 낮음 / 미만 매우 낮음
    """
    pct = round(conf * 100)
    label = (
        "매우 높음" if pct >= 80 else
        "높음"      if pct >= 65 else
        "보통"      if pct >= 50 else
        "낮음"      if pct >= 25 else
        "매우 낮음"
    )
    return f"{pct}% / {label}"


def _score_to_level(score: float) -> str:
    """risk_score(0~1) → risk_level 문자열."""
    if score < 0.2:
        return "low"
    if score < 0.4:
        return "moderate"
    if score < 0.6:
        return "elevated"
    if score < 0.8:
        return "high"
    return "very_high"


def _estimate_risk_level_ko(score: float) -> str:
    """risk_score → 한국어 수준 문자열."""
    return RISK_LEVEL_KO.get(_score_to_level(score), "")


def _generate_summary_sentence(
    ticker: str,
    decision: str,
    confidence: float,
    risk_score: float,
    disp_name: str = "",
    trend: str = "",
    fund_rating: str = "",
) -> str:
    """투자 판단·신뢰도·리스크·추세·재무 등급을 바탕으로
    자연스러운 한국어 요약 문장을 생성한다.

    조건별로 5개 이상의 템플릿 중 하나를 반환한다.
    """
    name      = disp_name or ticker
    conf_pct  = int(round(confidence * 100))
    rlevel    = _score_to_level(risk_score)
    risk_ko   = RISK_LEVEL_KO.get(rlevel, "")
    trend_ko  = TREND_KO.get(trend, "")
    fund_ko   = FUND_RATING_KO.get(fund_rating, "")

    # ── 템플릿 1: STRONG BUY + 낮음/보통 리스크 ──
    if decision == "STRONG BUY" and rlevel in ("low", "moderate"):
        trend_part = f"{trend_ko} 추세와 함께 " if trend_ko else ""
        fund_part  = f"재무 상태도 {fund_ko}한 편이며, " if fund_ko else ""
        return (
            f"{name}은(는) {trend_part}{fund_part}"
            f"기술적·펀더멘털 지표 모두 강한 매수 신호를 나타내고 있습니다. "
            f"리스크 수준은 {risk_ko}로 비교적 안정적이며, "
            f"신뢰도 {conf_pct}%를 기준으로 적극적인 매수를 검토할 수 있는 시점입니다."
        )

    # ── 템플릿 2: STRONG BUY + 높은 리스크 ──
    if decision == "STRONG BUY" and rlevel in ("elevated", "high", "very_high"):
        return (
            f"{name}은(는) 강한 매수 신호를 보이고 있으나, "
            f"리스크 수준이 {risk_ko}로 변동성에 주의가 필요합니다. "
            f"신뢰도 {conf_pct}%를 참고하되, 분할 매수와 손절 기준 설정을 권장합니다."
        )

    # ── 템플릿 3: BUY + 낮음/보통 리스크 ──
    if decision == "BUY" and rlevel in ("low", "moderate"):
        return (
            f"{name}은(는) 긍정적 지표가 우세하며 매수를 고려할 만한 시점입니다. "
            f"리스크 수준 {risk_ko}, 신뢰도 {conf_pct}%를 기준으로 "
            f"진입 전 단기 변동성을 확인하길 권장합니다."
        )

    # ── 템플릿 4: BUY + 높은 리스크 ──
    if decision == "BUY" and rlevel in ("elevated", "high", "very_high"):
        return (
            f"{name}에 매수 신호가 감지되었으나 리스크 수준이 {risk_ko}로 높습니다. "
            f"신뢰도 {conf_pct}%를 참고하되, 포지션 규모를 보수적으로 유지하고 "
            f"리스크 관리 후 접근하세요."
        )

    # ── 템플릿 5: HOLD / CAUTIOUS HOLD ──
    if decision in ("HOLD", "CAUTIOUS HOLD"):
        caution = "신중한 " if decision == "CAUTIOUS HOLD" else ""
        return (
            f"{name}은(는) 현재 뚜렷한 방향성을 보이지 않고 있습니다. "
            f"리스크 수준 {risk_ko}, 신뢰도 {conf_pct}%를 감안해 "
            f"{caution}관망하며 추가적인 시장 신호를 확인한 후 판단하세요."
        )

    # ── 템플릿 6: AVOID ──
    if decision == "AVOID":
        fund_note = f" 재무 상태는 {fund_ko}입니다." if fund_ko else ""
        return (
            f"{name}은(는) 현재 부정적 지표가 우세합니다.{fund_note} "
            f"리스크 수준이 {risk_ko}이며, 신뢰도 {conf_pct}% 기준으로 "
            f"투자 회피를 권고합니다. 상황 개선 후 재평가를 권장합니다."
        )

    # ── 기본 템플릿 (판단 미정 등) ──
    return (
        f"{name}에 대한 분석이 완료되었습니다. "
        f"리스크 수준 {risk_ko}, 신뢰도 {conf_pct}%입니다. "
        f"상세 탭에서 세부 분석 내용을 확인하세요."
    )


def _news_card_html(item: dict, index: int) -> str:
    """뉴스 항목 하나를 카드형 HTML로 변환."""
    headline = item.get("headline", "")[:130]
    interp   = item.get("interpretation", "")
    link     = item.get("link", "")
    sent     = item.get("sentiment", "neutral")
    cat_raw  = item.get("category", "general")
    pub      = item.get("publisher", "")
    pub_date = item.get("date", "")

    cat_ko    = CAT_KO.get(cat_raw, cat_raw)
    sent_ko   = SENT_KO.get(sent, sent)
    sent_icon = SENT_ICON.get(sent, "")
    badge_cls = SENT_BADGE_CLASS.get(sent, "news-badge")

    meta_parts = []
    if pub:
        meta_parts.append(pub)
    if pub_date:
        meta_parts.append(pub_date[:10])
    meta_str = " · ".join(meta_parts)

    link_html = (
        f'<a href="{link}" target="_blank" '
        f'style="font-size:12px;color:#3182ce;text-decoration:none;">'
        f"🔗 기사 보기</a>"
        if link else ""
    )

    return (
        f'<div class="news-card">'
        f'<div class="news-card-header">'
        f'<span class="news-badge">{cat_ko}</span>'
        f'<span class="{badge_cls}">{sent_icon} {sent_ko}</span>'
        f"</div>"
        f'<div class="news-headline">{headline}</div>'
        + (f'<div class="news-interp">💡 {interp}</div>' if interp else "")
        + f'<div class="news-meta">{meta_str}'
        + ("&nbsp;&nbsp;" if meta_str and link_html else "")
        + f"{link_html}</div>"
        + "</div>"
    )


# ---------------------------------------------------------------------------
# ★ 구버전(v3/v4) session_state 키 정리 — 오래된 브라우저 세션 오염 방지
#   - page_override  : 화면 레이블(한국어)을 저장하던 구버전 키 → 삭제
#   - page_title     : 페이지 제목 문자열을 저장하던 구버전 키 → 삭제
#   - selected_page  : 구버전 페이지 선택 키 → 삭제
#   v5.0+에서는 page_override_key (영문 내부 key) 만 사용한다.
# ---------------------------------------------------------------------------
for _stale in ("page_override", "page_title", "selected_page"):
    st.session_state.pop(_stale, None)

# ---------------------------------------------------------------------------
# 사이드바 내비게이션
# ---------------------------------------------------------------------------
st.sidebar.title(UI_LABELS["SIDEBAR_TITLE"])
st.sidebar.caption(
    f"{UI_LABELS['SIDEBAR_DATE_PREFIX']}: {date.today().strftime('%Y년 %m월 %d일')}"
)
st.sidebar.markdown("---")

# page_override 처리 — "상세 분석 보기" 버튼 클릭 시 설정
_override_key = st.session_state.pop("page_override_key", None)
if _override_key and _override_key in _MENU_ORDER:
    _default_idx = _MENU_ORDER.index(_override_key)
else:
    _default_idx = 0

_selected_label = st.sidebar.radio(
    "메뉴",
    _MENU_LABELS,
    index=_default_idx,
    label_visibility="collapsed",
)
_page_key = _LABEL_TO_KEY[_selected_label]

st.sidebar.markdown("---")

# 운영 정보 — 개발자용, 접기 영역으로만 표시
with st.sidebar.expander(UI_LABELS["SIDEBAR_OPS"], expanded=False):
    _base_url_sidebar = settings_repo.get("base_url", "http://localhost:8501")
    st.caption(f"{UI_LABELS['SIDEBAR_URL_LABEL']}:\n`{_base_url_sidebar}`")
    st.caption(f"{UI_LABELS['SIDEBAR_DB_LABEL']}:\n`{DB_PATH}`")
    st.caption(
        f"**{UI_LABELS['SIDEBAR_SCHED_LABEL']}:**\n"
        "```\npython scheduler/scheduler.py\n```"
    )


# ===========================================================================
# 1. 오늘 보고서
# ===========================================================================
if _page_key == PAGE_TODAY:
    st.title(get_page_title(PAGE_TODAY))

    # ── 운영 요약 메트릭 ──────────────────────────────────────────────────
    today_reports = rp_repo.get_today()
    all_summary   = rp_repo.get_all_summary(limit=1)
    last_run_str  = fmt_dt(all_summary[0]["created_at"]) if all_summary else UI_LABELS["TODAY_NO_ANALYSIS"]

    today_email_logs = email_repo.get_today()
    if today_email_logs:
        latest = today_email_logs[0]
        if latest["status"] == "success":
            email_status = UI_LABELS["TODAY_EMAIL_OK"]
        elif latest["status"] == "failed":
            email_status = UI_LABELS["TODAY_EMAIL_FAIL"]
        else:
            email_status = UI_LABELS["TODAY_EMAIL_SKIP"]
    else:
        email_status = UI_LABELS["TODAY_EMAIL_NONE"]

    sched_time   = settings_repo.get("scheduler_time", "07:00")
    next_run_str = fmt_next_schedule(sched_time)

    today_count     = len(today_reports)
    today_count_str = (
        f"{today_count}개 종목"
        if today_count > 0
        else UI_LABELS["TODAY_COUNT_NONE"]
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(UI_LABELS["TODAY_METRIC_LAST_RUN"], last_run_str)
    c2.metric(UI_LABELS["TODAY_METRIC_COUNT"],    today_count_str)
    c3.metric(UI_LABELS["TODAY_METRIC_EMAIL"],    email_status)
    c4.metric(UI_LABELS["TODAY_METRIC_NEXT"],     next_run_str)

    st.markdown("---")

    # ── 즉시 분석 ─────────────────────────────────────────────────────────
    active_wl = wl_repo.list_active()

    st.subheader(f"⚡ {UI_LABELS['TODAY_RUN_SECTION']}")
    if active_wl:
        active_names = ", ".join(
            get_display_name_ko(w["ticker"], w.get("display_name", ""))
            for w in active_wl
        )
        st.caption(
            f"{UI_LABELS['TODAY_TARGET_LABEL']} ({len(active_wl)}개): {active_names}"
        )
    else:
        st.caption(
            f"{UI_LABELS['TODAY_NO_ACTIVE']} "
            f"{UI_LABELS['TODAY_ADD_WATCHLIST_HINT']}"
        )

    col_btn, col_opt = st.columns([2, 3])
    with col_btn:
        run_now = st.button(
            UI_LABELS["TODAY_RUN_BTN"],
            type="primary",
            disabled=not active_wl,
        )
    with col_opt:
        send_email_after = st.checkbox(
            UI_LABELS["TODAY_RUN_EMAIL_CHK"],
            value=True,
            help="체크 시 분석이 끝난 뒤 설정된 수신자에게 리포트를 자동 발송합니다.",
            disabled=not active_wl,
        )

    st.caption(UI_LABELS["TODAY_RUN_DESC"])

    if run_now and active_wl:
        from main import analyze_and_store

        progress_bar = st.progress(0)
        status_area  = st.empty()
        results_log  = []
        success_ids  = []

        for i, entry in enumerate(active_wl):
            ticker    = entry["ticker"]
            disp_name = get_display_name_ko(ticker, entry.get("display_name", ""))
            status_area.info(
                f"⏳ {UI_LABELS['TODAY_ANALYZING']}: **{disp_name}** ({i+1}/{len(active_wl)})"
            )
            try:
                out = analyze_and_store(
                    ticker   = ticker,
                    market   = entry.get("market",   "US"),
                    style    = entry.get("style",    "neutral"),
                    horizon  = entry.get("horizon",  "mid"),
                    language = entry.get("language", "ko"),
                )
                rid = out.get("report_id")
                results_log.append((disp_name, True, rid))
                if rid:
                    success_ids.append(rid)
            except Exception as exc:
                results_log.append((disp_name, False, str(exc)))
            progress_bar.progress((i + 1) / len(active_wl))

        status_area.empty()
        for name, ok, info in results_log:
            if ok:
                st.success(f"✅ {name}: {UI_LABELS['TODAY_ANALYSIS_OK']}")
            else:
                st.error(f"❌ {name}: {UI_LABELS['TODAY_ANALYSIS_FAIL']} — {info}")

        # 이메일 발송 (옵션)
        if send_email_after and success_ids:
            from email_service.email_sender import send_daily_report
            with st.spinner(UI_LABELS["TODAY_EMAIL_SENDING"]):
                full_rows = [rp_repo.get_by_id(rid) for rid in success_ids if rid]
                full_rows = [r for r in full_rows if r]
                try:
                    ok = send_daily_report(full_rows, db_path=DB_PATH)
                    if ok:
                        st.success(UI_LABELS["TODAY_EMAIL_OK_MSG"])
                    else:
                        st.warning(UI_LABELS["TODAY_EMAIL_FAIL_MSG"])
                except Exception as exc:
                    st.warning(f"{UI_LABELS['TODAY_EMAIL_ERR_PREFIX']}: {exc}")

        st.rerun()

    st.markdown("---")

    # ── 오늘 리포트 목록 ──────────────────────────────────────────────────
    st.subheader(f"📋 {UI_LABELS['TODAY_REPORT_SECTION']} ({len(today_reports)}건)")

    if not today_reports:
        st.info(
            f"{UI_LABELS['TODAY_NO_REPORT']}\n\n"
            f"{UI_LABELS['TODAY_RUN_HINT']}"
        )
    else:
        import pandas as pd
        rows = []
        for r in today_reports:
            ticker     = r["ticker"]
            disp_name  = get_display_name_ko(ticker, r.get("display_name", ""))
            risk_score = r.get("risk_score", 0.0) or 0.0
            rows.append({
                UI_LABELS["HISTORY_COL_TICKER"]:     ticker,
                UI_LABELS["HISTORY_COL_COMPANY"]:    disp_name,
                UI_LABELS["DETAIL_METRIC_DECISION"]: VERDICT_ICON.get(
                    r["final_decision"], r.get("final_decision") or "-"
                ),
                UI_LABELS["DETAIL_METRIC_CONFIDENCE"]: confidence_bar(r.get("confidence", 0)),
                UI_LABELS["DETAIL_METRIC_RISK"]:     fmt_risk_display(
                    risk_score, _score_to_level(risk_score)
                ),
                UI_LABELS["DETAIL_METRIC_TIME"]:     fmt_dt(r["created_at"]),
                "_id":                               r["id"],
            })

        df = pd.DataFrame(rows)
        st.dataframe(df.drop(columns=["_id"]), use_container_width=True, hide_index=True)

        st.markdown("---")
        options = {
            f"{get_display_name_ko(r['ticker'], r.get('display_name',''))} "
            f"({r['ticker']}) — {fmt_dt(r['created_at'])}": r["id"]
            for r in today_reports
        }
        chosen = st.selectbox(UI_LABELS["TODAY_SELECT_REPORT"], list(options.keys()))
        if chosen and st.button(UI_LABELS["TODAY_BTN_DETAIL"]):
            st.session_state["selected_report_id"] = options[chosen]
            st.session_state["page_override_key"]  = PAGE_DETAIL
            st.rerun()


# ===========================================================================
# 2. 과거 보고서
# ===========================================================================
elif _page_key == PAGE_HISTORY:
    st.title(get_page_title(PAGE_HISTORY))
    st.caption(UI_LABELS["HISTORY_DESC"])

    tickers_with_reports = rp_repo.list_tickers()
    watchlist_tickers    = [w["ticker"] for w in wl_repo.list_active()]
    all_tickers          = list(dict.fromkeys(watchlist_tickers + tickers_with_reports))

    if not all_tickers:
        st.info(UI_LABELS["HISTORY_NO_DATA"])
    else:
        # ── 조회 조건 필터 ────────────────────────────────────────────────
        with st.expander(UI_LABELS["HISTORY_FILTER_SECTION"], expanded=True):
            fc1, fc2, fc3, fc4 = st.columns(4)

            # 조회 기간
            period_map = {
                UI_LABELS["HISTORY_PERIOD_ALL"]:  0,
                UI_LABELS["HISTORY_PERIOD_7D"]:   7,
                UI_LABELS["HISTORY_PERIOD_30D"]:  30,
                UI_LABELS["HISTORY_PERIOD_90D"]:  90,
            }
            period_label = fc1.selectbox(
                UI_LABELS["HISTORY_FILTER_PERIOD"],
                list(period_map.keys()),
            )
            filter_days = period_map[period_label]

            # 종목
            ticker_display_map = {
                t: f"{get_display_name_ko(t)} ({t})" for t in all_tickers
            }
            ticker_opts = [UI_LABELS["HISTORY_TICKER_ALL"]] + all_tickers
            sel_ticker = fc2.selectbox(
                UI_LABELS["HISTORY_FILTER_TICKER"],
                ticker_opts,
                format_func=lambda t: ticker_display_map.get(t, t)
                if t != UI_LABELS["HISTORY_TICKER_ALL"] else UI_LABELS["HISTORY_TICKER_ALL"],
            )

            # 시장
            market_opts = [UI_LABELS["HISTORY_MARKET_ALL"]] + MARKETS
            sel_market = fc3.selectbox(
                UI_LABELS["HISTORY_FILTER_MARKET"],
                market_opts,
                format_func=lambda m: MARKET_LABEL.get(m, m)
                if m != UI_LABELS["HISTORY_MARKET_ALL"] else UI_LABELS["HISTORY_MARKET_ALL"],
            )

            # 투자 판단
            decision_opts = [UI_LABELS["HISTORY_DECISION_ALL"]] + list(VERDICT_ICON.keys())
            sel_decision = fc4.selectbox(
                UI_LABELS["HISTORY_FILTER_DECISION"],
                decision_opts,
                format_func=lambda d: VERDICT_ICON.get(d, d)
                if d != UI_LABELS["HISTORY_DECISION_ALL"] else UI_LABELS["HISTORY_DECISION_ALL"],
            )

        # ── 리포트 조회 및 필터링 ─────────────────────────────────────────
        if sel_ticker != UI_LABELS["HISTORY_TICKER_ALL"]:
            history_raw = rp_repo.get_by_ticker(sel_ticker, limit=200)
        else:
            history_raw = rp_repo.get_all_summary(limit=200)

        filtered = []
        cutoff = (
            (datetime.now() - timedelta(days=filter_days)) if filter_days > 0 else None
        )
        for r in history_raw:
            if cutoff:
                try:
                    if datetime.fromisoformat(r["created_at"]) < cutoff:
                        continue
                except Exception:
                    pass
            if (
                sel_market != UI_LABELS["HISTORY_MARKET_ALL"]
                and r.get("market", "") != sel_market
            ):
                continue
            if (
                sel_decision != UI_LABELS["HISTORY_DECISION_ALL"]
                and r.get("final_decision", "") != sel_decision
            ):
                continue
            filtered.append(r)

        st.caption(f"{UI_LABELS['HISTORY_RESULT_PREFIX']}: **{len(filtered)}건**")

        if not filtered:
            st.info(UI_LABELS["HISTORY_NO_RESULT"])
        else:
            import pandas as pd
            rows = []
            for r in filtered:
                rs        = r.get("risk_score", 0.0) or 0.0
                ticker    = r["ticker"]
                disp_name = get_display_name_ko(ticker, r.get("display_name", ""))
                rows.append({
                    UI_LABELS["HISTORY_COL_TICKER"]:   ticker,
                    UI_LABELS["HISTORY_COL_COMPANY"]:  disp_name,
                    UI_LABELS["HISTORY_COL_DECISION"]: VERDICT_ICON.get(
                        r["final_decision"], r.get("final_decision") or "-"
                    ),
                    UI_LABELS["HISTORY_COL_CONFIDENCE"]: confidence_bar(r.get("confidence", 0)),
                    UI_LABELS["HISTORY_COL_RISK"]:     fmt_risk_display(rs, _score_to_level(rs)),
                    UI_LABELS["HISTORY_COL_STYLE"]:    STYLE_LABEL.get(
                        r.get("style", ""), r.get("style", "-")
                    ),
                    UI_LABELS["HISTORY_COL_HORIZON"]:  HORIZON_LABEL.get(
                        r.get("horizon", ""), r.get("horizon", "-")
                    ),
                    UI_LABELS["HISTORY_COL_TIME"]:     fmt_dt(r["created_at"]),
                    "_id":                             r["id"],
                })

            df = pd.DataFrame(rows)
            st.dataframe(df.drop(columns=["_id"]), use_container_width=True, hide_index=True)

            st.markdown("---")
            options = {
                f"{get_display_name_ko(r['ticker'], r.get('display_name',''))} "
                f"({r['ticker']}) | {fmt_dt(r['created_at'])} | "
                f"{VERDICT_ICON.get(r.get('final_decision',''), r.get('final_decision',''))}": r["id"]
                for r in filtered
            }
            chosen = st.selectbox(UI_LABELS["HISTORY_SELECT_REPORT"], list(options.keys()))
            if chosen and st.button(UI_LABELS["HISTORY_BTN_DETAIL"]):
                st.session_state["selected_report_id"] = options[chosen]
                st.session_state["page_override_key"]  = PAGE_DETAIL
                st.rerun()


# ===========================================================================
# 3. 상세 분석
# ===========================================================================
elif _page_key == PAGE_DETAIL:
    st.title(get_page_title(PAGE_DETAIL))
    st.caption(UI_LABELS["DETAIL_DESC"])

    all_reports = rp_repo.get_all_summary(limit=100)

    if not all_reports:
        st.info(UI_LABELS["DETAIL_NO_DATA"])
    else:
        options = {
            f"{get_display_name_ko(r['ticker'], r.get('display_name',''))} "
            f"({r['ticker']}) | {fmt_dt(r['created_at'])} | "
            f"{VERDICT_ICON.get(r['final_decision'], r.get('final_decision') or '')}": r["id"]
            for r in all_reports
        }

        # 다른 페이지에서 넘어온 경우 사전 선택
        default_key    = None
        preselected_id = st.session_state.get("selected_report_id")
        if preselected_id:
            for k, v in options.items():
                if v == preselected_id:
                    default_key = k
                    break
            st.session_state.pop("selected_report_id", None)

        keys_list   = list(options.keys())
        default_idx = keys_list.index(default_key) if default_key in keys_list else 0

        chosen = st.selectbox(UI_LABELS["DETAIL_SELECT_REPORT"], keys_list, index=default_idx)

        if chosen:
            report_id = options[chosen]
            report    = rp_repo.get_by_id(report_id)

            if not report:
                st.error(UI_LABELS["DETAIL_NOT_FOUND"])
            else:
                ticker    = report["ticker"]
                disp_name = get_display_name_ko(ticker, report.get("display_name", ""))
                mkt       = report.get("market", "US")
                rs        = report.get("risk_score", 0.0) or 0.0

                # ── JSON 파싱 ────────────────────────────────────────────────
                json_str  = report.get("json_report", "{}")
                json_data: dict = {}
                try:
                    json_data = (
                        json.loads(json_str)
                        if isinstance(json_str, str)
                        else (json_str or {})
                    )
                except Exception:
                    pass

                da = json_data.get("decision", {})
                ma = json_data.get("market_analysis", {})
                fa = json_data.get("fundamental_analysis", {})
                na = json_data.get("news_analysis", {})
                ra = json_data.get("risk_analysis", {})

                risk_level_raw = ra.get("risk_level", _score_to_level(rs))
                risk_level_ko  = RISK_LEVEL_KO.get(risk_level_raw, risk_level_raw)

                # ── 헤더 카드 ────────────────────────────────────────────────
                mkt_disp   = MARKET_LABEL.get(mkt, mkt)
                style_disp = STYLE_LABEL.get(report.get("style", ""), "-")
                hor_disp   = HORIZON_LABEL.get(report.get("horizon", ""), "-")

                st.markdown(
                    f'<div class="report-header-card">'
                    f'<div style="font-size:20px;font-weight:700;margin-bottom:10px;">'
                    f"{disp_name}"
                    f'<span style="font-size:14px;font-weight:400;color:#718096;margin-left:8px;">'
                    f"{ticker} · {mkt_disp} · {style_disp} · {hor_disp}"
                    f"</span></div></div>",
                    unsafe_allow_html=True,
                )

                hc1, hc2, hc3, hc4 = st.columns(4)
                hc1.metric(
                    UI_LABELS["DETAIL_METRIC_DECISION"],
                    VERDICT_ICON.get(
                        report["final_decision"],
                        report.get("final_decision") or "-",
                    ),
                )
                hc2.metric(
                    UI_LABELS["DETAIL_METRIC_CONFIDENCE"],
                    confidence_bar(report.get("confidence", 0)),
                )
                hc3.metric(
                    UI_LABELS["DETAIL_METRIC_RISK"],
                    fmt_risk_display(rs, risk_level_raw),
                )
                hc4.metric(
                    UI_LABELS["DETAIL_METRIC_TIME"],
                    fmt_dt(report["created_at"]),
                )

                # ── 자동 생성 요약 문장 ──────────────────────────────────────
                auto_sentence = _generate_summary_sentence(
                    ticker     = ticker,
                    decision   = report.get("final_decision", ""),
                    confidence = report.get("confidence", 0.0) or 0.0,
                    risk_score = rs,
                    disp_name  = disp_name,
                    trend      = ma.get("trend", ""),
                    fund_rating= fa.get("fundamental_rating", ""),
                )
                st.info(auto_sentence)

                st.markdown("---")

                # ── 탭 ───────────────────────────────────────────────────────
                (
                    tab_summary,
                    tab_market,
                    tab_fund,
                    tab_news,
                    tab_risk,
                    tab_full,
                ) = st.tabs([
                    UI_LABELS["DETAIL_TAB_SUMMARY"],
                    UI_LABELS["DETAIL_TAB_MARKET"],
                    UI_LABELS["DETAIL_TAB_FUND"],
                    UI_LABELS["DETAIL_TAB_NEWS"],
                    UI_LABELS["DETAIL_TAB_RISK"],
                    UI_LABELS["DETAIL_TAB_FULL"],
                ])

                # ── 탭 1: 요약 ───────────────────────────────────────────────
                with tab_summary:
                    reasoning = _sanitize_llm_text(da.get("reasoning", ""))
                    if reasoning:
                        st.markdown(f"##### {UI_LABELS['DETAIL_SECTION_ANALYSIS']}")
                        st.info(reasoning)

                    bull_pts = [_sanitize_llm_text(p) for p in da.get("bull_points", [])]
                    bear_pts = [_sanitize_llm_text(p) for p in da.get("bear_points", [])]
                    col_b, col_r = st.columns(2)
                    with col_b:
                        st.markdown(
                            f"##### ✅ {UI_LABELS['DETAIL_SECTION_BULL']}"
                        )
                        if bull_pts:
                            for pt in bull_pts:
                                st.markdown(f"- {pt}")
                        else:
                            st.caption(UI_LABELS["DETAIL_BULL_NONE"])
                    with col_r:
                        st.markdown(
                            f"##### ⚠️ {UI_LABELS['DETAIL_SECTION_BEAR']}"
                        )
                        if bear_pts:
                            for pt in bear_pts:
                                st.markdown(f"- {pt}")
                        else:
                            st.caption(UI_LABELS["DETAIL_BEAR_NONE"])

                    actions = [_sanitize_llm_text(a) for a in da.get("action_items", [])]
                    if actions:
                        st.markdown(
                            f"##### 🔍 {UI_LABELS['DETAIL_SECTION_CHECK']}"
                        )
                        for a in actions:
                            st.markdown(f"- {a}")

                    if da.get("conflict_detected"):
                        st.warning(UI_LABELS["DETAIL_SIGNAL_CONFLICT"])

                # ── 탭 2: 시장 분석 ──────────────────────────────────────────
                with tab_market:
                    if ma:
                        cur_price = json_data.get("current_price")
                        if cur_price:
                            st.metric(UI_LABELS["DETAIL_CURRENT_PRICE"],
                                      _fmt_price(cur_price, mkt))
                        st.markdown(f"**{ma.get('summary', '-')}**")
                        mc1, mc2 = st.columns(2)
                        raw_trend = ma.get("trend", "")
                        mc1.metric(UI_LABELS["DETAIL_TREND"],
                                   TREND_KO.get(raw_trend, raw_trend) or "-")
                        mc2.metric(UI_LABELS["DETAIL_CONFIDENCE"],
                                   confidence_bar(ma.get("confidence", 0)))

                        col_b2, col_r2 = st.columns(2)
                        with col_b2:
                            st.markdown(f"**{UI_LABELS['DETAIL_BULL_SIGNAL']}**")
                            for pt in ma.get("bull_points", []):
                                st.markdown(f"- {pt}")
                        with col_r2:
                            st.markdown(f"**{UI_LABELS['DETAIL_BEAR_SIGNAL']}**")
                            for pt in ma.get("bear_points", []):
                                st.markdown(f"- {pt}")

                        with st.expander(UI_LABELS["DETAIL_TECH_DETAIL"]):
                            for ev in ma.get("evidence", []):
                                st.markdown(f"- {ev}")
                    else:
                        st.info(UI_LABELS["DETAIL_MARKET_NONE"])

                # ── 탭 3: 재무 분석 ──────────────────────────────────────────
                with tab_fund:
                    if fa:
                        st.markdown(f"**{fa.get('summary', '-')}**")
                        fc1, fc2 = st.columns(2)
                        raw_rating = fa.get("fundamental_rating", "")
                        fc1.metric(UI_LABELS["DETAIL_FUND_GRADE"],
                                   FUND_RATING_KO.get(raw_rating, raw_rating) or "-")
                        fc2.metric(UI_LABELS["DETAIL_CONFIDENCE"],
                                   confidence_bar(fa.get("confidence", 0)))

                        km = fa.get("key_metrics", {})
                        if km:
                            st.markdown(f"**{UI_LABELS['DETAIL_KEY_METRICS']}**")
                            km_cols = st.columns(4)
                            metric_defs = [
                                ("P/E (주가수익비율)",  "pe_ratio"),
                                ("선행 P/E",            "forward_pe"),
                                ("영업이익률",           "operating_margin_pct"),
                                ("ROE (자기자본이익률)", "roe_pct"),
                            ]
                            for i, (lbl, key) in enumerate(metric_defs):
                                val = km.get(key)
                                display_val = (
                                    f"{val:.1f}%"
                                    if key.endswith("_pct") and val is not None
                                    else (f"{val:.1f}" if val is not None else "-")
                                )
                                km_cols[i].metric(lbl, display_val)

                        col_b3, col_r3 = st.columns(2)
                        with col_b3:
                            st.markdown(f"**{UI_LABELS['DETAIL_BULL_SIGNAL']}**")
                            for pt in fa.get("bull_points", []):
                                st.markdown(f"- {pt}")
                        with col_r3:
                            st.markdown(f"**{UI_LABELS['DETAIL_BEAR_SIGNAL']}**")
                            for pt in fa.get("bear_points", []):
                                st.markdown(f"- {pt}")

                        with st.expander(UI_LABELS["DETAIL_FUND_DETAIL"]):
                            for ev in fa.get("evidence", []):
                                st.markdown(f"- {ev}")
                    else:
                        st.info(UI_LABELS["DETAIL_FUND_NONE"])

                # ── 탭 4: 뉴스/이슈 ─────────────────────────────────────────
                with tab_news:
                    if na:
                        nc1, nc2, nc3 = st.columns(3)
                        nc1.metric(UI_LABELS["DETAIL_NEWS_SENTIMENT"],
                                   SENT_KO.get(na.get("sentiment", ""), "-"))
                        nc2.metric(UI_LABELS["DETAIL_NEWS_COUNT"],
                                   f"{na.get('news_count', 0)}건")
                        nc3.metric(UI_LABELS["DETAIL_NEWS_CONFIDENCE"],
                                   confidence_bar(na.get("confidence", 0)))

                        if na.get("summary"):
                            st.info(na["summary"])

                        cat_bd = na.get("category_breakdown", {})
                        if cat_bd:
                            top    = sorted(cat_bd.items(), key=lambda x: x[1], reverse=True)[:5]
                            badges = " ".join(
                                f"`{CAT_KO.get(c, c)} {n}건`" for c, n in top
                            )
                            st.markdown(
                                f"**{UI_LABELS['DETAIL_NEWS_CAT']}:** {badges}"
                            )

                        st.markdown("---")
                        evidence = na.get("evidence", [])
                        if evidence:
                            st.markdown(f"##### {UI_LABELS['DETAIL_NEWS_TOP5']}")
                            display_items = [e for e in evidence if isinstance(e, dict)][:5]
                            if display_items:
                                cards_html = "".join(
                                    _news_card_html(item, i)
                                    for i, item in enumerate(display_items)
                                )
                                st.markdown(cards_html, unsafe_allow_html=True)
                            else:
                                st.info(UI_LABELS["DETAIL_NEWS_NO_CARD"])

                            total_dict = len([e for e in evidence if isinstance(e, dict)])
                            if total_dict > 5:
                                st.caption(
                                    f"전체 {total_dict}건 {UI_LABELS['DETAIL_NEWS_NONE']}"
                                )
                        else:
                            st.info(UI_LABELS["DETAIL_NEWS_NO_DATA"])
                    else:
                        st.info(UI_LABELS["DETAIL_NEWS_NONE"])

                # ── 탭 5: 리스크 ─────────────────────────────────────────────
                with tab_risk:
                    if ra:
                        rc1, rc2 = st.columns(2)
                        raw_risk = ra.get("risk_level", "")
                        rc1.metric(UI_LABELS["DETAIL_RISK_LEVEL"],
                                   RISK_LEVEL_KO.get(raw_risk, raw_risk) or "-")
                        rc2.metric(
                            UI_LABELS["DETAIL_RISK_SCORE"],
                            f"{ra.get('risk_score', 0):.2f} / 1.00",
                            help="0.0=최소  0.2=낮음  0.4=보통  0.6=다소 높음  0.8=높음  1.0=위험",
                        )
                        st.markdown(f"**{ra.get('summary', '-')}**")

                        risk_fs = ra.get("risk_factors", [])
                        mitig   = ra.get("bull_points", [])
                        col_r4, col_m = st.columns(2)
                        with col_r4:
                            st.markdown(f"**{UI_LABELS['DETAIL_RISK_FACTORS']}**")
                            if risk_fs:
                                for f in risk_fs:
                                    st.markdown(f"- {f}")
                            else:
                                st.caption(UI_LABELS["DETAIL_RISK_NONE"])
                        with col_m:
                            st.markdown(f"**{UI_LABELS['DETAIL_MITIG']}**")
                            if mitig:
                                for m in mitig:
                                    st.markdown(f"- {m}")
                            else:
                                st.caption(UI_LABELS["DETAIL_MITIG_NONE"])
                    else:
                        st.info(UI_LABELS["DETAIL_RISK_NONE_DATA"])

                # ── 탭 6: 전체 보고서 ────────────────────────────────────────
                with tab_full:
                    md = _sanitize_llm_text(report.get("markdown_report", ""))
                    if md:
                        st.markdown(md)
                    else:
                        st.warning(UI_LABELS["DETAIL_FULL_NO_REPORT"])

                    with st.expander(UI_LABELS["DETAIL_FULL_RAW"], expanded=False):
                        if json_data:
                            st.json(json_data)
                        elif json_str:
                            st.code(json_str, language="json")
                        else:
                            st.caption(UI_LABELS["DETAIL_FULL_NO_RAW"])


# ===========================================================================
# 4. 종목 관리
# ===========================================================================
elif _page_key == PAGE_WATCHLIST:
    st.title(get_page_title(PAGE_WATCHLIST))
    st.caption(UI_LABELS["WATCHLIST_DESC"])

    # ── 등록된 종목 목록 ──────────────────────────────────────────────────
    st.subheader(UI_LABELS["WATCHLIST_SECTION_LIST"])
    all_wl = wl_repo.list_all()

    if all_wl:
        import pandas as pd
        rows = []
        for w in all_wl:
            rows.append({
                UI_LABELS["WATCHLIST_COL_CODE"]:    w["ticker"],
                UI_LABELS["WATCHLIST_COL_COMPANY"]: get_display_name_ko(
                    w["ticker"], w.get("display_name", "")
                ),
                UI_LABELS["WATCHLIST_COL_MARKET"]:  MARKET_LABEL.get(
                    w.get("market", ""), w.get("market", "-")
                ),
                UI_LABELS["WATCHLIST_COL_STYLE"]:   STYLE_LABEL.get(
                    w.get("style", ""), w.get("style", "-")
                ),
                UI_LABELS["WATCHLIST_COL_HORIZON"]: HORIZON_LABEL.get(
                    w.get("horizon", ""), w.get("horizon", "-")
                ),
                UI_LABELS["WATCHLIST_COL_STATUS"]:  (
                    UI_LABELS["WATCHLIST_ACTIVE"]
                    if w["is_active"]
                    else UI_LABELS["WATCHLIST_INACTIVE"]
                ),
                UI_LABELS["WATCHLIST_COL_DATE"]:    (w.get("created_at") or "")[:10] or "-",
                "_id":                              w["id"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df.drop(columns=["_id"]), use_container_width=True, hide_index=True)
    else:
        st.info(UI_LABELS["WATCHLIST_NO_DATA"])

    st.markdown("---")

    # ── 종목 추가 ─────────────────────────────────────────────────────────
    st.subheader(UI_LABELS["WATCHLIST_SECTION_ADD"])
    with st.form("add_ticker_form"):
        col1, col2 = st.columns(2)
        new_ticker = col1.text_input(
            UI_LABELS["WATCHLIST_FORM_TICKER"],
            placeholder=UI_LABELS["WATCHLIST_TICKER_PH"],
        )
        new_name = col2.text_input(
            UI_LABELS["WATCHLIST_FORM_NAME"],
            placeholder=UI_LABELS["WATCHLIST_NAME_HINT"],
            help=UI_LABELS["WATCHLIST_NAME_PH"],
        )

        col3, col4, col5, col6 = st.columns(4)
        new_market = col3.selectbox(
            UI_LABELS["WATCHLIST_FORM_MARKET"],
            MARKETS,
            format_func=lambda m: MARKET_LABEL.get(m, m),
            index=0,
        )
        new_style = col4.selectbox(
            UI_LABELS["WATCHLIST_FORM_STYLE"],
            INVESTMENT_STYLES,
            format_func=lambda s: STYLE_LABEL.get(s, s),
            index=1,
        )
        new_horizon = col5.selectbox(
            UI_LABELS["WATCHLIST_FORM_HORIZON"],
            HORIZONS,
            format_func=lambda h: HORIZON_LABEL.get(h, h),
            index=1,
        )
        new_lang = col6.selectbox(
            UI_LABELS["WATCHLIST_FORM_LANG"],
            LANGUAGES,
            format_func=lambda l: LANG_LABEL.get(l, l),
            index=LANGUAGES.index(DEFAULT_LANGUAGE),
        )
        submitted = st.form_submit_button(UI_LABELS["WATCHLIST_BTN_ADD"])

    if submitted:
        if not new_ticker.strip():
            st.error(UI_LABELS["WATCHLIST_ERR_NO_TICKER"])
        else:
            norm = normalize_ticker(new_ticker.strip(), new_market)
            name = new_name.strip() or get_display_name(norm) or get_display_name_ko(norm)
            added = wl_repo.add(
                ticker=norm, display_name=name,
                market=new_market, style=new_style,
                horizon=new_horizon, language=new_lang,
            )
            if added:
                st.success(f"✅ '{name}' ({norm}) 추가되었습니다.")
            else:
                st.info(f"'{norm}'은 이미 존재하며 활성화되었습니다.")
            st.rerun()

    st.markdown("---")

    # ── 수정 및 삭제 ─────────────────────────────────────────────────────
    st.subheader(UI_LABELS["WATCHLIST_SECTION_EDIT"])

    if all_wl:
        ticker_options = [
            f"{get_display_name_ko(w['ticker'], w.get('display_name', ''))} ({w['ticker']})"
            for w in all_wl
        ]
        selected_idx = st.selectbox(
            UI_LABELS["WATCHLIST_MANAGE_SELECT"],
            range(len(ticker_options)),
            format_func=lambda i: ticker_options[i],
            key="manage_wl_idx",
        )
        entry     = all_wl[selected_idx]
        is_active = bool(entry["is_active"])

        with st.expander(UI_LABELS["WATCHLIST_EDIT_SECTION"], expanded=True):
            with st.form("edit_ticker_form"):
                c1, c2 = st.columns(2)
                edit_name   = c1.text_input(
                    UI_LABELS["WATCHLIST_FORM_NAME"],
                    value=entry.get("display_name", ""),
                )
                edit_market = c2.selectbox(
                    UI_LABELS["WATCHLIST_FORM_MARKET"],
                    MARKETS,
                    format_func=lambda m: MARKET_LABEL.get(m, m),
                    index=MARKETS.index(entry.get("market", "US"))
                          if entry.get("market", "US") in MARKETS else 0,
                )
                c3, c4, c5 = st.columns(3)
                edit_style = c3.selectbox(
                    UI_LABELS["WATCHLIST_FORM_STYLE"],
                    INVESTMENT_STYLES,
                    format_func=lambda s: STYLE_LABEL.get(s, s),
                    index=INVESTMENT_STYLES.index(entry.get("style", "neutral"))
                          if entry.get("style", "neutral") in INVESTMENT_STYLES else 1,
                )
                edit_horizon = c4.selectbox(
                    UI_LABELS["WATCHLIST_FORM_HORIZON"],
                    HORIZONS,
                    format_func=lambda h: HORIZON_LABEL.get(h, h),
                    index=HORIZONS.index(entry.get("horizon", "mid"))
                          if entry.get("horizon", "mid") in HORIZONS else 1,
                )
                edit_lang = c5.selectbox(
                    UI_LABELS["WATCHLIST_FORM_LANG"],
                    LANGUAGES,
                    format_func=lambda l: LANG_LABEL.get(l, l),
                    index=LANGUAGES.index(entry.get("language", DEFAULT_LANGUAGE))
                          if entry.get("language", DEFAULT_LANGUAGE) in LANGUAGES else 0,
                )
                save_btn = st.form_submit_button(UI_LABELS["WATCHLIST_BTN_SAVE"])

            if save_btn:
                wl_repo.update(
                    ticker=entry["ticker"],
                    display_name=edit_name,
                    market=edit_market,
                    style=edit_style,
                    horizon=edit_horizon,
                    language=edit_lang,
                )
                st.success(f"'{entry['ticker']}' 정보가 저장되었습니다.")
                st.rerun()

            st.markdown("---")
            ca, cb, cc = st.columns(3)

            if ca.button(UI_LABELS["WATCHLIST_BTN_ACTIVATE"],
                         disabled=is_active, key="activate_btn"):
                wl_repo.activate(entry["ticker"])
                st.success(f"'{entry['ticker']}' 활성화되었습니다.")
                st.rerun()

            if cb.button(UI_LABELS["WATCHLIST_BTN_DEACTIVATE"],
                         disabled=not is_active, key="deactivate_btn"):
                wl_repo.deactivate(entry["ticker"])
                st.warning(f"'{entry['ticker']}' 비활성화되었습니다.")
                st.rerun()

            if "confirm_delete" not in st.session_state:
                st.session_state["confirm_delete"] = False

            if not st.session_state["confirm_delete"]:
                if cc.button(UI_LABELS["WATCHLIST_BTN_DELETE"],
                             key="delete_btn", type="secondary"):
                    st.session_state["confirm_delete"] = True
                    st.rerun()
            else:
                st.warning(
                    f"**'{entry['ticker']}'**"
                    f"{UI_LABELS['WATCHLIST_DELETE_WARN']}"
                )
                col_yes, col_no = st.columns(2)
                if col_yes.button(UI_LABELS["WATCHLIST_BTN_CONFIRM_DEL"],
                                  key="confirm_yes", type="primary"):
                    wl_repo.remove(entry["ticker"])
                    st.session_state["confirm_delete"] = False
                    st.success(f"'{entry['ticker']}' 삭제되었습니다.")
                    st.rerun()
                if col_no.button(UI_LABELS["WATCHLIST_BTN_CANCEL"], key="confirm_no"):
                    st.session_state["confirm_delete"] = False
                    st.rerun()
    else:
        st.info(UI_LABELS["WATCHLIST_NO_MANAGE"])


# ===========================================================================
# 5. 이메일 설정
# ===========================================================================
elif _page_key == PAGE_EMAIL:
    st.title(get_page_title(PAGE_EMAIL))
    st.caption(UI_LABELS["EMAIL_DESC"])

    # ── SMTP 상태 ─────────────────────────────────────────────────────────
    smtp_ok = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)
    if smtp_ok:
        st.success(
            f"✅ {UI_LABELS['EMAIL_SMTP_OK']} ({SMTP_HOST} · {SMTP_USER})"
        )
    else:
        st.error(
            f"❌ {UI_LABELS['EMAIL_SMTP_FAIL']}\n\n"
            "```\nSMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\n"
            "SMTP_USER=your@gmail.com\nSMTP_PASSWORD=your_app_password\n"
            "SENDER_EMAIL=your@gmail.com\n```"
        )

    st.markdown("---")

    # ── 이메일 수신 설정 ─────────────────────────────────────────────────
    st.subheader(UI_LABELS["EMAIL_SECTION_RECIPIENT"])
    recipients  = settings_repo.get_recipients()
    primary_val = recipients["primary"]
    cc_val      = "\n".join(recipients["cc_list"])

    with st.form("recipient_form"):
        new_primary = st.text_input(
            UI_LABELS["EMAIL_LABEL_PRIMARY"],
            value=primary_val,
            placeholder="example@gmail.com",
        )
        new_cc = st.text_area(
            UI_LABELS["EMAIL_LABEL_CC"],
            value=cc_val,
            height=80,
            placeholder="cc1@example.com\ncc2@example.com",
            help=UI_LABELS["EMAIL_CC_HINT"],
        )
        col_save, col_test = st.columns(2)
        save_btn = col_save.form_submit_button(UI_LABELS["EMAIL_BTN_SAVE"])
        test_btn = col_test.form_submit_button(UI_LABELS["EMAIL_BTN_TEST"])

    if save_btn:
        new_cc_list = [e.strip() for e in new_cc.strip().splitlines() if e.strip()]
        settings_repo.set_recipients(new_primary.strip(), new_cc_list)
        st.success(UI_LABELS["EMAIL_SAVE_OK"])
        st.rerun()

    if test_btn:
        to_addr = new_primary.strip() if new_primary.strip() else recipients["primary"]
        if not to_addr:
            st.error(UI_LABELS["EMAIL_ERR_NO_ADDR"])
        elif not smtp_ok:
            st.error(UI_LABELS["EMAIL_ERR_NO_SMTP"])
        else:
            from email_service.email_sender import EmailSender
            sender    = EmailSender()
            test_html = (
                "<h2>📈 투자 분석 시스템 — 테스트 메일</h2>"
                "<p>이 메일이 수신되었다면 이메일 발송 설정이 정상입니다.</p>"
                "<p style='color:#718096;font-size:12px;'>"
                "투자 분석 대시보드에서 발송된 테스트 메일입니다.</p>"
            )
            ok, err = sender.send(
                subject="[투자 분석] 이메일 연결 테스트",
                html_body=test_html,
                recipient=to_addr,
            )
            if ok:
                st.success(
                    f"✅ {UI_LABELS['EMAIL_TEST_OK']} ({to_addr})"
                )
            else:
                st.error(f"❌ {UI_LABELS['EMAIL_TEST_FAIL']}: {err}")

    st.markdown("---")

    # ── 자동 실행 및 대시보드 URL 설정 ───────────────────────────────────
    st.subheader(UI_LABELS["EMAIL_SECTION_SCHEDULE"])

    sched_val = settings_repo.get("scheduler_time", "07:00")
    url_val   = settings_repo.get("base_url", "http://localhost:8501")

    if is_localhost_url(url_val):
        st.warning(
            f"⚠️ **{UI_LABELS['EMAIL_URL_WARN']}**\n\n"
            f"{UI_LABELS['EMAIL_URL_WARN_DETAIL']}"
        )
    else:
        st.success(f"✅ {UI_LABELS['EMAIL_URL_OK']}: **{url_val}**")

    with st.form("scheduler_form"):
        new_time = st.text_input(
            UI_LABELS["EMAIL_LABEL_TIME"],
            value=sched_val,
            help=UI_LABELS["EMAIL_TIME_HINT"],
        )
        new_url = st.text_input(
            UI_LABELS["EMAIL_LABEL_URL"],
            value=url_val,
            help=UI_LABELS["EMAIL_URL_HINT"],
            placeholder="http://3.34.46.169:8501",
        )
        save_sched = st.form_submit_button(UI_LABELS["EMAIL_BTN_SAVE"])

    if save_sched:
        parts = new_time.strip().split(":")
        valid = (
            len(parts) == 2
            and all(p.isdigit() for p in parts)
            and 0 <= int(parts[0]) <= 23
            and 0 <= int(parts[1]) <= 59
        )
        if not valid:
            st.error(UI_LABELS["EMAIL_ERR_TIME_FMT"])
        else:
            settings_repo.set("scheduler_time", new_time.strip())
            settings_repo.set("base_url", new_url.strip())
            st.success(UI_LABELS["EMAIL_SCHED_SAVE_OK"])
            st.rerun()

    st.markdown("---")

    # ── 이메일 발송 이력 ─────────────────────────────────────────────────
    st.subheader(UI_LABELS["EMAIL_SECTION_LOG"])
    logs = email_repo.get_all(limit=20)
    if logs:
        import pandas as pd
        log_rows = []
        for lg in logs:
            if lg["status"] == "success":
                s = UI_LABELS["EMAIL_LOG_SUCCESS"]
            elif lg["status"] == "skipped":
                s = UI_LABELS["EMAIL_LOG_SKIP"]
            else:
                s = UI_LABELS["EMAIL_LOG_FAIL"]
            log_rows.append({
                UI_LABELS["EMAIL_LOG_TIME"]:      fmt_dt(lg.get("sent_at", "")),
                UI_LABELS["EMAIL_LOG_RECIPIENT"]: lg.get("recipient", "-"),
                UI_LABELS["EMAIL_LOG_STATUS"]:    s,
                UI_LABELS["EMAIL_LOG_ERROR"]:     lg.get("error_message", "") or "-",
            })
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
    else:
        st.info(UI_LABELS["EMAIL_LOG_EMPTY"])
