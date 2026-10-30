(function () {
  const meta = window.META || {};
  const SPORTS = ["수영", "태권도", "헬스", "축구(풋살)", "복싱", "필라테스", "댄스(줌바 등)", "무용(발레 등)", "줄넘기", "농구", "야구", "검도", "유도", "합기도", "요가", "주짓수", "배드민턴", "탁구", "기타종목"];
  let sc = loadScenario() || emptyScenario();
  const $ = (id) => document.getElementById(id);
  function revealHelp(hash) {
    const target = document.getElementById(hash.replace(/^#/, ""));
    const detail = $("sc-help-details");
    if (!target) return;
    for (let parent = target; parent; parent = parent.parentElement) {
      if (parent.tagName === "DETAILS") parent.open = true;
    }
    if (detail && (target === detail || detail.contains(target))) detail.open = true;
    requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  }
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-scenario-help]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    history.replaceState(null, "", link.hash);
    revealHelp(link.hash);
  });
  window.addEventListener("hashchange", () => revealHelp(location.hash));
  if (location.hash) revealHelp(location.hash);
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

  // Keep help attached when editable rows are rebuilt after changes.
  function explainEditor(scope) {
    const fields = {
      g: {
        label: "집단을 구분할 익명 이름입니다. 개인 이름·연락처는 입력하지 마세요.",
        size: "이 조건으로 강좌를 이용하려는 사람 수입니다. 등록 건수로 불러온 값은 실제 인원을 확인해 수정하세요.",
        sport: "이 집단의 희망 종목입니다. 강좌 종목과 정확히 일치해야 연결됩니다.",
        ageMin: "집단의 최소 만 나이입니다. 양쪽 연령 정보가 있으면 집단 전체 범위가 강좌 대상 연령 안에 있어야 합니다.",
        ageMax: "집단의 최대 만 나이입니다. 연령을 비우면 연령 조건으로 차단하지 않으므로 실제 자격을 확인하세요.",
        sessionsPerWeek: "요일 선택 강좌에서 필요한 주당 수업 횟수입니다. 비우면 1회로 비교하며 전 요일 필수 강좌에는 적용하지 않습니다.",
        bufferMinutes: "수업 시작 전과 종료 후에 각각 확보할 이동·준비 시간입니다. 이 여유를 포함한 전체 시간이 집단의 이용 가능 시간 안에 들어가야 합니다.",
        transport: "자력 이동·기관 차량은 이동 가능 여부 미입력 시 이동 조건으로 차단하지 않습니다. 이동 지원 필요 집단은 이동 가능 확인이나 해당 시설·집단 이동 지원 조치가 필요합니다."
      },
      o: {
        label: "기존 또는 신설 예정 강좌를 구분할 이름입니다.",
        sport: "이 강좌의 종목입니다. 집단의 희망 종목과 일치해야 연결됩니다.",
        capacity: "이번 수요를 추가로 받을 수 있는 인원입니다. 빈칸은 미확인, 0은 추가 수용 불가입니다. 신설 조치에 정원을 입력한다면 여기에는 0을 입력해 중복 합산을 피하세요.",
        attendanceRule: "전 요일 필수는 모든 수업이 시간에 맞아야 합니다. 요일 선택은 주당 필요 횟수만큼 맞으면 됩니다. 미확인은 전 요일 필수로 계산합니다.",
        ageMin: "강좌에서 받을 수 있는 최소 만 나이입니다. 연령 미입력은 연령 제한 없음이 아니라 확인되지 않은 상태입니다.",
        ageMax: "강좌에서 받을 수 있는 최대 만 나이입니다. 집단 연령 범위가 강좌 대상 범위 안에 들어가야 합니다.",
        voucherAffiliated: "스포츠 강좌이용권 가맹 상태를 입력합니다. 미가맹·미확인은 이 시설의 가맹 협의 조치가 선택되어야 이용 가능한 상태로 가정합니다.",
        priceWon: "공개 자료 또는 확인한 월 수강료입니다. 개선 조치 예산에서 차감하는 비용이 아니며 현재 요금·지원 가능 금액은 별도 확인이 필요합니다.",
        exists: "이미 운영 중인 강좌인지 신설 예정인지 선택합니다. 신설 필요 강좌는 해당 강좌 신설 조치를 선택해야 계산에 포함됩니다."
      },
      a: {
        label: "개선 조치를 구분할 이름입니다. 선행·동시 선택 불가 조건에는 이름 대신 상단의 조치 ID를 사용합니다.",
        kind: "가맹 협의는 시설 가맹 상태, 강좌 신설은 개설과 정원, 정원 추가는 추가 좌석, 이동 지원은 선택한 집단·시설의 이동 가능 상태를 계산에 반영합니다.",
        facilityId: "가맹 협의 또는 이동 지원을 적용할 시설입니다. 이동 지원에서는 대상 집단도 함께 선택하세요.",
        supplyOptionId: "강좌 신설·정원 추가 조치를 적용할 강좌입니다. 이름이 비슷한 기존·신설 강좌를 구분해 선택하세요.",
        capacity: "이 조치로 새로 확보할 자리 수입니다. 강좌의 추가 수용 인원과 합산되므로 같은 인원을 중복 입력하지 마세요.",
        demandGroupId: "이동 지원을 적용할 집단입니다. 선택한 집단과 시설의 이동 조건에만 반영됩니다.",
        costWon: "이 조치의 비용입니다. 0은 비용 없음, 빈칸은 미확인입니다. 비용 미확인 조합은 예산 내 최선 조합에서 제외됩니다.",
        requires: "이 조치를 선택하려면 함께 필요한 조치 ID를 쉼표로 입력합니다. 예: a1,a2. 이름이 아닌 카드 상단의 ID를 쓰며, 필요한 조치가 없으면 ‘없음’으로 입력합니다.",
        conflicts: "이 조치와 동시에 선택할 수 없는 조치 ID를 쉼표로 입력합니다. 함께 선택할 수 없는 조치가 없으면 ‘없음’으로 입력합니다."
      }
    };
    scope.querySelectorAll("[data-g], [data-o], [data-a]").forEach((el) => {
      const kind = el.hasAttribute("data-g") ? "g" : el.hasAttribute("data-o") ? "o" : "a";
      const text = fields[kind][el.dataset[kind]];
      if (text) { el.dataset.tooltip = text; const label = el.closest(".field")?.querySelector("label"); if (label) label.dataset.tooltip = text; }
      if (kind === "o" && ["ageMin", "ageMax", "attendanceRule"].includes(el.dataset.o)) {
        const option = sc.supplyOptions[Number(el.closest(".list-item").dataset.i)];
        if (option.meta?.assumedFields?.includes(el.dataset.o)) {
          el.dataset.tooltip += " 이 예시 입력값에서는 공개 자료로 확인되지 않아 가정값으로 채웠습니다.";
          const label = el.closest(".field")?.querySelector("label");
          if (label && !label.querySelector(".preset-assumption")) label.insertAdjacentHTML("beforeend", ' <span class="badge badge-warn preset-assumption" data-tooltip="공개 자료에 확인된 값이 없어 예시 계산을 위해 채운 가정입니다. 실제 대상 연령·출석 조건은 시설에 확인해야 합니다.">가정값</span>');
        }
      }
    });
    const controls = {
      "[data-del-group]": "이 수요 집단을 작성 내용에서 삭제합니다. 연결된 이동 지원 조치가 있으면 함께 확인하세요.",
      "[data-del-option]": "이 강좌를 작성 내용에서 삭제합니다. 이 강좌를 참조하는 개선 조치가 있으면 수정하거나 삭제하세요.",
      "[data-del-action]": "이 개선 조치를 삭제합니다. 다른 조치의 선행·동시 선택 불가 조건에서 해당 ID를 참조하는지 확인하세요.",
      "[data-add-avail]": "집단이 수업에 참여할 수 있는 요일과 시간 구간을 추가합니다. 여러 구간을 입력할 수 있습니다.",
      "[data-avail-field]": "집단이 이동·준비 시간을 포함해 참여할 수 있는 요일·시작·종료 시간입니다. 모든 구간을 비우면 시간 제약 없이 계산합니다.",
      "[data-del-avail]": "이 이용 가능 시간 구간을 삭제합니다. 모두 삭제하면 시간 제한 없이 계산합니다.",
      "[data-add-sess]": "강좌의 실제 수업 요일과 시작·종료 시각을 추가합니다. 수업 시간표가 없으면 연결할 수 없습니다.",
      "[data-sess-field]": "강좌 수업의 요일·시작·종료 시간입니다. 공개 시간표가 현재 일정과 같은지 시설에 확인하세요.",
      "[data-del-sess]": "이 수업 시간 구간을 삭제합니다. 시간표가 전부 없어지면 강좌와 집단을 연결할 수 없습니다.",
      "[data-reach]": "이 집단이 해당 시설에 갈 수 있는지 입력합니다. 불가는 이동 지원이 필요하며, 미확인 상태의 자력 이동·기관 차량 집단은 이동 때문에 차단하지 않습니다.",
      ".g-prov, .o-capprov, .a-costprov": "정보의 출처·확인 상태입니다. 직접 확인한 값은 담당자확인, 시험 계산용 값은 가정으로 표시합니다. 출처 선택만으로 빈 정원·비용이 채워지지는 않습니다."
    };
    Object.entries(controls).forEach(([selector,text]) => scope.querySelectorAll(selector).forEach(el => el.dataset.tooltip = text));
    const badges = { "기존": "기존 강좌로 입력된 상태입니다. 현재 운영 여부를 자동으로 확인한 결과는 아닙니다.", "신설 필요": "신설 예정으로 입력되어 강좌 신설 조치를 선택해야 이용 가능한 상태로 계산됩니다.", "가맹": "가맹 상태로 입력된 시설입니다. 현재 실제 가맹 유지 여부는 별도로 확인하세요.", "비가맹": "미가맹으로 입력된 상태입니다. 가맹 협의 조치를 선택하면 가맹이 가능하다는 가정으로 계산합니다.", "가맹 미확인": "실제 가맹 여부를 확인하지 않은 상태입니다. 계산에서 이용하려면 가맹 협의 조치가 필요합니다." };
    Object.assign(badges, {
      "가맹 협의": "이 시설을 스포츠 강좌이용권 가맹 상태로 가정하는 조치입니다. 실제 가맹 승인이나 비용 집행을 실행하지 않습니다.",
      "강좌 신설": "선택한 신설 예정 강좌를 개설 상태로 가정하고 입력한 정원을 추가하는 조치입니다.",
      "정원 추가": "선택한 강좌의 추가 수용 인원에 이 조치의 정원을 더합니다.",
      "이동 지원": "선택한 집단이 선택한 시설에 이동할 수 있도록 지원하는 상태로 가정합니다."
    });
    scope.querySelectorAll(".prov").forEach(el => {
      const key = [...el.classList].find(c => c.startsWith("prov-"))?.slice(5);
      if (typeof PROV_HELP !== "undefined" && PROV_HELP[key]) el.dataset.tooltip = PROV_HELP[key];
    });
    scope.querySelectorAll(".badge").forEach(el => { if (badges[el.textContent]) el.dataset.tooltip = badges[el.textContent]; });
  }

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
          <div class="field"><label>구분 이름</label><input class="input" data-g="label" value="${esc(g.label)}" /></div>
          <div class="field"><label>인원</label><input class="input" data-g="size" type="number" min="1" value="${g.size}" /></div>
          <div class="field"><label>종목</label><select class="input" data-g="sport">${SPORTS.map((s) => `<option ${s === g.sport ? "selected" : ""}>${s}</option>`).join("")}</select></div>
          <div class="field"><label>연령(만)</label><div class="row"><input class="input" data-g="ageMin" type="number" min="3" max="100" placeholder="최소" value="${g.ageMin ?? ""}" /><input class="input" data-g="ageMax" type="number" min="3" max="100" placeholder="최대" value="${g.ageMax ?? ""}" /></div></div>
          <div class="field"><label>주당 횟수(선택 출석용)</label><input class="input" data-g="sessionsPerWeek" type="number" min="1" max="7" value="${g.sessionsPerWeek ?? ""}" /></div>
          <div class="field"><label>이동·준비 여유(분)</label><input class="input" data-g="bufferMinutes" type="number" min="0" max="120" value="${g.bufferMinutes ?? 0}" /></div>
          <div class="field"><label>이동 수단</label><select class="input" data-g="transport"><option value="walk" ${g.transport === "walk" ? "selected" : ""}>자력 이동</option><option value="own_vehicle" ${g.transport === "own_vehicle" ? "selected" : ""}>기관 차량</option><option value="needs_support" ${g.transport === "needs_support" ? "selected" : ""}>이동 지원 필요</option></select></div>
          <div class="field"><label>출처</label>${provSelect(g.provenance, "g-prov")}</div>
        </div>
        <div class="field mt-8"><label>이용 가능 시간 <span class="faint">(요일별, 비우면 제약 없음)</span></label>
          <div class="stack" data-avail="${i}">${(g.availability || []).map((w, j) => availRow(i, j, w)).join("")}</div>
          <button class="btn btn-sm btn-ghost mt-8" data-add-avail="${i}">+ 시간 추가</button></div>
      </div>`).join("");
    explainEditor(el);
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
    if (!sc.supplyOptions.length) { el.innerHTML = '<p class="muted">강좌와 가맹 검토 시설을 불러오거나 강좌를 직접 추가해 주세요.</p>'; return; }
    el.innerHTML = sc.supplyOptions.map((o, i) => `
      <div class="list-item" data-i="${i}">
        <div class="head"><b>${esc(o.label)}</b><div class="row">${o.exists ? '<span class="badge badge-ok">기존</span>' : '<span class="badge badge-warn">신설 필요</span>'}${o.voucherAffiliated === true ? '<span class="badge">가맹</span>' : (o.voucherAffiliated === false ? '<span class="badge badge-muted">비가맹</span>' : '<span class="badge badge-warn">가맹 미확인</span>')}<button class="btn-icon" data-del-option="${i}" aria-label="삭제">&times;</button></div></div>
        <div class="grid">
          <div class="field"><label>구분 이름</label><input class="input" data-o="label" value="${esc(o.label)}" /></div>
          <div class="field"><label>종목</label><select class="input" data-o="sport">${SPORTS.map((s) => `<option ${s === o.sport ? "selected" : ""}>${s}</option>`).join("")}</select></div>
          <div class="field"><label>정원(추가 수용)</label><div class="row"><input class="input" data-o="capacity" type="number" min="0" placeholder="미확인" value="${o.capacity ?? ""}" />${provSelect(o.capacityProvenance, "o-capprov")}</div></div>
          <div class="field"><label>출석 규칙</label><select class="input" data-o="attendanceRule"><option value="unknown" ${o.attendanceRule === "unknown" ? "selected" : ""}>미확인(전 요일 필수로 가정)</option><option value="all_required" ${o.attendanceRule === "all_required" ? "selected" : ""}>전 요일 필수</option><option value="selectable" ${o.attendanceRule === "selectable" ? "selected" : ""}>요일 선택</option></select></div>
          <div class="field"><label>대상 연령</label><div class="row"><input class="input" data-o="ageMin" type="number" placeholder="최소" value="${o.ageMin ?? ""}" /><input class="input" data-o="ageMax" type="number" placeholder="최대" value="${o.ageMax ?? ""}" /></div></div>
          <div class="field"><label>가맹 여부</label><select class="input" data-o="voucherAffiliated"><option value="" ${o.voucherAffiliated == null ? "selected" : ""}>미확인</option><option value="true" ${o.voucherAffiliated === true ? "selected" : ""}>가맹</option><option value="false" ${o.voucherAffiliated === false ? "selected" : ""}>비가맹</option></select></div>
          <div class="field"><label>월 수강료</label><input class="input" data-o="priceWon" type="number" value="${o.priceWon ?? ""}" /></div>
          <div class="field"><label>개설 상태</label><select class="input" data-o="exists"><option value="true" ${o.exists ? "selected" : ""}>기존 강좌</option><option value="false" ${!o.exists ? "selected" : ""}>신설 필요</option></select></div>
        </div>
        <div class="field mt-8"><label>시간표 <span class="faint">${o.meta && o.meta.scheduleAmbiguous ? "· 시간표 연결 후보가 여러 개 · 확인 필요" : ""}${o.meta && o.meta.lastMonth ? " · 마지막 기록월 " + esc(o.meta.lastMonth) + " · 마지막 집계월 신청 " + fmtNum(o.meta.lastApplicants) : ""}</span></label>
          <div class="stack" data-sess="${i}">${(o.sessions || []).map((s, j) => sessRow(i, j, s)).join("")}</div>
          <button class="btn btn-sm btn-ghost mt-8" data-add-sess="${i}">+ 수업 시간 추가</button></div>
        <div class="field mt-8"><label>집단별 이동 가능 여부 <span class="faint">(비우면 미확인)</span></label><div class="row">${sc.demandGroups.map((g) => `<label class="checkbox-row" style="margin:0"><select class="input" style="min-height:32px;padding:4px" data-reach="${i}:${g.id}"><option value="" ${o.reachable && o.reachable[g.id] == null ? "selected" : ""}>${esc(g.label)}: 미확인</option><option value="true" ${o.reachable && o.reachable[g.id] === true ? "selected" : ""}>${esc(g.label)}: 가능</option><option value="false" ${o.reachable && o.reachable[g.id] === false ? "selected" : ""}>${esc(g.label)}: 불가</option></select></label>`).join("") || '<span class="faint">수요 집단을 먼저 추가하세요</span>'}</div></div>
      </div>`).join("");
    explainEditor(el);
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
          <div class="field"><label>구분 이름</label><input class="input" data-a="label" value="${esc(a.label)}" /></div>
          <div class="field"><label>종류</label><select class="input" data-a="kind">${Object.entries(KIND).map(([k, l]) => `<option value="${k}" ${k === a.kind ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          ${a.kind === "affiliate" || a.kind === "transport" ? `<div class="field"><label>시설</label><select class="input" data-a="facilityId"><option value="">선택</option>${facilities.map(([id, n]) => `<option value="${esc(id)}" ${id === a.facilityId ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>` : ""}
          ${a.kind === "open_course" || a.kind === "add_capacity" ? `<div class="field"><label>대상 강좌</label><select class="input" data-a="supplyOptionId"><option value="">선택</option>${sc.supplyOptions.map((o) => `<option value="${esc(o.id)}" ${o.id === a.supplyOptionId ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select></div>
          <div class="field"><label>정원(석)</label><input class="input" data-a="capacity" type="number" min="0" placeholder="미확인" value="${a.capacity ?? ""}" /></div>` : ""}
          ${a.kind === "transport" ? `<div class="field"><label>수요 집단</label><select class="input" data-a="demandGroupId"><option value="">선택</option>${sc.demandGroups.map((g) => `<option value="${esc(g.id)}" ${g.id === a.demandGroupId ? "selected" : ""}>${esc(g.label)}</option>`).join("")}</select></div>` : ""}
          <div class="field"><label>비용(원)</label><div class="row"><input class="input" data-a="costWon" type="number" min="0" placeholder="미확인" value="${a.costWon ?? ""}" />${provSelect(a.costProvenance, "a-costprov")}</div></div>
          <div class="field"><label>선행 조치 ID</label><input class="input" data-a="requires" value="${esc((a.requires || []).join(",") || "없음")}" /></div>
          <div class="field"><label>동시 선택 불가 조치 ID</label><input class="input" data-a="conflicts" value="${esc((a.conflicts || []).join(",") || "없음")}" /></div>
        </div>
      </div>`).join("");
    explainEditor(el);
    el.querySelectorAll("[data-a]").forEach((inp) => inp.addEventListener("change", (e) => {
      const i = Number(e.target.closest(".list-item").dataset.i); const k = e.target.dataset.a; let v = e.target.value;
      if (["capacity", "costWon"].includes(k)) v = v === "" ? null : Number(v);
      if (["requires", "conflicts"].includes(k)) v = v.split(",").map((s) => s.trim()).filter((s) => s && s !== "없음");
      if (["facilityId", "supplyOptionId", "demandGroupId"].includes(k) && v === "") v = null;
      sc.actions[i][k] = v; persist(); if (["kind", "label"].includes(k)) renderActions();
    }));
    el.querySelectorAll(".a-costprov").forEach((s) => s.addEventListener("change", (e) => { sc.actions[Number(e.target.closest(".list-item").dataset.i)].costProvenance = e.target.value; persist(); renderActions(); }));
    el.querySelectorAll("[data-del-action]").forEach((b) => b.addEventListener("click", () => { sc.actions.splice(Number(b.dataset.delAction), 1); persist(); renderActions(); }));
  }

  // ---------- 불러오기
  let presets = [], presetRequest = 0, presetSource = null;
  const presetSelect = $("sc-preset");
  const selectedPreset = () => presets.find(p => p.id === presetSelect.value);
  function describePreset() {
    const preset = selectedPreset();
    $("sc-preset-description").textContent = preset?.description || "실제 강좌의 입력값을 불러오는 중입니다.";
    const explanation = preset?.explanation;
    $("sc-preset-explanation").innerHTML = explanation ? `<h4>이 입력 조합은 무엇을 비교하나요?</h4><p>${esc(explanation.purpose)}</p><dl>${[["현재 상태(가정)", explanation.before], ["추가하는 지원(가정)", explanation.support], ["결과를 읽는 방법", explanation.interpretation]].map(([label, text]) => `<div><dt>${esc(label)}</dt><dd>${esc(text)}</dd></div>`).join("")}</dl>` : "";
    $("sc-preset-source").innerHTML = preset ? `<p class="small"><b>공개 자료에서 가져오는 강좌</b></p><ul class="small stack">${preset.scenario.supplyOptions.map(o => `<li>${esc(o.facilityName)} · ${esc(o.meta.sourceCourseName)}<br><span class="muted">${esc(fmtSessions(o.sessions))} · 월 ${fmtWon(o.priceWon)} · 마지막 기록월 ${esc(o.meta.lastMonth)}</span></li>`).join("")}</ul><p class="faint">희망 인원·추가 정원·비용·예산·이동 조건과 자료에 없는 연령·출석 규칙은 가정값입니다. 현재 모집·잔여석·실제 지원 가능성을 확인한 값은 아닙니다.</p>${presetSource?.fallbackRegion ? `<p class="small muted">선택 지역에 적합한 강좌 두 개가 없어 ${esc(presetSource.regionName)}의 실제 강좌를 사용합니다. 불러오면 지역도 함께 변경됩니다.</p>` : ""}` : "";
  }
  async function refreshPresets() {
    const serial = ++presetRequest;
    presets = []; presetSelect.replaceChildren();
    $("sc-preset-load").disabled = true; presetSelect.disabled = true;
    $("sc-preset-description").textContent = "공개 자료의 실제 강좌와 시간표를 확인하는 중입니다…";
    $("sc-preset-source").replaceChildren();
    $("sc-preset-explanation").replaceChildren();
    try {
      const data = await fetchScenarioPresets(sg.value || sc.regionCode || "11110", sport.value || "수영");
      if (serial !== presetRequest) return;
      presetSource = data; presets = data.items;
      presets.forEach(preset => { const option = document.createElement("option"); option.value = preset.id; option.textContent = preset.label; presetSelect.appendChild(option); });
      describePreset();
      $("sc-preset-load").disabled = !presets.length; presetSelect.disabled = !presets.length;
    } catch (error) { if (serial === presetRequest) $("sc-preset-description").textContent = error.message; }
  }
  presetSelect.addEventListener("change", describePreset);
  sg.addEventListener("change", refreshPresets); sport.addEventListener("change", refreshPresets);
  refreshPresets();
  $("sc-preset-load").addEventListener("click", async () => {
    const preset = selectedPreset();
    if (!preset) return;
    const request = presetRequest;
    if (sc.demandGroups.length && !confirm("현재 작성 내용을 선택한 예시 입력값으로 교체할까요? 기존 내용이 필요하면 취소하고 먼저 JSON으로 내보내 주세요.")) return;
    const button = $("sc-preset-load");
    button.disabled = true; presetSelect.disabled = true; button.textContent = "입력값 불러오는 중…";
    try {
      const next = structuredClone(preset.scenario);
      const region = next.regionCode;
      const validation = await api.post("/api/scenarios/validate", next);
      if (request !== presetRequest) throw new Error("지역이나 종목이 변경되었습니다. 새로 불러온 예시 입력값을 선택해 주세요.");
      if (!validation.ok || validation.unresolved.length) throw new Error("예시 입력값을 확인하지 못했습니다. 다시 시도해 주세요.");
      if (!saveScenario(next)) throw new Error("브라우저에 저장하지 못했습니다. 저장 공간 설정을 확인해 주세요.");
      sc = next;
      sido.value = region.slice(0, 2); fillSigungu(); sg.value = region; sport.value = sc.sport;
      $("sc-budget").value = sc.budgetWon; $("sc-mode").value = sc.mode; $("sc-title").value = sc.title;
      renderAll();
      try { localStorage.removeItem(SC_BUNDLE_KEY); } catch (e) {}
      $("sc-existing-note").textContent = `${sc.title} · 강좌·시설·시간표·수강료는 공개 자료이며 정원·비용·희망 인원은 가정값입니다.`;
      $("sc-saved").textContent = "예시 입력값 저장 완료";
      $("sc-validation").innerHTML = `<div class="notice"><b>예시 입력값을 모두 채웠습니다.</b> 추가 입력 없이 아래 <b>조합 계산</b>을 누르면 결과를 확인할 수 있습니다. 강좌·시설·시간표·수강료는 공개 자료이며 정원·비용·희망 인원 등은 가정값입니다.</div>`;
      showSnackbar("입력 완료. 조합 계산을 눌러 주세요.", "success");
      requestAnimationFrame(() => $("sc-compare").scrollIntoView({ block: "center" }));
    } catch (error) { showSnackbar(error.message, "error"); }
    finally { if (request === presetRequest) { button.disabled = false; presetSelect.disabled = false; } button.textContent = "예시 입력값 불러오기"; }
  });
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
      showSnackbar(`강좌 ${d.supplyOptions.length}개와 가맹 검토 시설 ${d.candidateActions.length}곳을 불러왔습니다.`, "success");
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
