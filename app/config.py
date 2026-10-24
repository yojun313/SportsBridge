"""환경변수 설정. 비밀값은 .env에만 두고 여기서는 읽기만 합니다."""

import os
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


APP_NAME = os.getenv("APP_NAME", "스포츠브릿지")
APP_FULL_NAME = "스포츠 강좌이용권과 시설을 연결하는 지자체 공급 플래너"
ENV = os.getenv("ENV", "development")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8010")
COOKIE_SECURE = BASE_URL.startswith("https://")
ADMIN_AUTH_ENABLED = _bool("ADMIN_AUTH_ENABLED", "true")
ADMIN_ROOT_USERNAME = os.getenv("ADMIN_ROOT_USERNAME", "admin").strip().lower()
ADMIN_ROOT_PASSWORD = os.getenv("ADMIN_ROOT_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", os.getenv("MAIL_SENDER", "")).strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", os.getenv("MAIL_PASSWORD", ""))
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME).strip()
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]
if not ALLOWED_HOSTS:
    configured_host = urlsplit(BASE_URL).hostname or "localhost"
    ALLOWED_HOSTS = (
        list(dict.fromkeys([configured_host, "localhost", "127.0.0.1"]))
        if ENV == "development"
        else [configured_host]
    )
if ENV != "development":
    if not COOKIE_SECURE:
        raise ValueError("운영 환경의 BASE_URL은 https:// 주소여야 합니다.")
    if "*" in ALLOWED_HOSTS:
        raise ValueError("운영 환경에서 ALLOWED_HOSTS=* 는 허용되지 않습니다.")
if ADMIN_AUTH_ENABLED and (not ADMIN_ROOT_USERNAME or len(ADMIN_ROOT_PASSWORD) < 12):
    raise ValueError(
        "관리자 인증을 사용하려면 ADMIN_ROOT_USERNAME과 12자 이상의 ADMIN_ROOT_PASSWORD가 필요합니다."
    )

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("DB_NAME", "sportsbridge")
DATA_RAW_DIR = os.getenv("DATA_RAW_DIR", "./data/raw")
DEMO_MODE = _bool("DEMO_MODE", "true")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
# 키가 없으면 켜 두어도 동작할 수 없으므로 자동으로 꺼집니다.
LLM_ENABLED = _bool("LLM_ENABLED", "false") and bool(OPENAI_API_KEY)
# GPT-5.6 Luna: OpenAI 최저가 티어($0.20/$1.20 per 1M). 대화·문서·대량 추출 모두 같은 모델을 씁니다.
LLM_MODEL_MAIN = os.getenv("LLM_MODEL_MAIN", "gpt-5.6-luna")
LLM_MODEL_BULK = os.getenv("LLM_MODEL_BULK", "gpt-5.6-luna")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")
LLM_DAILY_BUDGET_USD = _float("LLM_DAILY_BUDGET_USD", 10.0)
LLM_PROMPT_VERSION = os.getenv("LLM_PROMPT_VERSION", "v1")
AGENT_MAX_TURNS = _int("AGENT_MAX_TURNS", 10)
AGENT_TIME_BUDGET_SECONDS = _float("AGENT_TIME_BUDGET_SECONDS", 90.0)

# 시제품 계산 상한 (아이디어2·4 문서)
MAX_DEMAND_GROUPS = 10
MAX_SUPPLY_OPTIONS = 30
MAX_ACTIONS = 10
