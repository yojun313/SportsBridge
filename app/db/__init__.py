"""컬렉션 등록소. 모든 컬렉션은 여기서 한 번 선언하고 import해 씁니다.

INDEX_SPECS는 비동기(앱 시작)와 동기(적재 스크립트) 양쪽에서 같은 인덱스를 만들기 위한 단일 정의입니다.
"""

from app.db.mongo import db

datasets_col = db["datasets"]
catalog_state_col = db["catalog_state"]
facilities_all_col = db["facilities_all"]
facilities_voucher_col = db["facilities_voucher"]
courses_col = db["courses"]
course_facts_col = db["course_facts"]
facility_class_col = db["facility_class"]
usage_monthly_col = db["usage_monthly"]
region_stats_col = db["region_stats"]
match_results_col = db["match_results"]
gap_aggregates_col = db["gap_aggregates"]
review_queue_col = db["review_queue"]
llm_calls_col = db["llm_calls"]
agent_history_col = db["agent_history"]
demand_signals_col = db["demand_signals"]
votes_col = db["facility_votes"]

CATALOG_STATE_ID = "catalog"

# 적재 때 통째로 교체되는 컬렉션 (staging → rename)
VERSIONED_COLLECTIONS = ["region_stats", "facilities_voucher", "courses", "usage_monthly", "facilities_all", "match_results", "gap_aggregates"]

INDEX_SPECS: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "datasets": [([("datasetVersion", 1)], {"unique": True})],
    "facilities_all": [([("datasetVersion", 1), ("sourceFacilityId", 1)], {}), ([("datasetVersion", 1), ("regionCode", 1)], {}),
                       ([("datasetVersion", 1), ("nameNorm", 1), ("addressNorm", 1)], {}),
                       ([("datasetVersion", 1), ("regionCode", 1), ("voucherMatch", 1), ("status", 1)], {}), ([("name", 1)], {})],
    "facilities_voucher": [([("datasetVersion", 1), ("sourceFacilityId", 1)], {}), ([("datasetVersion", 1), ("regionCode", 1)], {}),
                           ([("datasetVersion", 1), ("nameNorm", 1), ("addressNorm", 1)], {}), ([("name", 1)], {}), ([("regionCode", 1), ("usage.last12mApplicants", -1)], {})],
    "courses": [([("datasetVersion", 1), ("facilityId", 1)], {}), ([("datasetVersion", 1), ("regionCode", 1), ("sport", 1)], {}),
                ([("datasetVersion", 1), ("sourceCourseId", 1)], {}), ([("regionCode", 1), ("lastMonth", -1)], {})],
    "course_facts": [([("datasetVersion", 1), ("courseId", 1)], {"unique": True})],
    "facility_class": [([("datasetVersion", 1), ("facilityId", 1)], {"unique": True})],
    "usage_monthly": [([("datasetVersion", 1), ("facilityId", 1), ("yearMonth", 1)], {})],
    "region_stats": [([("datasetVersion", 1), ("regionCode", 1)], {"unique": True})],
    "match_results": [([("datasetVersion", 1), ("allFacilityId", 1)], {}), ([("datasetVersion", 1), ("voucherFacilityId", 1)], {"unique": True}), ([("datasetVersion", 1), ("status", 1)], {})],
    "gap_aggregates": [([("datasetVersion", 1), ("regionCode", 1)], {"unique": True})],
    "review_queue": [([("status", 1), ("kind", 1), ("createdAt", -1)], {})],
    "llm_calls": [([("createdAt", 1)], {}), ([("inputHash", 1), ("promptVersion", 1), ("model", 1)], {})],
    "agent_history": [([("createdAt", 1)], {})],
    "demand_signals": [([("regionCode", 1), ("sport", 1), ("createdAt", -1)], {})],
    "facility_votes": [([("facilityId", 1)], {}), ([("regionCode", 1)], {})],
}


async def create_indexes() -> None:
    for col, specs in INDEX_SPECS.items():
        for keys, opts in specs:
            await db[col].create_index(keys, **opts)


def create_indexes_sync(sync_db, collections: list[str] | None = None) -> None:
    for col, specs in INDEX_SPECS.items():
        if collections and col not in collections:
            continue
        for keys, opts in specs:
            sync_db[col].create_index(keys, **opts)
