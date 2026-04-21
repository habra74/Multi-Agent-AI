"""
data_fetcher.py
---------------
Fetches price data, financial fundamentals, and news from yfinance.
Handles both the legacy (pre-0.2.x) and new (0.2.x+) yfinance news formats.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
from config import PRICE_HISTORY_DAYS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Price data
# ---------------------------------------------------------------------------

def fetch_price_data(ticker: str, days: int = PRICE_HISTORY_DAYS) -> Optional[pd.DataFrame]:
    """Download OHLCV price history via yfinance. Returns None on failure."""
    try:
        import yfinance as yf
        end = datetime.today()
        start = end - timedelta(days=days)
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            logger.warning(f"No price data found for {ticker}")
            return None
        # Flatten multi-level columns (multi-ticker download)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        logger.info(f"Fetched {len(df)} trading days of price data for {ticker}")
        return df
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None
    except Exception as e:
        logger.error(f"Price data fetch failed for {ticker}: {e}")
        return None


# ---------------------------------------------------------------------------
# Financial fundamentals
# ---------------------------------------------------------------------------

def fetch_financial_data(ticker: str) -> Dict[str, Any]:
    """Fetch company fundamentals from yfinance Ticker.info."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        data = {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "forward_pe": info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "free_cashflow": info.get("freeCashflow"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "target_price": info.get("targetMeanPrice"),
            "analyst_rating": info.get("recommendationMean"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "short_ratio": info.get("shortRatio"),
            "description": (info.get("longBusinessSummary") or "")[:500],
        }
        logger.info(f"Fetched financial data for {ticker}: {data['company_name']}")
        return data
    except ImportError:
        logger.error("yfinance not installed.")
        return {"ticker": ticker, "error": "yfinance not installed"}
    except Exception as e:
        logger.error(f"Financial data fetch failed for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def _parse_news_item(item: dict) -> Optional[Dict[str, str]]:
    """
    Parse a single yfinance news item, handling both old and new API formats.

    Old format (yfinance < 0.2.x):
        {"title": "...", "publisher": "...", "providerPublishTime": 1234567890, ...}

    New format (yfinance >= 0.2.x):
        {"id": "...", "content": {"title": "...", "pubDate": "2024-01-01T...",
          "provider": {"displayName": "..."}, "summary": "..."}, ...}
    """
    if not item or not isinstance(item, dict):
        return None

    title = ""
    publisher = ""
    published = ""
    link = ""
    summary = ""

    # ---- New format: content object ----
    content = item.get("content")
    if isinstance(content, dict):
        title = content.get("title", "")
        summary = content.get("summary", "") or content.get("description", "")

        # Date: ISO 8601 string e.g. "2024-01-15T12:30:00.000Z"
        pub_date = content.get("pubDate", "") or content.get("publishedAt", "")
        if pub_date:
            try:
                published = pub_date[:10]  # take "YYYY-MM-DD" portion
            except Exception:
                published = ""

        # Publisher
        provider = content.get("provider", {})
        if isinstance(provider, dict):
            publisher = provider.get("displayName", "") or provider.get("name", "")

        # Link
        canonical = content.get("canonicalUrl", {})
        if isinstance(canonical, dict):
            link = canonical.get("url", "")
        if not link:
            link = content.get("url", "")

    # ---- Old format: flat keys ----
    if not title:
        title = item.get("title", "")
    if not publisher:
        publisher = item.get("publisher", "")
    if not published:
        ts = item.get("providerPublishTime")
        if ts:
            try:
                published = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
            except Exception:
                published = ""
    if not link:
        link = item.get("link", "")
    if not summary:
        summary = item.get("summary", "")

    # Drop items with no title at all
    if not title.strip():
        logger.debug(f"Skipping news item with no title. Keys: {list(item.keys())}")
        return None

    return {
        "title": title.strip(),
        "publisher": publisher.strip(),
        "published": published,
        "link": link,
        "summary": summary.strip()[:300],
    }


def fetch_news_data(ticker: str, max_news: int = 15) -> List[Dict[str, str]]:
    """
    Fetch recent news for a ticker.

    Returns a list of dicts with keys:
        title, publisher, published, link, summary
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        raw_news = stock.news or []

        result = []
        skipped = 0
        for item in raw_news:
            parsed = _parse_news_item(item)
            if parsed:
                result.append(parsed)
                if len(result) >= max_news:
                    break
            else:
                skipped += 1

        if skipped:
            logger.debug(f"Skipped {skipped} unparseable news items for {ticker}")

        logger.info(f"Fetched {len(result)} news items for {ticker} "
                    f"(raw: {len(raw_news)}, skipped: {skipped})")
        return result

    except ImportError:
        logger.error("yfinance not installed.")
        return []
    except Exception as e:
        logger.error(f"News fetch failed for {ticker}: {e}")
        return []
