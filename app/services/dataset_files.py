"""원본 CSV 파일 찾기와 데이터 출처 등록소. 파일명이 NFC/NFD 어느 쪽으로 저장돼 있어도 찾습니다."""

from __future__ import annotations

import unicodedata
from pathlib import Path

FILES = {
    "regional_usage": "데이터_지역별스포츠강좌이용권활용정보.csv",
    "voucher_facilities": "데이터_스포츠강좌이용권시설.csv",
    "voucher_courses": "데이터_스포츠강좌이용권이용시설강좌.csv",
    "voucher_usage": "데이터_스포츠강좌이용권.csv",
    "all_facilities": "데이터_전국체육시설현황.csv",
    "public_facilities": "데이터_전국공공체육시설.csv",
    "open_schools": "데이터_개방학교체육시설.csv",
    "safety": "데이터_체육시설안전점검정보.csv",
    "transit_voucher": "데이터_스포츠강좌이용권시설인접대중교통정보.csv",
    "transit_public": "데이터_체육시설인접대중교통정보.csv",
}

BASE = "https://www.bigdata-culture.kr/bigdata/user/data_market/detail.do?id="
SOURCES = {
    "regional_usage": {
        "title": "지역별 스포츠강좌이용권 활용정보",
        "url": BASE + "5b30e290-2594-11eb-af9a-4b03f0a582d6",
        "provider": "국민체육진흥공단",
        "cycle": "비정기",
        "role": "시군구 대상자·수급자·시설 수 (표준 지역코드)",
        "required": True,
    },
    "voucher_facilities": {
        "title": "스포츠강좌이용권 시설",
        "url": BASE + "98eb52c8-da31-462a-9c01-5b9cb2f9d077",
        "provider": "국민체육진흥공단",
        "cycle": "연간",
        "role": "가맹시설 이름·주소·전화·종목·좌표",
        "required": True,
    },
    "voucher_courses": {
        "title": "스포츠강좌이용권 이용시설 강좌",
        "url": BASE + "4e1a59b2-c54b-42a5-9a75-b86bb33ce279",
        "provider": "국민체육진흥공단",
        "cycle": "연간",
        "role": "강좌명·종목·요일·시각·설명",
        "required": True,
    },
    "voucher_usage": {
        "title": "스포츠강좌이용권 이용현황",
        "url": BASE + "04e1e27f-51fc-4ad2-a87b-112ea3b868e5",
        "provider": "국민체육진흥공단",
        "cycle": "비정기",
        "role": "시설·강좌별 월 신청 인원·가격 (강좌 기본 단위)",
        "required": True,
    },
    "all_facilities": {
        "title": "전국체육시설현황",
        "url": BASE + "3b5399ad-88c4-43aa-a1d7-7ef6a630370b",
        "provider": "국민체육진흥공단",
        "cycle": "비정기",
        "role": "업종·운영상태·주소·좌표 (비가맹 후보 모집단)",
        "required": True,
    },
    "public_facilities": {
        "title": "전국공공체육시설",
        "url": BASE + "b5880ea0-247a-4258-9f7b-79eab6751591",
        "provider": "국민체육진흥공단",
        "cycle": "연간",
        "role": "공공시설 보충",
        "required": False,
    },
    "open_schools": {
        "title": "개방학교 체육시설",
        "url": BASE + "ddd74830-f977-11eb-8e60-2bcdc8456bfb",
        "provider": "대한체육회",
        "cycle": "연간",
        "role": "학교 개방 공간·운영시간",
        "required": False,
    },
    "safety": {
        "title": "체육시설 안전점검정보",
        "url": BASE + "1762f1c0-2594-11eb-af9a-4b03f0a582d6",
        "provider": "국민체육진흥공단",
        "cycle": "비정기",
        "role": "안전등급·점검일",
        "required": False,
    },
    "transit_voucher": {
        "title": "이용권시설 인접 대중교통",
        "url": BASE + "914ac658-d64b-4fc9-add5-9773393bbe51",
        "provider": "국민체육진흥공단·산림빅데이터거래소",
        "cycle": "비정기",
        "role": "가맹시설 정류장 도보시간",
        "required": False,
    },
    "transit_public": {
        "title": "체육시설 인접 대중교통",
        "url": BASE + "615e7eb0-6e17-11ee-88b4-1384e6e2c3c9",
        "provider": "국민체육진흥공단·산림빅데이터거래소",
        "cycle": "비정기",
        "role": "공공시설 정류장 도보시간",
        "required": False,
    },
}
ORDER = list(FILES.keys())


def find_file(raw_dir: Path, key: str) -> Path | None:
    """원본 CSV를 찾는다. 풀어 놓은 .csv가 있으면 그것을, 없으면 git에 들어 있는 .csv.gz를 쓴다."""
    want = unicodedata.normalize("NFC", FILES[key])
    if not raw_dir.exists():
        return None
    gz = None
    for p in raw_dir.iterdir():
        name = unicodedata.normalize("NFC", p.name)
        if name == want:
            return p
        if name == want + ".gz":
            gz = p
    return gz
