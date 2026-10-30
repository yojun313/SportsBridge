(function () {
  const chat = document.getElementById("chat"), tl = document.getElementById("timeline"), ev = document.getElementById("evidence");
  const form = document.getElementById("chat-form"), q = document.getElementById("q"), send = document.getElementById("send"), status = document.getElementById("run-status");
  let currentRun = null, es = null;
  const modeEl = document.querySelector("[data-agent-mode]");
  const MODE = modeEl ? modeEl.dataset.agentMode : "admin";
  const TOOL_LABEL = { resolve_place: "지역·시설 확인", get_region_diagnosis: "시군구 현황 조회", compare_regions: "지역 비교", list_supply_options: "강좌 조회", list_candidates: "가맹 검토 시설 조회", build_scenario: "지원 방안 구성", run_simulation: "조합 시뮬레이션", get_provenance: "출처 조회" };

  function addMsg(role, text, appendix) {
    const el = document.createElement("div"); el.className = "msg " + role;
    if (role === "assistant" && window.renderMarkdown) el.innerHTML = renderMarkdown(text); else el.textContent = text;
    if (appendix) { const a = document.createElement("div"); a.className = "appendix"; a.innerHTML = appendix; el.appendChild(a); }
    chat.appendChild(el); chat.scrollTop = chat.scrollHeight; return el;
  }
  function tlItem(kind, title, text, id) {
    const el = document.createElement("div"); el.className = "tl-item " + kind; el.dataset.tooltip = "답변 작성을 위해 수행한 자료 조회·계산 단계와 처리 상태입니다. 성공 표시는 현재 시설 운영 조건이나 사업 승인을 보장하지 않습니다."; if (id) el.dataset.id = id;
    const ic = { turn: "▶", call: "⚙", result: "✓", error: "✕", guard: "!", note: "·", answer: "✎", usage: "$" }[kind] || "·";
    el.innerHTML = `<span class="icon">${ic}</span><div><div class="title">${esc(title)}</div>${text ? `<div class="text">${esc(text)}</div>` : ""}</div>`;
    tl.appendChild(el); tl.scrollTop = tl.scrollHeight; return el;
  }
  function handleEvent(e) {
    if (e.type === "turn") tlItem("turn", `자료 확인 단계 ${e.turn} / ${e.max_turns}`);
    else if (e.type === "tool_call") { const el = tlItem("call", TOOL_LABEL[e.tool] || e.tool, JSON.stringify(e.input), e.id); el.classList.add("pending"); }
    else if (e.type === "tool_result") { const el = tl.querySelector(`[data-id="${CSS.escape(e.id)}"]`); if (el) { el.classList.remove("pending"); el.classList.add(e.ok ? "result" : "error"); el.querySelector(".text").textContent = e.summary; } else tlItem(e.ok ? "result" : "error", e.tool, e.summary); }
    else if (e.type === "guard") tlItem("guard", "답변 확인", e.text);
    else if (e.type === "note") tlItem(e.level === "error" ? "error" : (e.level === "warn" ? "warn" : "note"), e.text);
    else if (e.type === "answer") tlItem("answer", e.forced ? "수집된 정보로 마무리" : "최종 답변 생성");
    else if (e.type === "usage") status.textContent = `토큰 ${fmtNum(e.usage.input_tokens + e.usage.output_tokens)} · ${e.costUsd} USD`;
  }
  function renderEvidence(res) {
    const E = res.evidence || {}; const parts = [];
    (E.regions || []).forEach((r) => { const g = r.region || {}; const target = MODE === "user" ? `/user/region?region=${encodeURIComponent(g.regionCode || "")}` : `/gap/${encodeURIComponent(g.regionCode || "")}`; parts.push(`<div class="evidence-card" data-tooltip="답변 작성에 사용한 조회 자료 또는 모의 계산 결과입니다. 신청 기록은 현재 모집 인원과 다르며, 후보 시설은 실제 미가맹이 확정된 곳이 아닙니다. 출처·확인 상태와 미확인 항목을 함께 확인하세요."><div class="k">${esc(g.sidoName)} ${esc(g.sigunguName)} ${provBadge("public")}</div><div>대상자 ${fmtNum(g.targetsTotal)} · 집계기간 내 기록 시설 ${fmtNum(g.activeFacilityCount)} · 1,000명당 ${g.facilitiesPer1000Targets ?? "–"} (전국 ${g.rankFacilitiesPer1000}/${g.regionTotal}) · 종목 ${g.sportCount} · 저녁 ${fmtPct(g.eveningShare)}</div><a href="${target}" class="small" data-tooltip="이 지역의 시설·종목·시간대 지표와 자료 기준을 확인하는 화면으로 이동합니다.">지역 현황 보기</a></div>`); });
    if (E.compare && E.compare.regions) parts.push(`<div class="evidence-card" data-tooltip="답변 작성에 사용한 조회 자료 또는 모의 계산 결과입니다. 신청 기록은 현재 모집 인원과 다르며, 후보 시설은 실제 미가맹이 확정된 곳이 아닙니다. 출처·확인 상태와 미확인 항목을 함께 확인하세요."><div class="k">지역 비교 ${provBadge("public")}</div>${E.compare.regions.map((g) => `<div>${esc(g.sidoName)} ${esc(g.sigunguName)}: 대상자 ${fmtNum(g.targetsTotal)}, 집계기간 내 기록 시설 ${fmtNum(g.activeFacilityCount)}, 종목 ${g.sportCount}</div>`).join("")}</div>`);
    (E.courses || []).slice(0, 5).forEach((c) => parts.push(`<div class="evidence-card" data-tooltip="답변 작성에 사용한 조회 자료 또는 모의 계산 결과입니다. 신청 기록은 현재 모집 인원과 다르며, 후보 시설은 실제 미가맹이 확정된 곳이 아닙니다. 출처·확인 상태와 미확인 항목을 함께 확인하세요."><div class="k">${esc(c.facility)} · ${esc(c.name)} ${provBadge("public")}${c.facts && c.facts.provenance ? provBadge(c.facts.provenance) : ""}</div><div>${esc(fmtSessions(c.sessions))} · ${fmtWon(c.priceWon)} · 마지막 집계월 신청 ${fmtNum(c.lastApplicants)}</div></div>`));
    (E.candidates || []).slice(0, 5).forEach((c) => parts.push(`<div class="evidence-card" data-tooltip="답변 작성에 사용한 조회 자료 또는 모의 계산 결과입니다. 신청 기록은 현재 모집 인원과 다르며, 후보 시설은 실제 미가맹이 확정된 곳이 아닙니다. 출처·확인 상태와 미확인 항목을 함께 확인하세요."><div class="k">${esc(c.name)} ${provBadge("rule")}</div><div>${esc(c.category || "")} · 점수 ${c.score} · ${(c.reasons || []).map(esc).join(", ")}</div><div class="faint">${(c.needsConfirmation || []).map(esc).join("; ")}</div></div>`));
    if (E.simulation) { const s = E.simulation; parts.push(`<div class="evidence-card" data-tooltip="답변 작성에 사용한 조회 자료 또는 모의 계산 결과입니다. 신청 기록은 현재 모집 인원과 다르며, 후보 시설은 실제 미가맹이 확정된 곳이 아닙니다. 출처·확인 상태와 미확인 항목을 함께 확인하세요."><div class="k">지원 방안 비교 ${provBadge("confirmed")}${provBadge("assumed")}</div><div>현재 ${s.baseline ? (s.baseline.assigned ?? s.baseline.connectedGroups) : "–"} → 최선 ${s.best ? (s.best.assigned ?? s.best.connectedGroups) : "없음"} (${s.best ? s.best.actions.join(" + ") : "–"}) · 비용 ${s.best ? fmtWon(s.best.costWon) : "–"} · 개별 효과 순 ${s.greedy ? s.greedy.objective : "–"}</div><div class="faint">${s.synergy ? (s.synergy.hasSynergy ? "결합 효과 있음" : "결합 효과 없음") : ""}</div></div>`); }
    ev.innerHTML = parts.join("") || '<p class="faint">근거 없음</p>';
  }
  function finish(res) {
    status.textContent = res.completed ? "완료" : "미완료";
    const prov = Object.entries(res.provenance_summary || {}).map(([k, v]) => `${provBadge(k)} ${v}`).join(" ");
    const unres = (res.unresolved || []).map(esc).join("<br>");
    const app = `${res.cost_usd ? `비용 ${res.cost_usd} USD · ` : ""}${res.tool_trace ? `자료 조회·계산 ${res.tool_trace.length}회` : ""}${prov ? "<br>" + prov : ""}${unres ? "<br><b>확인 필요</b><br>" + unres : ""}`;
    addMsg("assistant", res.answer, app);
    renderEvidence(res);
    if (res.think_trace && res.think_trace.length) tlItem("note", "처리 요약", res.think_trace.join("\n"));
    send.disabled = false; currentRun = null;
  }
  function connect() {
    if (es) es.close();
    es = new EventSource("/events");
    es.onmessage = (m) => {
      let d; try { d = JSON.parse(m.data); } catch (e) { return; }
      if (!currentRun || d.run_id !== currentRun) return;
      if (d.type === "run_event") handleEvent(d.event);
      else if (d.type === "run_done") finish(d.result);
    };
    es.onerror = () => { status.textContent = "연결 재시도 중"; };
  }
  async function ask(text) {
    if (!text.trim() || currentRun) return;
    addMsg("user", text); tl.innerHTML = ""; ev.innerHTML = '<p class="faint">실행 중…</p>'; status.textContent = "실행 중"; send.disabled = true;
    try {
      const r = await api.post("/runs", { question: text, mode: MODE });
      currentRun = r.run_id;
      // SSE를 놓쳤을 때를 대비한 폴링
      const poll = setInterval(async () => {
        if (!currentRun) { clearInterval(poll); return; }
        try { const run = await api.get(`/runs/${r.run_id}`); if (run.status === "done" && currentRun) { clearInterval(poll); run.events.forEach((e) => { if (!tl.querySelector(`[data-id="${CSS.escape(e.id || "")}"]`) && e.type === "tool_call") handleEvent(e); }); finish(run.result); } } catch (e) {}
      }, 4000);
    } catch (e) { addMsg("assistant", e.message); send.disabled = false; currentRun = null; }
  }
  form.addEventListener("submit", (e) => { e.preventDefault(); const t = q.value; q.value = ""; ask(t); });
  q.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  document.querySelectorAll("#samples button").forEach((b) => b.addEventListener("click", () => { q.value = b.textContent; q.focus(); }));
  if (MODE === "admin") document.getElementById("hist-btn").addEventListener("click", async () => {
    openDialog("hist-dialog"); const body = document.getElementById("hist-body"); body.innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
    try { const d = await api.get("/history" + qs({ mode: MODE })); body.innerHTML = d.items.length ? d.items.map((it) => `<details class="expandable"><summary data-tooltip="선택한 과거 질문의 저장된 답변을 펼칩니다. 당시 자료와 계산 조건이 현재와 다를 수 있습니다.">${esc(it.question)} <span class="faint">${esc((it.created_at || "").slice(0, 16))}</span></summary><div class="doc-preview mt-8">${window.renderMarkdown ? renderMarkdown(it.answer) : esc(it.answer)}</div></details>`).join("") : '<p class="muted">기록이 없습니다.</p>'; }
    catch (e) { body.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
  });
  if (MODE === "admin") connect();
})();
