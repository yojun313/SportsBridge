(function () {
  const root = document.getElementById("detail-root");
  const code = root.dataset.region;
  const body = document.getElementById("detail-body");
  const missingReasons = { "time_axis:no_schedule": "저녁 강좌 비율: 시간표 자료 미확인", "quantity_axis:no_targets": "대상자 1,000명당 시설 수: 대상 인원 미확인 또는 0명" };
  let usagePeriod = "기간 미확인";
  const terms = {
    "가맹시설 수": "스포츠 강좌이용권 대상자 1,000명당 집계기간에 강좌 기록이 있는 가맹시설 수입니다. 시설 총수나 잔여석이 아닙니다.",
    "운영 종목 수": "집계기간에 강좌 기록이 있는 운동 종목의 가짓수입니다. 같은 종목의 여러 강좌는 한 종목으로 셉니다.",
    "저녁 강좌 비율": "시간표가 확인된 강좌 중 오후 6시 이후 시작하는 수업이 하나 이상 있는 강좌의 비율입니다. 주말 수업도 포함합니다.",
    "수급률": "지역별 활용정보의 지원 대상 인원 대비 수급 인원 비율입니다. 실제 강좌 출석률이나 지원금 사용률이 아닙니다.",
    "이용자 희망 등록 현황": "서비스에 등록된 희망 강좌 조건과 시설 이용 희망 건수입니다. 지역 전체 주민 수요나 실제 강좌 수강 신청 인원과 다릅니다.",
    "집계기간": "표시된 시작월부터 마지막 월까지 양끝 월을 포함한 자료 집계 범위입니다. 현재 시점의 모집·영업 상태와 구분해야 합니다.",
    "공개 시간표 연결됨": "별도 공개 시간표 자료를 강좌 정보와 비교해 연결한 상태입니다. 현재 운영 일정은 시설에 확인해야 합니다.",
    "시간표 연결 후보": "시간표 연결 후보가 여러 개여서 한 시간표로 확정하기 어렵습니다. 이용 전 실제 일정을 확인해야 합니다.",
    "시간표 미확인": "해당 강좌에 시간표 자료가 연결되지 않았습니다. 수업 일정이 없다는 의미가 아닙니다.",
    "전 요일 필수": "시간표에 표시된 모든 수업에 참여하는 조건으로 비교합니다.",
    "요일 선택": "시간표 중 이용 가능한 요일을 선택하는 출석 규칙입니다. 필요한 주당 횟수를 함께 확인해야 합니다.",
    "주소": "공개 시설 자료의 소재지입니다. 현재 주소와 다를 수 있습니다.",
    "전화": "공개 시설 자료의 연락처입니다. –는 연락처 미확인입니다.",
    "가맹 결정일": "공개 자료에 기록된 가맹 결정일입니다. 현재 가맹 유지 여부나 영업 시작일을 뜻하지 않습니다.",
    "이용 이력": "이 시설에 연결된 공개 강좌 신청 기록의 기간과 합계입니다. 기록 없음은 이용자가 없다는 뜻이 아닙니다.",
    "출처": "이 항목에 사용한 공개 자료의 출처입니다. 자료별 기준일과 갱신 주기가 다를 수 있습니다.",
    "집계기간 내 기록 있음": "표시된 집계기간에 강좌 기록이 있는 시설입니다. 현재 영업·모집 여부나 잔여석을 보장하지 않습니다. 신청 인원이 0명이어도 기록이 있으면 해당됩니다.",
    "집계기간 내 기록 없음": "과거 강좌 기록은 있으나 표시된 집계기간에는 기록이 없습니다. 폐업이나 스포츠 강좌이용권 가맹 해제를 뜻하지 않습니다.",
    "기록 미확인": "이 시설에 연결된 강좌 이용 이력이 없어 활동 여부를 판단할 수 없습니다. 신청 인원 0명이나 폐업을 뜻하지 않습니다.",
    "가맹시설": "공개 스포츠 강좌이용권 가맹시설·이용현황 자료에 포함된 시설입니다. 가맹을 요청한 시설 목록이 아니며 현재 이용 가능 여부는 시설에 확인해야 합니다.",
    "수강 신청 누계(연인원)": "표시된 집계기간의 월별·강좌별 신청 인원 합계입니다. 동일인의 반복 신청이 포함될 수 있으며, 시설 이용 희망 등록·가맹 신청·현재 대기 인원이 아닙니다. 0은 집계값 0명, –는 연결된 기록 미확인을 뜻합니다.",
    "마지막 기록월": "연결된 강좌 이용현황에서 확인된 가장 최근 연월입니다. 현재 운영일이나 가맹 종료일을 뜻하지 않습니다.",
    "정류장 도보": "공개 교통자료에 연결된 정류장 중 최소 도보 시간을 분 단위로 반올림한 값입니다. 0분은 반올림 결과일 수 있습니다. –는 자료 미확인이며 대중교통 이용 불가를 뜻하지 않습니다.",
    "시설 목록 연결": "가맹시설 목록과 전체 체육시설 목록에서 동일 시설로 연결했는지 표시합니다. 스포츠 강좌이용권 가맹 여부와는 별도입니다.",
    "목록 연결됨": "이름·주소·지역·전화번호 등의 비교 또는 담당자 검토로 전체 체육시설 목록의 시설과 연결했습니다. 현재 영업이나 이용 가능성을 확인한 결과는 아닙니다.",
    "동일 시설 확인 필요": "전체 체육시설 목록에 유사한 시설이 있으나 동일 시설인지 확정하지 못했습니다. 이름·주소 등을 추가로 확인해야 합니다.",
    "목록 연결 안 됨": "전체 체육시설 목록에서 동일 시설로 연결된 항목이 없습니다. 스포츠 강좌이용권 미가맹이나 시설 부재를 뜻하지 않습니다.",
    "마지막 집계월 신청": "해당 강좌의 마지막 기록월 신청 인원입니다. 시설 전체 신청 누계·실제 출석 인원·현재 대기 인원·잔여석과 다릅니다.",
    "월 수강료": "공개 자료의 월 수강료입니다. 현재 요금·지원금 적용액·본인부담금은 시설과 사업 안내에서 확인해야 합니다. –는 요금 미확인으로 무료가 아닙니다.",
    "추출 정보": "강좌 설명에서 추출한 연령·출석 규칙 등입니다. AI 추출·검토 전은 담당자 확인 전 정보이며, 검토 완료도 현재 시설 상황을 보장하지 않습니다. 추출 기록 없음은 조건 제한이 없다는 뜻이 아닙니다.",
    "시간": "연결된 공개 시간표의 요일·수업 시간입니다. 시간 미확인은 자료가 없거나 연결하지 못한 경우이며 상시 이용 가능을 뜻하지 않습니다.",
    "종목": "공개 강좌·시설 자료에 표시된 운동 종목입니다. 시설의 현재 전체 프로그램 목록과 다를 수 있습니다.",
    "시설": "시설명을 선택하면 주소·전화·가맹 결정일·이용 이력과 강좌 목록을 확인합니다. 표시된 목록은 불러온 자료 기준입니다.",
    "강좌": "집계기간에 기록이 있는 강좌를 표시합니다. 현재 모집 중인 강좌만을 뜻하지 않습니다. 종목 필터로 표시 목록을 좁힐 수 있습니다.",
    "해석": "공공자료의 지표와 지역 간 비교를 설명합니다. 시설 부족의 원인이나 정책 효과를 확정한 결과는 아닙니다.",
    "종목 분포": "집계기간에 기록이 있는 강좌 수를 종목별로 집계한 상위 10개 항목입니다. 비율은 전체 해당 강좌 수 기준이며 정원이나 참여 인원이 아닙니다.",
    "시작 시각 분포": "시간표가 연결된 강좌를 시작 시각 기준 2시간 구간으로 집계합니다. 한 강좌가 여러 구간에 포함될 수 있습니다. 06시 이전은 첫 구간, 22시 이후는 마지막 구간에 포함됩니다.",
    "요일 분포": "연결된 시간표의 수업 일정을 요일별로 센 값입니다. 같은 강좌의 여러 수업 일정이 반복 포함될 수 있어 강좌 수와 다릅니다.",
    "전국 비교": "지역별 지표와 순위를 비교하는 지역 현황 목록으로 이동합니다. 순위 1위는 해당 지표가 낮은 지역이며 종합 서비스 순위가 아닙니다.",
    "가맹 검토 시설 보기": "공개 가맹 목록과 연결되지 않은 체육시설 후보를 확인합니다. 실제 미가맹이 확정된 시설 목록이 아닙니다.",
    "지원 방안 작성": "이 지역을 선택한 지원 방안 입력 화면으로 이동합니다. 수요·강좌·정원·비용을 확인한 뒤 조합을 계산합니다.",
    "전체 보기": "서버에서 불러온 시설을 최대 400곳까지 표시합니다. 기본 화면에는 상위 20곳을 표시하며 전체 지역 시설 수와 다를 수 있습니다.",
    "접기": "시설 목록을 신청 누계 상위 20곳으로 줄여 표시합니다.",
    "전체 종목": "강좌 목록의 종목을 선택합니다. 최대 100개 강좌를 표시하며 상단 지역 지표는 바뀌지 않습니다.",
  };
  const matchTypes = { exact_name_addr: "이름·주소 일치", exact_name_region: "지역 내 이름 일치", exact_tel_region: "지역 내 전화번호 일치", llm_reviewed: "담당자 검토로 연결" };
  function tip(text, description, cls = "") {
    return `<span class="${cls}" tabindex="0" data-gap-tip="${esc(description)}">${esc(text)}</span>`;
  }
  function explain(scope = root) {
    scope.querySelectorAll("th, h3, .label, .desc, .rank-pill, p, dt, dd, a.btn, button, select, td[data-label], .prov, .bar-row, .name .sub").forEach((el) => {
      if (el.dataset.gapTip) return;
      const label = el.dataset.label || el.textContent.trim();
      const key = Object.keys(terms).sort((a,b) => b.length-a.length).find((k) => label === k || label.startsWith(k + " "));
      const text = el.dataset.help || el.title || terms[key] || (el.matches(".rank-pill") ? "지표 값이 낮은 지역부터 매긴 상대 순위입니다. 1위는 해당 지표가 가장 낮은 지역이며 종합 평가 순위가 아닙니다." : el.matches(".bar-row") ? el.closest(".card")?.querySelector("h3")?.dataset.gapTip : el.matches(".desc") ? label : null);
      if (text) el.dataset.gapTip = text;
    });
  }
  const pageHelp = document.getElementById("region-terms-help");
  pageHelp.dataset.help = Object.entries(terms).map(([k,v]) => `${k}\n${v}`).join("\n\n");
  pageHelp.dataset.gapTip = "지역 현황의 지표·시설 상태·표 항목·버튼 설명을 한곳에서 확인합니다. 클릭하거나 Enter 키를 누르면 전체 안내가 열립니다.";
  explain();

  function statCard(a) {
    const na = !a.computable;
    let v = "–";
    if (!na) v = a.key === "sport" ? fmtNum(a.value) : (a.key === "quantity" ? fmtNum(a.value, 2) : fmtPct(a.value, 1));
    const rank = a.rankNational ? `<span class="rank-pill ${a.rankNational <= 20 ? "hot" : ""}">전국 ${a.rankNational} / ${a.regionTotal}</span>` : "";
    return `<div class="card stat ${na ? "na" : ""}"><div class="label">${esc(a.label)} ${provBadge("public")}</div><div class="value">${v}</div><div class="desc">${esc(a.desc)}${na ? " · 계산 불가(데이터 없음)" : ""}</div><div class="mt-8">${rank}</div></div>`;
  }

  function bars(pairs, total, labelFn) {
    const max = Math.max(1, ...pairs.map((p) => p[1]));
    return `<div class="bar-list">${pairs.map(([k, v]) => `<div class="bar-row"><span class="k">${esc(labelFn ? labelFn(k) : k)}</span><div class="bar"><span style="width:${(v / max * 100).toFixed(1)}%"></span></div><span class="v">${fmtNum(v)}${total ? ` <small>(${fmtPct(v / total)})</small>` : ""}</span></div>`).join("")}</div>`;
  }

  async function load() {
    try {
      const d = await api.get(`/api/gap/${code}`);
      const r = d.region, s = d.stats || {};
      usagePeriod = r.activeCutoffMonth && r.dataMaxMonth ? `${r.activeCutoffMonth} ~ ${r.dataMaxMonth}` : "기간 미확인";
      document.getElementById("region-title").textContent = `${r.sidoName} ${r.sigunguName}`;
      document.getElementById("region-sub").textContent = `인구 ${fmtNum(r.population)} · 스포츠 강좌이용권 대상자 ${fmtNum(r.targetsTotal)} · 수급자 ${fmtNum(r.recipientsTotal)} · 기준연도 ${s.baseYear || "–"} · 강좌 기록 기준 ${r.activeCutoffMonth || "–"} 이후`;
      const flags = Object.entries(s.targets || {}).map(([k, v]) => `${esc((s.flagNames || {})[k] || k)} 대상 ${fmtNum(v)} / 수급 ${fmtNum((s.recipients || {})[k])}`).join(" · ");
      const sportsTotal = r.activeCourseCount || 0;
      const hourPairs = Object.entries(d.hourBins).map(([h, v]) => [`${h}시`, v]);
      const dowPairs = ["월", "화", "수", "목", "금", "토", "일"].map((n, i) => [n, d.dowCounts[i]]);
      body.innerHTML = `
        <div class="grid-4 mb-16">${d.axes.map(statCard).join("")}</div>
        <div class="grid-2 mb-16">
          <div class="card card-pad">
            <div class="card-head"><h3>해석</h3>${provBadge("public")}</div>
            <ul class="stack small">${d.interpretation.map((t) => `<li>• ${esc(t)}</li>`).join("")}</ul>
            <p class="faint mt-8">${flags}</p>
            <p class="small mt-8"><b>이용자 희망 등록 현황</b> · 등록 수요 ${fmtNum((d.signals || {}).demand ? d.signals.demand.total : 0)}건${d.signals && d.signals.demand && d.signals.demand.bySport.length ? " (" + d.signals.demand.bySport.slice(0, 4).map((s) => esc(s.sport) + " " + s.count).join(", ") + ")" : ""} · 시설 이용 희망 ${fmtNum((d.signals || {}).voteTotal || 0)}건${d.signals && d.signals.votes && d.signals.votes.length ? " — " + d.signals.votes.slice(0, 3).map((v) => esc(v.name) + " " + v.votes).join(", ") : ""}</p>
            ${r.notComputable && r.notComputable.length ? `<p class="faint">계산 불가: ${esc(r.notComputable.map((v) => missingReasons[v] || "지표 계산에 필요한 자료 미확인").join(", "))}</p>` : ""}
          </div>
          <div class="card card-pad">
            <div class="card-head"><h3>종목 분포 <small class="faint">집계기간 내 강좌 ${fmtNum(sportsTotal)}개</small></h3></div>
            ${d.sportCounts.length ? bars(d.sportCounts.slice(0, 10), sportsTotal) : '<p class="muted">집계기간에 기록이 있는 강좌가 없습니다.</p>'}
          </div>
        </div>
        <div class="grid-2 mb-16">
          <div class="card card-pad"><div class="card-head"><h3>시작 시각 분포 <small class="faint">시간 확인 강좌 ${fmtNum(r.scheduleKnownCount)}개</small></h3></div>${r.scheduleKnownCount ? bars(hourPairs) : '<p class="muted">시간표가 결합된 강좌가 없습니다.</p>'}</div>
          <div class="card card-pad"><div class="card-head"><h3>요일 분포</h3></div>${r.scheduleKnownCount ? bars(dowPairs) : '<p class="muted">–</p>'}</div>
        </div>
        <div class="card card-pad mb-16">
          <div class="card-head"><h3>가맹시설 <small class="faint">${fmtNum(r.voucherFacilityCount)}곳 · 수강 신청 누계 많은 순</small> <button class="help-button" type="button" data-help-title="수강 신청 누계 안내" data-help="공개 이용현황의 월별·강좌별 수강 신청 인원을 합산한 값입니다. 같은 사람이 여러 달 또는 여러 강좌를 신청하면 반복 포함될 수 있습니다. 시설 이용 희망 등록이나 가맹 신청 건수와는 다른 값입니다." aria-label="수강 신청 누계 안내">?</button></h3><button class="btn btn-sm btn-ghost" id="toggle-fac">전체 보기</button></div>
          <p class="small muted">집계기간: ${esc(usagePeriod)} · 수강 신청 연인원이며, 같은 사람의 월별·강좌별 신청이 반복 포함될 수 있습니다.</p>
          <div class="table-wrap"><table class="table responsive" id="fac-table"><thead><tr><th>시설</th><th>종목</th><th class="num">수강 신청 누계(연인원)</th><th>마지막 기록월</th><th>정류장 도보</th><th>시설 목록 연결</th></tr></thead><tbody id="fac-body"></tbody></table></div>
        </div>
        <div class="card card-pad">
          <div class="card-head"><h3>강좌 <small class="faint">집계기간 내 강좌 · 종목별 조회</small></h3><select class="input" id="course-sport" style="width:auto;min-width:160px"><option value="">전체 종목</option></select></div>
          <div id="course-list"><div class="empty-state"><span class="spinner"></span></div></div>
        </div>`;
      explain();
      renderFacilities(d.facilities, 20);
      let expanded = false;
      document.getElementById("toggle-fac").addEventListener("click", (e) => { expanded = !expanded; renderFacilities(d.facilities, expanded ? 400 : 20); e.target.textContent = expanded ? "접기" : "전체 보기"; e.target.dataset.gapTip = terms[expanded ? "접기" : "전체 보기"]; });
      loadCourses("");
      document.getElementById("course-sport").addEventListener("change", (e) => loadCourses(e.target.value));
    } catch (e) { body.innerHTML = `<div class="notice error">${esc(e.message)}</div>`; }
  }

  function renderFacilities(list, n) {
    const tb = document.getElementById("fac-body");
    tb.innerHTML = list.slice(0, n).map((f) => {
      const u = f.usage || {}; const t = f.transit; const m = f.allMatch || {};
      const matchLabel = m.allFacilityId ? tip(`목록 연결됨 · ${matchTypes[m.matchType] || "연결 기준 미확인"}`, terms["목록 연결됨"], "badge badge-ok") : (m.status === "candidates" ? tip("동일 시설 확인 필요", terms["동일 시설 확인 필요"], "badge badge-warn") : tip("목록 연결 안 됨", terms["목록 연결 안 됨"], "badge badge-muted"));
      const activity = !u.lastMonth ? "기록 미확인" : (u.active ? "집계기간 내 기록 있음" : "집계기간 내 기록 없음");
      return `<tr><td class="name" data-label="시설"><a href="#" data-gap-tip="${esc(terms["시설"])}" data-fac="${esc(f.facilityId)}">${esc(f.name)}</a><span class="sub">${esc(f.address || "")}</span></td>
        <td data-label="종목">${esc((f.sports || []).join(", "))}</td>
        <td class="num" data-label="수강 신청 누계(연인원)">${fmtNum(u.last12mApplicants)} ${tip(activity, terms[activity], `badge ${u.active ? "badge-ok" : "badge-muted"}`)}</td>
        <td data-label="마지막 기록월">${esc(u.lastMonth || "–")}</td>
        <td data-label="정류장 도보">${t ? `${Math.round(t.minWalkSec / 60)}분 (${esc(t.stopType)} ${esc(t.stopName)})` : "–"}</td>
        <td data-label="시설 목록 연결">${matchLabel}</td></tr>`;
    }).join("") || '<tr><td colspan="6" class="empty-state">가맹시설이 없습니다.</td></tr>';
    explain(tb);
    tb.querySelectorAll("[data-fac]").forEach((a) => a.addEventListener("click", async (e) => { e.preventDefault(); showFacility(a.dataset.fac); }));
  }

  async function showFacility(id) {
    try {
      const f = await api.get(`/api/gap/${code}/facility/${id}`);
      const u = f.usage || {};
      const html = `<div class="dialog-backdrop open" id="fac-dialog"><div class="dialog dialog-lg"><div class="dialog-header"><h2>${esc(f.name)}</h2><button class="btn-icon" data-dialog-close aria-label="시설 상세 닫기" data-gap-tip="시설 상세 창을 닫고 지역 현황으로 돌아갑니다.">&times;</button></div>
        <dl class="kv"><dt>주소</dt><dd>${esc(f.address || "")} ${esc(f.detailAddress || "")}</dd><dt>전화</dt><dd>${esc(f.tel || "–")}</dd><dt>종목</dt><dd>${esc((f.sports || []).join(", "))}</dd><dt>가맹 결정일</dt><dd>${esc(f.decisionDate || "–")}</dd>
        <dt>이용 이력</dt><dd>${u.firstMonth ? `${esc(u.firstMonth)} ~ ${esc(u.lastMonth)} · 전체 기록의 수강 신청 ${fmtNum(u.totalApplicants)}명(연인원) · 집계기간 ${esc(usagePeriod)}의 수강 신청 ${fmtNum(u.last12mApplicants)}명(연인원)` : "없음"}</dd>
        <dt>출처</dt><dd>${(f.sources || []).map(provBadge.bind(null, "public")).join(" ")} ${esc((f.sources || []).join(", "))}</dd></dl>
        <h3 class="mt-16">강좌 ${f.courses.length}개</h3>
        <div class="table-wrap"><table class="table"><thead><tr><th>강좌</th><th>종목</th><th>시간</th><th class="num">월 수강료</th><th>마지막 기록월</th><th class="num">마지막 집계월 신청</th></tr></thead><tbody>
        ${f.courses.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.sport)}</td><td>${esc(fmtSessions(c.sessions))}</td><td class="num">${fmtWon(c.priceWon)}</td><td>${esc(c.lastMonth)}</td><td class="num">${fmtNum(c.lastApplicants)}</td></tr>`).join("")}
        </tbody></table></div></div></div>`;
      const old = document.getElementById("fac-dialog"); if (old) old.remove();
      document.body.insertAdjacentHTML("beforeend", html);
      explain(document.getElementById("fac-dialog"));
    } catch (e) { showSnackbar(e.message, "error"); }
  }

  async function loadCourses(sport) {
    const el = document.getElementById("course-list");
    try {
      const d = await api.get(`/api/gap/${code}/courses` + qs({ sport, limit: 100 }));
      const sel = document.getElementById("course-sport");
      if (sel.options.length === 1) d.sports.forEach((s) => { const o = document.createElement("option"); o.value = s.sport; o.textContent = `${s.sport} (${s.count})`; sel.appendChild(o); });
      if (!d.courses.length) { el.innerHTML = '<p class="muted">집계기간에 기록이 있는 강좌가 없습니다.</p>'; return; }
      el.innerHTML = `<div class="table-wrap"><table class="table responsive"><thead><tr><th>강좌</th><th>시설</th><th>시간</th><th class="num">월 수강료</th><th class="num">마지막 집계월 신청</th><th>추출 정보</th></tr></thead><tbody>
        ${d.courses.map((c) => {
          const fx = c.facts;
          const facts = fx ? `${provBadge(fx.provenance)} ${fx.age_min != null || fx.age_max != null ? `연령 ${fx.age_min ?? "?"}~${fx.age_max ?? "?"}` : ""} ${fx.attendance_rule && fx.attendance_rule !== "unknown" ? (fx.attendance_rule === "all_required" ? "전 요일 필수" : "요일 선택") : ""}` : '<span class="faint">추출 기록 없음</span>';
          return `<tr><td class="name" data-label="강좌">${esc(c.name)}<span class="sub">${esc(c.sport)} · ${c.scheduleAmbiguous ? "시간표 연결 후보 " + c.scheduleCandidates + "개 · 확인 필요" : (c.scheduleSource === "none" ? "시간표 미확인" : "공개 시간표 연결됨")}</span></td>
            <td data-label="시설">${esc(c.facilityName)}</td><td data-label="시간">${esc(fmtSessions(c.sessions))}</td><td class="num" data-label="월 수강료">${fmtWon(c.priceWon)}</td><td class="num" data-label="마지막 집계월 신청">${fmtNum(c.lastApplicants)} <span class="sub">${esc(c.lastMonth)}</span></td><td data-label="추출 정보">${facts}</td></tr>`;
        }).join("")}</tbody></table></div>`;
      explain(el);
    } catch (e) { el.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
  }
  load();
})();
