"""관리자 가입, 메일 확인, 승인 및 세션 저장."""

import asyncio
import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from app.config import (
    ADMIN_ROOT_PASSWORD,
    ADMIN_ROOT_USERNAME,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)
from app.db import admin_sessions_col, admin_signups_col, admin_users_col
from app.security import SESSION_COOKIE

logger = logging.getLogger(__name__)
CODE_LIFETIME = timedelta(minutes=10)
SESSION_LIFETIME = timedelta(days=7)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) > 1_000_000:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def _send_code(email: str, code: str) -> None:
    message = EmailMessage()
    message["Subject"] = "[스포츠브릿지] 관리자 가입 이메일 확인"
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(
        f"관리자 가입 확인 코드: {code}\n\n10분 안에 입력해 주세요. 본인이 신청하지 않았다면 이 메일을 무시해 주세요."
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)


async def request_signup(username: str, email: str, password: str) -> None:
    username, email = username.strip().lower(), email.strip().lower()
    if not all((SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM)):
        raise HTTPException(503, "메일 발송 설정이 없어 관리자 가입을 진행할 수 없습니다.")
    if username == ADMIN_ROOT_USERNAME:
        raise HTTPException(409, "사용할 수 없는 아이디입니다.")
    if await admin_users_col.find_one({"$or": [{"username": username}, {"email": email}]}):
        raise HTTPException(409, "이미 등록된 아이디 또는 이메일입니다.")
    now = datetime.now(UTC)
    previous = await admin_signups_col.find_one({"$or": [{"username": username}, {"email": email}]})
    if previous:
        if previous["username"] != username or previous["email"] != email:
            raise HTTPException(409, "이미 사용 중인 아이디 또는 이메일입니다.")
        if previous.get("sentAt", now) > now - timedelta(seconds=60):
            raise HTTPException(429, "잠시 후 인증 코드를 다시 요청해 주세요.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    try:
        await asyncio.to_thread(_send_code, email, code)
    except (OSError, smtplib.SMTPException):
        logger.exception("관리자 가입 확인 메일 발송 실패")
        raise HTTPException(
            503, "인증 메일을 보내지 못했습니다. 메일 설정을 확인해 주세요."
        ) from None
    doc = {
        "username": username,
        "email": email,
        "passwordHash": hash_password(password),
        "codeHash": hashlib.sha256((salt + code).encode()).hexdigest(),
        "codeSalt": salt,
        "attempts": 0,
        "sentAt": now,
        "expiresAt": now + CODE_LIFETIME,
    }
    try:
        await admin_signups_col.replace_one(
            {"username": username, "email": email}, doc, upsert=True
        )
    except DuplicateKeyError:
        raise HTTPException(409, "이미 사용 중인 아이디 또는 이메일입니다.") from None


async def verify_signup(email: str, code: str) -> None:
    email = email.strip().lower()
    now = datetime.now(UTC)
    doc = await admin_signups_col.find_one_and_update(
        {"email": email, "expiresAt": {"$gt": now}, "attempts": {"$lt": 5}},
        {"$inc": {"attempts": 1}},
        return_document=ReturnDocument.BEFORE,
    )
    if not doc:
        raise HTTPException(400, "인증 요청이 만료되었습니다. 다시 신청해 주세요.")
    digest = hashlib.sha256((doc["codeSalt"] + code.strip()).encode()).hexdigest()
    if not hmac.compare_digest(digest, doc["codeHash"]):
        raise HTTPException(400, "인증 코드가 올바르지 않습니다.")
    try:
        await admin_users_col.insert_one(
            {
                "username": doc["username"],
                "email": email,
                "passwordHash": doc["passwordHash"],
                "emailVerified": True,
                "status": "pending",
                "createdAt": now,
            }
        )
    except DuplicateKeyError:
        raise HTTPException(409, "이미 등록된 아이디 또는 이메일입니다.") from None
    await admin_signups_col.delete_one({"_id": doc["_id"]})


async def authenticate(username: str, password: str) -> dict | None:
    username = username.strip().lower()
    if username == ADMIN_ROOT_USERNAME and ADMIN_ROOT_PASSWORD:
        if hmac.compare_digest(password.encode(), ADMIN_ROOT_PASSWORD.encode()):
            return {"username": username, "role": "root"}
        return None
    user = await admin_users_col.find_one({"username": username})
    if not user or not verify_password(password, user.get("passwordHash", "")):
        return None
    if user.get("status") != "approved":
        raise HTTPException(403, "계정 승인 후 로그인할 수 있습니다.")
    return {"username": username, "role": "admin"}


async def create_session(response, identity: dict) -> None:
    from app.config import COOKIE_SECURE

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    await admin_sessions_col.insert_one(
        {
            "tokenHash": hashlib.sha256(token.encode()).hexdigest(),
            "username": identity["username"],
            "role": identity["role"],
            "rootTag": hashlib.sha256(ADMIN_ROOT_PASSWORD.encode()).hexdigest()
            if identity["role"] == "root"
            else None,
            "createdAt": now,
            "expiresAt": now + SESSION_LIFETIME,
        }
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


async def delete_session(request, response) -> None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        await admin_sessions_col.delete_one(
            {"tokenHash": hashlib.sha256(token.encode()).hexdigest()}
        )
    response.delete_cookie(SESSION_COOKIE, path="/")
