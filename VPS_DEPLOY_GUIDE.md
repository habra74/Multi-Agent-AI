# VPS 배포 가이드 — 투자 분석 시스템

> **대상 환경**: Ubuntu 22.04 LTS (단일 VPS)  
> **배포 방식**: Docker Compose (dashboard + scheduler)  
> **예상 소요 시간**: 30~60분 (서버 선택·발급 시간 제외)

---

## 목차

- [A. 배포 방식 비교 (1안 vs 2안)](#a-배포-방식-비교)
- [B. 서버 준비](#b-서버-준비)
- [C. Docker 설치](#c-docker-설치)
- [D. 코드 배포](#d-코드-배포)
- [E. 환경변수 설정 (.env)](#e-환경변수-설정)
- [F. 컨테이너 실행](#f-컨테이너-실행)
- [G. 상태 및 로그 확인](#g-상태-및-로그-확인)
- [H. 방식 1 — 포트 직접 오픈](#h-방식-1--포트-직접-오픈-http8501)
- [I. 방식 2 — Nginx 리버스 프록시 + HTTPS](#i-방식-2--nginx-리버스-프록시--https)
- [J. 검증 절차](#j-검증-절차)
- [K. 백업 및 운영 유지](#k-백업-및-운영-유지)

---

## A. 배포 방식 비교

| 항목 | 방식 1: 포트 직접 오픈 | 방식 2: Nginx + HTTPS (권장) |
|------|----------------------|---------------------------|
| 접속 주소 | `http://서버IP:8501` | `https://your-domain.com` |
| 설정 난이도 | ★☆☆ 쉬움 | ★★☆ 보통 |
| 도메인 필요 | 불필요 | 필요 (무료 도메인 가능) |
| HTTPS | ❌ HTTP만 | ✅ Let's Encrypt 무료 |
| 모바일 접속 | 가능 (포트 번호 입력) | 가능 (일반 URL) |
| 권장 상황 | 테스트·개인 사용 | 장기 운영·팀 공유 |

**빠른 시작 → 방식 1부터 적용 후 필요 시 방식 2로 전환 권장**

---

## B. 서버 준비

### B-1. VPS 선택 (권장 사양)

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| 디스크 | 10 GB | 20 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| 월 비용 | $4~6 | $10~15 |

**서비스 예시**: DigitalOcean Droplet / Vultr / Hetzner CX11 / AWS EC2 t3.micro  
**완전 무료 옵션**: Oracle Cloud Always Free (ARM A1, 1 OCPU, 6 GB RAM)

### B-2. 서버 접속

```bash
# 로컬 PC에서 서버에 SSH 접속
ssh root@<서버IP>

# 또는 키 파일 사용 시
ssh -i ~/.ssh/my-key.pem ubuntu@<서버IP>
```

### B-3. 서버 기본 설정

```bash
# 패키지 업데이트
apt update && apt upgrade -y

# 필수 도구 설치
apt install -y git curl wget nano ufw

# 서버 시간대 확인 (컨테이너는 KST 고정이므로 서버 시간대 불일치해도 무관)
timedatectl
# 스케줄러는 컨테이너 내부 TZ=Asia/Seoul 기준으로 동작함

# 비root 유저 생성 (선택, 보안 강화)
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy   # Docker 설치 후
```

---

## C. Docker 설치

```bash
# 공식 스크립트로 Docker Engine 설치
curl -fsSL https://get.docker.com | sh

# 현재 사용자에게 Docker 권한 부여 (재로그인 필요)
usermod -aG docker $USER
newgrp docker

# Docker Compose Plugin 설치 확인 (최신 Docker에 포함됨)
docker compose version
# 출력 예: Docker Compose version v2.xx.x

# Docker 서비스 자동 시작 활성화 (서버 재부팅 시 Docker도 자동 시작)
systemctl enable docker
systemctl start docker

# 설치 확인
docker --version
docker run hello-world
```

> **주의**: `docker compose` (공백)와 `docker-compose` (하이픈) 두 가지 모두 동작.  
> 이 가이드에서는 `docker compose`(플러그인 방식)를 사용.

---

## D. 코드 배포

### D-1. 방법 A: Git Clone (권장)

```bash
# 앱 설치 디렉터리 생성
mkdir -p /opt/investment && cd /opt/investment

# 저장소 클론 (Git 저장소가 없다면 D-2 방법 사용)
git clone https://github.com/<your-username>/<your-repo>.git .

# 이후 업데이트 시
git pull origin main
```

### D-2. 방법 B: SCP 파일 업로드 (Git 없을 때)

```bash
# 로컬 PC에서 실행 (서버가 아님!)
# 전체 프로젝트 폴더를 서버로 전송
scp -r ./project root@<서버IP>:/opt/investment

# 또는 rsync (더 빠름, 변경분만 전송)
rsync -avz --exclude='.env' --exclude='db/' --exclude='logs/' \
    ./project/ root@<서버IP>:/opt/investment/
```

### D-3. 디렉터리 확인

```bash
# 서버에서
cd /opt/investment
ls -la
# 확인: Dockerfile, docker-compose.yml, docker-entrypoint.sh, .env.example 등 존재
```

---

## E. 환경변수 설정

```bash
cd /opt/investment

# 템플릿에서 .env 생성
cp .env.example .env

# 편집
nano .env
```

**`.env` 필수 항목 체크리스트**

```bash
# ── 반드시 채워야 하는 항목 ──────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-api03-...          # Anthropic 콘솔에서 발급

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx           # Gmail 앱 비밀번호 (16자리)
SENDER_EMAIL=your_gmail@gmail.com
RECIPIENT_EMAIL=you@example.com             # 리포트 받을 이메일

# ── 배포 환경에 맞게 변경해야 하는 항목 ──────────────────────
# 방식 1 (포트 직접): http://<서버IP>:8501
# 방식 2 (Nginx/도메인): https://invest.yourdomain.com
BASE_URL=http://<서버IP>:8501

SCHEDULER_TIME=07:00                        # KST 기준 (컨테이너 TZ=Asia/Seoul)
```

```bash
# 저장 후 내용 확인 (민감 정보 출력 주의)
grep -v "PASSWORD\|API_KEY" .env

# 파일 권한 제한 (본인만 읽기)
chmod 600 .env
```

> **Gmail 앱 비밀번호 발급**: Google 계정 → 보안 → 2단계 인증 활성화 →  
> 앱 비밀번호 → "기타(직접 입력)" → 생성된 16자리 입력

---

## F. 컨테이너 실행

```bash
cd /opt/investment

# 이미지 빌드 (최초 1회 또는 코드 변경 후)
docker compose build

# 백그라운드 실행
docker compose up -d

# 실행 상태 확인
docker compose ps
```

**정상 출력 예시**

```
NAME                      STATUS
investment-dashboard      Up 2 minutes (healthy)
investment-scheduler      Up 2 minutes
```

> `healthy` 상태가 될 때까지 약 30초~1분 소요됨.  
> `starting` → `healthy` 순서로 변경됨.

---

## G. 상태 및 로그 확인

### 실시간 로그

```bash
# 전체 로그 스트리밍
docker compose logs -f

# 대시보드만
docker compose logs -f dashboard

# 스케줄러만
docker compose logs -f scheduler

# 최근 50줄만
docker compose logs --tail=50 scheduler
```

### 컨테이너 상태

```bash
# 서비스 상태 요약
docker compose ps

# 상세 정보 (healthcheck 포함)
docker inspect investment-dashboard | grep -A5 "Health"

# 리소스 사용량 실시간 확인
docker stats
```

### 대시보드 healthcheck 직접 테스트

```bash
# 서버에서
curl -s http://localhost:8501/_stcore/health
# 정상: {"status": "ok"} 반환
```

---

## H. 방식 1 — 포트 직접 오픈 (HTTP:8501)

### 방화벽 설정 (UFW)

```bash
# UFW 활성화 (처음 한 번만)
ufw allow OpenSSH      # SSH 먼저! (잠기지 않도록)
ufw allow 8501/tcp     # 대시보드 포트
ufw enable
ufw status
```

**클라우드 방화벽 추가 설정** (서비스별 Security Group / Firewall 설정 필요)

| 서비스 | 설정 위치 |
|--------|---------|
| AWS EC2 | EC2 콘솔 → 보안 그룹 → 인바운드 규칙 → TCP 8501 추가 |
| DigitalOcean | Networking → Firewalls → Inbound → TCP 8501 |
| Vultr | Firewall → Add rule → TCP 8501 |
| Hetzner | Firewall → Inbound → TCP 8501 |
| Oracle Cloud | 가상 클라우드 네트워크 → 보안 목록 → 수신 규칙 → TCP 8501 |

### .env BASE_URL 설정

```bash
# .env 파일에서
BASE_URL=http://<서버IP>:8501
```

### 접속 테스트

```bash
# 브라우저에서
http://<서버IP>:8501
```

---

## I. 방식 2 — Nginx 리버스 프록시 + HTTPS

### I-1. 도메인 준비

1. 도메인 구입 또는 무료 도메인 발급
   - 무료: [Freenom](https://www.freenom.com) 또는 [Duck DNS](https://www.duckdns.org) (서브도메인)
   - 유료: Namecheap, GoDaddy ($10~15/년)
2. DNS A 레코드 설정: `invest.yourdomain.com` → 서버IP

```bash
# DNS 전파 확인 (1~10분 소요)
nslookup invest.yourdomain.com
# 또는
dig invest.yourdomain.com A
```

### I-2. Nginx 설치

```bash
apt install -y nginx
systemctl enable nginx
systemctl start nginx

# 방화벽 오픈
ufw allow 80/tcp
ufw allow 443/tcp
# 8501은 외부 오픈 불필요 (Nginx가 내부에서 프록시)
```

### I-3. Nginx 설정 파일 작성

```bash
nano /etc/nginx/sites-available/investment
```

**HTTP → HTTPS 리다이렉트 + Streamlit WebSocket 설정**

```nginx
# /etc/nginx/sites-available/investment

# HTTP → HTTPS 리다이렉트
server {
    listen 80;
    server_name invest.yourdomain.com;
    return 301 https://$host$request_uri;
}

# HTTPS 본문 (SSL 인증서 발급 후 활성화)
server {
    listen 443 ssl http2;
    server_name invest.yourdomain.com;

    # Let's Encrypt 인증서 (certbot이 자동으로 채움)
    ssl_certificate     /etc/letsencrypt/live/invest.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/invest.yourdomain.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # 보안 헤더
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;

    # Streamlit 프록시
    location / {
        proxy_pass         http://localhost:8501;
        proxy_http_version 1.1;

        # WebSocket 지원 (Streamlit 필수)
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 헤더 전달
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 타임아웃 (긴 분석 요청 대비)
        proxy_read_timeout  300s;
        proxy_send_timeout  300s;
        proxy_connect_timeout 10s;
    }

    # Streamlit static assets 캐시
    location ~* \.(js|css|png|jpg|ico|woff2?)$ {
        proxy_pass http://localhost:8501;
        proxy_cache_bypass $http_upgrade;
        expires 7d;
    }
}
```

```bash
# 심볼릭 링크로 활성화
ln -s /etc/nginx/sites-available/investment /etc/nginx/sites-enabled/

# 기본 사이트 비활성화 (선택)
rm -f /etc/nginx/sites-enabled/default

# 설정 문법 검사
nginx -t
# 출력: syntax is ok / test is successful
```

### I-4. Let's Encrypt SSL 인증서 발급

```bash
# Certbot 설치
apt install -y certbot python3-certbot-nginx

# 인증서 발급 + Nginx 자동 설정
certbot --nginx -d invest.yourdomain.com

# 이메일 입력 → 이용약관 동의 → 자동 갱신 설정
# 갱신은 90일 주기로 자동 처리됨

# 갱신 테스트
certbot renew --dry-run
```

### I-5. Nginx 재시작 및 .env 업데이트

```bash
# Nginx 재시작
systemctl reload nginx

# .env 에서 BASE_URL 업데이트
nano /opt/investment/.env
# BASE_URL=https://invest.yourdomain.com

# 컨테이너 재시작 (BASE_URL 반영)
cd /opt/investment
docker compose down && docker compose up -d
```

---

## J. 검증 절차

### J-1. 대시보드 외부 접속 테스트

```bash
# 방식 1: 브라우저에서 접속
http://<서버IP>:8501

# 방식 2: 브라우저에서 접속
https://invest.yourdomain.com
```

- [ ] 대시보드 메인 화면이 로딩됨
- [ ] 사이드바 메뉴 5개가 모두 표시됨
- [ ] 운영 요약 패널 4개 메트릭 표시됨

### J-2. 즉시 실행 버튼 테스트

1. 사이드바 → **🏠 홈 대시보드**
2. **🚀 지금 즉시 실행** 버튼 클릭
3. 진행 바와 종목별 분석 로그 확인
4. 완료 후 "오늘 생성된 리포트" 목록 확인

```bash
# 서버에서 대시보드 로그로 동작 확인
docker compose logs -f dashboard
```

### J-3. 스케줄러 즉시 1회 실행 테스트 (scheduler-now)

```bash
# 서버에서 실행 — scheduler-now 모드로 컨테이너 일회성 실행
docker run --rm \
  --env-file /opt/investment/.env \
  --volumes-from investment-dashboard \
  investment-system:latest \
  scheduler-now
```

또는 실행 중인 스케줄러 컨테이너에서 직접:

```bash
docker exec investment-scheduler \
  python scheduler/scheduler.py --now
```

- [ ] 분석 완료 로그 출력됨
- [ ] 이메일 발송 성공/실패 로그 확인

### J-4. 이메일 수신 확인

```bash
# 이메일 설정 페이지에서 테스트 메일 발송
# 대시보드 → 📧 이메일 설정 → 📧 테스트 메일 보내기
```

- [ ] 테스트 메일이 지정 수신함에 도착함
- [ ] "대시보드에서 상세 보기" 버튼 링크가 실제 서버 URL로 연결됨
- [ ] 공개 URL일 경우 "로컬 PC" 안내 문구가 숨겨짐

### J-5. 스케줄러 다음 예약 시각 확인

```bash
# 스케줄러 로그에서 실행 시각 확인
docker compose logs scheduler | grep "스케줄러 시작"
# 예: 스케줄러 시작 — 매일 07:00에 분석 실행

# 컨테이너 내부 현재 시각 확인 (KST 기준이어야 함)
docker exec investment-scheduler date
# 예: Tue Apr 21 14:30:00 KST 2026
```

- [ ] 컨테이너 시각이 KST(한국 표준시)임
- [ ] 로그에 "매일 07:00에 분석 실행" 메시지 확인

### J-6. 서버 재부팅 후 자동 복구 확인

```bash
# 서버 재부팅
reboot

# 재접속 후 컨테이너 자동 재시작 확인 (1~2분 후)
ssh root@<서버IP>
docker compose -f /opt/investment/docker-compose.yml ps
# 두 서비스 모두 Up 상태여야 함
```

- [ ] 재부팅 후 dashboard 컨테이너가 자동으로 Up 됨
- [ ] 재부팅 후 scheduler 컨테이너가 자동으로 Up 됨

### J-7. 모바일 브라우저 테스트

브라우저(Chrome/Safari)에서 서버 URL 접속:

- [ ] 페이지가 모바일에서 읽기 쉬운 형태로 표시됨
- [ ] 사이드바 메뉴가 접을 수 있음 (햄버거 버튼)
- [ ] 메트릭 수치가 잘린 없이 표시됨
- [ ] 리포트 상세 탭이 스크롤 없이 탐색 가능함

---

## K. 백업 및 운영 유지

### K-1. SQLite DB 백업

```bash
# 수동 백업
mkdir -p /opt/investment/backup
docker cp investment-dashboard:/app/db/investment.db \
    /opt/investment/backup/investment_$(date +%Y%m%d_%H%M).db

# 확인
ls -lh /opt/investment/backup/
```

**자동 백업 (cron 설정)**

```bash
crontab -e
```

```cron
# 매일 오전 6시 50분 (분석 실행 10분 전) DB 백업
50 6 * * * docker cp investment-dashboard:/app/db/investment.db \
    /opt/investment/backup/investment_$(date +\%Y\%m\%d).db

# 30일 이상 된 백업 삭제
0 7 * * 0 find /opt/investment/backup -name "*.db" -mtime +30 -delete
```

### K-2. 로그 보존

```bash
# 로그 볼륨에서 로그 파일 목록 확인
docker exec investment-scheduler ls /app/logs/

# 로그 파일 가져오기
docker cp investment-scheduler:/app/logs/ /opt/investment/logs-backup/
```

**Docker 로그 크기 제한** (docker-compose.yml에 추가 가능)

```yaml
# docker-compose.yml services.dashboard 에 추가
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### K-3. 코드 업데이트 절차

```bash
cd /opt/investment

# 코드 업데이트 (Git 사용 시)
git pull origin main

# 이미지 재빌드 + 재시작
docker compose down
docker compose build --no-cache
docker compose up -d

# 또는 한 번에
docker compose up -d --build
```

### K-4. 운영 중 설정 변경

대부분의 설정은 **대시보드 → 📧 이메일 설정** 페이지에서 재시작 없이 변경 가능:
- 수신 이메일 (primary / CC)
- 자동 분석 시각 (`scheduler_time`)
- 대시보드 URL (`base_url`)

`.env` 파일 변경이 필요한 경우(API 키, SMTP 설정):

```bash
nano /opt/investment/.env
# 변경 후 재시작
docker compose down && docker compose up -d
```

### K-5. 디스크 공간 관리

```bash
# 현재 디스크 사용량
df -h

# Docker 이미지/컨테이너 정리 (오래된 이미지 제거)
docker system prune -f

# 볼륨 크기 확인
docker system df
```

---

## 참고: 주요 명령어 빠른 참조

```bash
# 위치 이동
cd /opt/investment

# 서비스 시작/중지/재시작
docker compose up -d          # 시작 (백그라운드)
docker compose down           # 중지
docker compose restart        # 재시작 (이미지 재빌드 없음)

# 로그
docker compose logs -f                 # 전체 실시간
docker compose logs -f scheduler       # 스케줄러만
docker compose logs --tail=100 dashboard  # 최근 100줄

# 상태
docker compose ps             # 서비스 상태
docker stats                  # 리소스 사용량

# 즉시 분석 실행
docker exec investment-scheduler python scheduler/scheduler.py --now

# DB 백업
docker cp investment-dashboard:/app/db/investment.db ./backup/investment_$(date +%Y%m%d).db

# 이미지 재빌드 (코드 변경 후)
docker compose build --no-cache && docker compose up -d
```
