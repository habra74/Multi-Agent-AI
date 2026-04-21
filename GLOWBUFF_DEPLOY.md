# dashboard.glowbuff.com 배포 가이드

> **도메인**: `dashboard.glowbuff.com`  
> **접속 URL**: `https://dashboard.glowbuff.com`  
> **스택**: Ubuntu 22.04 + Docker Compose + Nginx + Let's Encrypt

---

## 목차

1. [사전 준비](#1-사전-준비)
2. [DNS 설정](#2-dns-설정)
3. [서버 설정 및 코드 배포](#3-서버-설정-및-코드-배포)
4. [환경변수 설정](#4-환경변수-설정)
5. [컨테이너 실행](#5-컨테이너-실행)
6. [Nginx 설치 및 설정](#6-nginx-설치-및-설정)
7. [Let's Encrypt HTTPS 인증서 발급](#7-lets-encrypt-https-인증서-발급)
8. [최종 확인 및 검증](#8-최종-확인-및-검증)
9. [운영 유지](#9-운영-유지)

---

## 1. 사전 준비

### 필요한 것

| 항목 | 설명 |
|------|------|
| VPS 서버 | Ubuntu 22.04 LTS, RAM 2GB 이상 권장 |
| glowbuff.com 도메인 관리 권한 | DNS A 레코드 추가 가능해야 함 |
| Anthropic API 키 | https://console.anthropic.com |
| Gmail 앱 비밀번호 | 이메일 발송용 (SMTP) |

### 배포 구조

```
인터넷
  │
  ▼ HTTPS:443 / HTTP:80
┌─────────────────────────────┐
│  Nginx (리버스 프록시)        │  ← dashboard.glowbuff.com SSL 처리
│  /etc/nginx/sites-enabled/  │
└───────────────┬─────────────┘
                │ HTTP localhost:8501
                ▼
┌───────────────────────────────────┐
│  Docker: investment-dashboard     │  ← Streamlit UI
│  (포트 8501, 외부 비공개)          │
├───────────────────────────────────┤
│  Docker: investment-scheduler     │  ← 매일 07:00 KST 자동 분석
│  (포트 없음)                      │
├───────────────────────────────────┤
│  Docker Volume: app-db            │  ← SQLite DB 영속화
│  Docker Volume: app-logs          │  ← 실행 로그 영속화
└───────────────────────────────────┘
```

> Nginx가 HTTPS를 처리하고 Docker 컨테이너(8501)로 프록시.  
> **8501 포트는 외부에 열지 않는다** — Nginx만 공개.

---

## 2. DNS 설정

glowbuff.com 도메인의 DNS 관리 패널(Cloudflare, Namecheap 등)에서:

### A 레코드 추가

| 타입 | 호스트명 | 값 | TTL |
|------|---------|-----|-----|
| A | `dashboard` | `<서버 공인 IP>` | 300 |

```
# 결과: dashboard.glowbuff.com → <서버IP>
```

### DNS 전파 확인 (서버에서)

```bash
# 서버에 SSH 접속 후
dig dashboard.glowbuff.com A +short
# 출력: <서버IP> 가 나오면 전파 완료

# 또는
nslookup dashboard.glowbuff.com
# Address: <서버IP>
```

> DNS 전파는 보통 1~10분, 최대 24시간 소요.  
> **전파 확인 후 다음 단계 진행** (Let's Encrypt 발급 시 도메인 검증 필요).

---

## 3. 서버 설정 및 코드 배포

### 3-1. 서버 기본 설정

```bash
# 패키지 업데이트
apt update && apt upgrade -y
apt install -y git curl wget nano ufw
```

### 3-2. Docker 설치

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER
newgrp docker
systemctl enable docker

# 확인
docker --version
docker compose version
```

### 3-3. 코드 배포

```bash
mkdir -p /opt/investment
cd /opt/investment

# Git 사용 시
git clone https://github.com/<your-username>/<your-repo>.git .

# 또는 로컬 PC에서 업로드
# scp -r ./project/ root@<서버IP>:/opt/investment/
```

---

## 4. 환경변수 설정

```bash
cd /opt/investment
cp .env.example .env
nano .env
```

### .env 설정값 (dashboard.glowbuff.com 기준)

```bash
# ── LLM ──────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-api03-여기에입력

# ── SMTP (Gmail) ─────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SENDER_EMAIL=your_gmail@gmail.com
RECIPIENT_EMAIL=you@example.com

# ── 스케줄러 ──────────────────────────────────────
SCHEDULER_TIME=07:00

# ── 대시보드 URL ← 반드시 이 값으로 설정 ─────────
BASE_URL=https://dashboard.glowbuff.com
```

```bash
# 파일 권한 제한
chmod 600 .env
```

> `BASE_URL=https://dashboard.glowbuff.com` 으로 설정하면:
> - 이메일의 "대시보드 열기" 버튼이 올바른 공개 URL로 연결됨
> - "로컬 PC에서 실행 중일 때" 안내 문구가 자동으로 숨겨짐

---

## 5. 컨테이너 실행

```bash
cd /opt/investment

# 이미지 빌드
docker compose build

# 백그라운드 실행
docker compose up -d

# 상태 확인
docker compose ps
```

**정상 상태 예시**

```
NAME                     STATUS
investment-dashboard     Up 1 minute (healthy)
investment-scheduler     Up 1 minute
```

> 이 시점에서 대시보드는 **localhost:8501** 에서만 접근 가능.  
> 외부 접근은 Nginx 설정 후 가능.

---

## 6. Nginx 설치 및 설정

### 6-1. Nginx 설치

```bash
apt install -y nginx
systemctl enable nginx
systemctl start nginx
```

### 6-2. 방화벽 설정

```bash
ufw allow OpenSSH    # SSH 먼저 (잠기지 않도록)
ufw allow 80/tcp     # HTTP (Let's Encrypt 챌린지 + 리다이렉트)
ufw allow 443/tcp    # HTTPS
# 8501은 열지 않음 — Nginx가 내부에서 프록시
ufw enable
ufw status
```

클라우드 Security Group / Firewall도 **TCP 80, 443** 허용.  
(8501 외부 오픈 불필요)

### 6-3. 설정 파일 배포

```bash
# 이 저장소에 포함된 Nginx 설정 파일 복사
cp /opt/investment/nginx/dashboard.glowbuff.com.conf \
   /etc/nginx/sites-available/dashboard.glowbuff.com

# 활성화
ln -s /etc/nginx/sites-available/dashboard.glowbuff.com \
      /etc/nginx/sites-enabled/

# 기본 사이트 비활성화 (충돌 방지)
rm -f /etc/nginx/sites-enabled/default

# 문법 검사
nginx -t
# 예상 출력: syntax is ok / test is successful
```

> **주의**: 이 단계에서 nginx -t 는 SSL 인증서 파일이 없어서 **오류**가 날 수 있음.  
> 다음 단계(Let's Encrypt 발급) 후 정상화됨.  
> SSL 인증서 없이 먼저 테스트하려면 아래 "임시 HTTP 전용 설정" 참고.

### 6-4. 임시 HTTP 전용 설정 (인증서 발급 전 테스트용)

```bash
# 임시 설정 — HTTPS 블록 없이 HTTP만
cat > /etc/nginx/sites-available/dashboard.glowbuff.com << 'EOF'
server {
    listen 80;
    server_name dashboard.glowbuff.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass         http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host       $host;
    }
}
EOF

nginx -t && systemctl reload nginx

# 접속 테스트 (HTTPS 없이)
curl -I http://dashboard.glowbuff.com
```

---

## 7. Let's Encrypt HTTPS 인증서 발급

### 7-1. Certbot 설치

```bash
apt install -y certbot python3-certbot-nginx
```

### 7-2. 인증서 발급

```bash
certbot --nginx \
    -d dashboard.glowbuff.com \
    --email admin@glowbuff.com \
    --agree-tos \
    --no-eff-email
```

**진행 과정 예시**

```
Saving debug log to /var/log/letsencrypt/letsencrypt.log
Requesting a certificate for dashboard.glowbuff.com

Successfully received certificate.
Certificate is saved at:
  /etc/letsencrypt/live/dashboard.glowbuff.com/fullchain.pem
Key is saved at:
  /etc/letsencrypt/live/dashboard.glowbuff.com/privkey.pem

Deploying certificate to VirtualHost /etc/nginx/sites-enabled/dashboard.glowbuff.com
...
Congratulations! You have successfully enabled HTTPS on https://dashboard.glowbuff.com
```

### 7-3. 본 설정 파일로 교체 (임시 설정 사용했을 경우)

```bash
# 이 저장소의 완성된 설정 파일로 교체
cp /opt/investment/nginx/dashboard.glowbuff.com.conf \
   /etc/nginx/sites-available/dashboard.glowbuff.com

nginx -t && systemctl reload nginx
```

### 7-4. 자동 갱신 확인

Let's Encrypt 인증서는 **90일** 유효. Certbot이 시스템 cron에 자동 갱신을 등록함.

```bash
# 자동 갱신 테스트 (실제 갱신 아님)
certbot renew --dry-run
# 출력: Congratulations, all simulated renewals succeeded

# 갱신 cron 확인
systemctl list-timers | grep certbot
# 또는
cat /etc/cron.d/certbot
```

### 7-5. 인증서 상태 확인

```bash
certbot certificates
```

```
Found the following certs:
  Certificate Name: dashboard.glowbuff.com
    Domains: dashboard.glowbuff.com
    Expiry Date: 2026-07-21 (VALID: 89 days)
    Certificate Path: /etc/letsencrypt/live/dashboard.glowbuff.com/fullchain.pem
    Private Key Path: /etc/letsencrypt/live/dashboard.glowbuff.com/privkey.pem
```

---

## 8. 최종 확인 및 검증

### 8-1. HTTPS 접속 확인

```bash
# 서버에서 HTTPS 응답 확인
curl -I https://dashboard.glowbuff.com
# 예상: HTTP/2 200

# SSL 인증서 상세 확인
curl -vI https://dashboard.glowbuff.com 2>&1 | grep -E "SSL|subject|issuer|expire"
```

브라우저에서:
```
https://dashboard.glowbuff.com
```

- [ ] 주소창 자물쇠(🔒) 표시됨
- [ ] 인증서 발급기관: Let's Encrypt
- [ ] 만료일 90일 이후로 설정됨

### 8-2. HTTP → HTTPS 리다이렉트 확인

```bash
curl -I http://dashboard.glowbuff.com
# 예상:
# HTTP/1.1 301 Moved Permanently
# Location: https://dashboard.glowbuff.com/
```

### 8-3. WebSocket 연결 확인

브라우저 개발자 도구(F12) → Network 탭 → WS(WebSocket) 필터:
- `wss://dashboard.glowbuff.com/_stcore/stream` 연결이 `101 Switching Protocols` 상태여야 함
- 연결이 `failed` 이면 Nginx WebSocket 설정 오류 → 섹션 6.3 재확인

### 8-4. 이메일 링크 확인

```bash
# 스케줄러 즉시 1회 실행
docker exec investment-scheduler python scheduler/scheduler.py --now
```

수신된 이메일에서:
- [ ] "대시보드에서 상세 보기" 버튼 클릭 → `https://dashboard.glowbuff.com` 으로 이동
- [ ] "로컬 PC에서 실행 중" 안내 문구가 표시되지 않음 (공개 URL 감지)

### 8-5. 모바일 접속

`https://dashboard.glowbuff.com` 을 스마트폰 브라우저에서 접속:
- [ ] HTTPS 자물쇠 표시
- [ ] 대시보드 정상 로딩
- [ ] 사이드바 햄버거 메뉴 동작

---

## 9. 운영 유지

### 인증서 갱신 확인 (30일마다 권장)

```bash
certbot certificates
# Expiry Date 확인
```

### 컨테이너 재시작 없이 설정 반영

```bash
# 수신 이메일, 스케줄 시각 변경:
# 대시보드 → 📧 이메일 설정 → 변경 후 💾 저장
# (재시작 불필요 — DB 설정으로 즉시 반영)

# BASE_URL 등 .env 변경 시:
nano /opt/investment/.env
cd /opt/investment && docker compose down && docker compose up -d
```

### 코드 업데이트

```bash
cd /opt/investment
git pull origin main
docker compose build --no-cache
docker compose up -d
```

### Nginx 설정 변경 후 적용

```bash
nginx -t                   # 문법 검사 먼저
systemctl reload nginx     # 무중단 적용
```

### 로그 위치

| 로그 종류 | 위치 |
|---------|------|
| Nginx 접속 로그 | `/var/log/nginx/dashboard.glowbuff.com.access.log` |
| Nginx 에러 로그 | `/var/log/nginx/dashboard.glowbuff.com.error.log` |
| 스케줄러 로그 | `docker compose logs scheduler` 또는 볼륨 내 `/app/logs/` |
| 대시보드 로그 | `docker compose logs dashboard` |
| Let's Encrypt 로그 | `/var/log/letsencrypt/letsencrypt.log` |

---

## 빠른 참조 — 자주 쓰는 명령어

```bash
# ── 서비스 관리 ───────────────────────────────
cd /opt/investment
docker compose up -d          # 시작
docker compose down           # 중지
docker compose restart        # 재시작
docker compose ps             # 상태 확인
docker stats                  # 리소스 확인

# ── 로그 ──────────────────────────────────────
docker compose logs -f                     # 전체 실시간
docker compose logs -f scheduler           # 스케줄러
docker compose logs --tail=50 dashboard    # 최근 50줄
tail -f /var/log/nginx/dashboard.glowbuff.com.access.log   # Nginx

# ── 즉시 분석 실행 ─────────────────────────────
docker exec investment-scheduler python scheduler/scheduler.py --now

# ── SSL 인증서 ────────────────────────────────
certbot certificates           # 상태 확인
certbot renew --dry-run        # 갱신 테스트

# ── DB 백업 ───────────────────────────────────
docker cp investment-dashboard:/app/db/investment.db \
    /opt/investment/backup/investment_$(date +%Y%m%d).db

# ── Nginx ─────────────────────────────────────
nginx -t                       # 설정 문법 검사
systemctl reload nginx         # 무중단 재로드
```
