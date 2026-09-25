# 개발 설계 — Commeet 아키텍처·디자인 참조

작성일: 2026-09-18 / 상태: 구현 전 설계 초안

개발 담당: Claude. 이 문서는 현재 개발이 완료되었다는 보고가 아닙니다. 서비스의 차별화 확정과 실제 CSV 검증은 선행 조건입니다.

## 1. 구현 위치와 참조 원칙

- 개발 위치: `/home/yojun/sports`.
- 참조 프로젝트: `/home/yojun/Commeet`.
- 확인한 참조 커밋: `ba8992a`. 조사 시 `git status --short` 출력은 없었습니다.
- Commeet의 FastAPI·MongoDB·Jinja2·바닐라 JS 구조를 그대로 따릅니다.
- 별도의 React/Next.js 프런트엔드, SQLAlchemy/PostgreSQL 구조로 바꾸지 않습니다.
- Commeet의 코드 구조·디자인 패턴을 참고하되 새 프로젝트의 모듈로 구현합니다. 런타임에서 Commeet를 import하지 않습니다.
- Commeet의 `.env`, 데이터베이스, `instance/` 내부 파일, SSH·메일·OAuth 자격증명은 읽어 복제하거나 사용하지 않습니다. 기존 서비스를 실행하거나 수정할 필요도 없습니다.

## 2. 실제 코드에서 확인한 구조

| 참조 파일 | 확인한 역할 | 새 프로젝트 적용 |
|---|---|---|
| `run.py` | dotenv 로드, Uvicorn, 루프백 기본 바인딩, `app` 디렉터리만 reload 감시 | 같은 진입 방식, 별도 포트 8010 |
| `app/config.py` | 환경변수 설정 모음 | 서비스 전용 설정 모음 |
| `app/main.py` | 앱 생성, 미들웨어, `/static`, 라우터, 예외 처리 | 동일한 책임 분리 |
| `app/db/mongo.py` | Motor `AsyncIOMotorClient` 생성 지점, ping·close | DB 연결은 이곳에서만 |
| `app/db/__init__.py` | 컬렉션 핸들 및 `create_indexes` | 중앙 컬렉션 등록 |
| `app/core/templates.py` | Jinja 환경, 공통 값, mtime 기반 `asset()` | 같은 템플릿·자산 버전 방식 |
| `app/routes/page_routes.py` | 페이지 응답과 템플릿 문맥 | HTML 전용 라우트 |
| `app/routes/event_routes.py` | `/api/...` JSON API, 스키마·서비스 호출 | 시설·강좌·추천 API |
| `app/services/event_service.py` | 도메인 로직, 중앙 컬렉션 import | 검색·추천·정규화 서비스 |
| `app/schemas/event.py` | Pydantic 입력 검증 | 조건·추천 응답 검증 |
| `app/templates/base.html` | header·footer·CSS·공통 JS | 같은 상속 구조 |
| `app/static/js/api.js` | same-origin fetch, JSON·에러 처리 | 동일한 API 래퍼 패턴 |
| `app/static/js/event-grid.js` | 클릭·드래그 시간 선택 | 상호작용 패턴 참조, 주간 운동용으로 구현 |

주의: Commeet README에는 요일 반복·그룹 일정이 소개되지만 **현재 `app/schemas/event.py` 주석은 새 일정이 특정 날짜 방식으로 제한된다고 설명합니다.** README의 기능 목록을 현재 구현으로 간주하지 마세요. 기존 그리드의 날짜 타임스탬프 모델을 새 주간 반복 모델에 그대로 복사하지 않습니다.

참조는 Python 3.12 이상, `uv`, FastAPI, Jinja2, Motor/PyMongo를 사용합니다. 버전은 참조 `pyproject.toml`과 잠금파일을 기반으로 실행 호환성을 검증하고 새 프로젝트에서 잠급니다. 이 문서는 해당 버전을 최신·권장 버전으로 보증하지 않습니다. DB 드라이버 교체가 필요하면 호환성 문제를 문서화하고 단일 DB 모듈 경계를 유지합니다.

## 3. 목표 디렉터리

```text
sports/
  run.py
  pyproject.toml
  uv.lock
  .env.example
  .gitignore
  app/
    __init__.py
    main.py
    config.py
    core/
      paths.py
      templates.py
      serialize.py
    db/
      mongo.py
      __init__.py
    schemas/
      search.py
      recommendation.py
      plan.py
    routes/
      page_routes.py
      facility_routes.py
      course_routes.py
      recommendation_routes.py
      metadata_routes.py
    services/
      catalog_service.py
      recommendation_service.py
      schedule_service.py
      normalization_service.py
      dataset_service.py
    templates/
      base.html
      landing.html
      planner.html
      course_detail.html
      compare.html
      plan.html
      data_info.html
      partials/
        header.html
        footer.html
        course_card.html
        weekly_grid.html
      errors/
        404.html
        500.html
    static/
      css/style.css
      js/api.js
      js/ui.js
      js/weekly-grid.js
      js/planner.js
      js/compare.js
      js/plan.js
  scripts/
    inspect_datasets.py
    import_datasets.py
  tests/
    test_normalization.py
    test_schedule.py
    test_recommendation.py
    test_catalog_api.py
  data/
    raw/                 # 元CSV、定義書。Git管理対象外
    mappings/            # 確認済み列対応・出席ルール
    reports/             # 品質検証結果
```

上記ツリー末尾の注記は、原本CSV・定義書、検証済み列対応、品質結果をそれぞれ分離する意味です。実装時のコメント・画面は韓国語に統一します。

## 4. リクエストの流れ

```text
ブラウザ → page_routes → Jinja HTML
         → static/js/api.js → JSON API routes
                              → Pydantic 検証
                              → services
                              → app.db の collection handles
                              → app/db/mongo.py の MongoDB client
```

프런트는 입력 상태와 표시를 담당하고, 시간·가격 적합성의 최종 판정은 서버에서 합니다. 추천은 저장 작업이 아니므로 `POST /api/recommendations`가 개인 일정이나 검색 본문을 DB에 보관하지 않습니다.

초기화 때 DB ping과 인덱스 생성을 수행하고 종료 때 연결을 닫습니다. 참조의 startup 구조와 동일한 책임을 유지하되, 실제 구현에서는 lifecycle 처리가 명확하도록 구성합니다. Import 시 사용자 원본을 자동 적재하지 않습니다.

## 5. 원본 데이터 검사와 적재

### 원본 검사

필수 2종의 실제 CSV와 컬럼 정의서를 먼저 읽습니다. 다음을 보고서에 기록합니다.

- 파일명, SHA-256, 인코딩, 구분자, 기준일, 행 수, 원본 컬럼.
- 시설·강좌 ID 유일성, 조인 성공·실패·모호한 건수.
- 요일·시작·종료 시간, 가격·단위, 연령, 주소의 결측·오류 비율.
- 지역·종목별 추천 가능한 강좌 수.
- 정규화 규칙, 제외 사유, 원본 출처와 이용 조건 확인 상태.

CSV는 문자열로 먼저 읽고 ID·전화번호·요일 비트문자열의 선행 0을 보존합니다. 인코딩은 UTF-8-SIG 및 CP949 등 실제 파일에 맞게 확인하며, 깨진 문자를 조용히 무시하는 파싱은 하지 않습니다.

### 조인과 정규화

- 공통 시설 ID가 있으면 우선 사용합니다.
- 없으면 시설명+주소의 정규화된 정확 매칭을 시도합니다. 복수 매칭은 자동 연결하지 않습니다.
- 강좌명이 같다는 이유만으로 중복 제거하지 않습니다. 다른 시간·시설·요금의 강좌일 수 있습니다.
- 출석 요일 의미·가격 단위는 원본 설명 또는 확인 근거를 연결합니다. LLM 추측으로 채우지 않습니다.
- 원본값과 정규화값을 모두 보존하되, 공개 API는 화면에 필요한 필드만 반환합니다.

### 적재·버전

각 적재는 새로운 `datasetVersion`으로 시설·강좌를 staging 적재하고 검증 후 현재 버전 포인터를 바꿉니다. 요청 시작 때 버전을 한 번 읽고 시설·강좌 조회 전체에서 고정합니다. 실패하면 기존 활성 버전을 유지합니다.

동일 파일·매핑 버전 재적재는 중복 생성하지 않도록 키를 설계합니다. 참조 프로젝트 DB를 건드리는 삭제 명령이나 `drop_database`는 사용하지 않습니다. 이전 버전 제거는 별도 작업으로 분리합니다.

실제 파일을 받은 뒤 컬럼 매핑 문서를 생성합니다. 아래 모델은 **원본에 존재한다고 확인된 컬럼명이 아니라 앱 내부 설계명**입니다.

## 6. MongoDB 모델 초안

### `datasets`

`datasetVersion`, `status(staging/active/archived)`, `files[{name,sha256,sourceUrl,sourceAsOf}]`, `importedAt`, `mappingVersion`, `qualitySummary`.

현재 활성 버전은 고정 ID의 `catalog_state` 문서에서 읽습니다. 상태 전환은 검증된 버전에 대해서만 수행합니다.

### `facilities`

`_id`, `datasetVersion`, `sourceFacilityId`, `name`, `regionCode`, `regionName`, `address`, `phone`, `sports[]`, `location?`, `sourceAsOf`, `verifiedAt?`, `verificationSource?`.

GeoJSON을 쓸 경우 좌표 순서는 `[longitude, latitude]`. 좌표가 없으면 `location`을 생략하고 지도 기능을 비활성화합니다.

### `courses`

`_id`, `datasetVersion`, `sourceCourseId`, `facilityId`, `name`, `sportCode`, `sessions[{weekday,startMinute,endMinute}]`, `attendanceMode(required_all/selectable/unknown)`, `minSessionsPerWeek?`, `priceWon?`, `pricePeriod(month/session/term/unknown)`, `ageMin?`, `ageMax?`, `validFrom?`, `validTo?`, `sourceAsOf`, `verificationStatus`, `qualityFlags[]`, `sourceRef`.

요일은 월=0~일=6. 시각은 분 정수. 불명은 null 또는 명시적 unknown으로 유지합니다. 각 세션의 실제 분을 그대로 저장하고 UI 15분 격자에 맞춰 수업을 반올림하지 않습니다.

### `regional_usage` — 선택

지역 코드·명, 대상자 수, 수급자 수, 시설 수, 각 지표 기준시점과 누적 여부, 원본 출처. 분자·분모가 호환된 경우에만 비율을 계산합니다.

### 인덱스

- `facilities`: `(datasetVersion, sourceFacilityId)` 유일 인덱스는 ID가 존재하는 행에 한해 적용. 지역 검색 인덱스.
- `courses`: `(datasetVersion, sourceCourseId)`는 원본 유일성 검증 후 적용. `(datasetVersion, facilityId)`, `(datasetVersion, sportCode)` 검색 인덱스.
- ID가 없는 원본은 안정적인 내부 키를 매핑 단계에서 정의하고 충돌을 검출합니다.
- `datasets.datasetVersion` 유일 인덱스. `catalog_state._id`는 고정 키.
- 좌표 기능이 활성화된 경우에만 검증된 GeoJSON에 `2dsphere` 적용.

## 7. API 계약 초안

| 메서드·경로 | 입력 | 응답·역할 |
|---|---|---|
| `GET /api/metadata` | 없음 | 지원 지역·종목·버전·기준일·기능 지원 여부 |
| `GET /api/facilities` | 지역·종목·페이지 | 시설 목록과 총수 |
| `GET /api/courses` | 시설 또는 지역·종목·페이지 | 강좌 목록·상태·기준일 |
| `GET /api/courses/{id}` | 공개 강좌 ID | 연결된 시설과 강좌 상세 |
| `POST /api/recommendations` | 조건·주간 가용시간 | 확정 가능한 후보·확인 필요 후보·변경 제안 |
| `POST /api/plans/validate` | 강좌 ID·버전·가용시간·여유시간 | 서버에서 재조회한 일정·가격 합계·충돌 |
| `GET /health` | 없음 | 프로세스 상태, 자격증명 출력 금지 |
| `GET /ready` | 없음 | DB·활성 데이터셋 준비 여부. 미준비 시 503 |

초기에는 서버 저장용 계획 CRUD·로그인 API가 없습니다. 로컬 계획을 화면에 다시 띄울 때도 `plans/validate`로 최신 데이터를 검사합니다.

추천 요청 예시(값은 가상이며 원본 레코드가 아님):

```json
{
  "regionCode": "demo-region",
  "sports": ["swimming", "taekwondo"],
  "age": 10,
  "availability": [
    {"weekday": 1, "startMinute": 930, "endMinute": 1080},
    {"weekday": 3, "startMinute": 930, "endMinute": 1080}
  ],
  "bufferMinutesEachWay": 15,
  "monthlyBudgetWon": 120000,
  "limit": 20
}
```

실제 지역·종목 코드는 metadata에서 받습니다. 화·목의 15:30~18:00 예시입니다.

응답 최상위: `datasetVersion`, `sourceAsOf`, `matchedCount`, `candidates[]`, `needsConfirmation[]`, `relaxations[]`, `coverageWarnings[]`. `candidates`는 현재 신청 가능의 의미가 아니라 **검사한 조건에 일치하는 공개 정보**입니다.

후보별로 강좌 ID, 적용 세션, 확인된 일치 근거, 불명 항목, 공시 수강료, 운영 확인 상태를 반환합니다. 변경 제안은 `changedField`, `oldValue`, `proposedValue`, `additionalCandidateCount`를 포함합니다.

입력 검증: 요일 0~6, 분 0~1440 및 start<end, 여유시간 0~120, limit 1~50, 가용구간 최대 56개, 종목 최대 3개. 가용구간은 같은 요일끼리 병합합니다. 월 예산은 null 또는 0 이상의 정수로 받고 서비스에 맞는 상한을 설정합니다.

422는 잘못된 입력, 404는 없는 ID, 503은 활성 데이터 없음. 데이터가 없는 상태를 추천 0건과 구분합니다. 오류 형식은 Commeet와 같은 `{ "detail": "..." }` 또는 검증 오류 배열입니다. 응답에 민감한 요청 원문을 반사하지 않습니다.

## 8. 추천 알고리즘

1. 활성 데이터 버전을 고정하고 지역·종목으로 후보를 조회합니다.
2. 불확실한 시설 연결·시간 파싱 실패 등은 자동 추천에서 분리합니다.
3. 필수 출석이면 모든 세션, 선택 출석이면 검증된 선택 규칙에 따라 세션 조합을 만듭니다. 선택 규칙 불명은 확인 필요로 분리합니다.
4. 각 세션의 `[start-buffer, end+buffer)`가 같은 요일의 가용구간에 완전히 포함되는지 검사합니다.
5. 알려진 연령 조건과 월 단위로 검증된 가격 조건을 검사합니다. 요청한 조건을 검사할 정보가 없으면 ‘일치’로 간주하지 않습니다.
6. 유효 후보를 확인 정보 충실도, 사용자 선호 종목 순서, 같은 단위의 비용, 강좌 ID 순으로 안정 정렬합니다. 비공개 가중치의 임의 적합도 퍼센트는 표시하지 않습니다.
7. 결과가 부족하면 허용된 한 조건만 바꿔 재계산합니다. 예: 사용자가 편집할 수 있는 특정 요일 시간 확장, 월 예산 1만 원 증가. 적용은 명시적 버튼으로만 합니다.
8. 변경 후보의 수가 증가하지 않으면 제안하지 않습니다. 연령 제한·이용 자격·데이터 검증 조건은 자동 완화하지 않습니다.

후보 수 상한을 두어 계산을 제한하면 전체 검색이 아닌 제한된 범위임을 응답에 표시합니다. 지도 없이도 핵심 추천이 동작해야 합니다.

## 9. 계획 저장과 데이터 최소화

초기에는 로그인 없이 사용할 수 있습니다. 입력 중인 상세 조건은 메모리·sessionStorage에 두고, 사용자가 ‘이 기기에 저장’을 선택하면 최소한의 강좌 ID·데이터 버전·선택 세션만 localStorage에 저장합니다. 정확한 주소·아이 이름·수급 유형을 저장하지 않습니다.

새로 열면 계획을 재검증하고 삭제·변경된 강좌를 표시합니다. 개인의 현재 시간 조건은 다시 입력해야 할 수 있습니다. ‘모든 기기 내 계획 삭제’ 버튼을 제공합니다. 브라우저에 저장한 계획은 다른 기기와 동기화되지 않음을 설명합니다.

다중 사용자 계정이나 링크 공유는 P1입니다. 이를 추가하면 소유자 검증·접근 제어·세션·CSRF 등 저장 기능에 맞는 설계가 선행되어야 합니다.

## 10. Commeet 디자인 적용

실제 `app/static/css/style.css`에서 확인한 값:

| 요소 | 기준 |
|---|---|
| 주색 | `#c80150` (README의 `#c8014f`보다 실제 CSS 우선) |
| 보조·제목 | `#34495e` |
| 밝은 배경·카드 | `#f9f9f9` / `#ffffff` |
| 테두리·본문 | `#ddd` / `#333` |
| 카드 반경·패딩 | 8px / 20px |
| 버튼 반경·크기 | 6px, 15px 글자, 11px 18px 패딩 |
| 컨테이너 | 최대 1400px, 좌우 20px |
| 헤더 높이 | 72px |
| 폰트 스택 | Noto Sans KR, Pretendard, 시스템 폰트 |

밝은 배경·흰 카드·진홍색 주요 버튼·남색 보조 상태·얕은 그림자를 유지합니다. 다크 테마는 참조의 `data-theme` 토큰 방식을 참고합니다. 테마 저장 키는 `sports_theme`로 분리합니다. 폰트 파일이 확보되지 않으면 시스템 폰트로 동작시킵니다.

상단 로고는 서비스명으로 만들고 POSTECH·학과 로고나 기관 공식 인증처럼 보이는 요소는 넣지 않습니다. Commeet의 레이아웃과 상호작용을 닮게 하되 학교 면담·지도비·교내 가입 문구는 가져오지 않습니다.

### 핵심 화면 배치

```text
헤더: 서비스명                       추천 찾기 / 내 계획 / 테마
──────────────────────────────────────────────────────────
조건 패널                    추천·시간표 영역
지역·종목·예산               월 화 수 목 금 토 일
이동·준비 여유               가능한 시간을 선택하는 그리드
확인된 조건 요약             추천 강좌 카드 / 비교함
추천 찾기                    결과 없음 → 조건 변경 제안
```

한 화면에서 필터와 결과의 관계가 보이게 합니다. 모바일은 단계별 입력으로 바꾸고 날짜별 세로 목록을 제공합니다. 색상만으로 가용·선택·불명 상태를 구별하지 않습니다. 드래그·터치·키보드 또는 숫자 입력 모두로 시간을 지정할 수 있어야 합니다.

## 11. 환경변수·실행

`.env.example`에 비밀이 아닌 예시만 작성합니다.

```dotenv
ENV=development
HOST=127.0.0.1
PORT=8010
BASE_URL=http://127.0.0.1:8010
APP_NAME=우리 아이 운동시간표
MONGO_URI=mongodb://127.0.0.1:27017
DB_NAME=sports_dev
DATA_RAW_DIR=./data/raw
DEMO_MODE=false
```

로컬 MongoDB가 실제로 있는지 먼저 확인합니다. 참조의 운영 접속정보로 대신 연결하지 않습니다. 키 없이 동작하는 기본 목록·시간표를 먼저 완성하고, 지도는 선택 기능으로 둡니다.

개발자가 구현할 CLI 계약 예시(현재 존재하지 않음):

```bash
uv sync
uv run python scripts/inspect_datasets.py --raw-dir data/raw --report-dir data/reports
uv run python scripts/import_datasets.py --raw-dir data/raw --dry-run
uv run python scripts/import_datasets.py --raw-dir data/raw
uv run python run.py
```

원본·`.env`·로컬 리포트의 민감한 경로·캐시를 Git에서 제외합니다. 데이터가 없으면 명시적 빈 상태를 보여주고, 합성 데이터는 `DEMO_MODE=true` 및 ‘샘플’ 표시가 있을 때만 사용합니다.

## 12. 운영 경계

- 공개 CSV 적재는 로컬 CLI로 수행하며 웹 업로드 기능은 만들지 않습니다.
- API 요청 크기·페이지 크기를 제한하고 입력값을 HTML로 실행하지 않습니다.
- 상세 시간표·주소·요청 본문을 접근 로그에 저장하지 않습니다.
- Commeet의 API no-store·정적 자산 버전·에러 처리 패턴을 적용합니다.
- 지도 SDK를 추가할 때만 필요한 출처에 맞게 CSP를 조정합니다. 참조의 외부 리소스 차단 정책을 복사하면 지도가 막힐 수 있습니다.
- 전화·공식 사이트 연결은 사용자 클릭으로 수행합니다. 사용자 대신 문의·신청·결제하지 않습니다.
- 운영 배포·DNS·기존 서버 설정 변경은 이 문서 작성과 별개입니다.

## 13. 검증과 완료 기준

핵심 계산과 데이터 결합에는 다음 테스트가 필요합니다.

| 검증 | 기대 결과 |
|---|---|
| 선행 0 요일 코드 | 원래 요일 보존 |
| 중복 시설명·다른 주소 | 잘못된 시설 자동 연결 없음 |
| 월·수·금 필수인데 화·목만 가능 | 일치 후보에서 제외 |
| 16~17시 수업, 15분 여유, 16시부터 가능 | 시간 불일치 |
| 연속 가용구간·경계 인접 | 병합 후 올바르게 포함·충돌 판단 |
| 가격 단위 미상 | 월 예산 일치로 표시하지 않음 |
| 누락 시간·불명 출석 규칙 | 확인 필요, 자동 계획 확정 금지 |
| 동일 원본 재적재 | 중복 없음 |
| 실패한 새 적재 | 기존 활성 버전 유지 |
| 저장 계획의 원본 갱신 | 재검증·변경 안내 |
| 조건 변경 제안 | 실제 후보 증가, 원 조건 자동 변경 없음 |

UI는 390px 모바일과 데스크톱, 밝은/어두운 테마, 키보드 입력, 로딩·빈 결과·오류·데이터 미준비 상태를 확인합니다. 일반 기능을 검사하기 위해 Commeet의 운영 서버나 데이터베이스에 접속하지 않습니다.

완료 기준: 실제 원본을 적재한 추천→비교→계획→문의 연결이 동작하고, 계산·결측·갱신 테스트가 통과하며, 품질 보고서·설치 방법·알려진 제약·실제 시연 증빙이 준비된 상태입니다. 합성 레코드만 표시하는 화면은 완료가 아닙니다.
