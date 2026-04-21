import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from tools.utils import safe_float, clamp, format_number


class FundamentalAgent(BaseAgent):
    def __init__(self):
        super().__init__("fundamental_agent")

    def run(self, input_data: dict) -> dict:
        financial = input_data.get("financial_data", {})
        ticker = input_data.get("ticker", "N/A")

        if not financial or financial.get("error"):
            return self._error_output(
                f"재무 데이터를 불러올 수 없습니다: {financial.get('error', 'unknown')}"
            )

        self.logger.info(f"Analyzing fundamentals for {ticker}")

        bull_points = []
        bear_points = []
        evidence = []
        score = 0.0
        checks = 0

        company = financial.get("company_name", ticker)
        sector = financial.get("sector", "Unknown")
        evidence.append(f"기업명: {company} | 업종: {sector}")

        # 밸류에이션
        pe = safe_float(financial.get("trailing_pe"))
        fwd_pe = safe_float(financial.get("forward_pe"))
        peg = safe_float(financial.get("peg_ratio"))
        pb = safe_float(financial.get("price_to_book"))
        ps = safe_float(financial.get("price_to_sales"))

        if pe > 0:
            checks += 1
            evidence.append(f"주가수익비율(P/E): {pe:.1f}배")
            if pe < 15:
                bull_points.append(f"밸류에이션 매력적: P/E {pe:.1f}배 (시장 평균 하회)")
                score += 1
            elif pe < 25:
                bull_points.append(f"밸류에이션 적정 수준: P/E {pe:.1f}배")
                score += 0.5
            elif pe > 40:
                bear_points.append(f"밸류에이션 부담: P/E {pe:.1f}배 (고평가 리스크)")
            else:
                bear_points.append(f"밸류에이션 다소 높음: P/E {pe:.1f}배")

        if fwd_pe > 0 and pe > 0:
            if fwd_pe < pe:
                bull_points.append(
                    f"선행 P/E({fwd_pe:.1f}배)가 후행 P/E({pe:.1f}배) 하회 — 이익 성장 기대"
                )
                score += 0.5

        if peg > 0:
            checks += 1
            evidence.append(f"PEG 비율: {peg:.2f}")
            if peg < 1.0:
                bull_points.append(f"PEG {peg:.2f} — 성장 대비 저평가 구간")
                score += 1
            elif peg < 1.5:
                bull_points.append(f"PEG {peg:.2f} — 성장 대비 합리적 가격 수준")
                score += 0.5
            else:
                bear_points.append(f"PEG {peg:.2f} — 성장 대비 다소 고평가")

        if pb > 0:
            evidence.append(f"주가순자산비율(P/B): {pb:.1f}배")
            if pb < 1.5:
                bull_points.append(f"장부가치 근처에서 거래 중 (P/B: {pb:.1f}배) — 하방 지지력 존재")
                score += 0.5

        # 수익성
        gross_margin = safe_float(financial.get("gross_margin"))
        op_margin = safe_float(financial.get("operating_margin"))
        net_margin = safe_float(financial.get("profit_margin"))
        roe = safe_float(financial.get("roe"))
        roa = safe_float(financial.get("roa"))

        if op_margin:
            checks += 1
            evidence.append(f"영업이익률: {op_margin*100:.1f}%")
            if op_margin > 0.20:
                bull_points.append(f"우수한 영업이익률: {op_margin*100:.1f}% — 높은 가격 결정력")
                score += 1
            elif op_margin > 0.10:
                bull_points.append(f"양호한 영업이익률: {op_margin*100:.1f}%")
                score += 0.5
            elif op_margin < 0:
                bear_points.append(
                    f"영업이익률 적자: {op_margin*100:.1f}% — 아직 흑자 전환 전"
                )

        if roe:
            checks += 1
            evidence.append(f"자기자본이익률(ROE): {roe*100:.1f}%")
            if roe > 0.15:
                bull_points.append(f"높은 자기자본이익률: ROE {roe*100:.1f}% — 자본 효율성 우수")
                score += 1
            elif roe > 0.08:
                bull_points.append(f"양호한 자기자본이익률: ROE {roe*100:.1f}%")
                score += 0.5
            elif roe < 0:
                bear_points.append(f"자기자본이익률 마이너스: ROE {roe*100:.1f}%")

        # 성장성
        rev_growth = safe_float(financial.get("revenue_growth"))
        earn_growth = safe_float(financial.get("earnings_growth"))

        if rev_growth:
            checks += 1
            evidence.append(f"매출 성장률: {rev_growth*100:+.1f}%")
            if rev_growth > 0.20:
                bull_points.append(f"매출 고성장: {rev_growth*100:+.1f}% — 강한 사업 확장세")
                score += 1
            elif rev_growth > 0.05:
                bull_points.append(f"매출 성장 지속: {rev_growth*100:+.1f}%")
                score += 0.5
            elif rev_growth < -0.05:
                bear_points.append(f"매출 감소 추세: {rev_growth*100:+.1f}% — 성장 둔화 우려")

        if earn_growth:
            evidence.append(f"이익 성장률: {earn_growth*100:+.1f}%")
            if earn_growth > 0.15:
                bull_points.append(f"이익 고성장: {earn_growth*100:+.1f}% — 수익성 개선 확인")
                score += 1

        # 재무 건전성
        debt_eq = safe_float(financial.get("debt_to_equity"))
        current_r = safe_float(financial.get("current_ratio"))

        if debt_eq > 0:
            checks += 1
            evidence.append(f"부채비율(D/E): {debt_eq:.2f}")
            if debt_eq < 0.5:
                bull_points.append(f"낮은 부채 부담 (D/E: {debt_eq:.2f}) — 재무 안정성 양호")
                score += 0.5
            elif debt_eq > 2.0:
                bear_points.append(
                    f"높은 레버리지 (D/E: {debt_eq:.2f}) — 금리 상승 시 재무 부담"
                )

        if current_r > 0:
            evidence.append(f"유동비율: {current_r:.2f}")
            if current_r > 2.0:
                bull_points.append(
                    f"풍부한 유동성 (유동비율: {current_r:.2f}) — 단기 채무 상환 능력 충분"
                )
                score += 0.5
            elif current_r < 1.0:
                bear_points.append(
                    f"유동성 부족 우려 (유동비율: {current_r:.2f}) — 단기 자금 조달 리스크"
                )

        # 시가총액 및 목표주가
        mktcap = financial.get("market_cap")
        if mktcap:
            evidence.append(f"시가총액: {format_number(mktcap)}")

        target = safe_float(financial.get("target_price"))
        current = safe_float(financial.get("current_price"))
        if target and current:
            upside = (target / current - 1) * 100
            evidence.append(f"애널리스트 목표주가: {target:,.2f} (상승여력: {upside:+.1f}%)")
            if upside > 15:
                bull_points.append(
                    f"애널리스트 평균 목표주가 기준 {upside:.1f}% 상승 여력 존재"
                )
                score += 0.5
            elif upside < -10:
                bear_points.append(
                    f"애널리스트 목표주가 대비 {abs(upside):.1f}% 고평가 상태"
                )

        confidence = clamp(score / max(checks, 1))
        fundamental_rating = self._rate_fundamentals(score, checks)

        summary = (
            f"{company} 펀더멘털 분석: {self._rating_ko(fundamental_rating)} 수준. "
            f"긍정 요인 {len(bull_points)}개, 우려 요인 {len(bear_points)}개."
        )

        self.logger.info(
            f"Fundamental analysis complete: rating={fundamental_rating}, confidence={confidence:.2f}"
        )

        return {
            "agent_name": self.name,
            "summary": summary,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "confidence": confidence,
            "evidence": evidence,
            "fundamental_rating": fundamental_rating,
            "key_metrics": {
                "pe_ratio": pe if pe else None,
                "forward_pe": fwd_pe if fwd_pe else None,
                "peg_ratio": peg if peg else None,
                "operating_margin_pct": round(op_margin * 100, 1) if op_margin else None,
                "roe_pct": round(roe * 100, 1) if roe else None,
                "revenue_growth_pct": round(rev_growth * 100, 1) if rev_growth else None,
                "debt_to_equity": debt_eq if debt_eq else None,
            },
        }

    def _rating_ko(self, rating: str) -> str:
        return {
            "strong":   "펀더멘털 우수",
            "moderate": "펀더멘털 보통",
            "weak":     "펀더멘털 취약",
            "poor":     "펀더멘털 불량",
        }.get(rating, rating)

    def _rate_fundamentals(self, score: float, checks: int) -> str:
        if checks == 0:
            return "insufficient data"
        ratio = score / checks
        if ratio >= 0.75:
            return "strong"
        elif ratio >= 0.5:
            return "moderate"
        elif ratio >= 0.3:
            return "weak"
        return "poor"
