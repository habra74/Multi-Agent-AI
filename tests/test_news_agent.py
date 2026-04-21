"""
Tests for NewsAgent.
Run: python -m pytest tests/test_news_agent.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from agents.news_agent import NewsAgent

REQUIRED_KEYS = {
    "agent_name", "summary", "bull_points", "bear_points",
    "confidence", "evidence", "sentiment", "news_count",
}

SAMPLE_NEWS = [
    {
        "title": "Apple beats Q3 earnings expectations",
        "publisher": "Reuters",
        "published": "2024-08-01",
        "link": "https://reuters.com/1",
        "summary": "",
    },
    {
        "title": "Apple faces antitrust investigation in EU",
        "publisher": "Bloomberg",
        "published": "2024-07-30",
        "link": "https://bloomberg.com/1",
        "summary": "",
    },
    {
        "title": "Analyst upgrades Apple to Buy, raises target to $250",
        "publisher": "Goldman Sachs",
        "published": "2024-07-28",
        "link": "https://gs.com/1",
        "summary": "",
    },
]


class TestNewsAgentSchema:
    def setup_method(self):
        self.agent = NewsAgent()

    def test_output_has_required_keys_with_news(self):
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": SAMPLE_NEWS,
            "financial_data": {"company_name": "Apple Inc."},
        })
        missing = REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_output_has_required_keys_empty_news(self):
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": [],
            "financial_data": {},
        })
        missing = REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_sentiment_is_valid(self):
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": SAMPLE_NEWS,
            "financial_data": {},
        })
        assert result["sentiment"] in ("positive", "negative", "neutral", "mixed")

    def test_confidence_in_range(self):
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": SAMPLE_NEWS,
            "financial_data": {},
        })
        assert 0.0 <= result["confidence"] <= 1.0

    def test_news_count_matches(self):
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": SAMPLE_NEWS,
            "financial_data": {},
        })
        assert result["news_count"] == len(SAMPLE_NEWS)

    def test_empty_news_safe(self):
        """Empty news list must not crash and must return usable output."""
        result = self.agent.run({"ticker": "AAPL", "news_data": [], "financial_data": {}})
        assert result["news_count"] == 0
        assert isinstance(result["bull_points"], list)
        assert isinstance(result["bear_points"], list)

    def test_items_with_no_title_filtered(self):
        """News items with empty titles should be filtered before analysis."""
        news_with_empties = [
            {"title": "", "publisher": "Reuters", "published": "2024-01-01"},
            {"title": "   ", "publisher": "Bloomberg", "published": "2024-01-02"},
            *SAMPLE_NEWS,
        ]
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": news_with_empties,
            "financial_data": {},
        })
        # Should process SAMPLE_NEWS only
        assert result["news_count"] == len(SAMPLE_NEWS)

    def test_evidence_is_structured(self):
        """Evidence items should be dicts with headline key."""
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": SAMPLE_NEWS,
            "financial_data": {},
        })
        assert isinstance(result["evidence"], list)
        for ev in result["evidence"]:
            assert isinstance(ev, dict)
            assert "headline" in ev, f"Missing 'headline' in evidence item: {ev}"

    def test_positive_keywords_trigger_bull(self):
        pos_news = [
            {
                "title": "Apple beats earnings and raises guidance",
                "publisher": "Reuters",
                "published": "2024-01-01",
                "link": "",
                "summary": "",
            }
        ]
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": pos_news,
            "financial_data": {},
        })
        assert result["sentiment"] in ("positive", "neutral")

    def test_negative_keywords_trigger_bear(self):
        neg_news = [
            {
                "title": "Apple hit with major antitrust lawsuit and faces massive fine",
                "publisher": "Reuters",
                "published": "2024-01-01",
                "link": "",
                "summary": "",
            }
        ]
        result = self.agent.run({
            "ticker": "AAPL",
            "news_data": neg_news,
            "financial_data": {},
        })
        assert result["sentiment"] in ("negative", "neutral")
