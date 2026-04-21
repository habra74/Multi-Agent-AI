"""
Tests for DecisionAgent.
Run: python -m pytest tests/test_decision_agent.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from agents.decision_agent import DecisionAgent, VALID_VERDICTS

REQUIRED_KEYS = {
    "agent_name", "summary", "bull_points", "bear_points",
    "confidence", "evidence", "final_decision", "reasoning", "action_items",
}

# Minimal agent input stubs
BULLISH_INPUT = {
    "ticker": "AAPL",
    "investment_style": "neutral",
    "horizon": "mid",
    "financial_data": {"company_name": "Apple Inc.", "current_price": 250.0},
    "market": {
        "trend": "strong_uptrend",
        "confidence": 0.80,
        "bull_points": ["Price above all MAs"],
        "bear_points": [],
    },
    "fundamental": {
        "fundamental_rating": "strong",
        "confidence": 0.85,
        "bull_points": ["High ROE", "Revenue growth 15%"],
        "bear_points": [],
        "key_metrics": {},
    },
    "news": {
        "sentiment": "positive",
        "confidence": 0.70,
        "bull_points": ["Earnings beat"],
        "bear_points": [],
        "category_breakdown": {"earnings": 2},
    },
    "risk": {
        "risk_level": "low",
        "risk_score": 0.15,
        "risk_factors": [],
        "bull_points": ["Low beta"],
    },
}

BEARISH_INPUT = {
    "ticker": "TSLA",
    "investment_style": "conservative",
    "horizon": "short",
    "financial_data": {"company_name": "Tesla Inc.", "current_price": 200.0},
    "market": {
        "trend": "strong_downtrend",
        "confidence": 0.75,
        "bull_points": [],
        "bear_points": ["Below all MAs"],
    },
    "fundamental": {
        "fundamental_rating": "weak",
        "confidence": 0.60,
        "bull_points": [],
        "bear_points": ["Shrinking margins"],
        "key_metrics": {},
    },
    "news": {
        "sentiment": "negative",
        "confidence": 0.65,
        "bull_points": [],
        "bear_points": ["CEO controversy", "Recall issued"],
        "category_breakdown": {"legal": 1},
    },
    "risk": {
        "risk_level": "high",
        "risk_score": 0.72,
        "risk_factors": ["High volatility", "Regulatory risk"],
        "bull_points": [],
    },
}


class TestDecisionAgentSchema:
    def setup_method(self):
        self.agent = DecisionAgent()

    def test_required_keys_bullish(self):
        result = self.agent.run(BULLISH_INPUT)
        missing = REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_required_keys_bearish(self):
        result = self.agent.run(BEARISH_INPUT)
        missing = REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_verdict_is_valid(self):
        for inp in (BULLISH_INPUT, BEARISH_INPUT):
            result = self.agent.run(inp)
            assert result["final_decision"] in VALID_VERDICTS, \
                f"Invalid verdict: {result['final_decision']}"

    def test_confidence_in_range(self):
        for inp in (BULLISH_INPUT, BEARISH_INPUT):
            result = self.agent.run(inp)
            assert 0.0 <= result["confidence"] <= 1.0

    def test_bullish_tends_toward_buy(self):
        result = self.agent.run(BULLISH_INPUT)
        assert result["final_decision"] in ("STRONG BUY", "BUY", "HOLD"), \
            f"Expected positive verdict, got {result['final_decision']}"

    def test_bearish_tends_toward_avoid(self):
        result = self.agent.run(BEARISH_INPUT)
        assert result["final_decision"] in ("AVOID", "CAUTIOUS HOLD", "HOLD"), \
            f"Expected negative verdict, got {result['final_decision']}"

    def test_action_items_is_list(self):
        result = self.agent.run(BULLISH_INPUT)
        assert isinstance(result["action_items"], list)

    def test_reasoning_non_empty(self):
        for inp in (BULLISH_INPUT, BEARISH_INPUT):
            result = self.agent.run(inp)
            assert result["reasoning"].strip() != ""

    def test_conservative_style_penalises_high_risk(self):
        """Conservative investor should be more likely to get CAUTIOUS HOLD/AVOID on risky stock."""
        conservative = {**BEARISH_INPUT, "investment_style": "conservative"}
        aggressive   = {**BEARISH_INPUT, "investment_style": "aggressive"}
        r_con = self.agent.run(conservative)
        r_agg = self.agent.run(aggressive)
        VERDICTS_ORDERED = ["STRONG BUY", "BUY", "HOLD", "CAUTIOUS HOLD", "AVOID"]
        c_idx = VERDICTS_ORDERED.index(r_con["final_decision"])
        a_idx = VERDICTS_ORDERED.index(r_agg["final_decision"])
        # Conservative should be >= aggressive (same or more cautious)
        assert c_idx >= a_idx, (
            f"Conservative ({r_con['final_decision']}) should not be more bullish "
            f"than Aggressive ({r_agg['final_decision']})"
        )

    def test_conflict_detected_field_present(self):
        result = self.agent.run(BULLISH_INPUT)
        assert "conflict_detected" in result
        assert isinstance(result["conflict_detected"], bool)
