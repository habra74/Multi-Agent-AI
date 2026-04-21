import sys
import os
import json
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.utils import setup_logging
from coordinator.coordinator import Coordinator
from report.report_generator import generate_report, generate_json_report
from config import (
    INVESTMENT_STYLES, HORIZONS, MARKETS, LANGUAGES,
    DEFAULT_INVESTMENT_STYLE, DEFAULT_HORIZON, DEFAULT_MARKET,
    DEFAULT_LANGUAGE, DB_PATH,
)


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Investment Decision Support System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시 / Examples:
  python main.py AAPL
  python main.py NVDA --style aggressive --horizon short
  python main.py 005930 --market KR --lang ko
  python main.py 삼성전자 --market KR --save-db
  python main.py TSLA --market US --output both --save --save-db
        """,
    )
    parser.add_argument(
        "ticker", nargs="?",
        help="종목 코드 또는 종목명 (예: AAPL, 005930, 삼성전자)",
    )
    parser.add_argument(
        "--market", choices=MARKETS, default=DEFAULT_MARKET,
        help=f"시장 (default: {DEFAULT_MARKET})",
    )
    parser.add_argument(
        "--style", choices=INVESTMENT_STYLES, default=DEFAULT_INVESTMENT_STYLE,
        help=f"투자 성향 (default: {DEFAULT_INVESTMENT_STYLE})",
    )
    parser.add_argument(
        "--horizon", choices=HORIZONS, default=DEFAULT_HORIZON,
        help=f"투자 기간 (default: {DEFAULT_HORIZON})",
    )
    parser.add_argument(
        "--lang", choices=LANGUAGES, default=DEFAULT_LANGUAGE,
        help=f"보고서 언어 (default: {DEFAULT_LANGUAGE})",
    )
    parser.add_argument(
        "--output", choices=["markdown", "json", "both"], default="markdown",
        help="출력 형식 (default: markdown)",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="리포트를 logs/ 디렉터리에 파일로 저장",
    )
    parser.add_argument(
        "--save-db", action="store_true",
        help="분석 결과를 SQLite DB에 저장",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# DB save helper
# ---------------------------------------------------------------------------

def save_to_db(results: dict, markdown_report: str, json_data: dict) -> int:
    """
    Persist analysis results to the reports table.
    Returns the new report id.
    """
    from db.database import init_db
    from db.repository import ReportRepository

    init_db(DB_PATH)
    repo = ReportRepository(DB_PATH)

    da = results.get("decision", {})
    ra = results.get("risk_analysis", {})

    report_id = repo.save(
        ticker           = results.get("ticker", ""),
        display_name     = results.get("company_name", ""),
        market           = results.get("market", "US"),
        style            = results.get("investment_style", "neutral"),
        horizon          = results.get("horizon", "mid"),
        language         = results.get("language", "ko"),
        final_decision   = da.get("final_decision", "N/A"),
        executive_summary= da.get("reasoning", ""),
        markdown_report  = markdown_report,
        json_report      = json_data,
        confidence       = da.get("confidence", 0.0),
        risk_score       = ra.get("risk_score", 0.0),
    )
    return report_id


# ---------------------------------------------------------------------------
# Public function: analyze_and_store
# ---------------------------------------------------------------------------

def analyze_and_store(
    ticker: str,
    market: str = DEFAULT_MARKET,
    style: str = DEFAULT_INVESTMENT_STYLE,
    horizon: str = DEFAULT_HORIZON,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """
    Run the full analysis pipeline and save results to the DB.

    Returns a dict with keys:
        results, markdown_report, json_data, report_id
    """
    coordinator = Coordinator()
    results = coordinator.run(
        ticker=ticker,
        market=market,
        investment_style=style,
        horizon=horizon,
        language=language,
    )

    markdown_report = generate_report(results, language=language)
    json_data       = generate_json_report(results)
    report_id       = save_to_db(results, markdown_report, json_data)

    return {
        "results":         results,
        "markdown_report": markdown_report,
        "json_data":       json_data,
        "report_id":       report_id,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Ensure UTF-8 output on Windows (CLI only — must not run at import time)
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    args = parse_args()

    # Interactive ticker prompt if not provided
    ticker = args.ticker
    if not ticker:
        print("\n" + "=" * 50)
        print("  투자 분석 시스템  |  Multi-Agent Investment System")
        print("=" * 50)
        ticker = input("\n종목 코드 입력 (예: AAPL, 005930, 삼성전자): ").strip()

    if not ticker:
        print("오류: 종목 코드를 입력하세요.")
        sys.exit(1)

    # Setup logging
    safe_ticker = ticker.replace("/", "_")
    logger = setup_logging(safe_ticker)
    logger.info(
        f"Starting: {ticker} | market={args.market} | "
        f"style={args.style} | horizon={args.horizon} | lang={args.lang}"
    )

    print(f"\n{'=' * 50}")
    print(f"  분석 대상: {ticker}")
    print(f"  성향: {args.style.capitalize()} | 기간: {args.horizon.capitalize()}")
    print(f"  시장: {args.market} | 언어: {args.lang.upper()}")
    print(f"{'=' * 50}")

    # Run coordinator
    coordinator = Coordinator()
    try:
        results = coordinator.run(
            ticker=ticker,
            market=args.market,
            investment_style=args.style,
            horizon=args.horizon,
            language=args.lang,
        )
    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        print(f"\n분석 중 오류 발생: {e}")
        sys.exit(1)

    # --- Generate reports ---
    markdown_report = None
    json_data       = None

    if args.output in ("markdown", "both"):
        markdown_report = generate_report(results, language=args.lang)
        print(markdown_report)

        if args.save:
            from config import LOG_DIR
            from datetime import datetime
            report_path = LOG_DIR / f"{safe_ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_report.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(markdown_report)
            print(f"\n리포트 저장됨: {report_path}")

    if args.output in ("json", "both"):
        json_data = generate_json_report(results)
        print("\n" + json.dumps(json_data, indent=2, ensure_ascii=False, default=str))

        if args.save:
            from config import LOG_DIR
            from datetime import datetime
            json_path = LOG_DIR / f"{safe_ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_report.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
            print(f"\nJSON 저장됨: {json_path}")

    # --- DB save ---
    if args.save_db:
        if markdown_report is None:
            markdown_report = generate_report(results, language=args.lang)
        if json_data is None:
            json_data = generate_json_report(results)
        try:
            report_id = save_to_db(results, markdown_report, json_data)
            print(f"\n[DB] 리포트 저장 완료 (id={report_id})")
        except Exception as e:
            logger.error(f"DB save failed: {e}")
            print(f"\n[DB] 저장 실패: {e}")

    logger.info("Analysis complete.")


if __name__ == "__main__":
    main()
