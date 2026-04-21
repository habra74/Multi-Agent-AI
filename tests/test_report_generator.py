"""
Tests for report_generator.
Run: python -m pytest tests/test_report_generator.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest
from report.report_generator import generate_report, generate_json_report

SAMPLE_RESULTS = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "sector": "Technology",
    "current_price": 255.92,
    "market": "US",
    "investment_style": "neutral",
    "horizon": "mid",
    "market_analysis": {
        "agent_name": "market_agent",
        "summary": "AAPL shows sideways trend.",
        "bull_points": ["Price above 200-day MA"],
        "bear_points": ["Below 50-day MA"],
        "confidence": 0.55,
        "evidence": ["SMA200: $248.80", "RSI: 59.4"],
        "trend": "sideways",
        "indicators_snapshot": {},
    },
    "fundamental_analysis": {
        "agent_name": "fundamental_agent",
        "summary": "Strong fundamentals.",
        "bull_points": ["High ROE: 152%", "Revenue growth: 15%"],
        "bear_points": ["High leverage D/E: 102"],
        "confidence": 0.85,
        "evidence": ["P/E: 32.4", "Operating margin: 35%"],
        "fundamental_rating": "strong",
        "key_metrics": {"pe_ratio": 32.4},
    },
    "news_analysis": {
        "agent_name": "news_agent",
        "summary": "Mixed news environment.",
        "bull_points": ["[Analyst] Upgrade to Buy"],
        "bear_points": ["[Legal] Antitrust probe"],
        "confidence": 0.50,
        "evidence": [
            {
                "headline": "Apple upgraded by Goldman Sachs",
                "publisher": "Reuters",
                "date": "2024-09-01",
                "sentiment": "positive",
                "category": "analyst",
            }
        ],
        "sentiment": "mixed",
        "news_count": 8,
        "category_breakdown": {"analyst": 2, "earnings": 1},
    },
    "risk_analysis": {
        "agent_name": "risk_agent",
        "summary": "Moderate risk.",
        "bull_points": ["Low beta: 1.1"],
        "bear_points": ["High leverage"],
        "confidence": 0.65,
        "evidence": ["Beta: 1.11"],
        "risk_level": "moderate",
        "risk_score": 0.34,
        "risk_factors": ["High leverage"],
    },
    "decision": {
        "agent_name": "decision_agent",
        "summary": "AAPL: HOLD",
        "bull_points": ["[Fundamental] Strong ROE"],
        "bear_points": ["[Market] Sideways trend"],
        "confidence": 0.62,
        "evidence": ["Composite score: +0.18"],
        "final_decision": "HOLD",
        "reasoning": "Neutral mid-term investor: strong fundamentals offset by weak near-term catalyst.",
        "action_items": ["Watch for breakout above 50-day MA", "Monitor earnings"],
        "conflict_detected": False,
    },
}


class TestMarkdownReport:
    def test_report_is_non_empty(self):
        report = generate_report(SAMPLE_RESULTS)
        assert len(report) > 500

    def test_ticker_present(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "AAPL" in report

    def test_verdict_present(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "HOLD" in report

    def test_executive_summary_section(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "EXECUTIVE SUMMARY" in report

    def test_bull_bear_case_section(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "BULL CASE" in report
        assert "BEAR CASE" in report

    def test_what_to_watch_section(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "WHAT TO WATCH" in report

    def test_news_headlines_rendered(self):
        """Structured evidence dicts should render as real headlines."""
        report = generate_report(SAMPLE_RESULTS)
        assert "Apple upgraded by Goldman Sachs" in report

    def test_price_present(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "255.92" in report

    def test_reasoning_present(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "strong fundamentals" in report

    def test_action_items_present(self):
        report = generate_report(SAMPLE_RESULTS)
        assert "Watch for breakout" in report

    def test_no_verdict_icons_cause_encoding_error(self):
        """Report must be convertible to UTF-8 without error."""
        report = generate_report(SAMPLE_RESULTS)
        report.encode("utf-8")  # should not raise

    def test_empty_news_evidence_handled(self):
        """Missing/empty evidence list must not crash."""
        results = {**SAMPLE_RESULTS}
        results["news_analysis"] = {
            **results["news_analysis"],
            "evidence": [],
        }
        report = generate_report(results)
        assert "AAPL" in report


class TestJsonReport:
    def test_json_report_serialisable(self):
        json_data = generate_json_report(SAMPLE_RESULTS)
        dumped = json.dumps(json_data)
        assert len(dumped) > 100

    def test_json_has_required_top_keys(self):
        json_data = generate_json_report(SAMPLE_RESULTS)
        for key in ("ticker", "company_name", "decision", "market_analysis",
                    "fundamental_analysis", "news_analysis", "risk_analysis"):
            assert key in json_data, f"Missing key: {key}"

    def test_json_verdict_correct(self):
        json_data = generate_json_report(SAMPLE_RESULTS)
        assert json_data["decision"]["final_decision"] == "HOLD"

    def test_json_no_dataframe(self):
        """JSON output must not contain any pandas DataFrame objects."""
        json_data = generate_json_report(SAMPLE_RESULTS)
        serialised = json.dumps(json_data)
        assert "DataFrame" not in serialised or "<DataFrame" in serialised
