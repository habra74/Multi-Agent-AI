"""
coordinator.py
--------------
Orchestrates the full multi-agent pipeline and saves a structured run log.

Execution order:
  DataAgent → [MarketAgent, FundamentalAgent, NewsAgent] → RiskAgent → DecisionAgent

Log saved to: logs/run_<TICKER>_<YYYYMMDD_HHMMSS>.json
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.data_agent import DataAgent
from agents.market_agent import MarketAgent
from agents.fundamental_agent import FundamentalAgent
from agents.news_agent import NewsAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from config import LOG_DIR
from models.llm import LLMClient

logger = logging.getLogger("coordinator")


# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------

def _serialise(obj: Any) -> Any:
    """Recursively convert non-JSON-serialisable objects to strings."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialise(v) for v in obj]
    # pandas DataFrame / Series
    try:
        import pandas as pd
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            return f"<DataFrame rows={len(obj)}>"
    except ImportError:
        pass
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class Coordinator:
    """Run the full investment analysis pipeline for a single ticker."""

    def __init__(self):
        self.data_agent        = DataAgent()
        self.market_agent      = MarketAgent()
        self.fundamental_agent = FundamentalAgent()
        self.news_agent        = NewsAgent()
        self.risk_agent        = RiskAgent()
        self.decision_agent    = DecisionAgent()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        ticker: str,
        market: str = "US",
        investment_style: str = "neutral",
        horizon: str = "mid",
        language: str = "ko",
    ) -> dict:
        """
        Run the full pipeline and return a results dict.

        Parameters
        ----------
        ticker           : raw ticker input (will be normalised by DataAgent)
        market           : "US" or "KR"
        investment_style : conservative / neutral / aggressive
        horizon          : short / mid / long
        language         : "ko" (Korean, default) or "en" (English)
        """
        ticker = ticker.strip()
        run_start = datetime.now()

        logger.info(
            f"Starting analysis: ticker={ticker} | market={market} | "
            f"style={investment_style} | horizon={horizon} | lang={language} | "
            f"llm={'yes' if LLMClient().available else 'no (rule-based)'}"
        )

        run_log: dict = {
            "run_id":           run_start.strftime("%Y%m%d_%H%M%S"),
            "ticker":           ticker,
            "market":           market,
            "investment_style": investment_style,
            "horizon":          horizon,
            "language":         language,
            "llm_mode":         LLMClient().available,
            "steps":            {},
            "errors":           [],
        }

        # ---- Step 1: Data collection ----
        print(f"\n[1/6] 데이터 수집 중: {ticker}..." if language == "ko"
              else f"\n[1/6] Fetching data for {ticker}...")
        raw_data = self._run_step(
            "data_agent", self.data_agent,
            {"ticker": ticker, "market": market},
            run_log,
        )

        # Use the normalised ticker from DataAgent for all subsequent steps
        normalised_ticker = raw_data.get("ticker", ticker)

        if raw_data.get("price_data") is None:
            logger.warning(f"Price data unavailable for {normalised_ticker}")
            run_log["errors"].append("Price data unavailable")

        fin_err = raw_data.get("financial_data", {}).get("error")
        if fin_err:
            logger.error(f"Financial data error: {fin_err}")
            run_log["errors"].append(f"Financial data: {fin_err}")

        # ---- Step 2: Market analysis ----
        print("[2/6] 시장 추세 분석 중..." if language == "ko"
              else "[2/6] Analyzing market trends...")
        market_result = self._run_step("market_agent", self.market_agent, raw_data, run_log)

        # ---- Step 3: Fundamental analysis ----
        print("[3/6] 펀더멘털 분석 중..." if language == "ko"
              else "[3/6] Analyzing fundamentals...")
        fundamental_result = self._run_step(
            "fundamental_agent", self.fundamental_agent, raw_data, run_log
        )

        # ---- Step 4: News & sentiment ----
        print("[4/6] 뉴스 및 심리 분석 중..." if language == "ko"
              else "[4/6] Analyzing news & sentiment...")
        news_result = self._run_step("news_agent", self.news_agent, raw_data, run_log)

        # ---- Step 5: Risk assessment ----
        print("[5/6] 리스크 평가 중..." if language == "ko"
              else "[5/6] Assessing risk...")
        risk_result = self._run_step(
            "risk_agent",
            self.risk_agent,
            {
                "market":      market_result,
                "fundamental": fundamental_result,
                "news":        news_result,
                "raw_data":    raw_data,
                "ticker":      normalised_ticker,
            },
            run_log,
        )

        # ---- Step 6: Final decision ----
        print("[6/6] 최종 투자 의견 생성 중..." if language == "ko"
              else "[6/6] Generating investment decision...")
        decision_result = self._run_step(
            "decision_agent",
            self.decision_agent,
            {
                "market":           market_result,
                "fundamental":      fundamental_result,
                "news":             news_result,
                "risk":             risk_result,
                "ticker":           normalised_ticker,
                "investment_style": investment_style,
                "horizon":          horizon,
                "financial_data":   raw_data.get("financial_data", {}),
            },
            run_log,
        )

        # ---- Assemble final results ----
        results = {
            "ticker":               normalised_ticker,
            "raw_ticker":           ticker,
            "market":               market,
            "investment_style":     investment_style,
            "horizon":              horizon,
            "language":             language,
            "company_name":         raw_data.get("financial_data", {}).get("company_name", normalised_ticker),
            "sector":               raw_data.get("financial_data", {}).get("sector", "Unknown"),
            "current_price":        raw_data.get("financial_data", {}).get("current_price"),
            "market_analysis":      market_result,
            "fundamental_analysis": fundamental_result,
            "news_analysis":        news_result,
            "risk_analysis":        risk_result,
            "decision":             decision_result,
        }

        # ---- Finalise run log ----
        run_log["duration_seconds"] = round((datetime.now() - run_start).total_seconds(), 1)
        run_log["final_verdict"]    = decision_result.get("final_decision", "N/A")
        run_log["final_confidence"] = decision_result.get("confidence", 0)
        self._save_run_log(run_log, normalised_ticker)

        logger.info(
            f"Analysis complete: {normalised_ticker} -> "
            f"{decision_result.get('final_decision', 'N/A')} "
            f"(confidence: {decision_result.get('confidence', 0):.0%}) "
            f"[{run_log['duration_seconds']}s]"
        )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_step(self, name: str, agent, input_data: dict, run_log: dict) -> dict:
        """Execute one agent, capture its output in the run log."""
        try:
            output = agent.run(input_data)
            snapshot = {k: v for k, v in output.items() if k not in ("price_data",)}
            run_log["steps"][name] = _serialise(snapshot)
            return output
        except Exception as exc:
            logger.exception(f"{name} raised an exception: {exc}")
            run_log["errors"].append(f"{name}: {exc}")
            run_log["steps"][name] = {"error": str(exc)}
            return {"agent_name": name, "error": str(exc), "summary": f"{name} failed"}

    def _save_run_log(self, run_log: dict, ticker: str) -> None:
        """Write full agent output log to logs/run_<TICKER>_<TIMESTAMP>.json."""
        try:
            log_path = Path(LOG_DIR) / f"run_{ticker}_{run_log['run_id']}.json"
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(_serialise(run_log), f, indent=2, ensure_ascii=False)
            logger.info(f"Run log saved: {log_path}")
        except Exception as e:
            logger.warning(f"Could not save run log: {e}")
