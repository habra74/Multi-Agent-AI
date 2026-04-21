# 운영 체크리스트 — 투자 분석 시스템

> 서버 배포 전·후에 이 체크리스트를 순서대로 확인하세요.  
> `[ ]` → 완료 시 `[x]`로 표시하거나 종이에 체크.

---

## 1단계: 배포 전 준비 (로컬 PC에서)

### 1-1. 로컬 테스트 완료 확인
- [ ] `python -m pytest tests/ -v` → 215개 모두 통과
- [ ] `streamlit run dashboard.py` 로컬 실행 → 정상 표시
- [ ] `python scheduler/scheduler.py --now` → 분석 1회 완료
- [ ] 이메일 테스트 메일 수신 확인

### 1-2. SMTP 설정 재확인
- [ ] Gmail 2단계 인증 활성화 상태 확인
- [ ] 앱 비밀번호 16자리 준비 (계정 → 보안 → 앱 비밀번호)
- [ ] `SMTP_USER` = 발신자 이메일 주소
- [ ] `SMTP_PASSWORD` = 앱 비밀번호 (일반 로그인 비밀번호 아님!)
- [ ] `RECIPIENT_EMAIL` = 리포트 받을 이메일

### 1-3. Anthropic API 키 준비
- [ ] https://console.anthropic.com 에서 API 키 확인
- [ ] 키 형식: `sk-ant-api03-...`
- [ ] 크레딧 잔액 확인 (0이면 rule-based 모드로 품질 저하)

---

## 2단계: 서버 초기 설정

### 2-1. 서버 접속 및 기본 설정
- [ ] SSH 접속 성공: `ssh root@<서버IP>`
- [ ] `apt update && apt upgrade -y` 완료
- [ ] `apt install -y git curl wget nano ufw` 완료

### 2-2. Docker 설치
- [ ] `curl -fsSL https://get.docker.com | sh` 완료
- [ ] `docker --version` → 정상 출력
- [ ] `docker compose version` → 정상 출력
- [ ] `systemctl enable docker` → 부팅 시 자동 시작 설정
- [ ] `usermod -aG docker $USER && newgrp docker` → 권한 설정

---

## 3단계: 코드 배포

### 3-1. 파일 배포
- [ ] `/opt/investment` 디렉터리 생성
- [ ] `git clone ...` 또는 `scp` 업로드 완료
- [ ] `Dockerfile` 존재 확인: `ls /opt/investment/Dockerfile`
- [ ] `docker-compose.yml` 존재 확인
- [ ] `docker-entrypoint.sh` 존재 확인

---

## 4단계: 환경변수 설정

### 4-1. .env 파일 작성
- [ ] `cp .env.example .env` 실행
- [ ] `nano .env` 편집 완료
- [ ] `chmod 600 .env` 권한 제한

### 4-2. .env 항목별 체크
- [ ] `ANTHROPIC_API_KEY=sk-ant-...` 입력됨
- [ ] `SMTP_HOST=smtp.gmail.com`
- [ ] `SMTP_PORT=587`
- [ ] `SMTP_USER=your@gmail.com`
- [ ] `SMTP_PASSWORD=xxxx xxxx xxxx xxxx` (앱 비밀번호, 공백 포함 가능)
- [ ] `SENDER_EMAIL=your@gmail.com`
- [ ] `RECIPIENT_EMAIL=recipient@example.com`
- [ ] `SCHEDULER_TIME=07:00` (KST 기준)
- [ ] `BASE_URL=http://<서버IP>:8501` (또는 도메인 URL)

---

## 5단계: 방화벽 / 포트 설정

### 5-1. UFW 방화벽 (서버 내)
- [ ] `ufw allow OpenSSH` 실행 (먼저!)
- [ ] `ufw allow 8501/tcp` 실행 (방식 1) 또는 `ufw allow 80/tcp && ufw allow 443/tcp` (방식 2)
- [ ] `ufw enable` 실행
- [ ] `ufw status` → 포트 열림 확인

### 5-2. 클라우드 방화벽 (서비스 콘솔에서)

**방식 1 (포트 직접 오픈)**
- [ ] 클라우드 콘솔에서 TCP 8501 인바운드 허용
  - AWS: EC2 → 보안 그룹 → 인바운드 규칙 → 사용자 지정 TCP 8501
  - DigitalOcean: Networking → Firewalls → 8501 추가
  - Hetzner: Firewall → Inbound TCP 8501

**방식 2 (Nginx 사용)**
- [ ] 클라우드 콘솔에서 TCP 80, 443 인바운드 허용
- [ ] 8501은 외부 오픈 불필요

---

## 6단계: 컨테이너 실행

- [ ] `cd /opt/investment && docker compose build` 완료 (5~10분 소요)
- [ ] `docker compose up -d` 실행
- [ ] `docker compose ps` → 두 서비스 모두 `Up` 상태
- [ ] `docker compose ps` → dashboard 서비스 `(healthy)` 상태 (30초 후)

---

## 7단계: 기능 검증

### 7-1. 대시보드 접속
- [ ] 브라우저에서 `http://<서버IP>:8501` (또는 도메인) 접속 성공
- [ ] 메인 화면 로딩 정상 (흰 화면 또는 에러 없음)
- [ ] 5개 사이드바 메뉴 표시됨
- [ ] 운영 요약 4개 메트릭 표시됨

### 7-2. Watchlist 확인
- [ ] Watchlist 관리 메뉴에서 시드 데이터 3개 종목 표시됨
  (AAPL / NVDA / 005930.KS)

### 7-3. 즉시 실행 테스트
- [ ] 🏠 홈 대시보드 → 🚀 지금 즉시 실행 클릭
- [ ] 진행 바 동작 확인
- [ ] 분석 완료 후 리포트 목록에 오늘 날짜 리포트 표시됨

### 7-4. 이메일 수신 테스트
- [ ] 📧 이메일 설정 → 수신 이메일 입력 → 💾 저장
- [ ] 📧 테스트 메일 보내기 클릭 → "성공" 메시지
- [ ] 수신함에서 테스트 메일 확인
- [ ] 메일 내 "대시보드에서 상세 보기" 버튼 → 실제 URL로 연결됨

### 7-5. 스케줄러 확인
- [ ] `docker compose logs scheduler | grep "스케줄러 시작"` → 로그 확인
- [ ] `docker exec investment-scheduler date` → KST 시간 출력 확인
- [ ] 스케줄러 즉시 실행 테스트:
  `docker exec investment-scheduler python scheduler/scheduler.py --now`

---

## 8단계: 서버 재부팅 후 자동 복구 확인

- [ ] `reboot` 실행
- [ ] 2분 후 재접속
- [ ] `docker compose -f /opt/investment/docker-compose.yml ps` → 두 서비스 모두 `Up`

---

## 9단계: 모바일 접속 확인

- [ ] 스마트폰 브라우저(Chrome/Safari)에서 대시보드 URL 접속
- [ ] 메인 화면이 모바일에서 읽기 쉽게 표시됨
- [ ] 사이드바가 햄버거 버튼으로 접힘
- [ ] 리포트 상세 탭 탐색 가능

---

## 10단계: 자동 백업 설정 (선택)

- [ ] `crontab -e` 열기
- [ ] 아래 내용 추가:

```
50 6 * * * docker cp investment-dashboard:/app/db/investment.db /opt/investment/backup/investment_$(date +\%Y\%m\%d).db
0 7 * * 0 find /opt/investment/backup -name "*.db" -mtime +30 -delete
```

- [ ] `mkdir -p /opt/investment/backup` 디렉터리 생성
- [ ] `crontab -l` → 설정 확인

---

## 실제 운영 첫 주 확인 사항

| 날짜 | 확인 항목 | 결과 |
|------|---------|------|
| D+1 | 오전 7시 이메일 리포트 수신 | |
| D+1 | `docker compose logs scheduler` 에러 없음 | |
| D+3 | 대시보드 → 분석 이력 → 3일치 리포트 확인 | |
| D+7 | DB 백업 파일 생성 확인 (`ls /opt/investment/backup/`) | |
| D+7 | `docker system df` 디스크 사용량 확인 | |

---

## 문제 발생 시 트러블슈팅

| 증상 | 확인 명령 | 원인 및 해결 |
|------|---------|------------|
| 대시보드 접속 불가 | `docker compose ps` | 컨테이너 `Up` 상태인지 확인. `docker compose up -d` 재실행 |
| 이메일 발송 실패 | `docker compose logs scheduler` | SMTP 설정 오류. `.env` 앱 비밀번호 확인 |
| 분석 결과 없음 | `docker compose logs dashboard` | API 키 오류. `ANTHROPIC_API_KEY` 확인 |
| 스케줄러가 07:00에 안 실행 | `docker exec investment-scheduler date` | KST 시간인지 확인. 컨테이너 TZ=Asia/Seoul |
| 서버 재부팅 후 컨테이너 미시작 | `systemctl status docker` | Docker 데몬 미시작. `systemctl enable docker` |
| 포트 8501 접속 불가 | `curl http://localhost:8501/_stcore/health` | 방화벽 확인: `ufw status`, 클라우드 Security Group |
| Nginx 502 Bad Gateway | `curl http://localhost:8501` | 대시보드 컨테이너 미시작. `docker compose ps` 확인 |
