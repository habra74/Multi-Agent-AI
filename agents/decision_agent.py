"""
decision_agent.py
-----------------
Synthesizes all agent outputs into a final investment verdict.

Verdicts: STRONG BUY / BUY / HOLD / CAUTIOUS HOLD / AVOID

Key improvements over v1:
  - style (conservative/neutral/aggressive) adjusts signal weights
  - horizon (short/mid/long) shifts emphasis between market/fundamental signals
  - Conflict detection between bullish fundamentals and bearish technicals
  - action_items: concrete triggers to watch (Korean)
  - LLM prompt loaded from prompts/decision_agent_prompt.txt
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from models.llm import LLMClient
from tools.utils import clamp, safe_float

# ---------------------------------------------------------------------------
# Weight matrices keyed by (horizon, style)
# ---------------------------------------------------------------------------

# Base weights: [market, fundamental, news, risk_penalty]
# Horizon shifts: short → market+news dominate; long → fundamental+risk dominate
HORIZON_WEIGHTS: Dict[str, List[float]] = {
    "short": [0.40, 0.20, 0.25, 0.15],
    "mid":   [0.30, 0.35, 0.20, 0.15],
    "long":  [0.20, 0.45, 0.15, 0.20],
}

# Style adjustments: multipliers applied to each weight
STYLE_MODIFIERS: Dict[str, List[float]] = {
    "conservative": [0.80, 1.10, 0.90, 1.20],   # risk_penalty up, market sensitivity down
    "neutral":      [1.00, 1.00, 1.00, 1.00],
    "aggressive":   [1.20, 0.90, 1.10, 0.80],   # market/news up, risk_penalty down
}

# Verdict thresholds (composite score → verdict)
VERDICT_THRESHOLDS = [
    (0.45,  "STRONG BUY"),
    (0.20,  "BUY"),
    (-0.10, "HOLD"),
    (-0.30, "CAUTIOUS HOLD"),
]
VERDICT_DEFAULT = "AVOID"

VALID_VERDICTS = {"STRONG BUY", "BUY", "HOLD", "CAUTIOUS HOLD", "AVOID"}

# ---------------------------------------------------------------------------
# Korean label maps
# ---------------------------------------------------------------------------

_STYLE_KO   = {"conservative": "보수적", "neutral": "중립적", "aggressive": "공격적"}
_HORIZON_KO = {"short": "단기", "mid": "중기", "long": "장기"}
_TREND_KO = {
    "strong_uptrend":   "강한 상승",
    "uptrend":          "상승",
    "sideways":         "횡보",
    "downtrend":        "하락",
    "strong_downtrend": "강한 하락",
    "unknown":          "불명확",
}
_FUND_KO = {
    "strong":   "우수",
    "moderate": "보통",
    "weak":     "취약",
    "poor":     "불량",
}
_SENTIMENT_KO = {
    "positive": "긍정적",
    "neutral":  "중립적",
    "negative": "부정적",
    "mixed":    "혼재",
}
_RISK_KO = {
    "low":       "낮음",
    "moderate":  "보통",
    "elevated":  "다소 높음",
    "high":      "높음",
    "very_high": "매우 높음",
}
_VERDICT_KO = {
    "STRONG BUY":    "적극 매수",
    "BUY":           "매수 고려",
    "HOLD":          "보유/관망",
    "CAUTIOUS HOLD": "신중 관망",
    "AVOID":         "회피",
}


# ---------------------------------------------------------------------------
# DecisionAgent
# ---------------------------------------------------------------------------

class DecisionAgent(BaseAgent):
    """Produces final investment verdict from aggregated agent signals."""

    def __init__(self):
        super().__init__("decision_agent")
        self.llm = LLMClient()
        self._prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "decision_agent_prompt.txt"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, input_data: dict) -> dict:
        market     = input_data.get("market", {})
        fundamental = input_data.get("fundamental", {})
        news       = input_data.get("news", {})
        risk       = input_data.get("risk", {})
        ticker     = input_data.get("ticker", "N/A")
        style      = input_data.get("investment_style", "neutral")
        horizon    = input_data.get("horizon", "mid")
        financial  = input_data.get("financial_data", {})

        self.logger.info(f"Decision for {ticker} | style={style} | horizon={horizon} | "
                         f"llm={'yes' if self.llm.available else 'no'}")

        if self.llm.available:
            return self._llm_decision(market, fundamental, news, risk,
                                      ticker, style, horizon, financial)
        return self._rule_based_decision(market, fundamental, news, risk,
                                         ticker, style, horizon, financial)

    # ------------------------------------------------------------------
    # Rule-based path
    # ------------------------------------------------------------------

    def _rule_based_decision(
        self, market, fundamental, news, risk,
        ticker, style, horizon, financial
    ) -> dict:

        w_market, w_fund, w_news, w_risk = self._get_weights(style, horizon)

        # --- Market signal: -1..+1 ---
        trend = market.get("trend", "unknown")
        m_conf = safe_float(market.get("confidence", 0.5))
        market_score = {
            "strong_uptrend":   +1.0, "uptrend":    +0.5,
            "sideways":          0.0,
            "downtrend":        -0.5, "strong_downtrend": -1.0,
        }.get(trend, 0.0) * m_conf

        # --- Fundamental signal: -1..+1 ---
        fund_rating = fundamental.get("fundamental_rating", "unknown")
        f_conf = safe_float(fundamental.get("confidence", 0.5))
        fund_score = {
            "strong": +1.0, "moderate": +0.4, "weak": -0.3, "poor": -0.8,
        }.get(fund_rating, 0.0) * f_conf

        # --- News signal: -1..+1 ---
        sentiment = news.get("sentiment", "neutral")
        n_conf = safe_float(news.get("confidence", 0.4))
        news_score = {
            "positive": +1.0, "neutral": 0.0, "mixed": -0.2, "negative": -1.0,
        }.get(sentiment, 0.0) * n_conf

        # --- Risk penalty: 0..1 (higher = worse) ---
        risk_score = safe_float(risk.get("risk_score", 0.3))

        # --- Composite score ---
        composite = (
            w_market * market_score +
            w_fund   * fund_score +
            w_news   * news_score -
            w_risk   * risk_score
        )

        verdict = self._score_to_verdict(composite)
        confidence = clamp(0.50 + abs(composite) * 0.5)

        # --- Build bull/bear/action lists ---
        bull_points, bear_points = self._collect_signal_bullets(
            market, fundamental, news, risk, style
        )
        action_items = self._build_action_items(
            market, fundamental, news, risk, financial, ticker, verdict
        )

        # Conflict flag
        conflict = self._detect_conflict(trend, fund_rating, sentiment)

        reasoning = self._build_reasoning(
            verdict, composite, trend, fund_rating, sentiment,
            risk, style, horizon, conflict
        )
        style_ko   = _STYLE_KO.get(style, style)
        horizon_ko = _HORIZON_KO.get(horizon, horizon)
        verdict_ko = _VERDICT_KO.get(verdict, verdict)
        summary = (
            f"{ticker}: {verdict_ko} | {style_ko} 투자자 {horizon_ko} 관점 | "
            f"종합점수={composite:+.2f} | 리스크={risk.get('risk_level', 'N/A')}"
        )

        self.logger.info(f"Rule-based verdict: {verdict} (score={composite:+.2f}, "
                         f"conf={confidence:.2f})")

        return {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points[:5],
            "bear_points": bear_points[:5],
            "confidence": confidence,
            "evidence": [
                f"종합점수: {composite:+.3f}",
                f"가중치 — 시장={w_market:.2f} 펀더멘털={w_fund:.2f} "
                f"뉴스={w_news:.2f} 리스크패널티={w_risk:.2f}",
                f"신호값 — 시장={market_score:+.2f} 펀더멘털={fund_score:+.2f} "
                f"뉴스={news_score:+.2f} 리스크={risk_score:.2f}",
            ],
            "final_decision": verdict,
            "reasoning": reasoning,
            "action_items": action_items,
            "conflict_detected": conflict,
        }

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_decision(
        self, market, fundamental, news, risk,
        ticker, style, horizon, financial
    ) -> dict:
        company = financial.get("company_name", ticker)
        key_metrics = fundamental.get("key_metrics", {})

        # Pre-compute rule-based composite for context
        w_market, w_fund, w_news, w_risk = self._get_weights(style, horizon)
        trend = market.get("trend", "unknown")
        m_score = {
            "strong_uptrend": 1.0, "uptrend": 0.5, "sideways": 0.0,
            "downtrend": -0.5, "strong_downtrend": -1.0,
        }.get(trend, 0.0) * safe_float(market.get("confidence", 0.5))
        f_score = {
            "strong": 1.0, "moderate": 0.4, "weak": -0.3, "poor": -0.8,
        }.get(fundamental.get("fundamental_rating", ""), 0.0) * safe_float(fundamental.get("confidence", 0.5))

        conflict = self._detect_conflict(
            trend, fundamental.get("fundamental_rating", ""), news.get("sentiment", "")
        )

        if self._prompt_template:
            prompt = self._prompt_template.format(
                company=company, ticker=ticker,
                style=style, horizon=horizon,
                trend=trend,
                market_summary=market.get("summary", ""),
                market_bull="; ".join(market.get("bull_points", [])[:3]),
                market_bear="; ".join(market.get("bear_points", [])[:3]),
                market_conf=f"{market.get('confidence', 0):.0%}",
                fund_rating=fundamental.get("fundamental_rating", "N/A"),
                fund_summary=fundamental.get("summary", ""),
                fund_bull="; ".join(fundamental.get("bull_points", [])[:3]),
                fund_bear="; ".join(fundamental.get("bear_points", [])[:3]),
                key_metrics=key_metrics,
                news_sentiment=news.get("sentiment", "neutral"),
                news_summary=news.get("summary", ""),
                news_bull="; ".join(news.get("bull_points", [])[:2]),
                news_bear="; ".join(news.get("bear_points", [])[:2]),
                risk_level=risk.get("risk_level", "N/A"),
                risk_score=f"{risk.get('risk_score', 0):.2f}",
                risk_summary=risk.get("summary", ""),
                risk_factors="; ".join(risk.get("risk_factors", [])[:3]),
                conflict=str(conflict),
            )
        else:
            prompt = self._default_llm_prompt(
                company, ticker, style, horizon,
                market, fundamental, news, risk, key_metrics, conflict
            )

        response = self.llm.generate(prompt, max_tokens=800)

        # Parse response
        verdict = "HOLD"
        confidence = 0.55
        reasoning = ""
        bull_points: List[str] = []
        bear_points: List[str] = []
        action_items: List[str] = []

        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
            key, _, val = line.partition(":")
            val = val.strip()
            key = key.strip().upper()

            if key == "VERDICT":
                candidate = val.upper()
                if candidate in VALID_VERDICTS:
                    verdict = candidate
            elif key == "CONFIDENCE":
                try:
                    confidence = clamp(float(val))
                except ValueError:
                    pass
            elif key == "REASONING" and val:
                reasoning = val
            elif key == "BULL" and val and not val.startswith("["):
                bull_points.append(val)
            elif key == "BEAR" and val and not val.startswith("["):
                bear_points.append(val)
            elif key == "ACTION" and val and not val.startswith("["):
                action_items.append(val)

        if not reasoning:
            reasoning = self._build_reasoning(
                verdict, 0, trend,
                fundamental.get("fundamental_rating", ""),
                news.get("sentiment", ""), risk, style, horizon, conflict
            )

        style_ko   = _STYLE_KO.get(style, style)
        horizon_ko = _HORIZON_KO.get(horizon, horizon)
        verdict_ko = _VERDICT_KO.get(verdict, verdict)
        summary = (
            f"{ticker}: {verdict_ko} | {style_ko} 투자자 {horizon_ko} 관점 | "
            f"신뢰도={confidence:.0%}"
        )

        self.logger.info(f"LLM verdict: {verdict} (conf={confidence:.2f})")

        return {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points[:5],
            "bear_points": bear_points[:5],
            "confidence": confidence,
            "evidence": ["LLM 기반 다중 요인 종합 분석"],
            "final_decision": verdict,
            "reasoning": reasoning,
            "action_items": action_items[:5],
            "conflict_detected": conflict,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_weights(self, style: str, horizon: str) -> Tuple[float, float, float, float]:
        """Return (w_market, w_fundamental, w_news, w_risk) adjusted by style & horizon."""
        base = HORIZON_WEIGHTS.get(horizon, HORIZON_WEIGHTS["mid"])
        mods = STYLE_MODIFIERS.get(style, STYLE_MODIFIERS["neutral"])
        raw = [b * m for b, m in zip(base, mods)]
        total = sum(raw[:3])  # normalise market+fund+news only (risk is a penalty)
        if total == 0:
            return 0.30, 0.35, 0.20, 0.15
        scale = (base[0] + base[1] + base[2]) / total  # maintain original magnitude
        return raw[0] * scale, raw[1] * scale, raw[2] * scale, raw[3]

    def _score_to_verdict(self, score: float) -> str:
        for threshold, verdict in VERDICT_THRESHOLDS:
            if score >= threshold:
                return verdict
        return VERDICT_DEFAULT

    def _detect_conflict(self, trend: str, fund_rating: str, sentiment: str) -> bool:
        """True if market technicals and fundamentals strongly disagree."""
        bullish_fund = fund_rating in ("strong", "moderate")
        bearish_market = "downtrend" in trend
        bullish_market = "uptrend" in trend
        bearish_fund = fund_rating in ("weak", "poor")
        return (bullish_fund and bearish_market) or (bearish_fund and bullish_market)

    def _collect_signal_bullets(
        self, market, fundamental, news, risk, style
    ) -> Tuple[List[str], List[str]]:
        """Pick the most informative bull/bear points from agent outputs."""
        bull: List[str] = []
        bear: List[str] = []

        for pt in market.get("bull_points", [])[:2]:
            bull.append(f"[시장] {pt}")
        for pt in fundamental.get("bull_points", [])[:3]:
            bull.append(f"[펀더멘털] {pt}")
        for pt in news.get("bull_points", [])[:1]:
            bull.append(f"[뉴스] {pt}")

        for pt in market.get("bear_points", [])[:2]:
            bear.append(f"[시장] {pt}")
        for pt in fundamental.get("bear_points", [])[:2]:
            bear.append(f"[펀더멘털] {pt}")
        for pt in risk.get("risk_factors", [])[:2]:
            bear.append(f"[리스크] {pt}")
        for pt in news.get("bear_points", [])[:1]:
            bear.append(f"[뉴스] {pt}")

        return bull, bear

    def _build_action_items(
        self, market, fundamental, news, risk, financial, ticker, verdict
    ) -> List[str]:
        """Generate concrete Korean monitoring triggers based on analysis."""
        actions: List[str] = []
        trend = market.get("trend", "")

        if "downtrend" in trend or trend == "sideways":
            sma50 = market.get("indicators_snapshot", {}).get("sma50")
            if sma50:
                actions.append(f"50일 이동평균({sma50:,.2f}) 돌파 여부를 추세 반전 신호로 주시")
            else:
                actions.append("50일 이동평균선 상향 돌파 여부를 추세 반전 신호로 모니터링")

        risk_score = safe_float(risk.get("risk_score", 0))
        if risk_score > 0.4:
            actions.append(
                f"리스크 점수({risk_score:.2f})가 높은 상태 — 0.55 이상 시 보유 비중 재검토"
            )

        if news.get("category_breakdown", {}).get("earnings", 0) > 0:
            actions.append("최근 실적 관련 뉴스 포착 — 다음 실적 발표일 및 가이던스 확인 필요")
        else:
            actions.append("다음 분기 실적 발표 일정 확인 및 컨센서스 대비 결과 모니터링")

        if news.get("category_breakdown", {}).get("legal", 0) > 0:
            actions.append("법적·규제 관련 뉴스 포착 — 소송·조사 진행 경과 추적 필요")

        if news.get("category_breakdown", {}).get("analyst", 0) > 0:
            actions.append("애널리스트 활동 감지 — 목표주가 변경 및 투자의견 변화 주시")

        target = safe_float(financial.get("target_price"))
        current = safe_float(financial.get("current_price"))
        if target and current:
            upside = (target / current - 1) * 100
            if upside > 0:
                actions.append(
                    f"애널리스트 컨센서스 목표주가: {target:,.2f} (상승여력 {upside:+.0f}%)"
                )

        if verdict in ("STRONG BUY", "BUY"):
            actions.append("타이밍 리스크 분산을 위해 분할 매수 전략 고려")
        elif verdict == "CAUTIOUS HOLD":
            actions.append("추가 매수 전 손절 기준 설정 및 포지션 규모 점검")
        elif verdict == "AVOID":
            actions.append("리스크 점수가 0.3 이하로 하락 시 재진입 조건 재평가")

        return actions[:5]

    def _build_reasoning(
        self, verdict, composite, trend, fund_rating,
        sentiment, risk, style, horizon, conflict
    ) -> str:
        """Construct a Korean natural-language reasoning string."""
        style_ko     = _STYLE_KO.get(style,       style)
        horizon_ko   = _HORIZON_KO.get(horizon,   horizon)
        trend_ko     = _TREND_KO.get(trend,        trend.replace("_", " "))
        fund_ko      = _FUND_KO.get(fund_rating,   fund_rating)
        sentiment_ko = _SENTIMENT_KO.get(sentiment, sentiment)
        risk_level   = risk.get("risk_level", "moderate")
        risk_ko      = _RISK_KO.get(risk_level, risk_level)
        verdict_ko   = _VERDICT_KO.get(verdict, verdict)

        base = (
            f"{style_ko} 투자자 기준에서 {horizon_ko} 투자 관점으로 볼 때, "
            f"이 종목은 {trend_ko} 시장 추세를 보이고 있으며 "
            f"펀더멘털은 {fund_ko} 수준으로 평가됩니다. "
            f"뉴스 심리는 {sentiment_ko}이며 전반적인 리스크 수준은 {risk_ko}입니다."
        )

        if conflict:
            base += (
                " 단, 펀더멘털 지표는 양호하나 가격 흐름이 약세를 보이는 신호 충돌이 감지됩니다. "
                "가치 투자 기회일 수 있으나, 사업 환경 변화 가능성도 함께 고려하시기 바랍니다."
            )

        conclusion_map = {
            "STRONG BUY":    f" 주요 신호 전반이 긍정적으로 정렬되어 있어 {verdict_ko}를 제안합니다.",
            "BUY":           f" 전반적인 증거가 현 수준에서의 매수를 지지하여 {verdict_ko}를 제안합니다.",
            "HOLD":          f" 혼재된 신호로 인해 기존 포지션 유지를 권고하며 {verdict_ko} 의견입니다.",
            "CAUTIOUS HOLD": f" 리스크 요인이 상승 여력을 제한하므로, 강세 시 비중 축소를 고려하는 {verdict_ko} 의견입니다.",
            "AVOID":         f" 현재 리스크 대비 기대수익이 불리하므로 더 명확한 신호 확인 전까지 {verdict_ko}를 권고합니다.",
        }
        base += conclusion_map.get(verdict, "")

        return base

    def _default_llm_prompt(
        self, company, ticker, style, horizon,
        market, fundamental, news, risk, key_metrics, conflict
    ) -> str:
        return f"""You are a professional equity analyst. Synthesize the following multi-agent analysis for {company} ({ticker}) and provide an investment verdict.

INVESTOR PROFILE:
- Style: {style} (conservative=risk-averse | neutral=balanced | aggressive=growth-focused)
- Time Horizon: {horizon} (short=weeks | mid=months | long=years)

MARKET ANALYSIS:
- Trend: {market.get('trend', 'N/A')}
- Summary: {market.get('summary', 'N/A')}
- Bull signals: {'; '.join(market.get('bull_points', [])[:3])}
- Bear signals: {'; '.join(market.get('bear_points', [])[:3])}
- Confidence: {market.get('confidence', 0):.0%}

FUNDAMENTAL ANALYSIS:
- Rating: {fundamental.get('fundamental_rating', 'N/A')}
- Summary: {fundamental.get('summary', 'N/A')}
- Key metrics: {key_metrics}
- Bull signals: {'; '.join(fundamental.get('bull_points', [])[:3])}
- Bear signals: {'; '.join(fundamental.get('bear_points', [])[:3])}

NEWS & SENTIMENT:
- Sentiment: {news.get('sentiment', 'neutral')}
- Summary: {news.get('summary', 'N/A')}
- Bull: {'; '.join(news.get('bull_points', [])[:2])}
- Bear: {'; '.join(news.get('bear_points', [])[:2])}

RISK:
- Level: {risk.get('risk_level', 'N/A')} (score: {risk.get('risk_score', 0):.2f}/1.0)
- Factors: {'; '.join(risk.get('risk_factors', [])[:3])}

CONFLICT: {"Fundamentals and market trend DISAGREE — interpret carefully." if conflict else "No major conflict between signals."}

Respond in EXACTLY this format (one item per line, no extra text):
VERDICT: [STRONG BUY / BUY / HOLD / CAUTIOUS HOLD / AVOID]
CONFIDENCE: [0.00-1.00]
REASONING: [2-3 sentences synthesizing the above for this specific investor profile]
BULL: [key supporting factor]
BULL: [second supporting factor]
BEAR: [key risk or concern]
BEAR: [second concern]
ACTION: [first concrete monitoring trigger]
ACTION: [second trigger]
ACTION: [third trigger]"""
