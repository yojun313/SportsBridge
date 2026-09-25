"""Collect public KSPO catalog metadata, not downloadable dataset contents."""
import concurrent.futures
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "https://www.bigdata-culture.kr/bigdata/user/data_market/process.ajax.do"


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def fetch(page):
    body = urllib.parse.urlencode({"currentPage": page, "TP": "organ", "publisherId": "kspo_org"}).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=body), timeout=30) as response:
        source = response.read().decode("utf-8")
    result = []
    pattern = r'box_cnt cnt01 dataMarcetDetail" data-id="([^"]+)"(.*?)(?=box_cnt cnt02)'
    for ident, block in re.findall(pattern, source, re.S):
        title = re.search(r'<p class="tit">(.*?)</p>', block, re.S)
        description = re.search(r'<p class="txt">(.*?)</p>', block, re.S)
        result.append({"id": ident, "title": clean(title.group(1)), "description": clean(description.group(1)) if description else "", "page": page,
                       "url": "https://www.bigdata-culture.kr/bigdata/user/data_market/detail.do?id=" + ident})
    total = re.search(r"센터 데이터\s*(\d+)개", source)
    return int(total.group(1)) if total else None, result


def main():
    total, first = fetch(1)
    if not total or not first:
        raise RuntimeError("Catalog format not recognized")
    pages = (total + len(first) - 1) // len(first)
    records = list(first)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for count, rows in pool.map(fetch, range(2, pages + 1)):
            if count != total:
                raise RuntimeError("Catalog changed during collection")
            records.extend(rows)
    if len(records) != total or len({r['id'] for r in records}) != total:
        raise RuntimeError(f"Incomplete catalog: {len(records)} / {total}")
    (ROOT / "kspo_catalog_2026-09-18.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 국민체육진흥공단 전체 상품 메타데이터 95종", "", "수집일: 2026-09-18. 원본 CSV가 아닌 공개 상품 목록의 설명입니다.", "", "기관 페이지: https://www.bigdata-culture.kr/bigdata/user/data_market/agency/detail.do?id=kspo_org", "", f"16개 목록 페이지 확인, 고유 상품 {len(records)}개 / 표시 총수 {total}개. 전체 상품 설명을 아이디어 검토 대상으로 사용했습니다. 다운로드 가능 여부·컬럼·원본 품질은 별도 검증 대상입니다.", ""]
    for index, row in enumerate(records, 1):
        lines += [f"## {index:02d}. {row['title']}", "", row["url"], "", row["description"], ""]
    (ROOT.parent / "00_전체데이터_95종_목록.md").write_text("\n".join(lines), encoding="utf-8")
    for index, row in enumerate(records, 1):
        print(f"{index:02d}. {row['title']} | {row['id']} | {row['description']}")


if __name__ == "__main__":
    main()
