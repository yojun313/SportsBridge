(function () {
  const meta = window.META || {};
  const $ = (id) => document.getElementById(id);
  const SPORTS = ["태권도", "수영", "헬스", "축구(풋살)", "복싱", "필라테스", "댄스(줌바 등)", "무용(발레 등)", "줄넘기", "농구", "야구", "검도", "유도", "합기도", "요가", "주짓수", "배드민턴", "탁구", "골프", "기타종목"];
  const DOWS = ["월", "화", "수", "목", "금", "토", "일"];
  const sido = $("u-sido"), sg = $("u-sigungu"), results = $("u-results");
  let sports = [], dows = new Set([1, 3]), lastProfile = null;
  const params = new URLSearchParams(location.search);
  function fillSigungu() { sg.innerHTML = '<option value="">시군구</option>'; const s = (meta.sidos || []).find((x) => x.sidoCode === sido.value); (s ? s.regions : []).forEach((r) => { const o = document.createElement("option"); o.value = r.regionCode; o.textContent = r.name; sg.appendChild(o); }); }
  sido.addEventListener("change", fillSigungu);
  if (params.get("region")) { sido.value = params.get("region").slice(0, 2); fillSigungu(); sg.value = params.get("region"); }
  const sp = $("u-sports");
  function renderSports() { sp.innerHTML = SPORTS.map((s) => `<button type="button" class="chip ${sports.includes(s) ? "" : "off"}" data-s="${esc(s)}" data-tooltip="${sports.includes(s) ? "선택한 종목을 해제합니다." : "희망 종목에 추가합니다. 최대 3개이며 먼저 선택한 종목을 우선 정렬합니다."}">${sports.includes(s) ? (sports.indexOf(s) + 1) + ". " : ""}${esc(s)}</button>`).join(""); sp.querySelectorAll("[data-s]").forEach((b) => b.addEventListener("click", () => { const s = b.dataset.s; if (sports.includes(s)) sports = sports.filter((x) => x !== s); else if (sports.length < 3) sports.push(s); else showSnackbar("종목은 최대 3개입니다"); renderSports(); })); }
  renderSports();
  const dw = $("u-dows");
  function renderDows() { dw.innerHTML = DOWS.map((d, i) => `<button type="button" class="dow-toggle ${dows.has(i) ? "active" : ""}" data-d="${i}" data-tooltip="${d}요일 이용 가능 여부를 선택하거나 해제합니다. 모든 요일을 해제하면 시간 제한 없이 비교합니다.">${d}</button>`).join(""); dw.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => { const i = Number(b.dataset.d); dows.has(i) ? dows.delete(i) : dows.add(i); renderDows(); })); }
  renderDows();
  const toMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + (m || 0); };
  function profile() {
    const s = toMin($("u-start").value || "16:00"), e = toMin($("u-end").value || "18:00");
    return { regionCode: sg.value, userType: $("u-type").value, sports, age: $("u-age").value ? Number($("u-age").value) : null,
      availability: [...dows].sort().map((d) => ({ weekday: d, startMinute: s, endMinute: Math.max(e, s + 15) })), bufferMinutes: Number($("u-buffer").value || 0),
      monthlyBudgetWon: $("u-budget").value ? Number($("u-budget").value) : null, transport: $("u-transport").value };
  }
  $("u-form").addEventListener("submit", (e) => { e.preventDefault(); if (!sg.value) { showSnackbar("시군구를 선택해 주세요.", "error"); return; } run(profile()); });

  function favs() { try { return JSON.parse(localStorage.getItem("sb_favorites") || "[]"); } catch (e) { return []; } }
  function isFav(id) { return favs().some((x) => x.courseId === id); }
  function toggleFav(btn) {
    const arr = favs(); const i = arr.findIndex((x) => x.courseId === btn.dataset.fav);
    if (i >= 0) { arr.splice(i, 1); btn.classList.remove("on"); btn.textContent = "☆ 저장"; }
    else { arr.push({ courseId: btn.dataset.fav, name: btn.dataset.name, facility: btn.dataset.facility, sport: btn.dataset.sport, sessions: btn.dataset.sessions, priceWon: btn.dataset.price ? Number(btn.dataset.price) : null, address: btn.dataset.address, tel: btn.dataset.tel, savedAt: new Date().toLocaleDateString("ko-KR") }); btn.classList.add("on"); btn.textContent = "★ 저장됨"; showSnackbar("관심 강좌에 저장했습니다.", "success"); }
    try { localStorage.setItem("sb_favorites", JSON.stringify(arr)); } catch (e) {}
  }
  function card(c) {
    const f = c.facility || {}, t = f.transit, sf = f.safety, fx = c.facts;
    const conf = c.status === "match" ? '<span class="badge badge-ok" data-tooltip="입력한 종목·시간·연령·월 수강료 조건에서 불일치나 확인 필요 항목이 발견되지 않은 강좌입니다. 실제 잔여석·지원 자격·현재 모집 여부를 확인한 결과는 아닙니다.">조건 일치</span>' : (c.status === "needs_confirmation" ? '<span class="badge badge-warn" data-tooltip="출석 규칙·대상 연령·수강료·시간표 연결 등에 확인되지 않은 정보가 있는 강좌입니다. 시설 확인 후 이용 여부를 판단해야 합니다.">확인 필요</span>' : '<span class="badge badge-muted" data-tooltip="입력 조건과 종목·시간·연령·월 수강료 중 하나 이상이 맞지 않는 강좌입니다. 표시된 사유를 확인하거나 조건을 바꿔 다시 검색할 수 있습니다.">조건 불일치</span>');
    const favKey = c.courseId;
    return `<div class="list-item"><div class="head"><b>${esc(c.name)}</b><span class="row">${conf}<button type="button" class="fav-btn ${isFav(favKey) ? "on" : ""}" data-fav="${esc(favKey)}" data-tooltip="이 브라우저의 관심 강좌에 저장하거나 저장을 해제합니다. 지원금 계산 화면에서 확인할 수 있으며 실제 수강 신청·예약이 아닙니다." data-name="${esc(c.name)}" data-facility="${esc(f.name || "")}" data-sport="${esc(c.sport)}" data-sessions="${esc(fmtSessions(c.sessions))}" data-price="${c.priceWon ?? ""}" data-address="${esc(f.address || "")}" data-tel="${esc(f.tel || "")}">${isFav(favKey) ? "★ 저장됨" : "☆ 저장"}</button></span></div>
      <div class="small"><b>${esc(f.name || "")}</b> <span class="faint">${esc(f.address || "")}${f.tel ? " · " + esc(f.tel) : ""}</span></div>
      <div class="row small mt-8"><span class="chip off">${esc(c.sport)}</span><span data-tooltip="별도 공개 시간표에서 연결한 요일·시간입니다. 시간 미확인은 상시 이용 가능을 뜻하지 않으며 현재 수업 일정은 시설에 확인해야 합니다.">${esc(fmtSessions(c.sessions))}${c.scheduleAmbiguous ? ' <span class="faint">(시간표 확인 필요)</span>' : ""}</span><span data-tooltip="공개 자료의 지원금 차감 전 월 수강료입니다. 실제 본인부담금·현재 요금과 다를 수 있으며 –는 무료가 아닌 미확인입니다.">월 ${fmtWon(c.priceWon)}</span>${t ? `<span data-tooltip="연결된 정류장 중 최소 도보 시간을 반올림한 값입니다. 실제 출발지에서 시설까지의 전체 이동시간이 아닙니다.">정류장 도보 ${Math.round(t.minWalkSec / 60)}분</span>` : ""}${sf ? `<span data-tooltip="공개 안전점검 자료의 결과입니다. 점검일 이후 현재 시설 상태를 보증하지 않으며 자료가 없다고 위험하다는 뜻은 아닙니다.">안전점검 ${esc(sf.grade)}</span>` : ""}<span class="faint" data-tooltip="해당 강좌의 마지막 기록월 신청 인원입니다. 실제 출석·현재 모집·대기 인원이나 잔여석과 다릅니다.">마지막 집계월 신청 ${fmtNum(c.lastApplicants)} (${esc(c.lastMonth)})</span></div>
      ${fx ? `<div class="small mt-8" data-tooltip="강좌 설명에서 추출한 정보입니다. 연령·출석 규칙은 담당자 검토 완료 정보만 조건 판정에 사용하며 현재 운영 여부는 별도 확인해야 합니다.">${provBadge(fx.provenance)} ${fx.age_min != null || fx.age_max != null ? `연령 ${fx.age_min ?? "?"}~${fx.age_max ?? "?"} ` : ""}${fx.attendance_rule && fx.attendance_rule !== "unknown" ? (fx.attendance_rule === "all_required" ? "전 요일 출석" : "요일 선택 가능") : ""}</div>` : ""}
      ${c.reasonLabels.length ? `<div class="small mt-8" style="color:var(--color-danger-text)">${c.reasonLabels.map(esc).join(" · ")}</div>` : ""}
      ${c.flagLabels.length ? `<div class="small mt-8 muted">시설에 확인: ${c.flagLabels.map(esc).join(" · ")}</div>` : ""}
    </div>`;
  }
  async function run(p) {
    lastProfile = p;
    results.innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
    try {
      const d = await api.post("/api/user/recommend", p);
      const c = d.counts;
      const relax = d.relaxations.length ? `<div class="card card-pad mb-16"><div class="card-head"><h3 data-tooltip="입력 조건을 하나씩 변경했을 때 조건 일치·확인 필요 강좌가 늘어나는 경우입니다. +숫자는 늘어나는 강좌 수이며 클릭하면 변경 조건으로 다시 계산합니다.">조건 변경 제안</h3><span class="faint">검색 결과가 늘어나는 조건만 표시합니다</span></div><div class="row">${d.relaxations.map((r, i) => `<button class="btn btn-outline btn-sm" data-relax="${i}" data-tooltip="이 제안의 조건으로 다시 검색합니다. +${r.gain}은 조건 일치와 확인 필요 강좌 수의 증가분이며 실제 정원·참여 인원이 아닙니다.">${esc(r.label)} <b>+${r.gain}</b></button>`).join("")}</div></div>` : "";
      const none = c.match + c.needs_confirmation === 0;
      const signal = `<div class="card card-pad mb-16 guide-promo"><div class="row between"><div><h3 style="margin:0 0 4px">${none ? "원하는 강좌가 없다면 희망 사항을 등록해 주세요" : "희망 강좌를 등록할 수 있습니다"}</h3><p class="small" style="margin:0">희망 종목·시간대 등 이용 조건이 익명으로 저장됩니다. 담당자가 지역별 공급을 검토할 때 참고합니다. 이 지역의 등록 건수는 <b>${fmtNum(d.demandSignals.total)}</b>건${d.demandSignals.sameSport ? `, 같은 종목은 ${fmtNum(d.demandSignals.sameSport)}건` : ""}입니다.</p></div><button class="btn btn-primary btn-sm" id="u-demand" data-tooltip="현재 검색의 지역·종목·시간대 등 조건을 익명 등록합니다. 실제 수강 신청이나 강좌 개설을 보장하지 않으며 반복 등록이 포함될 수 있습니다.">희망 강좌 등록</button></div></div>`;
      const cands = d.nearbyCandidates.length ? `<div class="card card-pad mb-16"><div class="card-head"><h3 data-tooltip="선택한 시군구의 공개 체육시설 중 가맹 목록과 동일 시설로 연결되지 않은 후보입니다. 실제 미가맹이나 거리순을 확정한 목록은 아닙니다.">지역 내 스포츠 강좌이용권 가맹 검토 시설</h3><span class="faint">이용 희망을 등록하면 담당자의 시설 검토에 참고됩니다</span></div><div class="table-wrap"><table class="table responsive"><thead><tr><th data-tooltip="공개 체육시설 자료의 시설명과 주소입니다. 현재 가맹·영업 여부는 추가 확인이 필요합니다.">시설</th><th data-tooltip="공개 자료의 업종과 규칙으로 추정한 운동 종목입니다. 실제 개설 강좌와 다를 수 있습니다.">업종</th><th data-tooltip="공개 안전점검 결과입니다. –는 자료 미확인이며 현재 안전 여부를 확정하지 않습니다.">안전</th><th data-tooltip="연결된 정류장부터 시설까지의 최소 도보 시간입니다. –는 자료 미확인으로 접근 불가를 뜻하지 않습니다.">접근</th><th class="num" data-tooltip="시설 이용 희망을 등록한 건수입니다. 실인원·실제 수강 신청·대기 인원이 아니며 반복 등록이 포함될 수 있습니다.">이용 희망 등록 수</th><th></th></tr></thead><tbody>${d.nearbyCandidates.map((f) => `<tr><td class="name" data-label="시설"><b>${esc(f.name)}</b><span class="sub">${esc(f.address || "")}</span></td><td data-label="업종">${esc(f.category || "")}${f.sportGuess ? " → " + esc(f.sportGuess) : ""}</td><td data-label="안전">${esc(f.safety || "–")}</td><td data-label="접근">${f.walkSec != null ? Math.round(f.walkSec / 60) + "분" : "–"}</td><td class="num" data-label="이용 희망 등록 수"><span id="v-${esc(f.facilityId)}">${f.votes}</span></td><td><button class="btn btn-sm btn-ghost" data-vote="${esc(f.facilityId)}" data-tooltip="이 시설의 이용을 희망한다는 의견을 익명 등록합니다. 실제 가맹 신청·수강 예약이 아니며 담당자 검토 점수에 최대 3점까지 반영됩니다.">이용 희망 등록</button></td></tr>`).join("")}</tbody></table></div></div>` : "";
      const open = d.openSpaces.length ? `<div class="card card-pad mb-16"><div class="card-head"><h3 data-tooltip="희망 시간과 일부라도 겹치는 공개 학교 개방 기록입니다. 무료 여부·예약·전체 시간 이용 가능성은 시설에 확인해야 합니다.">희망 시간과 개방시간이 겹치는 학교 체육시설</h3><span class="faint">개방학교 체육시설 · 기준연도 확인 필요</span></div><div class="list-editor">${d.openSpaces.map((o) => `<div class="list-item"><div class="head"><b>${esc(o.name)}</b><span class="badge badge-muted">${esc(o.baseYear || "")}년 기준</span></div><div class="small">${esc(o.address || "")}</div><div class="small mt-8">종목 ${esc(o.items || "–")} · 샤워실 ${o.showers ?? "–"} · 탈의실 ${o.lockers ?? "–"}</div><div class="small mt-8" data-tooltip="입력한 이용 가능 시간과 공개 개방시간이 겹치는 구간입니다. 이 시간의 실제 예약·입장 가능 여부를 확인한 결과는 아닙니다.">겹치는 시간: ${o.overlap.map((w) => `${DOWS[w.weekday]} ${fmtTime(w.startMinute)}~${fmtTime(w.endMinute)}`).join(", ") || esc(o.hours.map((w) => `${DOWS[w.weekday]} ${fmtTime(w.startMinute)}~${fmtTime(w.endMinute)}`).join(", "))}</div></div>`).join("")}</div></div>` : "";
      results.innerHTML = `
        <div class="grid-3 mb-16"><div class="card stat"><div class="label" data-tooltip="입력한 종목·시간·연령·월 수강료 조건에서 불일치나 확인 필요 항목이 발견되지 않은 강좌입니다. 실제 잔여석·지원 자격·현재 모집 여부를 확인한 결과는 아닙니다.">조건 일치</div><div class="value">${fmtNum(c.match)}</div></div><div class="card stat"><div class="label" data-tooltip="출석 규칙·대상 연령·수강료·시간표 연결 등에 확인되지 않은 정보가 있는 강좌입니다. 시설 확인 후 이용 여부를 판단해야 합니다.">확인 필요</div><div class="value">${fmtNum(c.needs_confirmation)}</div></div><div class="card stat"><div class="label" data-tooltip="입력 조건과 종목·시간·연령·월 수강료 중 하나 이상이 맞지 않는 강좌입니다. 표시된 사유를 확인하거나 조건을 바꿔 다시 검색할 수 있습니다.">조건 불일치</div><div class="value">${fmtNum(c.mismatch)}</div><div class="desc">집계기간 내 강좌 ${fmtNum(c.total)}개 중</div></div></div>
        ${relax}${signal}
        ${d.matched.length ? `<h3>조건 일치 ${fmtNum(c.match)}</h3><div class="list-editor mb-16">${d.matched.map(card).join("")}</div>` : ""}
        ${d.needsConfirmation.length ? `<h3>확인 필요 ${fmtNum(c.needs_confirmation)}</h3><div class="list-editor mb-16">${d.needsConfirmation.map(card).join("")}</div>` : ""}
        ${open}${cands}
        ${d.mismatched.length ? `<details class="expandable"><summary>조건 불일치 ${fmtNum(c.mismatch)}개 보기</summary><div class="list-editor mt-8">${d.mismatched.slice(0, 20).map(card).join("")}</div></details>` : ""}
        <p class="faint mt-16">강좌 기록 기준 ${esc(d.cutoff || "")} 이후 이용 기록이 있는 강좌만 검사했습니다. 현재 모집 여부와 잔여석은 시설에 확인하세요. 신청·결제는 <a href="https://svoucher.kspo.or.kr/main.do" target="_blank" rel="noopener">스포츠 강좌이용권 공식 사이트</a>에서 합니다.</p>`;
      results.querySelectorAll("[data-fav]").forEach((b) => b.addEventListener("click", () => toggleFav(b)));
      results.querySelectorAll("[data-relax]").forEach((b) => b.addEventListener("click", () => { const r = d.relaxations[Number(b.dataset.relax)]; showSnackbar(`${r.label} 조건으로 다시 계산`, "success"); run(r.profile); }));
      const dm = $("u-demand"); if (dm) dm.addEventListener("click", async () => { dm.disabled = true; try { const r = await api.post("/api/user/demand", { profile: lastProfile, note: "" }); showSnackbar(`수요를 등록했습니다. 이 지역 등록 수요 ${r.summary.total}건`, "success"); dm.textContent = "등록됨"; } catch (e) { showSnackbar(e.message, "error"); dm.disabled = false; } });
      results.querySelectorAll("[data-vote]").forEach((b) => b.addEventListener("click", async () => { b.disabled = true; try { const r = await api.post("/api/user/vote", { facilityId: b.dataset.vote, regionCode: lastProfile.regionCode, sport: lastProfile.sports[0] || null }); const el = document.getElementById("v-" + b.dataset.vote); if (el) el.textContent = r.votes; showSnackbar("시설 이용 희망을 등록했습니다. 담당자 검토 점수에 반영됩니다.", "success"); b.textContent = "등록됨"; } catch (e) { showSnackbar(e.message, "error"); b.disabled = false; } }));
    } catch (e) { const det = e.data && e.data.detail; results.innerHTML = `<div class="notice error">${Array.isArray(det) ? det.map((x) => esc((x.loc || []).join(".") + ": " + x.msg)).join("<br>") : esc(e.message)}</div>`; }
  }
})();
