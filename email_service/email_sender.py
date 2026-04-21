"""
email_service/email_sender.py
------------------------------
SMTP 기반 이메일 발송 모듈.

주요 클래스:
  EmailSender  – HTML 리포트 이메일을 생성·발송

주요 함수:
  build_ticker_card(report_row)   – 종목별 HTML 카드 문자열 반환
  build_html_email(report_rows)   – 전체 이메일 HTML 문자열 반환
  send_daily_report(report_rows)  – 이메일 발송 + DB 로그 저장
"""

import smtplib
import logging
import os
import sys
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SENDER_EMAIL, RECIPIENT_EMAIL, BASE_URL, DB_PATH,
)

logger = logging.getLogger(__name__)

# Template path
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "report_template.html"

# ---------------------------------------------------------------------------
# Verdict display helpers
# ---------------------------------------------------------------------------

VERDICT_KO = {
    "STRONG BUY":    "적극 매수",
    "BUY":           "매수 고려",
    "HOLD":          "보유/관망",
    "CAUTIOUS HOLD": "신중 관망",
    "AVOID":         "회피",
}

VERDICT_CSS_CLASS = {
    "STRONG BUY":    "STRONG_BUY",
    "BUY":           "BUY",
    "HOLD":          "HOLD",
    "CAUTIOUS HOLD": "CAUTIOUS_HOLD",
    "AVOID":         "AVOID",
}

_SENTIMENT_KO = {
    "positive": "긍정",
    "negative": "부정",
    "neutral":  "중립",
    "mixed":    "혼재",
}

_SENTIMENT_COLOR = {
    "positive": "#1a7a1a",
    "negative": "#c0392b",
    "neutral":  "#6b7c93",
    "mixed":    "#c06000",
}


def _pct(v: float) -> str:
    return f"{round(v * 100)}%"


def _conf_label(v: float) -> str:
    pct = round(v * 100)
    label = (
        "매우 높음" if pct >= 80 else
        "높음"      if pct >= 65 else
        "보통"      if pct >= 45 else
        "낮음"      if pct >= 25 else
        "매우 낮음"
    )
    return f"{pct}% ({label})"


def _html_list(items: List[str], empty_msg: str = "없음") -> str:
    """Convert a list of strings to an HTML <ul> block."""
    if not items:
        return f"<li style='color:#aaa;'>{empty_msg}</li>"
    safe = [str(i).replace("<", "&lt;").replace(">", "&gt;") for i in items[:5]]
    return "".join(f"<li>{s}</li>" for s in safe)


def _build_news_html(evidence: List[Dict]) -> str:
    """Build an HTML block for up to 3 news items with interpretation and link."""
    if not evidence:
        return ""
    items_html = []
    for item in evidence[:3]:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline", "")).replace("<", "&lt;").replace(">", "&gt;")
        if not headline:
            continue
        interp   = str(item.get("interpretation", "")).replace("<", "&lt;").replace(">", "&gt;")
        link     = item.get("link", "")
        sent     = item.get("sentiment", "neutral")
        sent_ko  = _SENTIMENT_KO.get(sent, sent)
        sent_col = _SENTIMENT_COLOR.get(sent, "#6b7c93")
        cat_raw  = item.get("category", "")
        cat_ko   = {
            "earnings": "실적", "product": "제품", "analyst": "애널리스트",
            "legal": "법률/규제", "macro": "거시경제", "corporate": "기업이슈",
            "sentiment": "시장심리", "general": "일반",
        }.get(cat_raw, cat_raw)

        link_html = (
            f'<a href="{link}" style="color:#1a7abf;font-size:11px;">기사 보기 &rarr;</a>'
            if link else ""
        )
        items_html.append(f"""
        <div class="news-item">
          <div class="news-meta">
            <span class="news-tag" style="border-color:{sent_col};color:{sent_col};">{sent_ko}</span>
            {f'<span class="news-cat">{cat_ko}</span>' if cat_ko else ''}
          </div>
          <div class="news-headline">{headline}</div>
          {f'<div class="news-interp">{interp}</div>' if interp else ''}
          {link_html}
        </div>""")

    if not items_html:
        return ""
    return f"""
        <div class="news-section">
          <div class="section-title">주요 뉴스</div>
          {''.join(items_html)}
        </div>"""


# ---------------------------------------------------------------------------
# HTML card builder (one per ticker)
# ---------------------------------------------------------------------------

def build_ticker_card(report_row: Dict[str, Any]) -> str:
    """
    Build an HTML card for a single ticker report row.

    Expected keys in report_row:
        ticker, display_name, final_decision, confidence, risk_score,
        executive_summary, json_report  (JSON string with decision / news_analysis)
    """
    import json as _json

    ticker       = report_row.get("ticker", "")
    display_name = report_row.get("display_name", ticker)
    decision     = report_row.get("final_decision", "HOLD")
    confidence   = float(report_row.get("confidence", 0) or 0)
    risk_score   = float(report_row.get("risk_score", 0) or 0)
    summary      = (report_row.get("executive_summary") or "").strip()

    # Parse full JSON for bull/bear/action_items + news
    bull_points: List[str] = []
    bear_points: List[str] = []
    action_items: List[str] = []
    news_evidence: List[Dict] = []

    json_raw = report_row.get("json_report", "{}")
    try:
        data = _json.loads(json_raw) if isinstance(json_raw, str) else json_raw
        da   = data.get("decision", {})
        bull_points  = da.get("bull_points",  []) or []
        bear_points  = da.get("bear_points",  []) or []
        action_items = da.get("action_items", []) or []
        na = data.get("news_analysis", {})
        news_evidence = (na.get("evidence") or [])[:3]
    except Exception:
        pass

    # Verdict badge
    verdict_ko  = VERDICT_KO.get(decision, decision)
    verdict_cls = VERDICT_CSS_CLASS.get(decision, "HOLD")

    # Risk colour
    risk_color = (
        "#c0392b" if risk_score >= 0.7 else
        "#c06000" if risk_score >= 0.5 else
        "#9c8c00" if risk_score >= 0.3 else
        "#1a7a1a"
    )

    watch_items = action_items[:4]
    news_html   = _build_news_html(news_evidence)

    card = f"""
    <div class="ticker-card">
      <div class="card-header">
        <div>
          <div class="card-ticker">{ticker}</div>
          <div class="card-name">{display_name}</div>
        </div>
        <span class="verdict-badge verdict-{verdict_cls}">{verdict_ko}</span>
      </div>
      <div class="card-body">
        <!-- meta row -->
        <div class="meta-row">
          <div class="meta-item">
            <div class="meta-label">신뢰도</div>
            <div class="meta-value">{_conf_label(confidence)}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">리스크 점수</div>
            <div class="meta-value" style="color:{risk_color};">{risk_score:.2f} / 1.00</div>
          </div>
        </div>

        <!-- Executive summary -->
        {f'<div class="exec-summary">{summary}</div>' if summary else ''}

        <!-- Bull / Bear -->
        <div class="signal-row">
          <div class="signal-box bull">
            <div class="signal-title">긍정 요인</div>
            <ul>{_html_list(bull_points, "긍정 신호 없음")}</ul>
          </div>
          <div class="signal-box bear">
            <div class="signal-title">부정 요인</div>
            <ul>{_html_list(bear_points, "부정 신호 없음")}</ul>
          </div>
        </div>

        <!-- News section -->
        {news_html}

        <!-- Watch items -->
        {f'''<div class="watch-section">
          <div class="watch-title">향후 체크 포인트</div>
          <ul>{_html_list(watch_items, "특이사항 없음")}</ul>
        </div>''' if watch_items else ''}
      </div>
    </div>
    """
    return card


# ---------------------------------------------------------------------------
# Full email HTML builder
# ---------------------------------------------------------------------------

def build_html_email(
    report_rows: List[Dict[str, Any]],
    base_url: Optional[str] = None,
) -> str:
    """
    Render the full HTML email from a list of report rows.
    Loads report_template.html and injects rendered card blocks.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    ticker_cards = "\n".join(build_ticker_card(r) for r in report_rows)
    today_str    = date.today().strftime("%Y년 %m월 %d일")
    url          = base_url or BASE_URL

    # local notice: localhost URL일 때만 표시, 공개 URL이면 숨김
    is_local = "localhost" in url or "127.0.0.1" in url
    local_notice_html = (
        '<p class="local-notice">'
        '이 링크는 로컬 PC에서 대시보드가 실행 중일 때 열립니다.<br>'
        '실행 방법: <code>streamlit run dashboard.py</code>'
        "</p>"
        if is_local else
        '<p class="local-notice" style="color:#aab0bb;">'
        '대시보드가 실행 중인 서버에서 열립니다.'
        "</p>"
    )

    html = (
        template
        .replace("{{report_date}}", today_str)
        .replace("{{ticker_count}}", str(len(report_rows)))
        .replace("{{ticker_cards}}", ticker_cards)
        .replace("{{dashboard_url}}", url)
        .replace("{{local_notice}}", local_notice_html)
    )
    return html


# ---------------------------------------------------------------------------
# EmailSender class
# ---------------------------------------------------------------------------

class EmailSender:
    """
    SMTP 이메일 발송 클래스.

    Usage:
        sender = EmailSender()
        ok, err = sender.send(subject, html_body, recipient)
    """

    def __init__(
        self,
        smtp_host: str = SMTP_HOST,
        smtp_port: int = SMTP_PORT,
        smtp_user: str = SMTP_USER,
        smtp_password: str = SMTP_PASSWORD,
        sender_email: str = SENDER_EMAIL,
    ):
        self.smtp_host     = smtp_host
        self.smtp_port     = smtp_port
        self.smtp_user     = smtp_user
        self.smtp_password = smtp_password
        self.sender_email  = sender_email or smtp_user

    @property
    def is_configured(self) -> bool:
        """True if SMTP credentials are fully set."""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    def send(
        self,
        subject: str,
        html_body: str,
        recipient: str,
        cc_recipients: Optional[List[str]] = None,
        retries: int = 2,
    ) -> tuple[bool, str]:
        """
        Send a single HTML email (with optional CC).

        Returns (success: bool, error_message: str).
        """
        if not self.is_configured:
            msg = "SMTP 설정이 없습니다. .env 파일에 SMTP_* 환경 변수를 설정하세요."
            logger.warning(msg)
            return False, msg

        if not recipient:
            msg = "수신자 이메일 주소가 없습니다."
            logger.warning(msg)
            return False, msg

        cc_list = [e for e in (cc_recipients or []) if e.strip()]

        last_error = ""
        for attempt in range(1, retries + 2):
            try:
                msg_obj = MIMEMultipart("alternative")
                msg_obj["Subject"] = subject
                msg_obj["From"]    = self.sender_email
                msg_obj["To"]      = recipient
                if cc_list:
                    msg_obj["Cc"] = ", ".join(cc_list)

                # Attach HTML part
                msg_obj.attach(MIMEText(html_body, "html", "utf-8"))

                all_recipients = [recipient] + cc_list
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.sender_email, all_recipients, msg_obj.as_string())

                logger.info(f"이메일 발송 성공: {recipient} | 제목: {subject}")
                return True, ""

            except smtplib.SMTPAuthenticationError as e:
                last_error = f"인증 실패: {e}"
                logger.error(f"[시도 {attempt}] {last_error}")
                break  # 인증 오류는 재시도 불필요

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[시도 {attempt}/{retries + 1}] 이메일 발송 실패: {e}")

        return False, last_error


# ---------------------------------------------------------------------------
# High-level helper: 하루 리포트 일괄 발송
# ---------------------------------------------------------------------------

def send_daily_report(
    report_rows: List[Dict[str, Any]],
    recipient: Optional[str] = None,
    cc_recipients: Optional[List[str]] = None,
    db_path=None,
) -> bool:
    """
    하루 분석 리포트를 하나의 HTML 이메일로 묶어 발송.

    Parameters
    ----------
    report_rows   : ReportRepository.get_today() 반환값 (전체 row, json_report 포함)
    recipient     : 기본 수신자 이메일 (None → DB settings → config.RECIPIENT_EMAIL 순으로 조회)
    cc_recipients : 추가 수신자 목록 (None → DB settings 조회)
    db_path       : EmailLogRepository/SettingsRepository DB 경로 (None → config.DB_PATH)

    Returns True if email was sent successfully.
    """
    if db_path is None:
        db_path = DB_PATH

    from db.repository import EmailLogRepository, SettingsRepository
    log_repo  = EmailLogRepository(db_path)
    settings  = SettingsRepository(db_path)

    # Resolve recipient & CC from settings → fallback to config/env
    recipients_db = settings.get_recipients()
    to_addr  = recipient or recipients_db["primary"] or RECIPIENT_EMAIL
    cc_list  = cc_recipients if cc_recipients is not None else recipients_db["cc_list"]
    base_url = settings.get("base_url") or BASE_URL

    today   = date.today().strftime("%Y년 %m월 %d일")
    subject = f"[투자 분석] {today} 일일 리포트 ({len(report_rows)}개 종목)"

    if not report_rows:
        logger.info("발송할 리포트 없음 — 이메일 생략")
        log_repo.log(
            ticker="(none)", recipient=to_addr,
            status="skipped", error_message="리포트 없음",
        )
        return False

    try:
        html_body = build_html_email(report_rows, base_url=base_url)
    except Exception as e:
        err = f"HTML 생성 실패: {e}"
        logger.error(err)
        log_repo.log(ticker="(all)", recipient=to_addr, status="failed", error_message=err)
        return False

    sender = EmailSender()
    ok, err = sender.send(subject, html_body, to_addr, cc_recipients=cc_list)

    # Log result
    ticker_str = ", ".join(r.get("ticker", "") for r in report_rows)
    log_repo.log(
        ticker=ticker_str,
        recipient=to_addr,
        status="success" if ok else "failed",
        error_message=err,
    )

    if ok:
        logger.info(f"일일 리포트 발송 완료 → {to_addr} ({len(report_rows)}개 종목)")
    else:
        logger.error(f"일일 리포트 발송 실패: {err}")

    return ok
