"""원본 문자열 정규화. 시설명·주소·전화·지역코드·요일·시각을 다룹니다.

정규화 규칙은 data/mappings/normalization.md에 사람이 읽을 수 있게도 적습니다.
"""

from __future__ import annotations

import re

_PAREN = re.compile(r"[\(\[（【].*?[\)\]）】]")
_NONWORD = re.compile(r"[^0-9a-z가-힣]+")
_CORP = re.compile(r"(주식회사|\(주\)|㈜|사단법인|\(사\)|재단법인|\(재\)|유한회사)")
_ADDR_PAREN = re.compile(r"\(.*?\)")
_MULTISPACE = re.compile(r"\s+")

# 시도명 표기 차이("서울" vs "서울특별시") → 코드는 앞 2자리로 같으므로 코드를 우선 씁니다.
SIDO_SHORT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
    "31": "울산", "36": "세종", "41": "경기", "42": "강원", "51": "강원", "43": "충북",
    "44": "충남", "45": "전북", "52": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def norm_name(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ").replace("\n", " ").strip().lower()
    s = _CORP.sub("", s)
    s = _PAREN.sub("", s)
    s = _NONWORD.sub("", s)
    return s


def norm_address(s: str | None) -> str:
    """도로명 주소의 핵심(시군구 이후 도로명+건물번호)만 남깁니다.
    괄호 안 동·건물명, 층·호수, 공백은 제거합니다."""
    if not s:
        return ""
    s = s.replace("\xa0", " ").replace("\n", " ").strip()
    s = _ADDR_PAREN.sub("", s)
    s = _MULTISPACE.sub(" ", s).strip()
    # 세부주소(층·호)가 본주소 뒤에 붙어 있으면 잘라냅니다.
    s = re.split(r"\s+\d+층|\s+지하\s*\d*층|\s+\d+호", s)[0]
    s = re.sub(r"\s", "", s)
    return s.lower()


def norm_tel(s: str | None) -> str:
    if not s:
        return ""
    digits = re.sub(r"\D", "", s)
    if len(digits) < 8:
        return ""
    # 지역번호 없는 8자리는 그대로 두되, 0으로 시작하는 국번은 보존
    return digits


def sigungu5(code: str | None) -> str:
    """지역코드를 5자리 시군구 코드로. 10자리(2820000000)는 앞 5자리, 5자리는 그대로."""
    if not code:
        return ""
    c = re.sub(r"\D", "", code)
    if len(c) >= 5:
        return c[:5]
    return c


def sido2(code: str | None) -> str:
    c = sigungu5(code)
    return c[:2] if c else ""


def parse_time_hhmm(s: str | None) -> int | None:
    """'20:30' → 1230(분). 잘못된 값은 None."""
    if not s:
        return None
    m = re.match(r"^\s*(\d{1,2})\s*[:시]\s*(\d{1,2})?", s)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    if h > 24 or mi > 59:
        return None
    return h * 60 + mi


def parse_weekday_bits(s: str | None) -> list[int] | None:
    """'1111100' → [0,1,2,3,4] (월=0 … 일=6). 7자리 0/1이 아니면 None.
    선행 0이 사라진 값('11100')은 왼쪽을 0으로 채워 7자리로 해석하지 않습니다 —
    '월' 자리가 사라진 것인지 알 수 없기 때문입니다."""
    if not s:
        return None
    s = s.strip()
    if not re.fullmatch(r"[01]{7}", s):
        return None
    days = [i for i, ch in enumerate(s) if ch == "1"]
    return days or None


def parse_int(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.strip().replace(",", "")
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_float(s: str | None) -> float | None:
    if s is None or s.strip() == "":
        return None
    try:
        return float(s.strip().replace(",", ""))
    except ValueError:
        return None


def parse_coord(lon: str | None, lat: str | None) -> dict | None:
    x, y = parse_float(lon), parse_float(lat)
    if x is None or y is None or x == 0 or y == 0:
        return None
    if not (124 <= x <= 132 and 33 <= y <= 39):
        return None
    return {"type": "Point", "coordinates": [x, y]}
