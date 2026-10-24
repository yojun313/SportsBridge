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
  function renderSports() { sp.innerHTML = SPORTS.map((s) => `<button type="button" class="chip ${sports.includes(s) ? "" : "off"}" data-s="${esc(s)}">${sports.includes(s) ? (sports.indexOf(s) + 1) + ". " : ""}${esc(s)}</button>`).join(""); sp.querySelectorAll("[data-s]").forEach((b) => b.addEventListener("click", () => { const s = b.dataset.s; if (sports.includes(s)) sports = sports.filter((x) => x !== s); else if (sports.length < 3) sports.push(s); else showSnackbar("종목은 최대 3개입니다"); renderSports(); })); }
  renderSports();
  const dw = $("u-dows");
  function renderDows() { dw.innerHTML = DOWS.map((d, i) => `<button type="button" class="dow-toggle ${dows.has(i) ? "active" : ""}" data-d="${i}">${d}</button>`).join(""); dw.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => { const i = Number(b.dataset.d); dows.has(i) ? dows.delete(i) : dows.add(i); renderDows(); })); }
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
    const conf = c.status === "match" ? '<span class="badge badge-ok">조건 일치</span>' : (c.status === "needs_confirmation" ? '<span class="badge badge-warn">확인 필요</span>' : '<span class="badge badge-muted">조건 불일치</span>');
    const favKey = c.courseId;
    return `<div class="list-item"><div class="head"><b>${esc(c.name)}</b><span class="row">${conf}<button type="button" class="fav-btn ${isFav(favKey) ? "on" : ""}" data-fav="${esc(favKey)}" data-name="${esc(c.name)}" data-facility="${esc(f.name || "")}" data-sport="${esc(c.sport)}" data-sessions="${esc(fmtSessions(c.sessions))}" data-price="${c.priceWon ?? ""}" data-address="${esc(f.address || "")}" data-tel="${esc(f.tel || "")}">${isFav(favKey) ? "★ 저장됨" : "☆ 저장"}</button></span></div>
      <div class="small"><b>${esc(f.name || "")}</b> <span class="faint">${esc(f.address || "")}${f.tel ? " · " + esc(f.tel) : ""}</span></div>
      <div class="row small mt-8"><span class="chip off">${esc(c.sport)}</span><span>${esc(fmtSessions(c.sessions))}${c.scheduleAmbiguous ? ' <span class="faint">(시간표 확인 필요)</span>' : ""}</span><span>월 ${fmtWon(c.priceWon)}</span>${t ? `<span>정류장 도보 ${Math.round(t.minWalkSec / 60)}분</span>` : ""}${sf ? `<span>안전점검 ${esc(sf.grade)}</span>` : ""}<span class="faint">최근 신청 ${fmtNum(c.lastApplicants)} (${esc(c.lastMonth)})</span></div>
      ${fx ? `<div class="small mt-8">${provBadge(fx.provenance)} ${fx.age_min != null || fx.age_max != null ? `연령 ${fx.age_min ?? "?"}~${fx.age_max ?? "?"} ` : ""}${fx.attendance_rule && fx.attendance_rule !== "unknown" ? (fx.attendance_rule === "all_required" ? "전 요일 출석" : "요일 선택 가능") : ""}</div>` : ""}
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
      const relax = d.relaxations.length ? `<div class="card card-pad mb-16"><div class="card-head"><h3>조건 변경 제안</h3><span class="faint">검색 결과가 늘어나는 조건만 표시합니다</span></div><div class="row">${d.relaxations.map((r, i) => `<button class="btn btn-outline btn-sm" data-relax="${i}">${esc(r.label)} <b>+${r.gain}</b></button>`).join("")}</div></div>` : "";
      const none = c.match + c.needs_confirmation === 0;
      const signal = `<div class="card card-pad mb-16 guide-promo"><div class="row between"><div><h3 style="margin:0 0 4px">${none ? "원하는 강좌가 없다면 희망 사항을 등록해 주세요" : "희망 강좌를 등록할 수 있습니다"}</h3><p class="small" style="margin:0">지역·종목·요일·시간대·연령대만 익명으로 저장됩니다. 담당자가 지역별 공급을 검토할 때 참고합니다. 이 지역의 등록 건수는 <b>${fmtNum(d.demandSignals.total)}</b>건${d.demandSignals.sameSport ? `, 같은 종목은 ${fmtNum(d.demandSignals.sameSport)}건` : ""}입니다.</p></div><button class="btn btn-primary btn-sm" id="u-demand">희망 강좌 등록</button></div></div>`;
      const cands = d.nearbyCandidates.length ? `<div class="card card-pad mb-16"><div class="card-head"><h3>인근 스포츠 강좌이용권 가맹 검토 시설</h3><span class="faint">이용 희망을 등록하면 담당자의 시설 검토에 참고됩니다</span></div><div class="table-wrap"><table class="table responsive"><thead><tr><th>시설</th><th>업종</th><th>안전</th><th>접근</th><th class="num">이용 희망 등록 수</th><th></th></tr></thead><tbody>${d.nearbyCandidates.map((f) => `<tr><td class="name" data-label="시설"><b>${esc(f.name)}</b><span class="sub">${esc(f.address || "")}</span></td><td data-label="업종">${esc(f.category || "")}${f.sportGuess ? " → " + esc(f.sportGuess) : ""}</td><td data-label="안전">${esc(f.safety || "–")}</td><td data-label="접근">${f.walkSec != null ? Math.round(f.walkSec / 60) + "분" : "–"}</td><td class="num" data-label="이용 희망 등록 수"><span id="v-${esc(f.facilityId)}">${f.votes}</span></td><td><button class="btn btn-sm btn-ghost" data-vote="${esc(f.facilityId)}">이용 희망 등록</button></td></tr>`).join("")}</tbody></table></div></div>` : "";
      const open = d.openSpaces.length ? `<div class="card card-pad mb-16"><div class="card-head"><h3>가능한 시간에 열려 있는 무료·공공 공간</h3><span class="faint">개방학교 체육시설 · 기준연도 확인 필요</span></div><div class="list-editor">${d.openSpaces.map((o) => `<div class="list-item"><div class="head"><b>${esc(o.name)}</b><span class="badge badge-muted">${esc(o.baseYear || "")}년 기준</span></div><div class="small">${esc(o.address || "")}</div><div class="small mt-8">종목 ${esc(o.items || "–")} · 샤워실 ${o.showers ?? "–"} · 탈의실 ${o.lockers ?? "–"}</div><div class="small mt-8">겹치는 시간: ${o.overlap.map((w) => `${DOWS[w.weekday]} ${fmtTime(w.startMinute)}~${fmtTime(w.endMinute)}`).join(", ") || esc(o.hours.map((w) => `${DOWS[w.weekday]} ${fmtTime(w.startMinute)}~${fmtTime(w.endMinute)}`).join(", "))}</div></div>`).join("")}</div></div>` : "";
      results.innerHTML = `
        <div class="grid-3 mb-16"><div class="card stat"><div class="label">조건 일치</div><div class="value">${fmtNum(c.match)}</div></div><div class="card stat"><div class="label">확인 필요</div><div class="value">${fmtNum(c.needs_confirmation)}</div></div><div class="card stat"><div class="label">조건 불일치</div><div class="value">${fmtNum(c.mismatch)}</div><div class="desc">활동 강좌 ${fmtNum(c.total)}개 중</div></div></div>
        ${relax}${signal}
        ${d.matched.length ? `<h3>조건 일치 ${fmtNum(c.match)}</h3><div class="list-editor mb-16">${d.matched.map(card).join("")}</div>` : ""}
        ${d.needsConfirmation.length ? `<h3>확인 필요 ${fmtNum(c.needs_confirmation)}</h3><div class="list-editor mb-16">${d.needsConfirmation.map(card).join("")}</div>` : ""}
        ${open}${cands}
        ${d.mismatched.length ? `<details class="expandable"><summary>조건 불일치 ${fmtNum(c.mismatch)}개 보기</summary><div class="list-editor mt-8">${d.mismatched.slice(0, 20).map(card).join("")}</div></details>` : ""}
        <p class="faint mt-16">활동 기준 ${esc(d.cutoff || "")} 이후 이용 기록이 있는 강좌만 검사했습니다. 현재 모집 여부와 잔여석은 시설에 확인하세요. 신청·결제는 <a href="https://svoucher.kspo.or.kr/main.do" target="_blank" rel="noopener">스포츠 강좌이용권 공식 사이트</a>에서 합니다.</p>`;
      results.querySelectorAll("[data-fav]").forEach((b) => b.addEventListener("click", () => toggleFav(b)));
      results.querySelectorAll("[data-relax]").forEach((b) => b.addEventListener("click", () => { const r = d.relaxations[Number(b.dataset.relax)]; showSnackbar(`${r.label} 조건으로 다시 계산`, "success"); run(r.profile); }));
      const dm = $("u-demand"); if (dm) dm.addEventListener("click", async () => { dm.disabled = true; try { const r = await api.post("/api/user/demand", { profile: lastProfile, note: "" }); showSnackbar(`수요를 등록했습니다. 이 지역 등록 수요 ${r.summary.total}건`, "success"); dm.textContent = "등록됨"; } catch (e) { showSnackbar(e.message, "error"); dm.disabled = false; } });
      results.querySelectorAll("[data-vote]").forEach((b) => b.addEventListener("click", async () => { b.disabled = true; try { const r = await api.post("/api/user/vote", { facilityId: b.dataset.vote, regionCode: lastProfile.regionCode, sport: lastProfile.sports[0] || null }); const el = document.getElementById("v-" + b.dataset.vote); if (el) el.textContent = r.votes; showSnackbar("표시했습니다. 담당자 후보 점수에 반영됩니다", "success"); b.textContent = "표시됨"; } catch (e) { showSnackbar(e.message, "error"); b.disabled = false; } }));
    } catch (e) { const det = e.data && e.data.detail; results.innerHTML = `<div class="notice error">${Array.isArray(det) ? det.map((x) => esc((x.loc || []).join(".") + ": " + x.msg)).join("<br>") : esc(e.message)}</div>`; }
  }
})();
