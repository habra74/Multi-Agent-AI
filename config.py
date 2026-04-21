import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DB_DIR = BASE_DIR / "db"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "investment.db"

# ── LLM ──────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = "claude-opus-4-6"

# ── Analysis defaults ─────────────────────────────────────────────────────────
DEFAULT_MARKET           = "US"
DEFAULT_INVESTMENT_STYLE = "neutral"
DEFAULT_HORIZON          = "mid"
DEFAULT_LANGUAGE         = "ko"

PRICE_HISTORY_DAYS = 365
SHORT_MA = 20
MID_MA   = 50
LONG_MA  = 200

INVESTMENT_STYLES = ["conservative", "neutral", "aggressive"]
HORIZONS          = ["short", "mid", "long"]
MARKETS           = ["US", "KR"]
LANGUAGES         = ["ko", "en"]

# ── Email (SMTP) ──────────────────────────────────────────────────────────────
SMTP_HOST      = os.getenv("SMTP_HOST",      "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT",  "587"))
SMTP_USER      = os.getenv("SMTP_USER",      "")
SMTP_PASSWORD  = os.getenv("SMTP_PASSWORD",  "")
SENDER_EMAIL   = os.getenv("SENDER_EMAIL",   SMTP_USER)
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")

# ── Scheduler ─────────────────────────────────────────────────────────────────
# Format: "HH:MM"  (24-hour local time)
SCHEDULER_TIME = os.getenv("SCHEDULER_TIME", "07:00")

# ── Web dashboard ─────────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "http://localhost:8501")
