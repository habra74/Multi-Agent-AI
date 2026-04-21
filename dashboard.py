"""
dashboard.py
------------
Streamlit 기반 투자 분석 대시보드

실행: streamlit run dashboard.py

메뉴:
  1. 홈 대시보드      - 운영 요약 패널, 오늘 리포트, 즉시 실행
  2. 분석 이력        - 종목별 과거 리포트 목록
  3. 리포트 상세 보기  - 탭 별 상세 분석 + 뉴스 + JSON
  4. Watchlist 관리   - 종목 추가 / 수정 / 삭제 / 활성화
  5. 이메일 설정      - 수신 이메일 관리 + SMTP 상태 + 즉시 발송
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from datetime import datetime, date

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

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="투자 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Mobile-friendly custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ── 모바일 반응형 개선 ─────────────────────── */
@media (max-width: 768px) {
    /* 메트릭 폰트 축소 */
    div[data-testid="metric-container"] > div:first-child  { font-size: 11px !important; }
    div[data-testid="metric-container"] > div:nth-child(2) { font-size: 18px !important; }
    /* 컬럼 패딩 축소 */
    div[data-testid="column"] { padding: 2px 4px !important; }
    /* 사이드바 기본 닫기 */
    section[data-testid="stSidebar"] { transform: translateX(-100%); }
}
/* ── 뉴스 카드 스타일 ───────────────────────── */
.news-card {
    border: 1px solid #e3e8ee;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 10px;
    background: #fafbfc;
}
.news-card .headline {
    font-weight: 600;
    font-size: 14px;
    color: #1a1a2e;
    margin-bottom: 4px;
}
.news-card .interp {
    font-size: 12px;
    color: #4a5568;
    font-style: italic;
}
/* ── 판정 배지 ─────────────────────────────── */
.verdict-pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 16px;
    font-weight: 700;
    font-size: 13px;
    color: #fff;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB initialisation (idempotent, cached)
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
# Verdict styling helpers
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
STYLE_LABEL   = {"conservative": "보수적", "neutral": "중립", "aggressive": "공격적"}
HORIZON_LABEL = {"short": "단기", "mid": "중기", "long": "장기"}
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
SENT_KO    = {"positive": "긍정적", "negative": "부정적", "neutral": "중립적", "mixed": "혼재"}
SENT_ICON  = {"positive": "📈", "negative": "📉", "neutral": "📊", "mixed": "↕️"}
CAT_KO     = {
    "earnings": "실적", "product": "제품",
    "analyst":  "애널리스트", "legal": "법률/규제",
    "macro":    "거시경제",   "corporate": "기업이슈",
    "sentiment":"시장심리",  "general": "일반",
}


def _fmt_price(price, market: str = "US") -> str:
    """시장별 가격 포맷: KR → 원화 표기, US → 달러 표기."""
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
    icon  = VERDICT_ICON.get(decision, f"⬜ {decision}")
    color = VERDICT_COLOR.get(decision, "#555")
    return f'<span style="color:{color};font-weight:bold;">{icon}</span>'


def fmt_dt(dt_str: str) -> str:
    try:
        return datetime.fromisoformat(dt_str).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str or "-"


def confidence_bar(conf: float) -> str:
    pct = round(conf * 100)
    label = (
        "매우 높음" if pct >= 80 else
        "높음"      if pct >= 65 else
        "보통"      if pct >= 45 else
        "낮음"      if pct >= 25 else
        "매우 낮음"
    )
    return f"{pct}% ({label})"


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("📈 투자 분석 대시보드")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "메뉴",
    ["🏠 홈 대시보드", "📊 분석 이력", "📄 리포트 상세", "⭐ Watchlist 관리", "📧 이메일 설정"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption(f"DB: `{DB_PATH}`")
_base_url = settings_repo.get("base_url", "http://localhost:8501")
st.sidebar.caption(f"URL: `{_base_url}`")
st.sidebar.markdown("---")
st.sidebar.caption(
    "**실행 방법**\n"
    "```\nstreamlit run dashboard.py\n```\n"
    "스케줄러:\n"
    "```\npython scheduler/scheduler.py\n```"
)


# ===========================================================================
# 1. 홈 대시보드
# ===========================================================================
if page == "🏠 홈 대시보드":
    st.title("🏠 투자 분석 대시보드")
    st.caption(f"기준일: {date.today().strftime('%Y년 %m월 %d일')}")

    # ── 운영 요약 패널 ─────────────────────────────────────────────────────
    today_reports = rp_repo.get_today()
    all_summary   = rp_repo.get_all_summary(limit=1)
    last_run_str  = fmt_dt(all_summary[0]["created_at"]) if all_summary else "없음"

    today_email_logs = email_repo.get_today()
    if today_email_logs:
        latest_email = today_email_logs[0]
        email_status = "✅ 발송 완료" if latest_email["status"] == "success" else "❌ 발송 실패"
    else:
        email_status = "— 미발송"

    sched_time = settings_repo.get("scheduler_time", "07:00")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("마지막 분석",    last_run_str)
    c2.metric("오늘 분석 종목", f"{len(today_reports)}개")
    c3.metric("이메일 상태",    email_status)
    c4.metric("다음 예약 시각", f"매일 {sched_time}")

    st.markdown("---")

    # ── 즉시 실행 버튼 ─────────────────────────────────────────────────────
    active_wl = wl_repo.list_active()
    col_run, col_hint = st.columns([1, 4])

    with col_run:
        run_now = st.button(
            "🚀 지금 즉시 실행",
            type="primary",
            disabled=not active_wl,
            help="Watchlist의 활성 종목 전체를 지금 즉시 분석합니다.",
        )

    with col_hint:
        if active_wl:
            tickers_str = ", ".join(w["ticker"] for w in active_wl)
            st.caption(f"분석 대상: {tickers_str}")
        else:
            st.caption("활성 Watchlist 항목이 없습니다.")

    if run_now and active_wl:
        from main import analyze_and_store
        progress_bar = st.progress(0)
        status_area  = st.empty()
        results_log  = []

        for i, entry in enumerate(active_wl):
            ticker = entry["ticker"]
            status_area.info(f"⏳ 분석 중: **{ticker}** ({i+1}/{len(active_wl)})")
            try:
                out = analyze_and_store(
                    ticker   = ticker,
                    market   = entry.get("market",  "US"),
                    style    = entry.get("style",   "neutral"),
                    horizon  = entry.get("horizon", "mid"),
                    language = entry.get("language","ko"),
                )
                results_log.append((ticker, True, out.get("report_id")))
            except Exception as exc:
                results_log.append((ticker, False, str(exc)))
            progress_bar.progress((i + 1) / len(active_wl))

        status_area.empty()
        for ticker, ok, info in results_log:
            if ok:
                st.success(f"✅ {ticker}: 분석 완료 (report_id={info})")
            else:
                st.error(f"❌ {ticker}: 실패 — {info}")
        st.rerun()

    st.markdown("---")

    # ── 오늘 리포트 목록 ────────────────────────────────────────────────────
    st.subheader("오늘 생성된 리포트")

    if not today_reports:
        st.info(
            "오늘 생성된 리포트가 없습니다.\n\n"
            "위 **🚀 지금 즉시 실행** 버튼을 누르거나, CLI로 실행하세요:\n"
            "```\npython main.py AAPL --save-db\n```"
        )
    else:
        import pandas as pd
        rows = []
        for r in today_reports:
            rows.append({
                "ID":      r["id"],
                "종목코드": r["ticker"],
                "종목명":   r.get("display_name") or r["ticker"],
                "시장":     r.get("market", "-"),
                "투자 의견": VERDICT_ICON.get(r["final_decision"], r.get("final_decision") or "-"),
                "신뢰도":   confidence_bar(r.get("confidence", 0)),
                "리스크":   f"{r.get('risk_score', 0):.2f}",
                "생성 시각": fmt_dt(r["created_at"]),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

        st.markdown("---")
        options = {
            f"[{r['id']}] {r.get('display_name') or r['ticker']} — {fmt_dt(r['created_at'])}": r["id"]
            for r in today_reports
        }
        chosen = st.selectbox("리포트를 선택하면 상세 내용을 볼 수 있습니다.", list(options.keys()))
        if chosen and st.button("📄 상세 보기"):
            st.session_state["selected_report_id"] = options[chosen]
            st.session_state["page_override"] = "📄 리포트 상세"
            st.rerun()


# ===========================================================================
# 2. 분석 이력
# ===========================================================================
elif page == "📊 분석 이력":
    st.title("📊 종목별 분석 이력")

    tickers_with_reports = rp_repo.list_tickers()
    watchlist_tickers    = [w["ticker"] for w in wl_repo.list_active()]
    all_tickers          = list(dict.fromkeys(watchlist_tickers + tickers_with_reports))

    if not all_tickers:
        st.info("저장된 리포트가 없습니다. CLI에서 `--save-db` 옵션으로 분석을 실행하세요.")
    else:
        selected_ticker = st.selectbox("종목 선택", all_tickers)

        if selected_ticker:
            history = rp_repo.get_by_ticker(selected_ticker, limit=30)

            if not history:
                st.warning(f"{selected_ticker}에 대한 리포트가 없습니다.")
            else:
                display = history[0].get("display_name") or selected_ticker
                st.markdown(f"**{display}** ({selected_ticker}) — {len(history)}개 리포트")

                import pandas as pd
                rows = []
                for r in history:
                    rows.append({
                        "ID":      r["id"],
                        "투자 의견": VERDICT_ICON.get(r["final_decision"], r.get("final_decision") or "-"),
                        "신뢰도":   confidence_bar(r.get("confidence", 0)),
                        "리스크 점수": f"{r.get('risk_score', 0):.2f}",
                        "성향":    STYLE_LABEL.get(r.get("style", ""), r.get("style", "-")),
                        "기간":    HORIZON_LABEL.get(r.get("horizon", ""), r.get("horizon", "-")),
                        "생성 시각": fmt_dt(r["created_at"]),
                    })

                df = pd.DataFrame(rows)
                st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

                st.markdown("---")
                options = {
                    f"[{r['id']}] {fmt_dt(r['created_at'])} — {VERDICT_ICON.get(r.get('final_decision',''), r.get('final_decision',''))}": r["id"]
                    for r in history
                }
                chosen = st.selectbox("리포트 선택", list(options.keys()))
                if chosen and st.button("📄 상세 보기"):
                    st.session_state["selected_report_id"] = options[chosen]
                    st.session_state["page_override"] = "📄 리포트 상세"
                    st.rerun()


# ===========================================================================
# 3. 리포트 상세 보기
# ===========================================================================
elif page == "📄 리포트 상세" or st.session_state.get("page_override") == "📄 리포트 상세":
    if st.session_state.get("page_override") == "📄 리포트 상세":
        st.session_state.pop("page_override", None)

    st.title("📄 리포트 상세 보기")

    all_reports = rp_repo.get_all_summary(limit=100)

    if not all_reports:
        st.info("저장된 리포트가 없습니다.")
    else:
        options = {
            f"[{r['id']}] {r.get('display_name') or r['ticker']} | {fmt_dt(r['created_at'])} | "
            f"{VERDICT_ICON.get(r['final_decision'], r.get('final_decision') or '')}": r["id"]
            for r in all_reports
        }

        # Pre-select from session state if navigated here from other pages
        default_key = None
        preselected_id = st.session_state.get("selected_report_id")
        if preselected_id:
            for k, v in options.items():
                if v == preselected_id:
                    default_key = k
                    break
            st.session_state.pop("selected_report_id", None)

        keys_list   = list(options.keys())
        default_idx = keys_list.index(default_key) if default_key in keys_list else 0

        chosen = st.selectbox("리포트 선택", keys_list, index=default_idx)

        if chosen:
            report_id = options[chosen]
            report    = rp_repo.get_by_id(report_id)

            if not report:
                st.error("리포트를 찾을 수 없습니다.")
            else:
                # ── Header metrics ───────────────────────────────────────────
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("종목코드",  report["ticker"])
                col2.metric("종목명",    report.get("display_name") or report["ticker"])
                col3.metric(
                    "투자 의견",
                    VERDICT_ICON.get(report["final_decision"], report.get("final_decision") or "-"),
                )
                col4.metric("신뢰도",    confidence_bar(report.get("confidence", 0)))

                st.caption(
                    f"생성: {fmt_dt(report['created_at'])} | "
                    f"시장: {report['market']} | "
                    f"성향: {STYLE_LABEL.get(report.get('style',''), report.get('style','-'))} | "
                    f"기간: {HORIZON_LABEL.get(report.get('horizon',''), report.get('horizon','-'))}"
                )
                st.markdown("---")

                # ── Parse JSON ───────────────────────────────────────────────
                json_str  = report.get("json_report", "{}")
                json_data: dict = {}
                try:
                    json_data = json.loads(json_str) if isinstance(json_str, str) else (json_str or {})
                except Exception:
                    pass

                da = json_data.get("decision", {})
                ma = json_data.get("market_analysis", {})
                fa = json_data.get("fundamental_analysis", {})
                na = json_data.get("news_analysis", {})
                ra = json_data.get("risk_analysis", {})

                # ── Tabs ─────────────────────────────────────────────────────
                tab_summary, tab_market, tab_fund, tab_news, tab_risk, tab_raw = st.tabs([
                    "핵심 요약", "시장 분석", "펀더멘털", "뉴스", "리스크", "원본 리포트",
                ])

                # ── Tab 1: 핵심 요약 ─────────────────────────────────────────
                with tab_summary:
                    reasoning = da.get("reasoning", "")
                    if reasoning:
                        st.markdown("**분석 근거**")
                        st.info(reasoning)

                    bull_pts = da.get("bull_points", [])
                    bear_pts = da.get("bear_points", [])
                    col_b, col_r = st.columns(2)
                    with col_b:
                        st.markdown("**긍정 요인**")
                        for pt in bull_pts:
                            st.markdown(f"- {pt}")
                        if not bull_pts:
                            st.caption("없음")
                    with col_r:
                        st.markdown("**부정 요인**")
                        for pt in bear_pts:
                            st.markdown(f"- {pt}")
                        if not bear_pts:
                            st.caption("없음")

                    actions = da.get("action_items", [])
                    if actions:
                        st.markdown("**향후 체크 포인트**")
                        for a in actions:
                            st.markdown(f"- {a}")

                # ── Tab 2: 시장 분석 ─────────────────────────────────────────
                with tab_market:
                    if ma:
                        # 현재 가격 (json_data 최상단에 저장됨)
                        cur_price = json_data.get("current_price")
                        mkt       = json_data.get("market") or report.get("market", "US")
                        if cur_price:
                            st.metric("현재 가격", _fmt_price(cur_price, mkt))
                        st.markdown(f"**요약:** {ma.get('summary', '-')}")
                        c1, c2 = st.columns(2)
                        raw_trend = ma.get("trend", "")
                        c1.metric("추세",  TREND_KO.get(raw_trend, raw_trend) or "-")
                        c2.metric("신뢰도", confidence_bar(ma.get("confidence", 0)))

                        col_b2, col_r2 = st.columns(2)
                        with col_b2:
                            st.markdown("**긍정 신호**")
                            for pt in ma.get("bull_points", []):
                                st.markdown(f"- {pt}")
                        with col_r2:
                            st.markdown("**부정 신호**")
                            for pt in ma.get("bear_points", []):
                                st.markdown(f"- {pt}")

                        with st.expander("기술적 데이터"):
                            for ev in ma.get("evidence", []):
                                st.markdown(f"- {ev}")
                    else:
                        st.info("시장 분석 데이터 없음")

                # ── Tab 3: 펀더멘털 ──────────────────────────────────────────
                with tab_fund:
                    if fa:
                        st.markdown(f"**요약:** {fa.get('summary', '-')}")
                        c1, c2 = st.columns(2)
                        raw_rating = fa.get("fundamental_rating", "")
                        c1.metric("등급",  FUND_RATING_KO.get(raw_rating, raw_rating) or "-")
                        c2.metric("신뢰도", confidence_bar(fa.get("confidence", 0)))

                        km = fa.get("key_metrics", {})
                        if km:
                            st.markdown("**주요 지표**")
                            km_cols = st.columns(4)
                            labels = [
                                ("P/E",       "pe_ratio"),
                                ("선행 P/E",  "forward_pe"),
                                ("영업이익률", "operating_margin_pct"),
                                ("ROE",       "roe_pct"),
                            ]
                            for i, (lbl, key) in enumerate(labels):
                                val = km.get(key)
                                km_cols[i].metric(lbl, f"{val:.1f}" if val is not None else "-")

                        col_b3, col_r3 = st.columns(2)
                        with col_b3:
                            st.markdown("**긍정 신호**")
                            for pt in fa.get("bull_points", []):
                                st.markdown(f"- {pt}")
                        with col_r3:
                            st.markdown("**부정 신호**")
                            for pt in fa.get("bear_points", []):
                                st.markdown(f"- {pt}")
                    else:
                        st.info("펀더멘털 분석 데이터 없음")

                # ── Tab 4: 뉴스 ─────────────────────────────────────────────
                with tab_news:
                    if na:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("뉴스 심리",  SENT_KO.get(na.get("sentiment", ""), "-"))
                        c2.metric("기사 수",    na.get("news_count", 0))
                        c3.metric("신뢰도",     confidence_bar(na.get("confidence", 0)))

                        if na.get("summary"):
                            st.info(na["summary"])
                        st.markdown("---")

                        evidence = na.get("evidence", [])
                        if evidence:
                            st.markdown("**핵심 뉴스 (최대 5건)**")
                            for item in evidence[:5]:
                                if not isinstance(item, dict):
                                    continue
                                headline = item.get("headline", "")
                                interp   = item.get("interpretation", "")
                                link     = item.get("link", "")
                                sent     = item.get("sentiment", "neutral")
                                cat_raw  = item.get("category", "")
                                cat_ko   = CAT_KO.get(cat_raw, cat_raw)
                                icon     = SENT_ICON.get(sent, "")
                                sent_label = SENT_KO.get(sent, sent)

                                with st.container():
                                    badge = f"`{sent_label}`" if sent_label else ""
                                    cat_badge = f"`{cat_ko}`" if cat_ko else ""
                                    st.markdown(
                                        f"{icon} **{headline}** {badge} {cat_badge}"
                                    )
                                    if interp:
                                        st.caption(f"💡 투자 해석: {interp}")
                                    if link:
                                        st.markdown(f"[📰 기사 보기]({link})")
                                    st.divider()
                        else:
                            st.info("뉴스 데이터 없음")
                    else:
                        st.info("뉴스 분석 데이터 없음")

                # ── Tab 5: 리스크 ────────────────────────────────────────────
                with tab_risk:
                    if ra:
                        c1, c2 = st.columns(2)
                        raw_risk = ra.get("risk_level", "")
                        c1.metric("리스크 수준", RISK_LEVEL_KO.get(raw_risk, raw_risk) or "-")
                        c2.metric("리스크 점수", f"{ra.get('risk_score', 0):.2f} / 1.00")

                        st.markdown(f"**요약:** {ra.get('summary', '-')}")

                        risk_fs = ra.get("risk_factors", [])
                        mitig   = ra.get("bull_points", [])
                        col_r4, col_m = st.columns(2)
                        with col_r4:
                            st.markdown("**리스크 요인**")
                            for f in risk_fs:
                                st.markdown(f"- {f}")
                        with col_m:
                            st.markdown("**완화 요인**")
                            for m in mitig:
                                st.markdown(f"- {m}")
                    else:
                        st.info("리스크 분석 데이터 없음")

                # ── Tab 6: 원본 리포트 ───────────────────────────────────────
                with tab_raw:
                    md = report.get("markdown_report", "")
                    if md:
                        st.text(md)
                    else:
                        st.warning("저장된 마크다운 리포트가 없습니다.")

                    with st.expander("JSON 데이터 전체 보기"):
                        if json_data:
                            st.json(json_data)
                        else:
                            st.code(json_str)


# ===========================================================================
# 4. Watchlist 관리
# ===========================================================================
elif page == "⭐ Watchlist 관리":
    st.title("⭐ Watchlist 관리")

    # ── 현재 Watchlist 표시 ────────────────────────────────────────────────
    st.subheader("현재 Watchlist")
    all_wl = wl_repo.list_all()

    if all_wl:
        import pandas as pd
        rows = []
        for w in all_wl:
            rows.append({
                "ID":      w["id"],
                "종목코드": w["ticker"],
                "종목명":   w.get("display_name") or w["ticker"],
                "시장":     w.get("market", "-"),
                "성향":     STYLE_LABEL.get(w.get("style", ""), w.get("style", "-")),
                "기간":     HORIZON_LABEL.get(w.get("horizon", ""), w.get("horizon", "-")),
                "상태":     "✅ 활성" if w["is_active"] else "⬜ 비활성",
                "등록일":   (w.get("created_at") or "")[:10] or "-",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
    else:
        st.info("Watchlist가 비어있습니다.")

    st.markdown("---")

    # ── 종목 추가 ─────────────────────────────────────────────────────────
    st.subheader("종목 추가")
    with st.form("add_ticker_form"):
        col1, col2 = st.columns(2)
        new_ticker = col1.text_input(
            "종목코드 또는 종목명",
            placeholder="예: AAPL, 005930, 삼성전자",
        )
        new_name = col2.text_input(
            "표시 이름 (선택)",
            placeholder="예: Apple Inc., 삼성전자",
        )

        col3, col4, col5, col6 = st.columns(4)
        new_market  = col3.selectbox("시장",    MARKETS,           index=0)
        new_style   = col4.selectbox("투자 성향", INVESTMENT_STYLES, index=1)
        new_horizon = col5.selectbox("투자 기간", HORIZONS,          index=1)
        new_lang    = col6.selectbox("언어",    LANGUAGES,          index=LANGUAGES.index(DEFAULT_LANGUAGE))

        submitted = st.form_submit_button("➕ 추가")

    if submitted:
        if not new_ticker.strip():
            st.error("종목코드를 입력하세요.")
        else:
            norm = normalize_ticker(new_ticker.strip(), new_market)
            name = new_name.strip() or get_display_name(norm)
            added = wl_repo.add(
                ticker=norm, display_name=name,
                market=new_market, style=new_style,
                horizon=new_horizon, language=new_lang,
            )
            if added:
                st.success(f"✅ '{norm}' ({name}) 추가되었습니다.")
            else:
                st.info(f"'{norm}'은 이미 존재하며 활성화되었습니다.")
            st.rerun()

    st.markdown("---")

    # ── 종목 수정 / 활성화 / 삭제 ─────────────────────────────────────────
    st.subheader("종목 수정 · 관리")

    if all_wl:
        ticker_options = [
            f"{w['ticker']} — {w.get('display_name') or w['ticker']}"
            for w in all_wl
        ]
        selected_idx = st.selectbox(
            "관리할 종목 선택",
            range(len(ticker_options)),
            format_func=lambda i: ticker_options[i],
            key="manage_wl_idx",
        )
        entry = all_wl[selected_idx]
        is_active = bool(entry["is_active"])

        with st.expander("수정 / 삭제", expanded=True):
            with st.form("edit_ticker_form"):
                c1, c2 = st.columns(2)
                edit_name    = c1.text_input("표시 이름", value=entry.get("display_name", ""))
                edit_market  = c2.selectbox(
                    "시장", MARKETS,
                    index=MARKETS.index(entry.get("market", "US")) if entry.get("market", "US") in MARKETS else 0,
                )
                c3, c4, c5 = st.columns(3)
                edit_style   = c3.selectbox(
                    "투자 성향", INVESTMENT_STYLES,
                    index=INVESTMENT_STYLES.index(entry.get("style", "neutral")) if entry.get("style", "neutral") in INVESTMENT_STYLES else 1,
                )
                edit_horizon = c4.selectbox(
                    "투자 기간", HORIZONS,
                    index=HORIZONS.index(entry.get("horizon", "mid")) if entry.get("horizon", "mid") in HORIZONS else 1,
                )
                edit_lang    = c5.selectbox(
                    "언어", LANGUAGES,
                    index=LANGUAGES.index(entry.get("language", DEFAULT_LANGUAGE)) if entry.get("language", DEFAULT_LANGUAGE) in LANGUAGES else 0,
                )
                save_btn = st.form_submit_button("💾 저장")

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

            if ca.button(
                "✅ 활성화",
                disabled=is_active,
                key="activate_btn",
            ):
                wl_repo.activate(entry["ticker"])
                st.success(f"'{entry['ticker']}' 활성화되었습니다.")
                st.rerun()

            if cb.button(
                "⬜ 비활성화",
                disabled=not is_active,
                key="deactivate_btn",
            ):
                wl_repo.deactivate(entry["ticker"])
                st.warning(f"'{entry['ticker']}' 비활성화되었습니다.")
                st.rerun()

            # Delete with confirmation via session state
            if "confirm_delete" not in st.session_state:
                st.session_state["confirm_delete"] = False

            if not st.session_state["confirm_delete"]:
                if cc.button("🗑 삭제", key="delete_btn", type="secondary"):
                    st.session_state["confirm_delete"] = True
                    st.rerun()
            else:
                st.warning(f"**'{entry['ticker']}'을 완전히 삭제합니다.** 이 작업은 되돌릴 수 없습니다.")
                col_yes, col_no = st.columns(2)
                if col_yes.button("확인 삭제", key="confirm_yes", type="primary"):
                    wl_repo.remove(entry["ticker"])
                    st.session_state["confirm_delete"] = False
                    st.success(f"'{entry['ticker']}' 삭제되었습니다.")
                    st.rerun()
                if col_no.button("취소", key="confirm_no"):
                    st.session_state["confirm_delete"] = False
                    st.rerun()
    else:
        st.info("관리할 Watchlist 항목이 없습니다.")


# ===========================================================================
# 5. 이메일 설정
# ===========================================================================
elif page == "📧 이메일 설정":
    st.title("📧 이메일 설정")

    # ── SMTP 상태 표시 ─────────────────────────────────────────────────────
    st.subheader("SMTP 서버 상태")
    smtp_ok = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

    if smtp_ok:
        st.success(f"✅ SMTP 설정 완료 (서버: {SMTP_HOST}:{SMTP_USER})")
    else:
        st.error(
            "❌ SMTP 설정이 없습니다.\n\n"
            "프로젝트 루트의 `.env` 파일에 아래 항목을 설정하세요:\n"
            "```\nSMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\n"
            "SMTP_USER=your@email.com\nSMTP_PASSWORD=your_app_password\n"
            "SENDER_EMAIL=your@email.com\n```"
        )

    st.markdown("---")

    # ── 수신 이메일 설정 ───────────────────────────────────────────────────
    st.subheader("수신 이메일 설정")

    recipients = settings_repo.get_recipients()
    primary_val = recipients["primary"]
    cc_val      = "\n".join(recipients["cc_list"])

    with st.form("recipient_form"):
        new_primary = st.text_input(
            "기본 수신 이메일",
            value=primary_val,
            placeholder="example@gmail.com",
        )
        new_cc = st.text_area(
            "추가 수신 이메일 (한 줄에 하나씩)",
            value=cc_val,
            height=100,
            placeholder="cc1@example.com\ncc2@example.com",
        )

        col_save, col_test = st.columns(2)
        save_btn = col_save.form_submit_button("💾 저장")
        test_btn = col_test.form_submit_button("📧 테스트 메일 보내기")

    if save_btn:
        new_cc_list = [e.strip() for e in new_cc.strip().splitlines() if e.strip()]
        settings_repo.set_recipients(new_primary.strip(), new_cc_list)
        st.success("✅ 수신 이메일 설정이 저장되었습니다.")
        st.rerun()

    if test_btn:
        to_addr = new_primary.strip() if new_primary.strip() else recipients["primary"]
        if not to_addr:
            st.error("기본 수신 이메일을 먼저 입력하세요.")
        elif not smtp_ok:
            st.error("SMTP 설정이 없어 테스트 메일을 보낼 수 없습니다.")
        else:
            from email_service.email_sender import EmailSender
            sender = EmailSender()
            test_html = (
                "<h2>테스트 메일</h2>"
                "<p>투자 분석 시스템의 이메일 발송 테스트입니다.</p>"
                "<p>이 메일이 수신되었다면 SMTP 설정이 정상입니다.</p>"
            )
            ok, err = sender.send(
                subject="[투자 분석] 테스트 메일",
                html_body=test_html,
                recipient=to_addr,
            )
            if ok:
                st.success(f"✅ 테스트 메일을 {to_addr} 로 발송했습니다.")
            else:
                st.error(f"❌ 발송 실패: {err}")

    st.markdown("---")

    # ── 스케줄러 / 대시보드 설정 ───────────────────────────────────────────
    st.subheader("스케줄러 및 대시보드 설정")

    sched_val = settings_repo.get("scheduler_time", "07:00")
    url_val   = settings_repo.get("base_url", "http://localhost:8501")

    with st.form("scheduler_form"):
        new_time = st.text_input(
            "자동 분석 시각 (HH:MM)",
            value=sched_val,
            help="매일 이 시각에 자동 분석이 실행됩니다.",
        )
        new_url = st.text_input(
            "대시보드 URL",
            value=url_val,
            help="이메일의 '대시보드 열기' 버튼에 연결될 주소입니다.",
        )
        save_sched = st.form_submit_button("💾 저장")

    if save_sched:
        # Validate HH:MM format
        parts = new_time.strip().split(":")
        valid = (
            len(parts) == 2 and all(p.isdigit() for p in parts)
            and 0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59
        )
        if not valid:
            st.error("시각 형식이 잘못되었습니다. HH:MM 형식으로 입력하세요 (예: 07:00).")
        else:
            settings_repo.set("scheduler_time", new_time.strip())
            settings_repo.set("base_url", new_url.strip())
            st.success("✅ 스케줄러 설정이 저장되었습니다.")
            st.rerun()

    st.markdown("---")

    # ── 이메일 발송 이력 ───────────────────────────────────────────────────
    st.subheader("최근 이메일 발송 이력")
    logs = email_repo.get_all(limit=20)
    if logs:
        import pandas as pd
        log_rows = []
        for lg in logs:
            log_rows.append({
                "발송 시각": fmt_dt(lg.get("sent_at", "")),
                "종목":     lg.get("ticker", "-"),
                "수신자":   lg.get("recipient", "-"),
                "상태":     "✅ 성공" if lg["status"] == "success" else ("⬜ 건너뜀" if lg["status"] == "skipped" else "❌ 실패"),
                "오류":     lg.get("error_message", "") or "-",
            })
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
    else:
        st.info("이메일 발송 이력이 없습니다.")
