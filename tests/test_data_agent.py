"""
Tests for DataAgent and data_fetcher utilities.
Run: python -m pytest tests/test_data_agent.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from tools.data_fetcher import _parse_news_item


# ---------------------------------------------------------------------------
# _parse_news_item: dual-format parsing
# ---------------------------------------------------------------------------

class TestParseNewsItem:
    def test_old_format_flat(self):
        """Legacy yfinance flat format is parsed correctly."""
        item = {
            "title": "Apple reports record earnings",
            "publisher": "Reuters",
            "link": "https://example.com",
            "providerPublishTime": 1700000000,
        }
        result = _parse_news_item(item)
        assert result is not None
        assert result["title"] == "Apple reports record earnings"
        assert result["publisher"] == "Reuters"
        assert result["published"] != ""
        assert result["link"] == "https://example.com"

    def test_new_format_content_object(self):
        """New yfinance nested content format is parsed correctly."""
        item = {
            "id": "abc123",
            "content": {
                "title": "Apple unveils new iPhone",
                "pubDate": "2024-09-15T10:00:00.000Z",
                "provider": {"displayName": "Bloomberg"},
                "canonicalUrl": {"url": "https://bloomberg.com/abc"},
                "summary": "Apple's latest flagship device...",
            }
        }
        result = _parse_news_item(item)
        assert result is not None
        assert result["title"] == "Apple unveils new iPhone"
        assert result["publisher"] == "Bloomberg"
        assert result["published"] == "2024-09-15"
        assert "bloomberg.com" in result["link"]

    def test_empty_item_returns_none(self):
        assert _parse_news_item({}) is None

    def test_none_item_returns_none(self):
        assert _parse_news_item(None) is None

    def test_missing_title_returns_none(self):
        item = {"publisher": "Reuters", "providerPublishTime": 1700000000}
        assert _parse_news_item(item) is None

    def test_whitespace_only_title_returns_none(self):
        item = {"title": "   ", "publisher": "Reuters"}
        assert _parse_news_item(item) is None

    def test_new_format_missing_provider(self):
        """Missing provider field should not crash."""
        item = {
            "content": {
                "title": "Market update",
                "pubDate": "2024-01-01T00:00:00Z",
            }
        }
        result = _parse_news_item(item)
        assert result is not None
        assert result["title"] == "Market update"
        assert result["publisher"] == ""


# ---------------------------------------------------------------------------
# DataAgent required fields
# ---------------------------------------------------------------------------

class TestDataAgent:
    def test_required_output_fields(self):
        """DataAgent output must always contain required keys."""
        from agents.data_agent import DataAgent
        agent = DataAgent()
        result = agent.run({"ticker": "AAPL"})
        required = {"ticker", "financial_data", "news_data", "indicators"}
        assert required.issubset(result.keys()), f"Missing: {required - result.keys()}"

    def test_ticker_normalised(self):
        from agents.data_agent import DataAgent
        agent = DataAgent()
        result = agent.run({"ticker": "aapl"})
        assert result["ticker"] == "AAPL"

    def test_empty_ticker_returns_error(self):
        from agents.data_agent import DataAgent
        agent = DataAgent()
        result = agent.run({"ticker": ""})
        assert "summary" in result
        assert "error" in result["summary"].lower() or result.get("financial_data", {}) == {}

    def test_news_data_is_list(self):
        from agents.data_agent import DataAgent
        agent = DataAgent()
        result = agent.run({"ticker": "AAPL"})
        assert isinstance(result["news_data"], list)

    def test_news_items_have_title(self):
        """Every returned news item must have a non-empty title."""
        from agents.data_agent import DataAgent
        agent = DataAgent()
        result = agent.run({"ticker": "AAPL"})
        for item in result["news_data"]:
            assert item.get("title", "").strip() != "", f"Empty title in: {item}"
