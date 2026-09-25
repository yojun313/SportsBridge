from fastapi.templating import Jinja2Templates

from app.config import APP_FULL_NAME, APP_NAME, DEMO_MODE, LLM_ENABLED
from app.core.paths import STATIC_DIR, TEMPLATES_DIR


def asset(path: str) -> str:
    """정적 파일 URL에 mtime을 붙여 수정 즉시 새 버전이 내려가게 합니다."""
    file_path = STATIC_DIR / path.lstrip("/")
    try:
        version = int(file_path.stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{path.lstrip('/')}?v={version}"


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["APP_NAME"] = APP_NAME
templates.env.globals["APP_FULL_NAME"] = APP_FULL_NAME
templates.env.globals["DEMO_MODE"] = DEMO_MODE
templates.env.globals["LLM_ENABLED"] = LLM_ENABLED
templates.env.globals["asset"] = asset
