"""관리 기능 인증과 요청 제한에 사용하는 공통 보안 규칙."""

import base64
import binascii
import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import ADMIN_TOKEN

ADMIN_PREFIXES = (
    "/gap",
    "/candidates",
    "/scenario",
    "/agent",
    "/review",
    "/data",
    "/api/gap",
    "/api/candidates",
    "/api/scenarios",
    "/api/review",
    "/api/llm",
    "/api/data",
    "/history",
    "/events",
)


def is_admin_path(path: str) -> bool:
    if path == "/api/data/import/status":
        return False
    return any(path == prefix or path.startswith(prefix + "/") for prefix in ADMIN_PREFIXES)


def is_admin(request: Request) -> bool:
    if not ADMIN_TOKEN:
        return False
    supplied = request.headers.get("X-Admin-Token", "")
    if supplied and hmac.compare_digest(supplied.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")):
        return True
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False
    username, separator, password = raw.partition(":")
    return (
        bool(separator)
        and username == "admin"
        and hmac.compare_digest(password.encode("utf-8"), ADMIN_TOKEN.encode("utf-8"))
    )


def require_admin(request: Request) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(503, "관리자 기능을 사용하려면 ADMIN_TOKEN을 설정해야 합니다.")
    if not is_admin(request):
        raise HTTPException(
            401,
            "관리자 인증이 필요합니다.",
            headers={"WWW-Authenticate": 'Basic realm="SportsBridge admin"'},
        )


def admin_response(request: Request) -> JSONResponse | None:
    try:
        require_admin(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    return None


class RateLimiter:
    """단일 프로세스의 과도한 공개 쓰기·AI 요청을 제한합니다."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, key: tuple[str, str], limit: int, period: int) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] <= now - period:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:
            self._hits = defaultdict(
                deque, {k: v for k, v in self._hits.items() if v and v[-1] > now - 3600}
            )
        return True


limiter = RateLimiter()
