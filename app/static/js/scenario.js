(function () {
  const meta = window.META || {};
  const SPORTS = ["수영", "태권도", "헬스", "축구(풋살)", "복싱", "필라테스", "댄스(줌바 등)", "무용(발레 등)", "줄넘기", "농구", "야구", "검도", "유도", "합기도", "요가", "주짓수", "배드민턴", "탁구", "기타종목"];
  let sc = loadScenario() || emptyScenario();
  const $ = (id) => document.getElementById(id);
  const sido = $("sc-sido"), sg = $("sc-sigungu"), sport = $("sc-sport");
  SPORTS.forEach((s) => { const o = document.createElement("option"); o.value = s; o.textContent = s; sport.appendChild(o); });
  function fillSigungu() {
    sg.innerHTML = '<option value="">시군구</option>';
    const s = (meta.sidos || []).find((x) => x.sidoCode === sido.value);
    (s ? s.regions : []).forEach((r) => { const o = document.createElement("option"); o.value = r.regionCode; o.textContent = r.name; sg.appendChild(o); });
  }
  const urlRegion = new URLSearchParams(location.search).get("region");
  if (urlRegion && !sc.regionCode) sc.regionCode = urlRegion;
  if (sc.regionCode) { sido.value = sc.regionCode.slice(0, 2); fillSigungu(); sg.value = sc.regionCode; }
  if (sc.sport) sport.value = sc.sport;
  sido.addEventListener("change", fillSigungu);
  $("sc-budget").value = sc.budgetWon ?? "";
  $("sc-mode").value = sc.mode || "capacity";
  $("sc-title").value = sc.title || "";

  const DOW = ["월", "화", "수", "목", "금", "토", "일"];
  const PROVS = [["confirmed", "담당자확인"], ["assumed", "가정"], ["public", "공공자료"], ["llm_reviewed", "AI검토완료"]];
  const provSelect = (v, cls) => `<select class="input ${cls}">${PROVS.map(([k, l]) => `<option value="${k}" ${k === v ? "selected" : ""}>${l}</option>`).join("")}</select>`;

  function persist() { syncFromForm(); saveScenario(sc); $("sc-saved").textContent = "이 브라우저에 저장됨 " + new Date().toLocaleTimeString("ko-KR"); }
  function syncFromForm() {
    sc.regionCode = sg.value || sc.regionCode; sc.sport = sport.value;
    sc.budgetWon = $("sc-budget").value === "" ? null : Number($("sc-budget").value);
    sc.mode = $("sc-mode").value; sc.title = $("sc-title").value;
  }

  // ---------- 수요 집단
  function renderGroups() {
    const el = $("groups");
    if (!sc.demandGroups.length) { el.innerHTML = '<p class="muted">수요 집단을 추가하세요. 예: 지역아동센터 A, 8명, 화·목 16~18시.</p>'; return; }
    el.innerHTML = sc.demandGroups.map((g, i) => `
      <div class="list-item" data-i="${i}">
        <div class="head"><b>${esc(g.label || "집단 " + (i + 1))}</b><div class="row"><span class="prov prov-${esc(g.provenance)}">${esc(PROV_LABEL[g.provenance] || g.provenance)}</span><button class="btn-icon" data-del-group="${i}" aria-label="삭제">&times;</button></div></div>
        <div class="grid">
          <div class="field"><label>이름</label><input class="input" data-g="label" value="${esc(g.label)}" /></div>
          <div class="field"><label>인원</label><input class="input" data-g="size" type="number" min="1" value="${g.size}" /></div>
          <div class="field"><label>종목</label><select class="input" data-g="sport">${SPORTS.map((s) => `<option ${s === g.sport ? "selected" : ""}>${s}</option>`).join("")}</select></div>
          <div class="field"><label>연령(만)</label><div class="row"><input class="input" data-g="ageMin" type="number" min="3" max="25" placeholder="최소" value="${g.ageMin ?? ""}" /><input class="input" data-g="ageMax" type="number" min="3" max="25" placeholder="최대" value="${g.ageMax ?? ""}" /></div></div>
          <div class="field"><label>주당 횟수(선택 출석용)</label><input class="input" data-g="sessionsPerWeek" type="number" min="1" max="7" value="${g.sessionsPerWeek ?? ""}" /></div>
          <div class="field"><label>이동·준비 여유(분)</label><input class="input" data-g="bufferMinutes" type="number" min="0" max="120" value="${g.bufferMinutes ?? 0}" /></div>
          <div class="field"><label>이동 수단</label><select class="input" data-g="transport"><option value="walk" ${g.transport === "walk" ? "selected" : ""}>자력 이동</option><option value="own_vehicle" ${g.transport === "own_vehicle" ? "selected" : ""}>기관 차량</option><option value="needs_support" ${g.transport === "needs_support" ? "selected" : ""}>이동 지원 필요</option></select></div>
          <div class="field"><label>출처</label>${provSelect(g.provenance, "g-prov")}</div>
        </div>
        <div class="field mt-8"><label>가용 시간 <span class="faint">(요일별, 비우면 제약 없음)</span></label>
          <div class="stack" data-avail="${i}">${(g.availability || []).map((w, j) => availRow(i, j, w)).join("")}</div>
          <button class="btn btn-sm btn-ghost mt-8" data-add-avail="${i}">+ 시간 추가</button></div>
      </div>`).join("");
    el.querySelectorAll("[data-g]").forEach((inp) => inp.addEventListener("change", (e) => {
      const i = Number(e.target.closest(".list-item").dataset.i); const k = e.target.dataset.g; let v = e.target.value;
      if (["size", "ageMin", "ageMax", "sessionsPerWeek", "bufferMinutes"].includes(k)) v = v === "" ? null : Number(v);
      sc.demandGroups[i][k] = v; persist(); if (k === "label") renderGroups();
    }));
    el.querySelectorAll(".g-prov").forEach((s) => s.addEventListener("change", (e) => { sc.demandGroups[Number(e.target.closest(".list-item").dataset.i)].provenance = e.target.value; persist(); renderGroups(); }));
    el.querySelectorAll("[data-del-group]").forEach((b) => b.addEventListener("click", () => { sc.demandGroups.splice(Number(b.dataset.delGroup), 1); persist(); renderGroups(); }));
    el.querySelectorAll("[data-add-avail]").forEach((b) => b.addEventListener("click", () => { const g = sc.demandGroups[Number(b.dataset.addAvail)]; (g.availability = g.availability || []).push({ weekday: 1, startMinute: 960, endMinute: 1080 }); persist(); renderGroups(); }));
    el.querySelectorAll("[data-avail-field]").forEach((inp) => inp.addEventListener("change", (e) => {
      const [i, j, k] = e.target.dataset.availField.split(":"); const w = sc.demandGroups[i].availability[j];
      if (k === "weekday") w.weekday = Number(e.target.value); else w[k] = toMin(e.target.value); persist();
    }));
    el.querySelectorAll("[data-del-avail]").forEach((b) => b.addEventListener("click", () => { const [i, j] = b.dataset.delAvail.split(":"); sc.demandGroups[i].availability.splice(Number(j), 1); persist(); renderGroups(); }));
  }
  function availRow(i, j, w) {
    return `<div class="row"><select class="input" style="width:auto" data-avail-field="${i}:${j}:weekday">${DOW.map((d, k) => `<option value="${k}" ${k === w.weekday ? "selected" : ""}>${d}</option>`).join("")}</select>
      <input class="input" style="width:auto" type="time" step="900" data-avail-field="${i}:${j}:startMinute" value="${fmtTime(w.startMinute)}" /> ~ <input class="input" style="width:auto" type="time" step="900" data-avail-field="${i}:${j}:endMinute" value="${fmtTime(w.endMinute)}" />
      <button class="btn-icon" data-del-avail="${i}:${j}" aria-label="삭제">&times;</button></div>`;
  }
  function toMin(t) { const [h, m] = (t || "0:0").split(":").map(Number); return h * 60 + (m || 0); }

  // ---------- 공급 옵션
  function renderOptions() {
    const el = $("options");
    if (!sc.supplyOptions.length) { el.innerHTML = '<p class="muted">"공급 옵션·후보 불러오기"로 실제 강좌를 채우거나 직접 추가하세요.</p>'; return; }
    el.innerHTML = sc.supplyOptions.map((o, i) => `
      <div class="list-item" data-i="${i}">
        <div class="head"><b>${esc(o.label)}</b><div class="row">${o.exists ? '<span class="badge badge-ok">기존</span>' : '<span class="badge badge-warn">신설 필요</span>'}${o.voucherAffiliated === true ? '<span class="badge">가맹</span>' : (o.voucherAffiliated === false ? '<span class="badge badge-muted">비가맹</span>' : '<span class="badge badge-warn">가맹 미확인</span>')}<button class="btn-icon" data-del-option="${i}" aria-label="삭제">&times;</button></div></div>
        <div class="grid">
          <div class="field"><label>이름</label><input class="input" data-o="label" value="${esc(o.label)}" /></div>
          <div class="field"><label>종목</label><select class="input" data-o="sport">${SPORTS.map((s) => `<option ${s === o.sport ? "selected" : ""}>${s}</option>`).join("")}</select></div>
          <div class="field"><label>정원(추가 수용)</label><div class="row"><input class="input" data-o="capacity" type="number" min="0" placeholder="미확인" value="${o.capacity ?? ""}" />${provSelect(o.capacityProvenance, "o-capprov")}</div></div>
          <div class="field"><label>출석 규칙</label><select class="input" data-o="attendanceRule"><option value="unknown" ${o.attendanceRule === "unknown" ? "selected" : ""}>미확인(전 요일 필수로 가정)</option><option value="all_required" ${o.attendanceRule === "all_required" ? "selected" : ""}>전 요일 필수</option><option value="selectable" ${o.attendanceRule === "selectable" ? "selected" : ""}>요일 선택</option></select></div>
          <div class="field"><label>대상 연령</label><div class="row"><input class="input" data-o="ageMin" type="number" placeholder="최소" value="${o.ageMin ?? ""}" /><input class="input" data-o="ageMax" type="number" placeholder="최대" value="${o.ageMax ?? ""}" /></div></div>
          <div class="field"><label>가맹 여부</label><select class="input" data-o="voucherAffiliated"><option value="" ${o.voucherAffiliated == null ? "selected" : ""}>미확인</option><option value="true" ${o.voucherAffiliated === true ? "selected" : ""}>가맹</option><option value="false" ${o.voucherAffiliated === false ? "selected" : ""}>비가맹</option></select></div>
          <div class="field"><label>월 수강료</label><input class="input" data-o="priceWon" type="number" value="${o.priceWon ?? ""}" /></div>
          <div class="field"><label>존재 여부</label><select class="input" data-o="exists"><option value="true" ${o.exists ? "selected" : ""}>기존 강좌</option><option value="false" ${!o.exists ? "selected" : ""}>신설 필요</option></select></div>
        </div>
        <div class="field mt-8"><label>시간표 <span class="faint">${o.meta && o.meta.scheduleAmbiguous ? "· 원본 시간표 후보가 여럿(모호)" : ""}${o.meta && o.meta.lastMonth ? " · 마지막 강좌월 " + esc(o.meta.lastMonth) + " · 최근 신청 " + fmtNum(o.meta.lastApplicants) : ""}</span></label>
          <div class="stack" data-sess="${i}">${(o.sessions || []).map((s, j) => sessRow(i, j, s)).join("")}</div>
          <button class="btn btn-sm btn-ghost mt-8" data-add-sess="${i}">+ 세션 추가</button></div>
        <div class="field mt-8"><label>집단별 이동 가능 여부 <span class="faint">(비우면 미확인)</span></label><div class="row">${sc.demandGroups.map((g) => `<label class="checkbox-row" style="margin:0"><select class="input" style="min-height:32px;padding:4px" data-reach="${i}:${g.id}"><option value="" ${o.reachable && o.reachable[g.id] == null ? "selected" : ""}>${esc(g.label)}: 미확인</option><option value="true" ${o.reachable && o.reachable[g.id] === true ? "selected" : ""}>${esc(g.label)}: 가능</option><option value="false" ${o.reachable && o.reachable[g.id] === false ? "selected" : ""}>${esc(g.label)}: 불가</option></select></label>`).join("") || '<span class="faint">수요 집단을 먼저 추가하세요</span>'}</div></div>
      </div>`).join("");
    el.querySelectorAll("[data-o]").forEach((inp) => inp.addEventListener("change", (e) => {
      const i = Number(e.target.closest(".list-item").dataset.i); const k = e.target.dataset.o; let v = e.target.value;
      if (["capacity", "ageMin", "ageMax", "priceWon"].includes(k)) v = v === "" ? null : Number(v);
      if (k === "voucherAffiliated") v = v === "" ? null : v === "true";
      if (k === "exists") v = v === "true";
      sc.supplyOptions[i][k] = v; persist(); if (["label", "exists", "voucherAffiliated"].includes(k)) renderOptions();
    }));
    el.querySelectorAll(".o-capprov").forEach((s) => s.addEventListener("change", (e) => { sc.supplyOptions[Number(e.target.closest(".list-item").dataset.i)].capacityProvenance = e.target.value; persist(); }));
    el.querySelectorAll("[data-del-option]").forEach((b) => b.addEventListener("click", () => { sc.supplyOptions.splice(Number(b.dataset.delOption), 1); persist(); renderOptions(); renderActions(); }));
    el.querySelectorAll("[data-add-sess]").forEach((b) => b.addEventListener("click", () => { const o = sc.supplyOptions[Number(b.dataset.addSess)]; (o.sessions = o.sessions || []).push({ weekday: 1, startMinute: 960, endMinute: 1020 }); persist(); renderOptions(); }));
    el.querySelectorAll("[data-sess-field]").forEach((inp) => inp.addEventListener("change", (e) => {
      const [i, j, k] = e.target.dataset.sessField.split(":"); const s = sc.supplyOptions[i].sessions[j];
      if (k === "weekday") s.weekday = Number(e.target.value); else s[k] = toMin(e.target.value); persist();
    }));
    el.querySelectorAll("[data-del-sess]").forEach((b) => b.addEventListener("click", () => { const [i, j] = b.dataset.delSess.split(":"); sc.supplyOptions[i].sessions.splice(Number(j), 1); persist(); renderOptions(); }));
    el.querySelectorAll("[data-reach]").forEach((s) => s.addEventListener("change", (e) => { const [i, gid] = e.target.dataset.reach.split(":"); const o = sc.supplyOptions[i]; o.reachable = o.reachable || {}; if (e.target.value === "") delete o.reachable[gid]; else o.reachable[gid] = e.target.value === "true"; persist(); }));
  }
  function sessRow(i, j, s) {
    return `<div class="row"><select class="input" style="width:auto" data-sess-field="${i}:${j}:weekday">${DOW.map((d, k) => `<option value="${k}" ${k === s.weekday ? "selected" : ""}>${d}</option>`).join("")}</select>
      <input class="input" style="width:auto" type="time" step="300" data-sess-field="${i}:${j}:startMinute" value="${fmtTime(s.startMinute)}" /> ~ <input class="input" style="width:auto" type="time" step="300" data-sess-field="${i}:${j}:endMinute" value="${fmtTime(s.endMinute)}" />
      <button class="btn-icon" data-del-sess="${i}:${j}" aria-label="삭제">&times;</button></div>`;
  }

  // ---------- 조치
  const KIND = { affiliate: "가맹 협의", open_course: "강좌 신설", add_capacity: "정원 추가", transport: "이동 지원" };
  function renderActions() {
    const el = $("actions");
    if (!sc.actions.length) { el.innerHTML = '<p class="muted">조치를 추가하세요. 후보 시설을 불러오면 "가맹 협의 + 강좌 신설" 쌍이 채워집니다.</p>'; return; }
    const facilities = [...new Map(sc.supplyOptions.map((o) => [o.facilityId, o.facilityName || o.facilityId])).entries()];
    el.innerHTML = sc.actions.map((a, i) => `
      <div class="list-item" data-i="${i}">
        <div class="head"><b>${esc(a.id)} · ${esc(a.label)}</b><div class="row"><span class="badge">${KIND[a.kind]}</span><span class="prov prov-${esc(a.costProvenance)}">비용 ${esc(PROV_LABEL[a.costProvenance] || a.costProvenance)}</span><button class="btn-icon" data-del-action="${i}" aria-label="삭제">&times;</button></div></div>
        <div class="grid">
          <div class="field"><label>이름</label><input class="input" data-a="label" value="${esc(a.label)}" /></div>
          <div class="field"><label>종류</label><select class="input" data-a="kind">${Object.entries(KIND).map(([k, l]) => `<option value="${k}" ${k === a.kind ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          ${a.kind === "affiliate" || a.kind === "transport" ? `<div class="field"><label>시설</label><select class="input" data-a="facilityId"><option value="">선택</option>${facilities.map(([id, n]) => `<option value="${esc(id)}" ${id === a.facilityId ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>` : ""}
          ${a.kind === "open_course" || a.kind === "add_capacity" ? `<div class="field"><label>공급 옵션</label><select class="input" data-a="supplyOptionId"><option value="">선택</option>${sc.supplyOptions.map((o) => `<option value="${esc(o.id)}" ${o.id === a.supplyOptionId ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select></div>
          <div class="field"><label>정원(석)</label><input class="input" data-a="capacity" type="number" min="0" placeholder="미확인" value="${a.capacity ?? ""}" /></div>` : ""}
          ${a.kind === "transport" ? `<div class="field"><label>수요 집단</label><select class="input" data-a="demandGroupId"><option value="">선택</option>${sc.demandGroups.map((g) => `<option value="${esc(g.id)}" ${g.id === a.demandGroupId ? "selected" : ""}>${esc(g.label)}</option>`).join("")}</select></div>` : ""}
          <div class="field"><label>비용(원)</label><div class="row"><input class="input" data-a="costWon" type="number" min="0" placeholder="미확인" value="${a.costWon ?? ""}" />${provSelect(a.costProvenance, "a-costprov")}</div></div>
          <div class="field"><label>선행 조치(쉼표)</label><input class="input" data-a="requires" value="${esc((a.requires || []).join(","))}" /></div>
          <div class="field"><label>배타 조치(쉼표)</label><input class="input" data-a="conflicts" value="${esc((a.conflicts || []).join(","))}" /></div>
        </div>
      </div>`).join("");
    el.querySelectorAll("[data-a]").forEach((inp) => inp.addEventListener("change", (e) => {
      const i = Number(e.target.closest(".list-item").dataset.i); const k = e.target.dataset.a; let v = e.target.value;
      if (["capacity", "costWon"].includes(k)) v = v === "" ? null : Number(v);
      if (["requires", "conflicts"].includes(k)) v = v.split(",").map((s) => s.trim()).filter(Boolean);
      if (["facilityId", "supplyOptionId", "demandGroupId"].includes(k) && v === "") v = null;
      sc.actions[i][k] = v; persist(); if (["kind", "label"].includes(k)) renderActions();
    }));
    el.querySelectorAll(".a-costprov").forEach((s) => s.addEventListener("change", (e) => { sc.actions[Number(e.target.closest(".list-item").dataset.i)].costProvenance = e.target.value; persist(); renderActions(); }));
    el.querySelectorAll("[data-del-action]").forEach((b) => b.addEventListener("click", () => { sc.actions.splice(Number(b.dataset.delAction), 1); persist(); renderActions(); }));
  }

  // ---------- 불러오기
  $("sc-load").addEventListener("click", async () => {
    syncFromForm();
    if (!sc.regionCode || !sc.sport) { showSnackbar("지역과 종목을 선택하세요", "error"); return; }
    try {
      const d = await api.get("/api/scenarios/supply" + qs({ region: sc.regionCode, sport: sc.sport, limit: 20 }));
      const have = new Set(sc.supplyOptions.map((o) => o.id));
      d.supplyOptions.forEach((o) => { if (!have.has(o.id)) sc.supplyOptions.push(o); });
      const haveA = new Set(sc.actions.map((a) => a.id));
      d.candidateActions.forEach((c) => {
        if (!have.has(c.supplyOption.id)) sc.supplyOptions.push(c.supplyOption);
        c.actions.forEach((a) => { if (!haveA.has(a.id)) sc.actions.push(a); });
      });
      sc.datasetVersion = d.datasetVersion;
      const haveG = new Set(sc.demandGroups.map((g) => g.id));
      (d.demandGroups || []).forEach((g) => { if (!haveG.has(g.id)) sc.demandGroups.push(g); });
      if (d.demandGroups && d.demandGroups.length) showSnackbar(`이용자 등록 수요 ${d.demandGroups.length}개 집단을 불러왔습니다`, "success");
      if (!sc.demandGroups.length) sc.demandGroups.push({ id: uid("d"), label: "수요 집단 1", sport: sc.sport, size: 8, availability: [{ weekday: 1, startMinute: 960, endMinute: 1080 }, { weekday: 3, startMinute: 960, endMinute: 1080 }], sessionsPerWeek: 2, bufferMinutes: 0, transport: "walk", provenance: "assumed" });
      persist(); renderAll();
      showSnackbar(`공급 옵션 ${d.supplyOptions.length}개, 후보 시설 ${d.candidateActions.length}곳을 채웠습니다`, "success");
    } catch (e) { showSnackbar(e.message, "error"); }
  });
  $("add-group").addEventListener("click", () => { sc.demandGroups.push({ id: uid("d"), label: "수요 집단 " + (sc.demandGroups.length + 1), sport: sport.value || SPORTS[0], size: 8, availability: [], sessionsPerWeek: null, bufferMinutes: 0, transport: "walk", provenance: "confirmed" }); persist(); renderAll(); });
  $("add-option").addEventListener("click", () => { sc.supplyOptions.push({ id: uid("o"), label: "새 옵션", facilityId: uid("f"), facilityName: "새 시설", sport: sport.value || SPORTS[0], sessions: [], attendanceRule: "unknown", capacity: null, capacityProvenance: "assumed", voucherAffiliated: null, affiliationProvenance: "assumed", priceWon: null, exists: true, reachable: {}, provenance: "assumed" }); persist(); renderAll(); });
  $("add-action").addEventListener("click", () => { sc.actions.push({ id: uid("a"), label: "새 조치", kind: "affiliate", facilityId: null, supplyOptionId: null, demandGroupId: null, capacity: null, costWon: null, costProvenance: "assumed", requires: [], conflicts: [], provenance: "assumed" }); persist(); renderActions(); });
  ["sc-budget", "sc-mode", "sc-title"].forEach((id) => $(id).addEventListener("change", persist));
  sg.addEventListener("change", persist); sport.addEventListener("change", persist);
  $("sc-reset").addEventListener("click", () => { if (confirm("현재 시나리오를 지우고 새로 만들까요?")) { sc = emptyScenario(); saveScenario(sc); location.href = "/scenario"; } });
  $("sc-export").addEventListener("click", () => { syncFromForm(); const blob = new Blob([JSON.stringify(sc, null, 2)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `scenario_${sc.regionCode || "x"}.json`; a.click(); });
  $("sc-import").addEventListener("change", async (e) => { const f = e.target.files[0]; if (!f) return; try { sc = JSON.parse(await f.text()); saveScenario(sc); location.reload(); } catch (err) { showSnackbar("JSON을 읽지 못했습니다", "error"); } });
  $("sc-validate").addEventListener("click", validateNow);
  async function validateNow() {
    syncFromForm();
    const box = $("sc-validation");
    try {
      const v = await api.post("/api/scenarios/validate", sc);
      box.innerHTML = `${v.problems.length ? `<div class="notice error">${v.problems.map(esc).join("<br>")}</div>` : '<div class="notice">스키마 검증 통과</div>'}
        ${v.unresolved.length ? `<div class="notice warn"><b>미확인 ${v.unresolved.length}건</b> — ${v.unresolved.map((u) => esc(u.text)).join(" · ")}</div>` : ""}`;
      return v;
    } catch (e) {
      const d = e.data && e.data.detail;
      box.innerHTML = `<div class="notice error">${Array.isArray(d) ? d.map((x) => esc((x.loc || []).join(".") + ": " + x.msg)).join("<br>") : esc(e.message)}</div>`;
      return null;
    }
  }
  $("sc-compare").addEventListener("click", async () => { const v = await validateNow(); if (v && v.ok) { saveScenario(sc); location.href = "/scenario/compare"; } });
  function renderAll() { renderGroups(); renderOptions(); renderActions(); }
  renderAll();
})();
