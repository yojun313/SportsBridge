import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import APP_NAME, ENV
from app.core.paths import STATIC_DIR
from app.core.templates import templates
from app.db import create_indexes
from app.db.mongo import close, ping
from app.routes import (
    agent_routes,
    candidate_routes,
    data_routes,
    gap_routes,
    llm_routes,
    metadata_routes,
    page_routes,
    review_routes,
    scenario_routes,
    user_routes,
)

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
    docs_url="/docs" if ENV == "development" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENV == "development" else None,
    lifespan=lifespan,
)

_MAX_BODY_BYTES = 2 * 1024 * 1024


@app.middleware("http")
async def headers_middleware(request: Request, call_next):
    length = request.headers.get("content-length")
    if (
        length
        and length.isdigit()
        and int(length) > _MAX_BODY_BYTES
        and not request.url.path.startswith("/api/data/upload/")
    ):
        return JSONResponse(status_code=413, content={"detail": "요청이 너무 큽니다."})
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    return response


app.add_middleware(GZipMiddleware, minimum_size=1024)
mimetypes.add_type("application/manifest+json", ".webmanifest")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(page_routes.router)
app.include_router(metadata_routes.router)
app.include_router(gap_routes.router)
app.include_router(candidate_routes.router)
app.include_router(scenario_routes.router)
app.include_router(llm_routes.router)
app.include_router(review_routes.router)
app.include_router(agent_routes.router)
app.include_router(user_routes.router)
app.include_router(data_routes.router)


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
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
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
