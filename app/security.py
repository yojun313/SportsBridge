"""담당자 화면 접근 제어와 요청 제한."""

import hashlib
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.config import ADMIN_AUTH_ENABLED, ADMIN_ROOT_PASSWORD, ADMIN_ROOT_USERNAME
from app.db import admin_sessions_col, admin_users_col

ADMIN_PREFIXES = (
    "/admin",
    "/gap",
    "/candidates",
    "/scenario",
    "/agent",
    "/data",
    "/api/admin",
    "/api/gap",
    "/api/candidates",
    "/api/scenarios",
    "/api/llm",
    "/api/data",
    "/history",
    "/events",
)
PUBLIC_ADMIN_PATHS = {"/admin/login", "/admin/signup", "/api/data/import/status"}
SESSION_COOKIE = "sportsbridge_admin_session"


def is_admin_path(path: str) -> bool:
    if path in PUBLIC_ADMIN_PATHS:
        return False
    return any(path == prefix or path.startswith(prefix + "/") for prefix in ADMIN_PREFIXES)


async def load_admin_identity(request: Request) -> None:
    request.state.admin_identity = None
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token or len(token) > 128:
        return
    session = await admin_sessions_col.find_one(
        {
            "tokenHash": hashlib.sha256(token.encode()).hexdigest(),
            "expiresAt": {"$gt": datetime.now(UTC)},
        }
    )
    if not session:
        return
    if session.get("role") == "root":
        expected = hashlib.sha256(ADMIN_ROOT_PASSWORD.encode()).hexdigest()
        if session.get("username") == ADMIN_ROOT_USERNAME and session.get("rootTag") == expected:
            request.state.admin_identity = {"username": ADMIN_ROOT_USERNAME, "role": "root"}
        return
    user = await admin_users_col.find_one(
        {"username": session.get("username"), "status": "approved"}
    )
    if user:
        request.state.admin_identity = {"username": user["username"], "role": "admin"}


def is_admin(request: Request) -> bool:
    return bool(getattr(request.state, "admin_identity", None))


def require_admin(request: Request) -> None:
    if ADMIN_AUTH_ENABLED and not is_admin(request):
        raise HTTPException(401, "관리자 로그인이 필요합니다.")


def require_root(request: Request) -> None:
    identity = getattr(request.state, "admin_identity", None)
    if not identity or identity.get("role") != "root":
        raise HTTPException(403, "루트 관리자만 사용할 수 있습니다.")


def admin_response(request: Request) -> Response | None:
    if not ADMIN_AUTH_ENABLED or is_admin(request):
        return None
    if (
        request.method == "GET"
        and not request.url.path.startswith("/api/")
        and request.url.path not in {"/history", "/events"}
    ):
        destination = quote(
            request.url.path + ("?" + request.url.query if request.url.query else ""), safe=""
        )
        return RedirectResponse(f"/admin/login?next={destination}", status_code=303)
    return JSONResponse(status_code=401, content={"detail": "관리자 로그인이 필요합니다."})


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
