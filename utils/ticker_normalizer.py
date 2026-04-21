"""
ticker_normalizer.py
--------------------
Normalizes ticker symbols for US and KR (KRX) markets.

Rules (KR market):
  - Korean company name alias  → mapped ticker code (e.g. 삼성전자 → 005930.KS)
  - Pure digits (6-char code)  → append .KS  (e.g. 005930 → 005930.KS)
  - Already has .KS / .KQ      → return as-is (uppercase)

Rules (US market):
  - Uppercase, strip whitespace  (e.g. aapl → AAPL)
  - Korean alias mapped first    (e.g. 삼성전자 → 005930.KS  even if market=US)
"""

# ---------------------------------------------------------------------------
# Korean company name → normalized yfinance ticker
# ---------------------------------------------------------------------------
KR_ALIAS: dict[str, str] = {
    "삼성전자":  "005930.KS",
    "삼성":      "005930.KS",
    "SK하이닉스": "000660.KS",
    "하이닉스":   "000660.KS",
    "NAVER":     "035420.KS",
    "네이버":    "035420.KS",
    "카카오":    "035720.KS",
    "LG에너지솔루션": "373220.KS",
    "현대차":    "005380.KS",
    "현대자동차": "005380.KS",
    "POSCO홀딩스": "005490.KS",
    "셀트리온":   "068270.KS",
    "KB금융":    "105560.KS",
    "신한지주":  "055550.KS",
    "삼성SDI":   "006400.KS",
    "LG화학":    "051910.KS",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_ticker(ticker: str, market: str = "US") -> str:
    """
    Return the normalized yfinance ticker string.

    Parameters
    ----------
    ticker : str
        Raw user input (e.g. "005930", "삼성전자", "AAPL", "005930.KS").
    market : str
        "US" or "KR".  When market="KR", pure 6-digit codes get .KS appended.

    Returns
    -------
    str
        Normalized ticker ready for yfinance (e.g. "005930.KS", "AAPL").
    """
    if not ticker or not isinstance(ticker, str):
        return ticker

    ticker = ticker.strip()

    # 1. Korean alias check (works regardless of market)
    if ticker in KR_ALIAS:
        return KR_ALIAS[ticker]

    # 2. Already has a recognised exchange suffix
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ") or upper.endswith(".KO"):
        return upper

    # 3. KR market: pure digit codes → append .KS
    if market.upper() == "KR":
        if ticker.isdigit():
            return f"{ticker}.KS"
        # If letters mixed (e.g. user typed in uppercase already) → pass through
        return upper

    # 4. US (default): just uppercase
    return upper


def get_display_name(ticker: str) -> str:
    """Return a human-readable display name for well-known tickers."""
    _DISPLAY: dict[str, str] = {
        "005930.KS": "삼성전자",
        "000660.KS": "SK하이닉스",
        "035420.KS": "NAVER",
        "035720.KS": "카카오",
        "373220.KS": "LG에너지솔루션",
        "005380.KS": "현대차",
        "005490.KS": "POSCO홀딩스",
        "068270.KS": "셀트리온",
        "105560.KS": "KB금융",
        "055550.KS": "신한지주",
        "006400.KS": "삼성SDI",
        "051910.KS": "LG화학",
        "AAPL":  "Apple Inc.",
        "NVDA":  "NVIDIA",
        "MSFT":  "Microsoft",
        "TSLA":  "Tesla",
        "GOOG":  "Alphabet",
        "AMZN":  "Amazon",
        "META":  "Meta",
    }
    return _DISPLAY.get(ticker.upper(), ticker)


def infer_market(ticker: str) -> str:
    """Infer market from ticker suffix. Returns 'KR' or 'US'."""
    t = ticker.strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ") or t.endswith(".KO"):
        return "KR"
    # Check alias reverse-map
    for alias, code in KR_ALIAS.items():
        if code == t:
            return "KR"
    return "US"
