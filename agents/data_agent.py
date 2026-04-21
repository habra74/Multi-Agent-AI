import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent
from tools.data_fetcher import fetch_price_data, fetch_financial_data, fetch_news_data
from tools.indicators import compute_all_indicators
from utils.ticker_normalizer import normalize_ticker


class DataAgent(BaseAgent):
    def __init__(self):
        super().__init__("data_agent")

    def run(self, input_data: dict) -> dict:
        raw_ticker = input_data.get("ticker", "").strip()
        market     = input_data.get("market", "US")

        if not raw_ticker:
            return self._error_output("No ticker provided")

        # Normalize ticker for the given market (handles KRX codes + Korean aliases)
        ticker = normalize_ticker(raw_ticker, market)
        if ticker != raw_ticker:
            self.logger.info(f"Ticker normalized: {raw_ticker} → {ticker}")

        self.logger.info(f"Fetching data for {ticker}")

        price_df     = fetch_price_data(ticker)
        financial_data = fetch_financial_data(ticker)
        news_data    = fetch_news_data(ticker)
        indicators   = compute_all_indicators(price_df) if price_df is not None else {}

        result = {
            "ticker":         ticker,
            "raw_ticker":     raw_ticker,
            "market":         market,
            "price_data":     price_df,
            "financial_data": financial_data,
            "news_data":      news_data,
            "indicators":     indicators,
        }

        if price_df is not None:
            self.logger.info(
                f"Data collection complete: {len(price_df)} price records, "
                f"{len(news_data)} news items"
            )
        else:
            self.logger.warning(f"Price data unavailable for {ticker}")

        return result
