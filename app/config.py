"""환경변수 설정. 비밀값은 .env에만 두고 여기서는 읽기만 합니다."""

import os

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
APP_FULL_NAME = "이용권과 시설을 잇는 지자체 공급 플래너"
ENV = os.getenv("ENV", "development")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8010")
COOKIE_SECURE = BASE_URL.startswith("https://")

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
