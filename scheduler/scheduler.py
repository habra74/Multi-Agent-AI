"""
scheduler/scheduler.py
-----------------------
APScheduler 기반 자동 분석 스케줄러.

실행:
    python scheduler/scheduler.py

동작:
    1. .env 파일의 SCHEDULER_TIME (기본 07:00)에 매일 실행
    2. watchlist에서 is_active=1 종목 조회
    3. 각 종목에 대해 analyze_and_store() 실행
    4. 모든 종목 완료 후 오늘 리포트를 이메일로 발송
    5. 실행 결과 로그 기록

특징:
    - 한 종목 실패해도 나머지 종목 계속 진행
    - 이메일 실패해도 분석 결과는 DB에 보존
    - Ctrl+C 로 안전하게 종료
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Project root를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from config import SCHEDULER_TIME, DB_PATH, LOG_DIR
from db.database import init_db
from db.repository import WatchlistRepository, ReportRepository
from email_service.email_sender import send_daily_report
from main import analyze_and_store

# ---------------------------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------------------------

def _setup_scheduler_logging() -> logging.Logger:
    log_file = LOG_DIR / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("scheduler")


# 모듈 레벨에서는 basicConfig 호출 없이 단순 logger만 획득
# (basicConfig는 main() 진입 시에만 호출)
logger = logging.getLogger("scheduler")


# ---------------------------------------------------------------------------
# 핵심 분석 Job
# ---------------------------------------------------------------------------

def run_daily_analysis() -> None:
    """
    Watchlist의 활성 종목을 전부 분석하고 이메일로 발송.
    스케줄러 또는 수동 테스트에서 직접 호출 가능.
    """
    run_start = datetime.now()
    logger.info("=" * 60)
    logger.info(f"일일 자동 분석 시작: {run_start.strftime('%Y-%m-%d %H:%M:%S')}")

    # DB 초기화 (idempotent)
    init_db(DB_PATH)
    wl_repo = WatchlistRepository(DB_PATH)
    rp_repo = ReportRepository(DB_PATH)

    active_list = wl_repo.list_active()
    if not active_list:
        logger.warning("활성 watchlist 항목 없음 — 분석 건너뜀")
        return

    logger.info(f"분석 대상: {[w['ticker'] for w in active_list]}")

    success_ids: list[int] = []
    failed: list[str] = []

    # ---- 종목별 분석 ----
    for entry in active_list:
        ticker  = entry["ticker"]
        market  = entry.get("market",  "US")
        style   = entry.get("style",   "neutral")
        horizon = entry.get("horizon", "mid")
        language = entry.get("language", "ko")

        logger.info(f"[{ticker}] 분석 시작 | market={market} style={style} horizon={horizon}")
        try:
            out = analyze_and_store(
                ticker=ticker,
                market=market,
                style=style,
                horizon=horizon,
                language=language,
            )
            report_id = out.get("report_id")
            verdict   = out["results"].get("decision", {}).get("final_decision", "N/A")
            logger.info(f"[{ticker}] 분석 완료 → {verdict} (report_id={report_id})")
            success_ids.append(report_id)

        except Exception as exc:
            logger.exception(f"[{ticker}] 분석 실패: {exc}")
            failed.append(ticker)

    # ---- 이메일 발송 ----
    if success_ids:
        logger.info("이메일 발송 준비 중...")
        # full row (json_report 포함) 필요
        full_rows = [rp_repo.get_by_id(rid) for rid in success_ids if rid]
        full_rows = [r for r in full_rows if r]

        try:
            ok = send_daily_report(full_rows, db_path=DB_PATH)
            if ok:
                logger.info("이메일 발송 성공")
            else:
                logger.warning("이메일 발송 실패 (SMTP 설정 확인 필요) — 분석 결과는 DB에 보존됨")
        except Exception as exc:
            logger.error(f"이메일 발송 중 예외 발생: {exc}")

    # ---- 요약 ----
    elapsed = (datetime.now() - run_start).total_seconds()
    logger.info(
        f"일일 분석 완료: 성공={len(success_ids)} 실패={len(failed)} "
        f"소요={elapsed:.1f}s"
    )
    if failed:
        logger.warning(f"실패 종목: {failed}")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# APScheduler 이벤트 리스너
# ---------------------------------------------------------------------------

def _on_job_executed(event):
    logger.info(f"Job 완료: {event.job_id}")


def _on_job_error(event):
    logger.error(f"Job 오류: {event.job_id} | {event.exception}")


# ---------------------------------------------------------------------------
# 스케줄러 실행
# ---------------------------------------------------------------------------

def main():
    # 데몬 실행 시에만 파일 로그 설정
    _setup_scheduler_logging()

    # SCHEDULER_TIME 파싱: "HH:MM"
    try:
        hour, minute = SCHEDULER_TIME.split(":")
        hour   = int(hour)
        minute = int(minute)
    except Exception:
        logger.error(f"SCHEDULER_TIME 형식 오류: '{SCHEDULER_TIME}' — HH:MM 형식이어야 합니다.")
        hour, minute = 7, 0

    logger.info(f"스케줄러 시작 — 매일 {hour:02d}:{minute:02d}에 분석 실행")
    logger.info(f"Ctrl+C 로 종료")

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    scheduler.add_job(
        func     = run_daily_analysis,
        trigger  = CronTrigger(hour=hour, minute=minute),
        id       = "daily_analysis",
        name     = "일일 투자 분석",
        max_instances = 1,         # 중복 실행 방지
        coalesce = True,           # 밀린 실행 한 번으로 합산
        misfire_grace_time = 3600, # 1시간 내 지연 허용
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("스케줄러 종료 요청 (Ctrl+C)")
        scheduler.shutdown(wait=False)
        logger.info("스케줄러 정상 종료")


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="투자 분석 자동 스케줄러",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
실행 모드:
  python scheduler/scheduler.py          # 스케줄러 데몬으로 실행
  python scheduler/scheduler.py --now    # 지금 즉시 1회 실행 (테스트용)
        """,
    )
    parser.add_argument(
        "--now", action="store_true",
        help="스케줄 없이 즉시 1회 실행 (테스트 / 수동 실행용)",
    )
    args = parser.parse_args()

    if args.now:
        logger.info("즉시 실행 모드 (--now)")
        run_daily_analysis()
    else:
        main()
