import logging
import json
from pathlib import Path
from datetime import datetime
from config import LOG_DIR


def setup_logging(ticker: str = "system") -> logging.Logger:
    log_file = LOG_DIR / f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("investment_system")


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        import math
        return default if math.isnan(result) or math.isinf(result) else result
    except (TypeError, ValueError):
        return default


def format_number(value, decimals: int = 2) -> str:
    try:
        if abs(value) >= 1_000_000_000:
            return f"{value/1_000_000_000:.1f}B"
        elif abs(value) >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"{value/1_000:.1f}K"
        return f"{value:.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, value))
