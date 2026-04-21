# ============================================================
# Dockerfile — 투자 분석 시스템
# ============================================================
# 빌드:
#   docker build -t investment-system .
#
# 실행 (대시보드):
#   docker run -p 8501:8501 --env-file .env investment-system dashboard
#
# 실행 (스케줄러):
#   docker run --env-file .env investment-system scheduler
#
# docker-compose 권장:
#   docker-compose up -d
# ============================================================

FROM python:3.11-slim

# ── 시스템 패키지 ────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# 타임존 설정 (한국 시간)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# ── 작업 디렉터리 ─────────────────────────────────────────────
WORKDIR /app

# ── Python 의존성 ─────────────────────────────────────────────
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── 애플리케이션 소스 ─────────────────────────────────────────
COPY . .

# ── 런타임 디렉터리 생성 (볼륨 마운트 전 기본값) ──────────────
RUN mkdir -p /app/db /app/logs

# ── 환경변수 기본값 ───────────────────────────────────────────
# .env 파일 또는 docker run --env-file 로 오버라이드 가능
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BASE_URL=http://localhost:8501 \
    SCHEDULER_TIME=07:00

# ── 포트 노출 (대시보드용) ────────────────────────────────────
EXPOSE 8501

# ── 헬스체크 ─────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── 진입점 스크립트 ───────────────────────────────────────────
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["dashboard"]
