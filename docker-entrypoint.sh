#!/bin/sh
# ============================================================
# docker-entrypoint.sh
# ============================================================
# CMD 인자에 따라 대시보드 또는 스케줄러를 실행한다.
#
#   dashboard  → streamlit run dashboard.py
#   scheduler  → python scheduler/scheduler.py
#   scheduler-now → python scheduler/scheduler.py --now (1회 즉시 실행)
# ============================================================

set -e

MODE="${1:-dashboard}"

# DB 초기화 (테이블이 없으면 생성)
python -c "
from db.database import init_db
from config import DB_PATH
init_db(DB_PATH)
print('[entrypoint] DB initialised at', DB_PATH)
"

case "$MODE" in
  dashboard)
    echo "[entrypoint] Starting Streamlit dashboard on :8501"
    exec streamlit run dashboard.py \
        --server.port=8501 \
        --server.address=0.0.0.0 \
        --server.headless=true \
        --server.enableCORS=false \
        --server.enableXsrfProtection=false \
        --browser.gatherUsageStats=false
    ;;
  scheduler)
    echo "[entrypoint] Starting scheduler daemon (SCHEDULER_TIME=${SCHEDULER_TIME})"
    exec python scheduler/scheduler.py
    ;;
  scheduler-now)
    echo "[entrypoint] Running immediate one-shot analysis"
    exec python scheduler/scheduler.py --now
    ;;
  *)
    echo "[entrypoint] Unknown mode: $MODE"
    echo "Usage: docker run ... <image> [dashboard|scheduler|scheduler-now]"
    exit 1
    ;;
esac
