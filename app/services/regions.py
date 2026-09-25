"""지역코드 표준화.

표준 코드는 26번(지역별스포츠강좌이용권활용정보)의 5자리 시군구 코드입니다.
2026년 행정 개편으로 생긴 신형 코드(12xxx 전남광주통합특별시)와 구형 코드(42 강원, 45 전북)는
시도 묶음 + 시군구명으로 표준 코드에 붙입니다. 붙지 못하면 원래 코드를 유지하고 unmapped로 표시합니다.
"""

from __future__ import annotations

from app.services.normalization_service import sigungu5

# 신·구 시도 코드 → 표준(26번) 시도 코드 후보
SIDO_ALIASES: dict[str, list[str]] = {
    "12": ["29", "46"],  # 전남광주통합특별시 → 광주(29) 또는 전남(46)
    "42": ["51"],        # 강원도 → 강원특별자치도
    "45": ["52"],        # 전라북도 → 전북특별자치도
    "47": ["47", "27"],  # 군위군: 경북 → 대구 편입
}

# 행정구역 개편·구명 변경으로 26번에 없는 이름. (시도코드, 이름) → 표준 코드.
# 인천 2026 개편(제물포구·영종구·검단구·서해구)은 옛 중구·서구로 근사 매핑하며, 화면에 근사임을 표시합니다.
NAME_ALIASES: dict[tuple[str, str], str] = {
    ("28", "제물포구"): "28110", ("28", "영종구"): "28110", ("28", "검단구"): "28260",
    ("28", "서해구"): "28260", ("28", "남구"): "28177",
}


class RegionResolver:
    def __init__(self, regions: list[dict]):
        """regions: [{regionCode, sidoCode, sidoName, sigunguName}] (26번 기준)."""
        self.by_code = {r["regionCode"]: r for r in regions}
        self.by_sido_name: dict[tuple[str, str], str] = {}
        for r in regions:
            self.by_sido_name[(r["sidoCode"], _nm(r["sigunguName"]))] = r["regionCode"]
        self.unmapped: dict[str, str] = {}

    def resolve(self, code: str | None, sigungu_name: str | None) -> tuple[str, bool]:
        """(표준 5자리 코드, 매핑 성공 여부). 실패 시 원래 5자리 코드를 돌려줍니다."""
        c5 = sigungu5(code)
        if c5 in self.by_code:
            return c5, True
        sido = c5[:2]
        name = _nm(sigungu_name)
        candidates = SIDO_ALIASES.get(sido, []) + [sido]
        for sd in candidates:
            hit = self.by_sido_name.get((sd, name))
            if hit:
                return hit, True
        alias = NAME_ALIASES.get((sido, name))
        if alias and alias in self.by_code:
            return alias, True
        # 시 안의 구(41111 수원시 장안구)는 상위 시 코드(41110)로
        if len(c5) == 5 and c5[4] != "0":
            parent = c5[:4] + "0"
            if parent in self.by_code:
                return parent, True
        # "수원시 장안구"처럼 시+구가 붙은 이름은 앞쪽 시 이름으로 재시도
        if name:
            for sd in candidates:
                hits = [v for k, v in self.by_sido_name.items()
                        if k[0] == sd and len(k[1]) >= 2 and (name.startswith(k[1]) or name.endswith(k[1]))]
                if len(hits) == 1:
                    return hits[0], True
            # 전국에서 유일한 이름이면 시도가 달라도 붙입니다(군위군 등 편입 사례)
            hits = [v for k, v in self.by_sido_name.items() if k[1] == name]
            if len(hits) == 1:
                return hits[0], True
        if c5:
            self.unmapped[c5] = sigungu_name or ""
        return c5, False

    def name_of(self, code: str) -> str:
        r = self.by_code.get(code)
        return f"{r['sidoName']} {r['sigunguName']}" if r else code


def _nm(s: str | None) -> str:
    return (s or "").replace(" ", "").strip()
