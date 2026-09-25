(function () {
  const root = document.getElementById("detail-root");
  const code = root.dataset.region;
  const body = document.getElementById("detail-body");

  function statCard(a) {
    const na = !a.computable;
    let v = "–";
    if (!na) v = a.key === "sport" ? fmtNum(a.value) : (a.key === "quantity" ? fmtNum(a.value, 2) : fmtPct(a.value, 1));
    const rank = a.rankNational ? `<span class="rank-pill ${a.rankNational <= 20 ? "hot" : ""}">전국 ${a.rankNational} / ${a.regionTotal}</span>` : "";
    return `<div class="card stat ${na ? "na" : ""}"><div class="label">${esc(a.label)} ${provBadge("public")}</div><div class="value">${v}</div><div class="desc">${esc(a.desc)}${na ? " · 계산 불가(데이터 없음)" : ""}</div><div class="mt-8">${rank}</div></div>`;
  }

  function bars(pairs, total, labelFn) {
    const max = Math.max(1, ...pairs.map((p) => p[1]));
    return `<div class="bar-list">${pairs.map(([k, v]) => `<div class="bar-row"><span class="k" title="${esc(k)}">${esc(labelFn ? labelFn(k) : k)}</span><div class="bar"><span style="width:${(v / max * 100).toFixed(1)}%"></span></div><span class="v">${fmtNum(v)}${total ? ` <small>(${fmtPct(v / total)})</small>` : ""}</span></div>`).join("")}</div>`;
  }

  async function load() {
    try {
      const d = await api.get(`/api/gap/${code}`);
      const r = d.region, s = d.stats || {};
      document.getElementById("region-title").textContent = `${r.sidoName} ${r.sigunguName}`;
      document.getElementById("region-sub").textContent = `인구 ${fmtNum(r.population)} · 이용권 대상자 ${fmtNum(r.targetsTotal)} · 수급자 ${fmtNum(r.recipientsTotal)} · 기준연도 ${s.baseYear || "–"} · 강좌 활동 기준 ${r.activeCutoffMonth || "–"} 이후`;
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
            <p class="small mt-8"><b>이용자 신호</b> · 등록 수요 ${fmtNum((d.signals || {}).demand ? d.signals.demand.total : 0)}건${d.signals && d.signals.demand && d.signals.demand.bySport.length ? " (" + d.signals.demand.bySport.slice(0, 4).map((s) => esc(s.sport) + " " + s.count).join(", ") + ")" : ""} · 가맹 요청 ${fmtNum((d.signals || {}).voteTotal || 0)}건${d.signals && d.signals.votes && d.signals.votes.length ? " — " + d.signals.votes.slice(0, 3).map((v) => esc(v.name) + " " + v.votes).join(", ") : ""}</p>
            ${r.notComputable && r.notComputable.length ? `<p class="faint">계산 불가: ${esc(r.notComputable.join(", "))}</p>` : ""}
          </div>
          <div class="card card-pad">
            <div class="card-head"><h3>종목 분포 <small class="faint">최근 12개월 강좌 ${fmtNum(sportsTotal)}개</small></h3></div>
            ${d.sportCounts.length ? bars(d.sportCounts.slice(0, 10), sportsTotal) : '<p class="muted">활동 강좌가 없습니다.</p>'}
          </div>
        </div>
        <div class="grid-2 mb-16">
          <div class="card card-pad"><div class="card-head"><h3>시작 시각 분포 <small class="faint">시간 확인 강좌 ${fmtNum(r.scheduleKnownCount)}개</small></h3></div>${r.scheduleKnownCount ? bars(hourPairs) : '<p class="muted">시간표가 결합된 강좌가 없습니다.</p>'}</div>
          <div class="card card-pad"><div class="card-head"><h3>요일 분포</h3></div>${r.scheduleKnownCount ? bars(dowPairs) : '<p class="muted">–</p>'}</div>
        </div>
        <div class="card card-pad mb-16">
          <div class="card-head"><h3>가맹시설 <small class="faint">${fmtNum(r.voucherFacilityCount)}곳 · 최근 12개월 신청 인원 많은 순</small></h3><button class="btn btn-sm btn-ghost" id="toggle-fac">전체 보기</button></div>
          <div class="table-wrap"><table class="table responsive" id="fac-table"><thead><tr><th>시설</th><th>종목</th><th class="num">최근 12개월 신청</th><th>마지막 강좌월</th><th>정류장 도보</th><th>전체시설 대조</th></tr></thead><tbody id="fac-body"></tbody></table></div>
        </div>
        <div class="card card-pad">
          <div class="card-head"><h3>강좌 <small class="faint">활동 강좌, 종목 필터</small></h3><select class="input" id="course-sport" style="width:auto;min-width:160px"><option value="">전체 종목</option></select></div>
          <div id="course-list"><div class="empty-state"><span class="spinner"></span></div></div>
        </div>`;
      renderFacilities(d.facilities, 20);
      let expanded = false;
      document.getElementById("toggle-fac").addEventListener("click", (e) => { expanded = !expanded; renderFacilities(d.facilities, expanded ? 400 : 20); e.target.textContent = expanded ? "접기" : "전체 보기"; });
      loadCourses("");
      document.getElementById("course-sport").addEventListener("change", (e) => loadCourses(e.target.value));
    } catch (e) { body.innerHTML = `<div class="notice error">${esc(e.message)}</div>`; }
  }

  function renderFacilities(list, n) {
    const tb = document.getElementById("fac-body");
    tb.innerHTML = list.slice(0, n).map((f) => {
      const u = f.usage || {}; const t = f.transit; const m = f.allMatch || {};
      const matchLabel = m.allFacilityId ? `<span class="badge badge-ok">대조됨 (${esc(m.matchType)})</span>` : (m.status === "candidates" ? '<span class="badge badge-warn">유사 시설 검토 필요</span>' : '<span class="badge badge-muted">미대조</span>');
      return `<tr><td class="name" data-label="시설"><a href="#" data-fac="${esc(f.facilityId)}">${esc(f.name)}</a><span class="sub">${esc(f.address || "")}</span></td>
        <td data-label="종목">${esc((f.sports || []).join(", "))}</td>
        <td class="num" data-label="최근 12개월 신청">${fmtNum(u.last12mApplicants)} ${u.active ? '<span class="badge badge-ok">활동</span>' : '<span class="badge badge-muted">비활동</span>'}</td>
        <td data-label="마지막 강좌월">${esc(u.lastMonth || "–")}</td>
        <td data-label="정류장 도보">${t ? `${Math.round(t.minWalkSec / 60)}분 (${esc(t.stopType)} ${esc(t.stopName)})` : "–"}</td>
        <td data-label="전체시설 대조">${matchLabel}</td></tr>`;
    }).join("") || '<tr><td colspan="6" class="empty-state">가맹시설이 없습니다.</td></tr>';
    tb.querySelectorAll("[data-fac]").forEach((a) => a.addEventListener("click", async (e) => { e.preventDefault(); showFacility(a.dataset.fac); }));
  }

  async function showFacility(id) {
    try {
      const f = await api.get(`/api/gap/${code}/facility/${id}`);
      const u = f.usage || {};
      const html = `<div class="dialog-backdrop open" id="fac-dialog"><div class="dialog dialog-lg"><div class="dialog-header"><h2>${esc(f.name)}</h2><button class="btn-icon" data-dialog-close>&times;</button></div>
        <dl class="kv"><dt>주소</dt><dd>${esc(f.address || "")} ${esc(f.detailAddress || "")}</dd><dt>전화</dt><dd>${esc(f.tel || "–")}</dd><dt>종목</dt><dd>${esc((f.sports || []).join(", "))}</dd><dt>가맹 결정일</dt><dd>${esc(f.decisionDate || "–")}</dd>
        <dt>이용 이력</dt><dd>${u.firstMonth ? `${esc(u.firstMonth)} ~ ${esc(u.lastMonth)} · 누적 신청 ${fmtNum(u.totalApplicants)} · 최근 12개월 ${fmtNum(u.last12mApplicants)}` : "없음"}</dd>
        <dt>출처</dt><dd>${(f.sources || []).map(provBadge.bind(null, "public")).join(" ")} ${esc((f.sources || []).join(", "))}</dd></dl>
        <h3 class="mt-16">강좌 ${f.courses.length}개</h3>
        <div class="table-wrap"><table class="table"><thead><tr><th>강좌</th><th>종목</th><th>시간</th><th class="num">월 수강료</th><th>마지막 월</th><th class="num">신청</th></tr></thead><tbody>
        ${f.courses.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.sport)}</td><td>${esc(fmtSessions(c.sessions))}</td><td class="num">${fmtWon(c.priceWon)}</td><td>${esc(c.lastMonth)}</td><td class="num">${fmtNum(c.lastApplicants)}</td></tr>`).join("")}
        </tbody></table></div></div></div>`;
      const old = document.getElementById("fac-dialog"); if (old) old.remove();
      document.body.insertAdjacentHTML("beforeend", html);
    } catch (e) { showSnackbar(e.message, "error"); }
  }

  async function loadCourses(sport) {
    const el = document.getElementById("course-list");
    try {
      const d = await api.get(`/api/gap/${code}/courses` + qs({ sport, limit: 100 }));
      const sel = document.getElementById("course-sport");
      if (sel.options.length === 1) d.sports.forEach((s) => { const o = document.createElement("option"); o.value = s.sport; o.textContent = `${s.sport} (${s.count})`; sel.appendChild(o); });
      if (!d.courses.length) { el.innerHTML = '<p class="muted">활동 강좌가 없습니다.</p>'; return; }
      el.innerHTML = `<div class="table-wrap"><table class="table responsive"><thead><tr><th>강좌</th><th>시설</th><th>시간</th><th class="num">월 수강료</th><th class="num">최근 신청</th><th>AI 추출</th></tr></thead><tbody>
        ${d.courses.map((c) => {
          const fx = c.facts;
          const facts = fx ? `<span class="prov prov-${esc(fx.provenance)}">${esc(fx.provenance === "llm_reviewed" ? "검토완료" : "미검토")}</span> ${fx.age_min != null || fx.age_max != null ? `연령 ${fx.age_min ?? "?"}~${fx.age_max ?? "?"}` : ""} ${fx.attendance_rule && fx.attendance_rule !== "unknown" ? (fx.attendance_rule === "all_required" ? "전 요일 필수" : "요일 선택") : ""}` : '<span class="faint">없음</span>';
          return `<tr><td class="name" data-label="강좌">${esc(c.name)}<span class="sub">${esc(c.sport)} · ${c.scheduleAmbiguous ? "시간표 후보 " + c.scheduleCandidates + "개(모호)" : (c.scheduleSource === "none" ? "시간표 없음" : "시간표 결합")}</span></td>
            <td data-label="시설">${esc(c.facilityName)}</td><td data-label="시간">${esc(fmtSessions(c.sessions))}</td><td class="num" data-label="월 수강료">${fmtWon(c.priceWon)}</td><td class="num" data-label="최근 신청">${fmtNum(c.lastApplicants)} <span class="sub">${esc(c.lastMonth)}</span></td><td data-label="AI 추출">${facts}</td></tr>`;
        }).join("")}</tbody></table></div>`;
    } catch (e) { el.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
  }
  load();
})();
