"""익명 이용자 게시판과 인증이 필수인 관리자 제안 게시판."""

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.templates import templates
from app.db import suggestions_col
from app.routes.page_routes import _ctx
from app.security import is_admin, limiter, require_root

router = APIRouter(tags=["suggestions"])
Board = Literal["user", "admin"]
PAGE_SIZE = 20


class SuggestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=100)
    content: str = Field(min_length=5, max_length=5000)
    authorName: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("title", "content", "authorName")
    @classmethod
    def no_control_characters(cls, value: str | None) -> str | None:
        if value and any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("제어 문자는 입력할 수 없습니다.")
        return value


def _check_access(board: Board, request: Request) -> None:
    # The board remains private even when general admin authentication is disabled.
    if board == "admin" and not is_admin(request):
        raise HTTPException(401, "관리자 게시판은 로그인한 관리자만 이용할 수 있습니다.")


@router.get("/user/suggestions")
async def user_board(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="suggestions.html",
        context=await _ctx(request, app_mode="user", board="user"),
    )


@router.get("/admin/suggestions")
async def admin_board(request: Request):
    if not is_admin(request):
        return RedirectResponse(
            "/admin/login?next=" + quote("/admin/suggestions", safe=""), status_code=303
        )
    return templates.TemplateResponse(
        request=request,
        name="suggestions.html",
        context=await _ctx(request, board="admin"),
    )


@router.get("/api/suggestions/{board}")
async def list_suggestions(board: Board, request: Request, page: int = Query(1, ge=1, le=10000)):
    _check_access(board, request)
    query = {"board": board}
    total = await suggestions_col.count_documents(query)
    items = []
    cursor = (
        suggestions_col.find(query)
        .sort([("createdAt", -1), ("_id", -1)])
        .skip((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    async for doc in cursor:
        item = {
            "id": str(doc["_id"]),
            "title": doc["title"],
            "content": doc["content"],
            "createdAt": doc["createdAt"].isoformat(),
            "authorName": doc["authorName"] if board == "admin" else "익명",
        }
        if board == "admin":
            item["authorUsername"] = doc["authorUsername"]
        items.append(item)
    identity = getattr(request.state, "admin_identity", None)
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": PAGE_SIZE,
        "canModerate": bool(identity and identity.get("role") == "root"),
    }


@router.post("/api/suggestions/{board}", status_code=201)
async def create_suggestion(board: Board, body: SuggestionInput, request: Request):
    _check_access(board, request)
    identity = getattr(request.state, "admin_identity", None)
    if board == "admin" and not body.authorName:
        raise HTTPException(422, "작성자 이름을 입력해 주세요.")
    if board == "user" and body.authorName is not None:
        raise HTTPException(422, "이용자 게시판은 이름 없이 익명으로 작성합니다.")
    client = request.client.host if request.client else "unknown"
    actor = identity["username"] if board == "admin" else client
    if not limiter.allow((actor, f"suggestion_{board}"), 5, 3600):
        raise HTTPException(429, "제안은 1시간에 5건까지 등록할 수 있습니다.")
    doc = {
        "board": board,
        "title": body.title,
        "content": body.content,
        "createdAt": datetime.now(UTC),
    }
    if board == "admin":
        doc.update(authorName=body.authorName, authorUsername=identity["username"])
    result = await suggestions_col.insert_one(doc)
    return {"id": str(result.inserted_id), "detail": "제안을 등록했습니다."}


@router.delete("/api/suggestions/{board}/{post_id}")
async def delete_suggestion(board: Board, post_id: str, request: Request):
    _check_access(board, request)
    require_root(request)
    if not ObjectId.is_valid(post_id):
        raise HTTPException(404, "게시글을 찾을 수 없습니다.")
    result = await suggestions_col.delete_one({"_id": ObjectId(post_id), "board": board})
    if not result.deleted_count:
        raise HTTPException(404, "게시글을 찾을 수 없습니다.")
    return {"ok": True}
