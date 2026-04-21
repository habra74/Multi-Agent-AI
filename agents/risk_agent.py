import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from tools.utils import safe_float, clamp


class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__("risk_agent")

    def run(self, input_data: dict) -> dict:
        market = input_data.get("market", {})
        fundamental = input_data.get("fundamental", {})
        news = input_data.get("news", {})
        raw_data = input_data.get("raw_data", {})
        ticker = raw_data.get("ticker", input_data.get("ticker", "N/A"))

        self.logger.info(f"Analyzing risk for {ticker}")

        bull_points = []
        bear_points = []
        evidence = []
        risk_factors = []
        risk_score = 0.0  # 0 = low risk, 1 = high risk

        # Market volatility risk
        indicators = raw_data.get("indicators", {})
        vol_class = indicators.get("vol_classification", "unknown")
        vol_pct = safe_float(indicators.get("annualized_volatility_pct"))

        if vol_pct:
            evidence.append(f"Annualized volatility: {vol_pct:.1f}% ({vol_class})")
            vol_risk = {"low": 0.1, "moderate": 0.3, "high": 0.6, "very_high": 0.9}.get(vol_class, 0.4)
            risk_score += vol_risk * 0.3
            if vol_class in ("high", "very_high"):
                risk_factors.append(f"High price volatility ({vol_pct:.1f}% annualized)")
                bear_points.append(f"Elevated volatility risk: {vol_pct:.1f}% annualized")
            else:
                bull_points.append(f"Manageable volatility: {vol_pct:.1f}% annualized")

        # Beta risk
        financial = raw_data.get("financial_data", {})
        beta = safe_float(financial.get("beta"))
        if beta:
            evidence.append(f"Beta: {beta:.2f}")
            if beta > 1.5:
                risk_factors.append(f"High market sensitivity (beta: {beta:.2f})")
                bear_points.append(f"High beta ({beta:.2f}) — amplified market moves")
                risk_score += 0.2
            elif beta < 0.5:
                bull_points.append(f"Low correlation to market (beta: {beta:.2f}) — defensive characteristics")
            else:
                bull_points.append(f"Normal market sensitivity (beta: {beta:.2f})")

        # Trend risk
        trend = market.get("trend", "unknown")
        evidence.append(f"Market trend: {trend}")
        if "downtrend" in trend:
            risk_factors.append(f"Price in {trend}")
            bear_points.append(f"Unfavorable price trend: {trend}")
            risk_score += 0.15 if "strong" not in trend else 0.25
        elif "uptrend" in trend:
            bull_points.append(f"Favorable price trend: {trend}")

        # Fundamental risk
        fund_rating = fundamental.get("fundamental_rating", "unknown")
        debt_eq = safe_float(financial.get("debt_to_equity"))
        current_r = safe_float(financial.get("current_ratio"))
        op_margin = safe_float(financial.get("operating_margin"))

        if debt_eq > 2.0:
            risk_factors.append(f"High leverage (D/E: {debt_eq:.2f})")
            bear_points.append(f"High debt load (D/E: {debt_eq:.2f}) — financial risk")
            risk_score += 0.15
        elif debt_eq > 0 and debt_eq < 1.0:
            bull_points.append(f"Conservative balance sheet (D/E: {debt_eq:.2f})")

        if current_r and current_r < 1.0:
            risk_factors.append(f"Liquidity concern (current ratio: {current_r:.2f})")
            bear_points.append(f"Low liquidity (current ratio: {current_r:.2f})")
            risk_score += 0.1

        if op_margin and op_margin < 0:
            risk_factors.append("Company not yet profitable")
            bear_points.append("Negative operating margins — cash burn risk")
            risk_score += 0.15

        # News/sentiment risk
        news_sentiment = news.get("sentiment", "neutral")
        evidence.append(f"News sentiment: {news_sentiment}")
        if news_sentiment == "negative":
            risk_factors.append("Negative news sentiment")
            bear_points.append("Negative news flow may pressure stock price")
            risk_score += 0.1
        elif news_sentiment == "positive":
            bull_points.append("Positive news sentiment supports the investment case")

        # Short interest
        short_ratio = safe_float(financial.get("short_ratio"))
        if short_ratio > 5:
            risk_factors.append(f"High short interest (short ratio: {short_ratio:.1f} days)")
            bear_points.append(f"High short interest ({short_ratio:.1f} days to cover) — bearish signal")
            risk_score += 0.1
        elif short_ratio > 0:
            evidence.append(f"Short ratio: {short_ratio:.1f} days")

        # 52-week position risk
        pos = indicators.get("position_in_range")
        if pos is not None:
            if pos > 90:
                risk_factors.append("Near 52-week high — limited near-term upside")
                bear_points.append(f"Near 52-week high ({pos:.0f}% of range) — valuation stretch risk")
                risk_score += 0.05
            elif pos < 10:
                bull_points.append(f"Near 52-week low ({pos:.0f}% of range) — potential value entry")

        # Clamp risk score
        risk_score = clamp(risk_score)
        risk_level = self._classify_risk(risk_score)

        summary = (
            f"Risk assessment: {risk_level} risk level (score: {risk_score:.2f}). "
            f"Key risk factors: {', '.join(risk_factors[:3]) if risk_factors else 'none identified'}."
        )

        # Flip confidence: high confidence means risk is well-characterized
        confidence = 0.7 if risk_factors else 0.5

        self.logger.info(f"Risk analysis complete: level={risk_level}, score={risk_score:.2f}")

        return {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "confidence": confidence,
            "evidence": evidence,
            "risk_level": risk_level,
            "risk_score": round(risk_score, 2),
            "risk_factors": risk_factors,
        }

    def _classify_risk(self, score: float) -> str:
        if score < 0.2:
            return "low"
        elif score < 0.4:
            return "moderate"
        elif score < 0.6:
            return "elevated"
        elif score < 0.8:
            return "high"
        return "very_high"
