import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from tools.utils import safe_float, clamp
from config import SHORT_MA, MID_MA, LONG_MA


class MarketAgent(BaseAgent):
    def __init__(self):
        super().__init__("market_agent")

    def run(self, input_data: dict) -> dict:
        indicators = input_data.get("indicators", {})
        financial = input_data.get("financial_data", {})
        ticker = input_data.get("ticker", "N/A")

        if not indicators:
            return self._error_output("가격 지표 데이터를 불러올 수 없습니다.")

        self.logger.info(f"Analyzing market data for {ticker}")

        bull_points = []
        bear_points = []
        evidence = []
        score = 0.0
        checks = 0

        # 이동평균선 추세 분석
        price = safe_float(indicators.get("current_price"))
        sma20 = safe_float(indicators.get(f"sma_{SHORT_MA}"))
        sma50 = safe_float(indicators.get(f"sma_{MID_MA}"))
        sma200 = safe_float(indicators.get(f"sma_{LONG_MA}"))

        if price and sma200:
            checks += 1
            if price > sma200:
                bull_points.append(
                    f"현재가({price:,.2f})가 200일 이동평균({sma200:,.2f}) 상회 — 장기 상승 추세"
                )
                score += 1
            else:
                bear_points.append(
                    f"현재가({price:,.2f})가 200일 이동평균({sma200:,.2f}) 하회 — 장기 하락 추세"
                )
            evidence.append(f"200일 이동평균: {sma200:,.2f}")

        if price and sma50:
            checks += 1
            if price > sma50:
                bull_points.append(f"현재가가 50일 이동평균({sma50:,.2f}) 상회 — 중기 상승 추세")
                score += 1
            else:
                bear_points.append(f"현재가가 50일 이동평균({sma50:,.2f}) 하회 — 중기 하락 추세")

        if sma20 and sma50:
            checks += 1
            if sma20 > sma50:
                bull_points.append("골든크로스: 20일 이동평균이 50일 이동평균 상향 돌파")
                score += 1
            else:
                bear_points.append("데드크로스: 20일 이동평균이 50일 이동평균 하향 이탈")

        # 모멘텀 분석
        ret_21 = indicators.get("return_21d")
        ret_63 = indicators.get("return_63d")
        ret_252 = indicators.get("return_252d")

        if ret_21 is not None:
            checks += 1
            r = safe_float(ret_21)
            evidence.append(f"1개월 수익률: {r:+.1f}%")
            if r > 5:
                bull_points.append(f"1개월 수익률 강세: {r:+.1f}% — 단기 모멘텀 양호")
                score += 1
            elif r < -5:
                bear_points.append(f"1개월 수익률 부진: {r:+.1f}% — 단기 하락 압력 존재")

        if ret_252 is not None:
            checks += 1
            r = safe_float(ret_252)
            evidence.append(f"12개월 수익률: {r:+.1f}%")
            if r > 10:
                bull_points.append(f"12개월 수익률 강세: {r:+.1f}% — 장기 상승 모멘텀 확인")
                score += 1
            elif r < -20:
                bear_points.append(f"12개월 수익률 부진: {r:+.1f}% — 장기 투자자 심리 위축")

        # RSI 분석
        rsi = indicators.get("rsi")
        if rsi:
            checks += 1
            rsi = safe_float(rsi)
            evidence.append(f"RSI: {rsi:.1f}")
            if 40 <= rsi <= 60:
                bull_points.append(f"RSI 중립 구간({rsi:.1f}) — 과매수·과매도 부담 없음")
                score += 0.5
            elif rsi > 70:
                bear_points.append(f"RSI 과매수 구간({rsi:.1f}) — 단기 조정 가능성 존재")
            elif rsi < 30:
                bull_points.append(f"RSI 과매도 구간({rsi:.1f}) — 기술적 반등 기회 고려 가능")
                score += 0.5

        # 52주 가격 위치
        pos = indicators.get("position_in_range")
        high_52w = indicators.get("high_52w")
        low_52w = indicators.get("low_52w")
        if pos is not None:
            evidence.append(
                f"52주 범위: {low_52w:,.2f} — {high_52w:,.2f} (현재 위치: {pos:.0f}%)"
            )

        # 변동성
        vol = indicators.get("annualized_volatility_pct")
        vol_class = indicators.get("vol_classification", "unknown")
        if vol:
            evidence.append(f"연간 변동성: {vol:.1f}% ({vol_class})")
            if vol_class in ("high", "very_high"):
                bear_points.append(
                    f"변동성이 높은 편({vol:.1f}%)이어서 단기 가격 변동 리스크가 존재합니다."
                )
            elif vol_class == "low":
                bull_points.append(
                    f"변동성이 낮은 편({vol:.1f}%)이어서 안정적인 가격 흐름을 보이고 있습니다."
                )

        # 거래량 추세
        vol_trend = indicators.get("volume_trend")
        vol_ratio = indicators.get("volume_ratio")
        if vol_trend and vol_ratio:
            evidence.append(
                f"거래량 추세: {vol_trend} (60일 평균 대비 {vol_ratio:.2f}배)"
            )
            if vol_trend == "increasing" and ret_21 and safe_float(ret_21) > 0:
                bull_points.append("거래량 증가를 동반한 상승 — 상승 추세의 신뢰도 높음")
                score += 0.5

        # 신뢰도 계산
        confidence = clamp(score / max(checks, 1))
        trend = self._determine_trend(indicators)

        summary = (
            f"{ticker} 시장 분석: {self._trend_ko(trend)} 추세 확인. "
            f"긍정 신호 {len(bull_points)}개, 부정 신호 {len(bear_points)}개."
        )

        self.logger.info(f"Market analysis complete: trend={trend}, confidence={confidence:.2f}")

        return {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "confidence": confidence,
            "evidence": evidence,
            "trend": trend,
            "indicators_snapshot": {
                "price": price,
                "sma20": sma20,
                "sma50": sma50,
                "sma200": sma200,
                "rsi": rsi if rsi else None,
                "volatility_pct": vol,
                "vol_classification": vol_class,
            },
        }

    def _trend_ko(self, trend: str) -> str:
        return {
            "strong_uptrend":   "강한 상승",
            "uptrend":          "상승",
            "sideways":         "횡보",
            "downtrend":        "하락",
            "strong_downtrend": "강한 하락",
        }.get(trend, "불명확")

    def _determine_trend(self, indicators: dict) -> str:
        price = safe_float(indicators.get("current_price"))
        sma50 = safe_float(indicators.get(f"sma_{MID_MA}"))
        sma200 = safe_float(indicators.get(f"sma_{LONG_MA}"))
        ret_63 = safe_float(indicators.get("return_63d", 0))

        if not price:
            return "unknown"

        above_50 = price > sma50 if sma50 else False
        above_200 = price > sma200 if sma200 else False

        if above_50 and above_200 and ret_63 > 5:
            return "strong_uptrend"
        elif above_50 and above_200:
            return "uptrend"
        elif not above_50 and not above_200 and ret_63 < -5:
            return "strong_downtrend"
        elif not above_200:
            return "downtrend"
        return "sideways"
