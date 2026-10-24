"""관리자 로그인, 이메일 확인 가입과 루트 승인 API."""

import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.config import ADMIN_AUTH_ENABLED
from app.db import admin_sessions_col, admin_users_col
from app.security import limiter, require_root
from app.services import admin_auth_service

router = APIRouter(tags=["admin-auth"])
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not USERNAME_RE.fullmatch(value):
            raise ValueError(
                "아이디는 영문 소문자로 시작하고 영문 소문자·숫자·밑줄만 사용할 수 있습니다."
            )
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("올바른 이메일 주소를 입력해 주세요.")
        return value


class VerifyRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(pattern=r"^\d{6}$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


def _limit(request: Request, category: str, count: int, seconds: int) -> None:
    client = request.client.host if request.client else "unknown"
    if not limiter.allow((client, category), count, seconds):
        raise HTTPException(429, "요청이 많습니다. 잠시 후 다시 시도해 주세요.")


@router.post("/api/admin-auth/signup/request")
async def signup_request(body: SignupRequest, request: Request):
    _limit(request, "admin_signup", 5, 3600)
    await admin_auth_service.request_signup(body.username, body.email, body.password)
    return {"detail": "인증 코드를 보냈습니다. 메일을 확인해 주세요."}


@router.post("/api/admin-auth/signup/verify")
async def signup_verify(body: VerifyRequest, request: Request):
    _limit(request, "admin_verify", 10, 3600)
    await admin_auth_service.verify_signup(body.email, body.code)
    return {"detail": "이메일 확인을 마쳤습니다. 루트 관리자의 승인을 기다려 주세요."}


@router.post("/api/admin-auth/login")
async def login(body: LoginRequest, request: Request):
    _limit(request, "admin_login", 10, 300)
    identity = await admin_auth_service.authenticate(body.username, body.password)
    if not identity:
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    response = JSONResponse({"username": identity["username"], "role": identity["role"]})
    await admin_auth_service.create_session(response, identity)
    return response


@router.post("/api/admin-auth/logout")
async def logout(request: Request):
    response = JSONResponse({"ok": True})
    await admin_auth_service.delete_session(request, response)
    return response


@router.get("/api/admin-auth/me")
async def me(request: Request):
    return {
        "authEnabled": ADMIN_AUTH_ENABLED,
        "identity": getattr(request.state, "admin_identity", None),
    }


@router.get("/api/admin/members")
async def members(request: Request):
    require_root(request)
    users = []
    async for user in admin_users_col.find(
        {}, {"_id": 0, "username": 1, "email": 1, "status": 1, "createdAt": 1, "approvedAt": 1}
    ).sort("createdAt", -1):
        users.append(user)
    from app.core.serialize import jsonable

    return jsonable({"items": users})


@router.post("/api/admin/members/{username}/approve")
async def approve(username: str, request: Request):
    require_root(request)
    from datetime import UTC, datetime

    result = await admin_users_col.update_one(
        {"username": username.lower(), "emailVerified": True},
        {
            "$set": {
                "status": "approved",
                "approvedAt": datetime.now(UTC),
                "approvedBy": request.state.admin_identity["username"],
            }
        },
    )
    if not result.matched_count:
        raise HTTPException(404, "가입 신청을 찾을 수 없습니다.")
    return {"ok": True}


@router.post("/api/admin/members/{username}/reject")
async def reject(username: str, request: Request):
    require_root(request)
    result = await admin_users_col.update_one(
        {"username": username.lower()}, {"$set": {"status": "rejected"}}
    )
    if not result.matched_count:
        raise HTTPException(404, "가입 신청을 찾을 수 없습니다.")
    await admin_sessions_col.delete_many({"username": username.lower()})
    return {"ok": True}
