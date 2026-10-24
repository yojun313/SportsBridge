# 스포츠브릿지 (SportsBridge)

스포츠강좌이용권을 받아도 쓸 곳이 없는 지역을 공공데이터로 진단하고, 가맹되지 않은 체육시설 후보를 찾고,
수요 집단에 대해 "가맹 협의 · 강좌 신설 · 이동 지원" 중 함께 시행해야 효과가 나는 조합을 계산해 협의 계획서 초안까지 만드는
지자체·공단 담당자용 웹 서비스입니다. 2026년 국민체육진흥공단 공공데이터 활용 경진대회 출품용 시제품.

기획·설계 문서: [`docs/아이디어4/`](docs/아이디어4/README.md) (아이디어1~3의 통합안).

## 무엇을 하는가

| 단계 | 화면 | 내용 |
|---|---|---|
| 이용자용(청록 테마, 전용 메뉴 8개) | `/user`, `/user/region`, `/user/facilities`, `/user/spaces`, `/user/voice`, `/user/planner`, `/user/ask`, `/user/help` | 지역·종목·요일별 시간·예산으로 이용권 강좌를 조건 일치/확인 필요/불일치로 판정, 조건 변경 제안, 개방학교 무료 공간. 맞는 강좌가 없으면 익명 수요 등록·근처 비가맹 시설에 가맹 요청 표시 |
| ① 공백 진단 | `/gap`, `/gap/{시군구}` | 대상자 1,000명당 활동 가맹시설, 종목 편중, 저녁·주말 강좌 비율, 수급률을 전국·시도 순위로 |
| ② 후보 발굴 | `/gap/{시군구}/candidates` | 전국체육시설현황·공공체육시설·개방학교에서 가맹 목록과 대조되지 않은 시설을 안전등급·접근성·업종으로 점수화, CSV |
| ③ 조치 조합 시뮬레이션 | `/scenario`, `/scenario/compare` | 수요 집단 + 조치(≤10)의 모든 조합을 최대유량 배정으로 평가. A만·B만·A+B 비교, 탐욕 방식과 대조 |
| ④ 협의 계획서 | `/scenario/plan` | 엔진 결과 JSON만 근거로 초안 작성. 문서 안 모든 숫자·이름을 근거와 대조(가드) |
| 복구 에이전트 | `/agent` | 질문 한 번에 ①~③을 도구 호출로 수행. 숫자는 도구가 계산, 모델은 서술만. 인용·성과 단정 가드, SSE 타임라인 |
| 검토 큐 | `/review` | AI 추출·판정 결과를 사람이 승인해야 진단에 반영 |
| 데이터 관리 | `/data` | 원본 10종 출처·파일·적재 해시 관리, CSV 업로드로 교체, 전체 재적재(서버 공유 진행률, 모든 페이지 상단에 표시) |

이용자 신호(수요 등록·가맹 요청)는 담당자용 시나리오의 수요 집단과 후보 점수로 흘러갑니다. 이용권과 시설을 잇는 "브릿지"가 서비스 이름의 뜻입니다.

원칙: **숫자와 판정은 결정적 엔진이 만들고, LLM은 텍스트↔구조 변환만.** 모든 값에 출처 등급(공공자료 / 규칙 / AI추출·미검토 / AI추출·검토완료 / 담당자확인 / 가정)이 붙습니다.

## 모바일·PWA

휴대폰에서는 하단 탭바(4개 + 더보기 시트)로 이동하고, 홈 화면에 추가하면 전체 화면 앱처럼 열립니다(`/static/manifest.webmanifest`, 아이콘 `app/static/icons/`).
점검: `uv run --with playwright python /home/yojun/prompts/scripts/mobile_audit.py http://127.0.0.1:7004 out/ / /user /gap` (가로 넘침·작은 입력창·JS 오류), `ios_viewport_sim.py`(키보드).

## 데이터

`data/raw/`에 문화빅데이터플랫폼(국민체육진흥공단) CSV 10종을 그대로 둡니다(파일명 NFC/NFD 무관).
지역별 이용권 활용정보(26) · 이용권 시설(80) · 이용권 강좌(74) · 이용권 이용현황(05) · 전국체육시설현황(64) · 전국공공체육시설(73) ·
개방학교(19) · 체육시설 안전점검(34) · 이용권시설 인접 대중교통(06) · 체육시설 인접 대중교통(08).

핵심 결합 규칙(자세히는 `/data` 화면, `docs/아이디어4/03_데이터_및_매칭_설계.md`):
- 지역코드는 26번의 5자리 코드를 표준으로 하고 2026년 개편 코드(12xxx)·시 안의 구 코드를 이름으로 붙임.
- 강좌 데이터(74)에는 시설 키가 없어 이용현황(05)의 강좌번호를 기본 단위로 삼고 (종목·강좌명·가격·연도)로 시간표를 결합.
- 가맹시설(80∪05) ↔ 전체시설(64∪73∪19) 매칭: 이름+주소 정확일치 → 지역 내 유일 이름 → 전화 → 블로킹 후보(LLM 판정·검토 큐).

## 실행

```bash
uv sync
cp .env.example .env            # MONGO_URI, 관리자 계정·메일 설정, (선택) OPENAI_API_KEY
uv run python scripts/inspect_datasets.py                 # 품질 보고서 → data/reports/
uv run python scripts/import_datasets.py --raw-dir data/raw   # 적재(약 1분), 활성 버전 전환
uv run python run.py                                      # http://127.0.0.1:7004
uv run pytest -q                                          # 엔진·가드·문서·에이전트 루프 테스트
```

환경변수(`.env.example` 참고): `MONGO_URI`, `DB_NAME`, `PORT`(7004), `DEMO_MODE`, `LLM_ENABLED`, `OPENAI_API_KEY`,
`LLM_MODEL_MAIN`·`LLM_MODEL_BULK`(기본 gpt-5.6-luna, OpenAI 최저가 티어), `LLM_REASONING_EFFORT`(low), `LLM_DAILY_BUDGET_USD`, `AGENT_MAX_TURNS`, `AGENT_TIME_BUDGET_SECONDS`.
API 키가 없으면 LLM 기능(추출·문서 다듬기·에이전트)만 꺼지고 진단·후보·시나리오·템플릿 계획서는 그대로 동작합니다.

### 접근 보안

- `/docs`, `/redoc`, `/openapi.json`은 모든 환경에서 비활성화됩니다.
- `.env`의 `ADMIN_AUTH_ENABLED=false`이면 담당자 화면과 기능에 로그인 없이 접근할 수 있습니다. `true`이면 `/admin/login`에서 루트 또는 승인된 관리자 계정으로 로그인해야 합니다. 설정을 바꾼 뒤 서버를 재시작하세요.
- 루트 계정은 `.env`의 `ADMIN_ROOT_USERNAME`과 `ADMIN_ROOT_PASSWORD`로 로그인합니다. 기존 `ADMIN_TOKEN`은 사용하지 않습니다. 인증을 켤 때 루트 비밀번호는 12자 이상이어야 합니다.
- `/admin/signup`에서 관리자 가입을 신청하면 이메일로 6자리 확인 코드를 보냅니다. 확인을 마친 신청은 `/admin`의 루트 관리자 승인 대기 목록에 표시되며, 승인 후 로그인할 수 있습니다. 발신 계정과 Gmail 앱 비밀번호는 `.env`의 `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`에 보관합니다. `.env` 파일 권한은 `600`으로 유지하세요.
- 운영 시 `BASE_URL`을 실제 `https://` 주소로, `ALLOWED_HOSTS`를 서비스 호스트 이름으로 설정하고 TLS를 제공하는 역방향 프록시 뒤에서 실행하세요. `HOST`는 외부에 직접 노출하지 않는 주소로 유지하세요. 여러 서버나 작업자를 쓰면 공개 API의 요청 제한을 프록시에서도 적용해야 합니다.
- 변경 요청에는 `X-Requested-With: XMLHttpRequest` 헤더와 `Content-Length`가 필요합니다. 관리자 API는 로그인 세션 쿠키를 사용합니다.

## LLM 작업(키가 있을 때)

```bash
uv run python scripts/llm_extract_courses.py --submit --region 11110 --limit 200   # Batch 제출 (강좌 설명 → 연령·출석규칙 추출)
uv run python scripts/llm_extract_courses.py --collect <batch_id>                  # 수집 → course_facts + 검토 큐
uv run python scripts/llm_judge_matches.py --region 11110 --limit 50               # 애매한 시설 매칭 판정 → 검토 큐
uv run python scripts/llm_classify_facilities.py --region 11110 --limit 50         # 업종 unknown 시설 분류
uv run python scripts/run_eval_all.py                                              # 에이전트 평가 문항(docs/eval/EVAL_ALL.md) 실행
```

## 코드 구성

```
app/
  main.py, config.py           FastAPI 앱·설정
  db/                          MongoDB 연결(1곳)·컬렉션 등록·인덱스
  services/                    importer(적재 파이프라인), normalization, regions, catalog, gap, candidate, supply, scenario, document, review
  engine/                      models(Pydantic), constraints, assignment(최대유량), bundles(조합 탐색·탐욕 비교·추적)
  llm/                         client(모델·예산·기록), schemas, prompts/, extract(UC1~3), documents(UC5+가드)
  agent/                       tools(8종), loop(수동 루프), guards, answer, system_prompt
  api/events.py                SSE 브로드캐스터·실행 레지스트리
  routes/, templates/, static/ 페이지·API·바닐라 JS, 파란 계열 디자인 시스템(Commeet 레이아웃 참조, 모바일 대응)
scripts/                       inspect_datasets, import_datasets, llm_*, run_eval_all
tests/                         engine, documents(가드), guards, agent_loop(가짜 클라이언트)
docs/                          아이디어1~4 기획, eval 문항
data/                          raw(원본, git 제외) · mappings(규칙) · reports(품질) · eval
```

## 해석 한계

시설 수는 수용 인원이 아닙니다. 순위는 상대 비교이며 "부족·충분" 판정이 아닙니다. 신청 인원은 고유 이용자 수·출석·미충족 수요가 아닙니다.
비가맹 후보는 "가맹 목록과 대조되지 않음"이지 비가맹 확정이 아닙니다. 시뮬레이션의 배정 인원은 입력 조건과 가정하의 모델 값이며
실제 참여·예산 절감·사업 승인을 뜻하지 않습니다. 개인정보를 수집하지 않습니다.
