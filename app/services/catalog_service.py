"""활성 데이터셋 버전·메타데이터·지역 목록. 요청마다 버전을 한 번 읽어 고정합니다."""

from __future__ import annotations

from fastapi import HTTPException

from app.config import DEMO_MODE, LLM_ENABLED, LLM_MODEL_BULK, LLM_MODEL_MAIN
from app.db import (
    CATALOG_STATE_ID,
    catalog_state_col,
    datasets_col,
    gap_aggregates_col,
    region_stats_col,
)


async def active_version() -> str | None:
    state = await catalog_state_col.find_one({"_id": CATALOG_STATE_ID})
    return state.get("activeVersion") if state else None


async def require_version() -> str:
    v = await active_version()
    if not v:
        raise HTTPException(
            status_code=503,
            detail="활성 데이터셋이 없습니다. scripts/import_datasets.py 로 적재하세요.",
        )
    return v


async def dataset_info(version: str) -> dict | None:
    doc = await datasets_col.find_one({"datasetVersion": version}, {"_id": 0})
    return doc


async def metadata() -> dict:
    v = await active_version()
    info = await dataset_info(v) if v else None
    sidos: dict[str, dict] = {}
    if v:
        async for r in region_stats_col.find(
            {"datasetVersion": v},
            {"_id": 0, "regionCode": 1, "sidoCode": 1, "sidoName": 1, "sigunguName": 1},
        ).sort("regionCode", 1):
            s = sidos.setdefault(
                r["sidoCode"], {"sidoCode": r["sidoCode"], "sidoName": r["sidoName"], "regions": []}
            )
            s["regions"].append({"regionCode": r["regionCode"], "name": r["sigunguName"]})
    log = (info or {}).get("log", {})
    agg = (
        await gap_aggregates_col.find_one(
            {"datasetVersion": v}, {"_id": 0, "dataMaxMonth": 1, "activeCutoffMonth": 1}
        )
        if v
        else None
    )
    return {
        "datasetVersion": v,
        "importedAt": (info or {}).get("importedAt"),
        "isSynthetic": (info or {}).get("isSynthetic", DEMO_MODE),
        "files": [
            {"key": f["key"], "name": f["name"], "sha256": f["sha256"][:16], "bytes": f["bytes"]}
            for f in (info or {}).get("files", [])
        ],
        "steps": log.get("steps", {}),
        "dataMaxMonth": (agg or {}).get("dataMaxMonth"),
        "activeCutoffMonth": (agg or {}).get("activeCutoffMonth"),
        "sidos": list(sidos.values()),
        "llm": {"enabled": LLM_ENABLED, "modelMain": LLM_MODEL_MAIN, "modelBulk": LLM_MODEL_BULK},
        "features": {
            "gap": bool(v),
            "candidates": bool(v),
            "scenario": bool(v),
            "agent": LLM_ENABLED,
            "documents": LLM_ENABLED,
            "extraction": LLM_ENABLED,
        },
    }


async def region_options(version: str) -> list[dict]:
    out = []
    async for r in region_stats_col.find(
        {"datasetVersion": version},
        {"_id": 0, "regionCode": 1, "sidoCode": 1, "sidoName": 1, "sigunguName": 1},
    ).sort("regionCode", 1):
        out.append(r)
    return out
