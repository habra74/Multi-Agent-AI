import logging
import pandas as pd
import numpy as np
from typing import Optional
from config import SHORT_MA, MID_MA, LONG_MA

logger = logging.getLogger(__name__)


def compute_moving_averages(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    close = df["Close"].squeeze()
    result = {}
    for window in [SHORT_MA, MID_MA, LONG_MA]:
        if len(close) >= window:
            result[f"sma_{window}"] = float(close.rolling(window).mean().iloc[-1])
    result["current_price"] = float(close.iloc[-1])
    return result


def compute_momentum(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    close = df["Close"].squeeze()
    result = {}
    for days in [5, 21, 63, 126, 252]:
        if len(close) > days:
            result[f"return_{days}d"] = float((close.iloc[-1] / close.iloc[-days] - 1) * 100)
    return result


def compute_volatility(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    close = df["Close"].squeeze()
    daily_returns = close.pct_change().dropna()
    if len(daily_returns) < 10:
        return {}
    annualized_vol = float(daily_returns.std() * np.sqrt(252) * 100)
    recent_vol = float(daily_returns.tail(21).std() * np.sqrt(252) * 100) if len(daily_returns) >= 21 else annualized_vol
    return {
        "annualized_volatility_pct": annualized_vol,
        "recent_21d_volatility_pct": recent_vol,
        "vol_classification": _classify_volatility(annualized_vol),
    }


def compute_volume_trend(df: pd.DataFrame) -> dict:
    if df is None or df.empty or "Volume" not in df.columns:
        return {}
    volume = df["Volume"].squeeze()
    if len(volume) < 21:
        return {}
    avg_vol_20 = float(volume.tail(20).mean())
    avg_vol_60 = float(volume.tail(60).mean()) if len(volume) >= 60 else avg_vol_20
    recent_vol = float(volume.tail(5).mean())
    return {
        "avg_volume_20d": avg_vol_20,
        "volume_ratio": round(recent_vol / avg_vol_60, 2) if avg_vol_60 > 0 else 1.0,
        "volume_trend": "increasing" if recent_vol > avg_vol_60 * 1.1 else (
            "decreasing" if recent_vol < avg_vol_60 * 0.9 else "stable"
        ),
    }


def compute_52w_position(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 2:
        return {}
    close = df["Close"].squeeze()
    tail = close.tail(252)
    high_52w = float(tail.max())
    low_52w = float(tail.min())
    current = float(close.iloc[-1])
    range_size = high_52w - low_52w
    position = (current - low_52w) / range_size if range_size > 0 else 0.5
    return {
        "high_52w": high_52w,
        "low_52w": low_52w,
        "position_in_range": round(position * 100, 1),
    }


def compute_rsi(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df is None or len(df) < period + 1:
        return None
    close = df["Close"].squeeze()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def _classify_volatility(vol_pct: float) -> str:
    if vol_pct < 15:
        return "low"
    elif vol_pct < 30:
        return "moderate"
    elif vol_pct < 50:
        return "high"
    return "very_high"


def compute_all_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    indicators = {}
    indicators.update(compute_moving_averages(df))
    indicators.update(compute_momentum(df))
    indicators.update(compute_volatility(df))
    indicators.update(compute_volume_trend(df))
    indicators.update(compute_52w_position(df))
    rsi = compute_rsi(df)
    if rsi is not None:
        indicators["rsi"] = round(rsi, 1)
    return indicators
