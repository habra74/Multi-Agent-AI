"""
Smoke tests: run the full pipeline on AAPL, NVDA, TSLA.

Usage:
    python tests/smoke_test.py
    python -m pytest tests/smoke_test.py -v -s --timeout=120
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from coordinator.coordinator import Coordinator
from report.report_generator import generate_report, generate_json_report
from agents.decision_agent import VALID_VERDICTS

REQUIRED_AGENT_KEYS = {
    "agent_name", "summary", "bull_points", "bear_points", "confidence", "evidence"
}
REQUIRED_DECISION_KEYS = REQUIRED_AGENT_KEYS | {"final_decision", "reasoning", "action_items"}


def _validate_results(results: dict, ticker: str):
    """Assert structural invariants on coordinator output."""
    assert results["ticker"] == ticker.upper()
    assert isinstance(results["company_name"], str)

    for section_key, extra_keys in [
        ("market_analysis",      set()),
        ("fundamental_analysis", set()),
        ("news_analysis",        set()),
        ("risk_analysis",        set()),
        ("decision",             {"final_decision", "reasoning", "action_items"}),
    ]:
        section = results[section_key]
        required = REQUIRED_AGENT_KEYS | extra_keys
        missing = required - section.keys()
        assert not missing, f"{section_key}: missing keys {missing}"

        conf = section.get("confidence", -1)
        assert 0.0 <= conf <= 1.0, f"{section_key}: confidence out of range ({conf})"

    verdict = results["decision"]["final_decision"]
    assert verdict in VALID_VERDICTS, f"Invalid verdict: {verdict}"

    # Report generation must not crash
    report = generate_report(results)
    assert len(report) > 300
    assert ticker.upper() in report

    json_data = generate_json_report(results)
    assert json_data["ticker"] == ticker.upper()


@pytest.mark.parametrize("ticker,style,horizon", [
    ("AAPL", "neutral",      "mid"),
    ("NVDA", "aggressive",   "short"),
    ("TSLA", "conservative", "long"),
])
def test_full_pipeline(ticker, style, horizon):
    """End-to-end smoke test: data fetch → all agents → report generation."""
    coordinator = Coordinator()
    results = coordinator.run(ticker=ticker, investment_style=style, horizon=horizon)
    _validate_results(results, ticker)


@pytest.mark.parametrize("ticker,style,horizon", [
    ("AAPL", "neutral",      "mid"),
    ("NVDA", "aggressive",   "short"),
    ("TSLA", "conservative", "long"),
])
def test_news_headlines_non_empty(ticker, style, horizon):
    """After fix, news evidence should contain real headlines."""
    coordinator = Coordinator()
    results = coordinator.run(ticker=ticker, investment_style=style, horizon=horizon)
    news = results["news_analysis"]
    if news.get("news_count", 0) > 0:
        for ev in news.get("evidence", []):
            if isinstance(ev, dict):
                assert ev.get("headline", "").strip() != "", \
                    f"Empty headline in evidence: {ev}"


if __name__ == "__main__":
    import time
    tickers = [
        ("AAPL", "neutral",      "mid"),
        ("NVDA", "aggressive",   "short"),
        ("TSLA", "conservative", "long"),
    ]
    coordinator = Coordinator()
    for ticker, style, horizon in tickers:
        print(f"\n{'='*60}")
        print(f"SMOKE TEST: {ticker} | {style} | {horizon}")
        print("="*60)
        t0 = time.time()
        try:
            results = coordinator.run(ticker=ticker, investment_style=style, horizon=horizon)
            _validate_results(results, ticker)
            verdict = results["decision"]["final_decision"]
            conf    = results["decision"]["confidence"]
            nc      = results["news_analysis"]["news_count"]
            print(f"PASS: {ticker} -> {verdict} (conf={conf:.0%}, news={nc}) [{time.time()-t0:.1f}s]")
        except Exception as e:
            print(f"FAIL: {ticker} -> {e}")
