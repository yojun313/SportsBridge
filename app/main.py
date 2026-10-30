import logging
import mimetypes
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ALLOWED_HOSTS, APP_NAME, BASE_URL
from app.core.paths import STATIC_DIR
from app.core.templates import templates
from app.db import create_indexes
from app.db.mongo import close, ping
from app.routes import (
    admin_auth_routes,
    agent_routes,
    candidate_routes,
    data_routes,
    gap_routes,
    llm_routes,
    metadata_routes,
    page_routes,
    planner_routes,
    scenario_routes,
    suggestion_routes,
    user_routes,
)
from app.security import admin_response, is_admin, is_admin_path, limiter, load_admin_identity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await ping()
        await create_indexes()
        logger.info("MongoDB 연결·인덱스 준비 완료")
    except Exception:
        logger.exception("MongoDB 준비 실패 — /ready 는 503을 돌려줍니다")
    yield
    await close()


app = FastAPI(
    title=APP_NAME,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

_MAX_BODY_BYTES = 2 * 1024 * 1024
_MAX_UPLOAD_BYTES = 1_200 * 1024 * 1024 + 1024 * 1024


@app.middleware("http")
async def headers_middleware(request: Request, call_next):
    request.state.csp_nonce = secrets.token_urlsafe(24)
    await load_admin_identity(request)
    path = request.url.path
    response = None
    if is_admin_path(path):
        response = admin_response(request)
        if response is not None and response.status_code == 401:
            client = request.client.host if request.client else "unknown"
            if not limiter.allow((client, "admin_auth"), 10, 300):
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "인증 시도가 많습니다. 잠시 뒤 다시 시도해 주세요."},
                    headers={"Retry-After": "300"},
                )
    if response is None and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
            response = JSONResponse(
                status_code=403, content={"detail": "외부 사이트의 요청은 허용되지 않습니다."}
            )
        elif request.headers.get("X-Requested-With") != "XMLHttpRequest":
            response = JSONResponse(
                status_code=403, content={"detail": "요청 확인 헤더가 필요합니다."}
            )
        else:
            length = request.headers.get("content-length")
            if length is None or not length.isdecimal():
                response = JSONResponse(
                    status_code=411, content={"detail": "Content-Length가 필요합니다."}
                )
            elif int(length) > (
                _MAX_UPLOAD_BYTES if path.startswith("/api/data/upload/") else _MAX_BODY_BYTES
            ):
                response = JSONResponse(status_code=413, content={"detail": "요청이 너무 큽니다."})
    if (
        response is None
        and path in {"/runs", "/api/agent/answer"}
        and request.method == "POST"
        and not is_admin(request)
    ):
        client = request.client.host if request.client else "unknown"
        if not limiter.allow((client, "agent"), 10, 3600):
            response = JSONResponse(
                status_code=429,
                content={"detail": "질문 요청이 많습니다. 잠시 뒤 다시 시도해 주세요."},
                headers={"Retry-After": "3600"},
            )
    if (
        response is None
        and path in {"/api/user/demand", "/api/user/vote"}
        and request.method == "POST"
    ):
        client = request.client.host if request.client else "unknown"
        if not limiter.allow((client, "signals"), 30, 3600):
            response = JSONResponse(
                status_code=429,
                content={"detail": "등록 요청이 많습니다. 잠시 뒤 다시 시도해 주세요."},
                headers={"Retry-After": "3600"},
            )
    if response is None:
        response = await call_next(request)
    if (
        path.startswith(("/api/", "/runs/"))
        or path in {"/runs", "/history", "/events"}
        or is_admin_path(path)
    ):
        response.headers["Cache-Control"] = "no-store"
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    h.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if BASE_URL.startswith("https://"):
        h.setdefault("Strict-Transport-Security", "max-age=31536000")
    h.setdefault(
        "Content-Security-Policy",
        f"default-src 'self'; script-src 'self' 'nonce-{request.state.csp_nonce}'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    return response


app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)
mimetypes.add_type("application/manifest+json", ".webmanifest")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(page_routes.router)
app.include_router(admin_auth_routes.router)
app.include_router(metadata_routes.router)
app.include_router(gap_routes.router)
app.include_router(candidate_routes.router)
app.include_router(scenario_routes.router)
app.include_router(llm_routes.router)
app.include_router(agent_routes.router)
app.include_router(user_routes.router)
app.include_router(data_routes.router)
app.include_router(suggestion_routes.router)
app.include_router(planner_routes.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    for error in errors:
        error.pop("input", None)
        error.pop("url", None)
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api") or exc.status_code != 404:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
        )
    return templates.TemplateResponse(
        request=request, name="errors/404.html", context={}, status_code=404
    )


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error at %s", request.url.path)
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    return templates.TemplateResponse(
        request=request, name="errors/500.html", context={}, status_code=500
    )
