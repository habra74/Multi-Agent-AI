# 배포 준비 가이드 (Deployment Preparation Guide)

> 현재 상태: **배포 준비 완료** — 실제 클라우드 배포는 다음 단계(Phase 4)에서 수행  
> 마지막 업데이트: 2026-04-21

---

## 목차

1. [시스템 구조](#1-시스템-구조)
2. [로컬 실행 방법](#2-로컬-실행-방법)
3. [Docker 기반 배포 준비](#3-docker-기반-배포-준비)
4. [환경변수 설정](#4-환경변수-설정)
5. [클라우드 배포 후보 (Phase 4)](#5-클라우드-배포-후보-phase-4)
6. [운영 안정화 계획 (Phase 5)](#6-운영-안정화-계획-phase-5)

---

## 1. 시스템 구조

```
투자 분석 시스템
├── 대시보드 프로세스   streamlit run dashboard.py  (포트 8501)
└── 스케줄러 프로세스   python scheduler/scheduler.py  (백그라운드)
         ↓ 매일 SCHEDULER_TIME에 자동 실행
    ┌── WatchlistRepository (SQLite)
    ├── Multi-Agent 분석 파이프라인
    │     DataAgent → MarketAgent + FundamentalAgent + NewsAgent
    │     → RiskAgent → DecisionAgent
    ├── ReportRepository.save()
    └── send_daily_report() → SMTP 이메일 발송
```

### 프로세스 독립성

| 프로세스 | 역할 | 실패 시 영향 |
|---------|------|------------|
| dashboard | Streamlit 웹 UI, DB 조회 | 분석·발송 영향 없음 |
| scheduler | 자동 분석, 이메일 발송 | 대시보드 조회 영향 없음 |

두 프로세스는 **SQLite 파일 하나를 공유**하며 독립 실행됩니다.

---

## 2. 로컬 실행 방법

### 사전 준비

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY, SMTP_* 값 입력

# 3. DB 초기화 (자동, 첫 실행 시)
python -c "from db.database import init_db; from config import DB_PATH; init_db(DB_PATH)"
```

### 프로세스 실행

```bash
# 터미널 1: 대시보드
streamlit run dashboard.py

# 터미널 2: 스케줄러 (백그라운드 데몬)
python scheduler/scheduler.py

# 스케줄러 즉시 1회 실행 (테스트용)
python scheduler/scheduler.py --now

# CLI 단일 종목 분석
python main.py AAPL --save-db
python main.py 005930 --market KR --save-db
```

---

## 3. Docker 기반 배포 준비

### 빌드

```bash
# 이미지 빌드
docker build -t investment-system:latest .

# 빌드 확인
docker images | grep investment-system
```

### docker-compose 실행

```bash
# .env 파일 준비 (반드시 먼저)
cp .env.example .env
# .env 편집: ANTHROPIC_API_KEY, SMTP_*, BASE_URL 설정

# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f dashboard
docker-compose logs -f scheduler

# 중단
docker-compose down

# 재시작 (코드 업데이트 후)
docker-compose down && docker-compose up -d --build
```

### 단일 컨테이너 실행 (docker-compose 없이)

```bash
# 공유 볼륨 생성
docker volume create investment-db
docker volume create investment-logs

# 대시보드
docker run -d \
  --name investment-dashboard \
  -p 8501:8501 \
  --env-file .env \
  -v investment-db:/app/db \
  -v investment-logs:/app/logs \
  --restart unless-stopped \
  investment-system:latest dashboard

# 스케줄러
docker run -d \
  --name investment-scheduler \
  --env-file .env \
  -v investment-db:/app/db \
  -v investment-logs:/app/logs \
  --restart unless-stopped \
  investment-system:latest scheduler
```

### 데이터 경로 (볼륨)

| 경로 | 설명 | 볼륨 |
|------|------|------|
| `/app/db/investment.db` | SQLite DB | `app-db` |
| `/app/logs/` | 실행 로그 | `app-logs` |

> **백업**: `docker cp investment-dashboard:/app/db/investment.db ./backup/`

---

## 4. 환경변수 설정

### 필수 변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `ANTHROPIC_API_KEY` | Claude API 키 | `sk-ant-...` |
| `SMTP_HOST` | SMTP 서버 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 포트 | `587` |
| `SMTP_USER` | 발신 이메일 | `you@gmail.com` |
| `SMTP_PASSWORD` | 앱 비밀번호 | Gmail 앱 비밀번호 |

### 선택 변수 (대시보드에서도 변경 가능)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `RECIPIENT_EMAIL` | 기본 수신자 | `` |
| `SCHEDULER_TIME` | 자동 실행 시각 (HH:MM) | `07:00` |
| `BASE_URL` | 대시보드 공개 URL | `http://localhost:8501` |

### 클라우드 서버 배포 시 BASE_URL 변경

```bash
# .env 파일에서
BASE_URL=http://your-server-ip:8501
# 또는 도메인이 있을 때
BASE_URL=https://invest.yourdomain.com
```

> 이 URL이 이메일의 "대시보드 열기" 버튼 링크로 사용됩니다.  
> `localhost`가 아닌 URL이면 이메일에서 로컬 실행 안내 문구가 자동으로 숨겨집니다.

---

## 5. 클라우드 배포 후보 (Phase 4)

> 아직 실제 배포하지 않음. 다음 단계 후보 정리.

### 권장 배포 구성: 단일 VPS/VM

**대상 서비스 예시**
- AWS EC2 t3.small (2 vCPU, 2GB RAM, $15~20/월)
- DigitalOcean Droplet Basic ($6~12/월)
- Oracle Cloud Always Free (영구 무료 ARM 인스턴스)
- Hetzner Cloud CX11 (€3.79/월, EU)

**배포 절차 (개요)**

```bash
# 1. 서버 접속 후 Docker 설치
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. 코드 업로드 (git clone 또는 scp)
git clone <repo> /opt/investment-system
cd /opt/investment-system

# 3. .env 설정
cp .env.example .env && nano .env
# BASE_URL=http://<서버IP>:8501 으로 변경

# 4. 실행
docker-compose up -d

# 5. 방화벽 포트 오픈 (8501)
# AWS: Security Group inbound 8501 오픈
# DigitalOcean: Firewall에 8501 추가
```

**서버 재시작 시 자동 복구**

`docker-compose.yml`에 `restart: unless-stopped` 설정이 이미 포함되어 있습니다.  
Docker 데몬이 서버 부팅 시 자동 시작되면 컨테이너도 자동 재시작됩니다.

```bash
# Docker 데몬 자동 시작 활성화
sudo systemctl enable docker
```

**도메인 + HTTPS 적용 (선택)**

Nginx 리버스 프록시 + Let's Encrypt:

```nginx
# /etc/nginx/sites-available/investment
server {
    listen 443 ssl;
    server_name invest.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/invest.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/invest.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 6. 운영 안정화 계획 (Phase 5)

> 아직 구현하지 않음. 설계/제안 수준으로 정리.

### 실행 로그

- 현재: `logs/scheduler_YYYYMMDD.log` (파일 로그)
- 개선 제안: `logs/` 디렉터리를 볼륨으로 마운트하여 영속화 (이미 docker-compose에 포함)
- 추후: 중앙 로그 수집 (CloudWatch, Datadog, Grafana Loki 등) 연동 가능

### 이메일 실패 로그

- 현재: `email_logs` 테이블에 `status`, `error_message` 저장
- 대시보드 → 이메일 설정 페이지에서 최근 20건 조회 가능
- 개선 제안: 연속 실패 시 관리자에게 별도 알림 발송

### 백업 전략

```bash
# 일별 DB 백업 (cron 예시)
0 6 * * * docker cp investment-dashboard:/app/db/investment.db \
           /backup/investment_$(date +\%Y\%m\%d).db

# 7일 이상 된 백업 삭제
0 6 * * * find /backup -name "investment_*.db" -mtime +7 -delete
```

### 헬스체크

- Dockerfile에 Streamlit healthcheck (`/_stcore/health`) 이미 포함
- 스케줄러는 프로세스 생존 여부로 체크
- 추후 간단한 HTTP ping 엔드포인트 추가 가능

### SQLite → PostgreSQL 전환 시점과 기준

| 조건 | 권장 전환 시점 |
|------|--------------|
| 동시 사용자 > 5명 | PostgreSQL 전환 권장 |
| DB 파일 크기 > 500MB | 전환 고려 |
| 보고서 수 > 10만 건 | 전환 고려 |
| 분산 서버 배포 필요 | 전환 필수 |
| 현재 단일 사용자 운영 | SQLite로 충분 |

전환 방법: `db/database.py`의 `get_connection()` 함수만 교체하면 repository 레이어는 변경 불필요 (인터페이스가 동일).

---

## 파일 목록 (배포 관련)

| 파일 | 설명 |
|------|------|
| `Dockerfile` | 단일 이미지, dashboard/scheduler 모드 지원 |
| `docker-compose.yml` | 두 서비스 (dashboard + scheduler) 정의 |
| `docker-entrypoint.sh` | 컨테이너 진입점, DB 초기화 포함 |
| `.env.example` | 환경변수 템플릿 |
| `DEPLOYMENT_PREP.md` | 이 문서 |
| `requirements.txt` | Python 의존성 |
