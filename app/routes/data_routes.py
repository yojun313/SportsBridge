"""담당자용 데이터 관리: 출처 목록, 파일 교체 업로드, 전체 재적재, 진행 상태(서버 공유)."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from app.api.import_jobs import job
from app.config import DATA_RAW_DIR
from app.core.serialize import jsonable
from app.db import datasets_col
from app.security import is_admin, require_admin
from app.services import catalog_service
from app.services.dataset_files import FILES, ORDER, SOURCES, find_file

router = APIRouter(prefix="/api/data", tags=["data"])
RAW = Path(DATA_RAW_DIR)
MAX_UPLOAD = 1_200 * 1024 * 1024


async def _sources_overrides() -> dict:
    from app.db.mongo import db

    out = {}
    async for d in db["dataset_sources"].find(
        {}, {"_id": 1, "url": 1, "note": 1, "asOf": 1, "updatedAt": 1}
    ):
        out[d["_id"]] = d
    return out


@router.get("/sources")
async def sources():
    v = await catalog_service.active_version()
    info = await catalog_service.dataset_info(v) if v else None
    files_meta = {f["key"]: f for f in (info or {}).get("files", [])}
    steps = ((info or {}).get("log") or {}).get("steps", {})
    overrides = await _sources_overrides()
    rows = []
    for key in ORDER:
        p = find_file(RAW, key)
        st = p.stat() if p else None
        imported = files_meta.get(key)
        rows.append(
            {
                "key": key,
                "fileName": FILES[key],
                **SOURCES[key],
                **{k: v for k, v in (overrides.get(key) or {}).items() if k != "_id"},
                "present": bool(p),
                "bytes": st.st_size if st else None,
                "modifiedAt": datetime.fromtimestamp(st.st_mtime, UTC).isoformat() if st else None,
                "importedSha256": (imported or {}).get("sha256"),
                "importedBytes": (imported or {}).get("bytes"),
                "changedSinceImport": bool(imported and st and imported.get("bytes") != st.st_size),
            }
        )
    versions = []
    async for d in (
        datasets_col.find(
            {},
            {
                "_id": 0,
                "datasetVersion": 1,
                "status": 1,
                "importedAt": 1,
                "log.steps": 1,
                "log.elapsedSec": 1,
            },
        )
        .sort("importedAt", -1)
        .limit(8)
    ):
        versions.append(d)
    return jsonable(
        {
            "activeVersion": v,
            "rows": rows,
            "versions": versions,
            "job": job.snapshot(),
            "steps": steps,
        }
    )


class SourceEdit(BaseModel):
    url: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    asOf: str | None = Field(default=None, max_length=40)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(ord(c) < 32 for c in value)
        ):
            raise ValueError("http 또는 https 출처 주소를 입력해 주세요.")
        return value


@router.put("/sources/{key}")
async def edit_source(key: str, body: SourceEdit, request: Request):
    require_admin(request)
    if key not in FILES:
        raise HTTPException(404, "알 수 없는 데이터 키")
    from app.db.mongo import db

    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    upd["updatedAt"] = datetime.now(UTC)
    await db["dataset_sources"].update_one({"_id": key}, {"$set": upd}, upsert=True)
    return {"ok": True}


@router.post("/upload/{key}")
async def upload(key: str, request: Request, file: UploadFile = File(...)):  # noqa: B008
    """원본 CSV 교체. 임시 파일에 스트리밍 저장 후 원자적으로 바꿉니다. 적재는 별도 버튼으로 시작합니다."""
    require_admin(request)
    if key not in FILES:
        raise HTTPException(404, "알 수 없는 데이터 키")
    if job.snapshot()["status"] == "running":
        raise HTTPException(409, "적재가 진행 중입니다. 끝난 뒤 교체하세요.")
    name = file.filename or ""
    if not name.lower().endswith(".csv"):
        raise HTTPException(422, "CSV 파일만 올릴 수 있습니다")
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / unicodedata.normalize(
        "NFC", FILES[key]
    )  # 항상 풀어 놓은 .csv로 저장 (.csv.gz보다 우선 사용됨)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{key}.", suffix=".uploading", dir=RAW)
    tmp = Path(tmp_name)
    h = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await file.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "파일이 너무 큽니다 (1.2GB 제한)")
                h.update(chunk)
                out.write(chunk)
        with open(tmp, "rb") as fh:  # noqa: ASYNC230
            head = fh.read(4096)
        ok = False
        for cut in range(4):  # 4KB 경계에서 잘린 멀티바이트 문자를 최대 3바이트까지 보정
            try:
                head[: len(head) - cut].decode("utf-8-sig")
                ok = True
                break
            except UnicodeDecodeError:
                continue
        if not ok:
            raise HTTPException(422, "UTF-8 CSV가 아닙니다. 원본을 그대로 올려 주세요.")
        os.replace(tmp, target)  # 같은 이름의 .csv.gz가 있어도 .csv가 우선 사용되므로 그대로 둔다
    finally:
        tmp.unlink(missing_ok=True)
    return {"ok": True, "key": key, "bytes": size, "sha256": h.hexdigest(), "path": target.name}


@router.post("/import")
async def start_import(request: Request):
    require_admin(request)
    loop = asyncio.get_running_loop()
    if not job.start(RAW, loop):
        raise HTTPException(409, "이미 적재가 진행 중입니다")
    return {"ok": True, "job": job.snapshot()}


@router.get("/import/status")
async def import_status(request: Request):
    snapshot = job.snapshot()
    if not is_admin(request):
        return jsonable(
            {key: snapshot.get(key) for key in ("status", "percent", "stepLabel", "version")}
        )
    return jsonable(snapshot)
