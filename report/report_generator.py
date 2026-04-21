"""
report_generator.py
-------------------
Converts multi-agent analysis results into a readable Markdown report.

Supports English (language="en") and Korean (language="ko") output.
Default language is "en" for backward compatibility with existing tests;
the CLI defaults to "ko" via config.DEFAULT_LANGUAGE.

Sections:
  0. Header / metadata
  1. Executive Summary
  2. Market Analysis
  3. Fundamental Analysis
  4. News & Sentiment
  5. Risk Analysis
  6. Bull Case vs Bear Case
  7. What to Watch Next
  8. Final Investment Decision
"""

import json
import sys
import os
from datetime import datetime
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Translation tables
# ---------------------------------------------------------------------------

# Verdict display text
VERDICT_KO = {
    "STRONG BUY":   "적극 매수",
    "BUY":          "매수 고려",
    "HOLD":         "보유/관망",
    "CAUTIOUS HOLD": "신중 관망",
    "AVOID":        "회피",
}

TREND_KO = {
    "strong_uptrend":   "강한 상승세",
    "uptrend":          "상승세",
    "sideways":         "횡보",
    "downtrend":        "하락세",
    "strong_downtrend": "강한 하락세",
    "unknown":          "불명확",
}

SENTIMENT_KO = {
    "positive": "긍정적",
    "neutral":  "중립적",
    "negative": "부정적",
    "mixed":    "혼재",
}

RISK_LEVEL_KO = {
    "low":       "낮음",
    "moderate":  "보통",
    "elevated":  "다소 높음",
    "high":      "높음",
    "very_high": "매우 높음",
}

FUND_RATING_KO = {
    "strong":   "우수",
    "moderate": "보통",
    "weak":     "취약",
    "poor":     "불량",
}

STYLE_KO   = {"conservative": "보수적", "neutral": "중립", "aggressive": "공격적"}
HORIZON_KO = {"short": "단기", "mid": "중기", "long": "장기"}


def _get_labels(language: str = "en") -> dict:
    """Return a dict of all UI label strings for the given language."""
    if language == "ko":
        return {
            "report_title":    "투자 분석 리포트",
            "ticker":          "종목코드",
            "company":         "기업명",
            "sector":          "업종",
            "price":           "현재가",
            "market":          "시장",
            "style":           "투자 성향",
            "horizon":         "투자 기간",
            "generated":       "생성 시각",
            # Section titles
            "exec_summary":    "핵심 요약",
            "market_analysis": "시장 분석",
            "fund_analysis":   "펀더멘털 분석",
            "news_analysis":   "뉴스 및 심리 분석",
            "risk_analysis":   "리스크 분석",
            "bull_bear":       "긍정 요인 vs 부정 요인",
            "watch_next":      "향후 체크 포인트",
            "final_decision":  "최종 투자 의견",
            # Field labels
            "verdict":         "투자 의견",
            "confidence":      "신뢰도",
            "trend":           "추세",
            "rating":          "등급",
            "sentiment":       "뉴스 심리",
            "articles":        "기사 수",
            "risk_level":      "리스크 수준",
            "risk_score":      "리스크 점수",
            "bull_signals":    "긍정 신호",
            "bear_signals":    "부정 신호",
            "tech_data":       "기술적 데이터",
            "key_metrics":     "주요 지표",
            "cat_breakdown":   "카테고리 분류",
            "headlines":       "최근 헤드라인",
            "risk_factors":    "리스크 요인",
            "mitigating":      "완화 요인",
            "bull_case":       "긍정 시나리오",
            "bear_case":       "부정 시나리오",
            "action_suggest":  "실행 제안",
            "reasoning":       "분석 근거",
            "investor":        "투자자 프로필",
            "disclaimer":      (
                "본 리포트는 AI가 생성한 참고 자료입니다.\n"
                "  투자 조언이 아니며, 실제 투자 결정 전 전문가 상담을 권장합니다."
            ),
            "no_news":         "최근 기사 없음",
            "no_signals":      "(신호 없음)",
            "no_actions":      "  - 특이사항 없음",
            "conflict_note": (
                "\n  * 신호 충돌 감지: 펀더멘털은 긍정적이나 가격 흐름이 약세입니다.\n"
                "    가치 투자 기회일 수 있으나, 사업 환경 변화 가능성도 고려하십시오.\n"
                "    추가적인 자체 조사를 통해 확인하시기 바랍니다."
            ),
            "risk_scale": "(0.0=최소  0.2=낮음  0.4=보통  0.6=다소 높음  0.8=높음  1.0=위험)",
        }
    # --- English (default) ---
    return {
        "report_title":    "INVESTMENT ANALYSIS REPORT",
        "ticker":          "Ticker",
        "company":         "Company",
        "sector":          "Sector",
        "price":           "Price",
        "market":          "Market",
        "style":           "Style",
        "horizon":         "Horizon",
        "generated":       "Generated",
        "exec_summary":    "EXECUTIVE SUMMARY",
        "market_analysis": "1. MARKET ANALYSIS",
        "fund_analysis":   "2. FUNDAMENTAL ANALYSIS",
        "news_analysis":   "3. NEWS & SENTIMENT",
        "risk_analysis":   "4. RISK ANALYSIS",
        "bull_bear":       "5. BULL CASE vs BEAR CASE",
        "watch_next":      "6. WHAT TO WATCH NEXT",
        "final_decision":  "FINAL INVESTMENT DECISION",
        "verdict":         "Verdict",
        "confidence":      "Confidence",
        "trend":           "Trend",
        "rating":          "Rating",
        "sentiment":       "Sentiment",
        "articles":        "Articles",
        "risk_level":      "Risk Level",
        "risk_score":      "Risk Score",
        "bull_signals":    "Bullish signals",
        "bear_signals":    "Bearish signals",
        "tech_data":       "Technical data",
        "key_metrics":     "Key metrics",
        "cat_breakdown":   "Category breakdown",
        "headlines":       "Recent headlines",
        "risk_factors":    "Risk factors",
        "mitigating":      "Mitigating factors",
        "bull_case":       "BULL CASE",
        "bear_case":       "BEAR CASE",
        "action_suggest":  "Action suggestions",
        "reasoning":       "Reasoning",
        "investor":        "Investor",
        "disclaimer":      (
            "This report is AI-generated for informational purposes only.\n"
            "  It does not constitute financial advice. Consult a qualified advisor."
        ),
        "no_news":   "No recent news articles retrieved",
        "no_signals": "(none identified)",
        "no_actions": "  - No specific actions identified",
        "conflict_note": (
            "\n  * SIGNAL CONFLICT: Strong fundamentals diverge from weak price action.\n"
            "    This may indicate a value opportunity OR a business in transition.\n"
            "    Apply extra caution and confirm with own research."
        ),
        "risk_scale": "(0.0=minimal  0.2=low  0.4=moderate  0.6=elevated  0.8=high  1.0=critical)",
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_price(price, market: str = "US") -> str:
    """Format a price with the appropriate currency symbol."""
    if price is None:
        return "N/A"
    if market == "KR":
        return f"{price:,.0f}원"
    return f"${price:.2f}"


def _bullet_list(items: List, prefix: str = "  - ", fallback: str = "") -> str:
    if not items:
        return (fallback or "  - (none identified)") + "\n"
    return "".join(f"{prefix}{item}\n" for item in items if str(item).strip())


def _confidence_label(confidence: float, language: str = "en") -> str:
    """Return numeric + qualitative label."""
    pct = round(confidence * 100)
    if language == "ko":
        label = (
            "매우 높음" if pct >= 80 else
            "높음"      if pct >= 65 else
            "보통"      if pct >= 45 else
            "낮음"      if pct >= 25 else
            "매우 낮음"
        )
    else:
        label = (
            "Very High" if pct >= 80 else
            "High"      if pct >= 65 else
            "Moderate"  if pct >= 45 else
            "Low"       if pct >= 25 else
            "Very Low"
        )
    return f"{pct}% ({label})"


def _translate_trend(trend: str, language: str) -> str:
    if language == "ko":
        return TREND_KO.get(trend, trend)
    return trend.replace("_", " ").title()


def _translate_sentiment(sent: str, language: str) -> str:
    if language == "ko":
        return SENTIMENT_KO.get(sent.lower(), sent)
    return sent.title()


def _translate_risk_level(level: str, language: str) -> str:
    if language == "ko":
        return RISK_LEVEL_KO.get(level.lower(), level)
    return level.replace("_", " ").title()


def _translate_fund_rating(rating: str, language: str) -> str:
    if language == "ko":
        return FUND_RATING_KO.get(rating.lower(), rating)
    return rating.title()


def _translate_verdict(verdict: str, language: str) -> str:
    if language == "ko":
        return VERDICT_KO.get(verdict, verdict)
    return verdict


def _translate_style(style: str, language: str) -> str:
    if language == "ko":
        return STYLE_KO.get(style.lower(), style)
    return style.capitalize()


def _translate_horizon(horizon: str, language: str) -> str:
    if language == "ko":
        return HORIZON_KO.get(horizon.lower(), horizon)
    return f"{horizon.capitalize()}-term"


_CATEGORY_KO_RPT: dict = {
    "earnings":  "실적",
    "product":   "제품",
    "analyst":   "애널리스트",
    "legal":     "법률/규제",
    "macro":     "거시경제",
    "corporate": "기업이슈",
    "sentiment": "시장심리",
    "general":   "일반",
}

_SENTIMENT_ICON: dict = {
    "positive": "(+)",
    "negative": "(-)",
    "neutral":  "(=)",
    "mixed":    "(+-)",
}


def _news_evidence_block(evidence: List, language: str = "en") -> str:
    """Render structured news evidence; fall back to plain strings.

    Korean mode: shows [뉴스 요약] / [투자 해석] / [기사 링크] per article.
    English mode: compact one-liner per article.
    """
    no_news_msg = "  - 최근 기사 없음\n" if language == "ko" else "  - No recent news articles retrieved\n"
    if not evidence:
        return no_news_msg

    lines = []
    for item in evidence[:8]:
        if not isinstance(item, dict):
            lines.append(f"  - {str(item)[:120]}")
            continue

        date      = item.get("date", "")
        cat_raw   = item.get("category", "general")
        sent      = item.get("sentiment", "neutral")
        pub       = item.get("publisher", "")
        headline  = item.get("headline", "")[:120]
        link      = item.get("link", "")
        interp    = item.get("interpretation", "")

        if language == "ko":
            cat_label  = _CATEGORY_KO_RPT.get(cat_raw, cat_raw)
            icon       = _SENTIMENT_ICON.get(sent, "-")
            date_str   = f" ({date})" if date else ""
            src_str    = f" | {pub}" if pub else ""

            lines.append(f"  >> [{cat_label}]{date_str}{src_str}  {icon}")
            lines.append(f"     [뉴스 요약] {headline}")
            if interp:
                lines.append(f"     [투자 해석] {interp}")
            if link:
                lines.append(f"     [기사 링크] {link}")
        else:
            cat    = cat_raw.upper()
            tag    = f"[{cat}]" if cat else ""
            date_t = f" [{date}]" if date else ""
            sent_t = f" ({sent})" if sent else ""
            src    = f" | {pub}" if pub else ""
            lines.append(f"  - {tag}{date_t} {headline}{sent_t}{src}")

    return "\n".join(lines) + "\n"


def _section(title: str, body: str, char: str = "-") -> str:
    width = 70
    return f"\n{char * width}\n## {title}\n{char * width}\n{body}"


# ---------------------------------------------------------------------------
# Korean executive summary builder (4-part narrative)
# ---------------------------------------------------------------------------

def _build_ko_exec_summary(
    verdict_icon: str,
    verdict_display: str,
    da: dict,
    ma: dict,
    fa: dict,
    na: dict,
    ra: dict,
    style_display: str,
    horizon_display: str,
    L: dict,
    conflict_note: str,
) -> str:
    """
    Build a 4-part Korean narrative executive summary:
      ① 현재 상황   ② 긍정 요인   ③ 주의 요인   ④ 투자 결론
    """
    conf_str = _confidence_label(da.get("confidence", 0), "ko")

    # ① 현재 상황: trend + fundamental rating + sentiment
    trend_str  = _translate_trend(ma.get("trend", "unknown"), "ko")
    fund_str   = _translate_fund_rating(fa.get("fundamental_rating", "N/A"), "ko")
    sent_str   = _translate_sentiment(na.get("sentiment", "neutral"), "ko")
    risk_str   = _translate_risk_level(ra.get("risk_level", "N/A"), "ko")

    situation = (
        f"현재 {trend_str} 추세이며, 펀더멘털 등급은 '{fund_str}', "
        f"뉴스 심리는 {sent_str}, 리스크 수준은 {risk_str}입니다."
    )

    # ② 긍정 요인: top bull points from decision
    bull_pts = da.get("bull_points", [])
    if bull_pts:
        positives = "\n".join(f"    - {pt}" for pt in bull_pts[:3])
    else:
        positives = "    - (긍정 신호 없음)"

    # ③ 주의 요인: bear points from decision (already includes [리스크] tags)
    bear_pts = da.get("bear_points", [])
    if bear_pts:
        cautions = "\n".join(f"    - {pt}" for pt in bear_pts[:3])
    else:
        # fallback to raw risk factors if decision has no bear points
        risk_fcts = ra.get("risk_factors", [])
        cautions = "\n".join(f"    - {pt}" for pt in risk_fcts[:3]) if risk_fcts else "    - (부정 신호 없음)"

    # ④ 투자 결론: reasoning sentence
    reasoning = da.get("reasoning", "")

    summary = f"""
  {L['verdict']:10}: {verdict_icon} {verdict_display}
  {L['confidence']:10}: {conf_str}
  {L['investor']:10}: {style_display} | {horizon_display}

  ① 현재 상황
    {situation}

  ② 긍정 요인
{positives}

  ③ 주의 요인
{cautions}

  ④ 투자 결론
    {reasoning}
{conflict_note}"""
    return summary


# ---------------------------------------------------------------------------
# Main report function
# ---------------------------------------------------------------------------

def generate_report(results: dict, language: str = "en") -> str:
    """
    Generate a Markdown investment report.

    Parameters
    ----------
    results  : dict   – output from Coordinator.run()
    language : str    – "en" (default, backward-compatible) or "ko"
    """
    L = _get_labels(language)

    ticker  = results.get("ticker", "N/A")
    company = results.get("company_name", ticker)
    sector  = results.get("sector", "Unknown")
    price   = results.get("current_price")
    market  = results.get("market", "US")
    style   = results.get("investment_style", "neutral")
    horizon = results.get("horizon", "mid")
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")

    ma = results.get("market_analysis", {})
    fa = results.get("fundamental_analysis", {})
    na = results.get("news_analysis", {})
    ra = results.get("risk_analysis", {})
    da = results.get("decision", {})

    verdict = da.get("final_decision", "HOLD")
    verdict_display = _translate_verdict(verdict, language)
    verdict_icon = {
        "STRONG BUY":    "[++]",
        "BUY":           "[+] ",
        "HOLD":          "[=] ",
        "CAUTIOUS HOLD": "[-] ",
        "AVOID":         "[--]",
    }.get(verdict, "[?] ")

    price_str = _format_price(price, market)
    SEP = "=" * 70

    style_display   = _translate_style(style, language)
    horizon_display = _translate_horizon(horizon, language)

    # ------------------------------------------------------------------ #
    # 0. HEADER
    # ------------------------------------------------------------------ #
    header = f"""
{SEP}
  {L['report_title']}
{SEP}
  {L['ticker']:8}: {ticker}
  {L['company']:8}: {company}
  {L['sector']:8}: {sector}
  {L['price']:8}: {price_str}
  {L['market']:8}: {market}
  {L['style']:8}: {style_display}   |   {L['horizon']}: {horizon_display}
  {L['generated']:8}: {now}
{SEP}"""

    # ------------------------------------------------------------------ #
    # 1. EXECUTIVE SUMMARY
    # ------------------------------------------------------------------ #
    conflict_note = L["conflict_note"] if da.get("conflict_detected") else ""

    if language == "ko":
        exec_summary = _build_ko_exec_summary(
            verdict_icon, verdict_display, da, ma, fa, na, ra,
            style_display, horizon_display, L, conflict_note
        )
    else:
        exec_summary = f"""
  {L['verdict']:10}: {verdict_icon} {verdict_display}
  {L['confidence']:10}: {_confidence_label(da.get('confidence', 0), language)}

  {da.get('reasoning', 'Analysis complete.')}
{conflict_note}"""

    # ------------------------------------------------------------------ #
    # 2. MARKET ANALYSIS
    # ------------------------------------------------------------------ #
    market_body = f"""{ma.get('summary', 'N/A')}

  {L['trend']:10}: {_translate_trend(ma.get('trend', 'unknown'), language)}
  {L['confidence']:10}: {_confidence_label(ma.get('confidence', 0), language)}

  {L['bull_signals']}:
{_bullet_list(ma.get('bull_points', []), fallback='  - ' + L['no_signals'])}
  {L['bear_signals']}:
{_bullet_list(ma.get('bear_points', []), fallback='  - ' + L['no_signals'])}
  {L['tech_data']}:
{_bullet_list(ma.get('evidence', []))}"""

    # ------------------------------------------------------------------ #
    # 3. FUNDAMENTAL ANALYSIS
    # ------------------------------------------------------------------ #
    fund_body = f"""{fa.get('summary', 'N/A')}

  {L['rating']:10}: {_translate_fund_rating(fa.get('fundamental_rating', 'N/A'), language)}
  {L['confidence']:10}: {_confidence_label(fa.get('confidence', 0), language)}

  {L['bull_signals']}:
{_bullet_list(fa.get('bull_points', []), fallback='  - ' + L['no_signals'])}
  {L['bear_signals']}:
{_bullet_list(fa.get('bear_points', []), fallback='  - ' + L['no_signals'])}
  {L['key_metrics']}:
{_bullet_list(fa.get('evidence', [])[:7])}"""

    # ------------------------------------------------------------------ #
    # 4. NEWS & SENTIMENT
    # ------------------------------------------------------------------ #
    cat_bd = na.get("category_breakdown", {})
    cat_str = ""
    if cat_bd:
        top = sorted(cat_bd.items(), key=lambda x: x[1], reverse=True)[:4]
        cat_str = f"  {L['cat_breakdown']}: " + " | ".join(f"{k}:{v}" for k, v in top) + "\n"

    news_body = f"""{na.get('summary', 'N/A')}

  {L['sentiment']:10}: {_translate_sentiment(na.get('sentiment', 'neutral'), language)}
  {L['articles']:10}: {na.get('news_count', 0)}
  {L['confidence']:10}: {_confidence_label(na.get('confidence', 0), language)}
{cat_str}
  {L['bull_signals']}:
{_bullet_list(na.get('bull_points', []), fallback='  - ' + L['no_signals'])}
  {L['bear_signals']}:
{_bullet_list(na.get('bear_points', []), fallback='  - ' + L['no_signals'])}
  {L['headlines']}:
{_news_evidence_block(na.get('evidence', []), language)}"""

    # ------------------------------------------------------------------ #
    # 5. RISK ANALYSIS
    # ------------------------------------------------------------------ #
    risk_body = f"""{ra.get('summary', 'N/A')}

  {L['risk_level']:10}: {_translate_risk_level(ra.get('risk_level', 'N/A'), language)}
  {L['risk_score']:10}: {ra.get('risk_score', 0):.2f} / 1.00
  {L['risk_scale']}

  {L['risk_factors']}:
{_bullet_list(ra.get('risk_factors', []))}
  {L['mitigating']}:
{_bullet_list(ra.get('bull_points', []))}"""

    # ------------------------------------------------------------------ #
    # 6. BULL CASE vs BEAR CASE
    # ------------------------------------------------------------------ #
    all_bull = da.get("bull_points", [])
    all_bear = da.get("bear_points", [])

    bull_bear_body = f"""  {L['bull_case']}:
{_bullet_list(all_bull, fallback='  - ' + L['no_signals'])}
  {L['bear_case']}:
{_bullet_list(all_bear, fallback='  - ' + L['no_signals'])}"""

    # ------------------------------------------------------------------ #
    # 7. WHAT TO WATCH NEXT
    # ------------------------------------------------------------------ #
    action_items = da.get("action_items", [])
    watch_items  = na.get("watch_items", [])
    all_watch    = action_items + [f"[News] {w}" for w in watch_items]

    watch_body = (
        _bullet_list(all_watch)
        if all_watch else
        ("  - 가격 흐름 및 실적 발표 모니터링\n" if language == "ko"
         else "  - Monitor price action and earnings releases\n")
    )

    # ------------------------------------------------------------------ #
    # 8. FINAL DECISION
    # ------------------------------------------------------------------ #
    final_body = f"""
  {verdict_icon}  {L['verdict']}: {verdict_display}

  {L['confidence']:10}: {_confidence_label(da.get('confidence', 0), language)}
  {L['investor']:10}: {style_display} | {horizon_display}

  {L['reasoning']}:
  {da.get('reasoning', 'N/A')}

  {L['action_suggest']}:
{_bullet_list(action_items, fallback=L['no_actions'])}"""

    # ------------------------------------------------------------------ #
    # Assemble
    # ------------------------------------------------------------------ #
    report = (
        header
        + _section(L["exec_summary"],    exec_summary,  "=")
        + _section(L["market_analysis"], market_body)
        + _section(L["fund_analysis"],   fund_body)
        + _section(L["news_analysis"],   news_body)
        + _section(L["risk_analysis"],   risk_body)
        + _section(L["bull_bear"],       bull_bear_body)
        + _section(L["watch_next"],      watch_body)
        + _section(L["final_decision"],  final_body, "=")
        + f"""
{SEP}
  {L['disclaimer']}
{SEP}
"""
    )
    return report


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def generate_json_report(results: dict) -> dict:
    """Return a clean JSON-serializable summary of all agent outputs."""
    def _clean(obj):
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_clean(v) for v in obj]
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)

    return _clean({
        "generated_at":     datetime.now().isoformat(),
        "ticker":           results.get("ticker"),
        "company_name":     results.get("company_name"),
        "sector":           results.get("sector"),
        "current_price":    results.get("current_price"),
        "investment_style": results.get("investment_style"),
        "horizon":          results.get("horizon"),
        "market":           results.get("market"),
        "language":         results.get("language", "en"),
        "market_analysis": {
            k: v for k, v in results.get("market_analysis", {}).items()
            if k != "price_data"
        },
        "fundamental_analysis": results.get("fundamental_analysis", {}),
        "news_analysis":        results.get("news_analysis", {}),
        "risk_analysis":        results.get("risk_analysis", {}),
        "decision":             results.get("decision", {}),
    })
