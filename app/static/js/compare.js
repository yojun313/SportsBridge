(function () {
  const sc = loadScenario();
  const root = document.getElementById("cmp-root");
  const sub = document.getElementById("cmp-sub");
  const toPlan = document.getElementById("to-plan");
  if (!sc || !sc.demandGroups || !sc.demandGroups.length) { root.innerHTML = '<div class="notice warn">시나리오가 없습니다. <a href="/scenario">편집 화면</a>에서 시나리오를 작성해 주세요.</div>'; return; }
  let result = null, selected = null;
  const objLabel = (r) => sc.mode === "capacity" ? `${fmtNum(r.assigned)}명 배정` : `${fmtNum(r.connectedGroups)}개 집단 연결`;
  const objVal = (r) => sc.mode === "capacity" ? r.assigned : r.connectedGroups;

  async function run() {
    try {
      result = await api.post("/api/scenarios/compare", sc);
      const L = result.labels;
      sub.textContent = `${sc.title || "제목 없음"} · 지역 ${sc.regionCode} · 종목 ${sc.sport || "–"} · 수요 ${result.baseline.totalDemand}명 · 조치 ${sc.actions.length}개 → 평가한 조합 ${result.evaluated}개 (불가 ${result.infeasible}, 예산 초과 ${result.overBudget}) · 모드: ${sc.mode === "capacity" ? "정원·비용" : "구조 탐색"}`;
      const base = result.baseline, best = result.best, g = result.greedy;
      const v = result.validation;
      const bundleCard = (r, tag, cls) => `
        <div class="combo-card ${cls || ""}" data-actions="${esc(r.actions.join(","))}">
          <div class="title"><b>${esc(tag)}</b><span class="big">${objLabel(r)}</span></div>
          <div class="combo-actions">${r.actions.length ? r.actions.map((a) => `<span class="chip">${esc(a)} ${esc(L.actions[a] || "")}</span>`).join("") : '<span class="chip off">조치 없음(현재 상태)</span>'}</div>
          <div class="row mt-8 small muted"><span>비용 ${fmtWon(r.costWon)}${r.unknownCostActions && r.unknownCostActions.length ? ` + 미확인 ${r.unknownCostActions.length}건` : ""}</span>${r.overBudget ? '<span class="badge badge-danger">예산 초과</span>' : ""}${r.budgetUndetermined ? '<span class="badge badge-warn">비용 미확인</span>' : ""}${r.assumptionDependent && r.assumptionDependent.length ? `<span class="badge badge-warn">가정 의존 ${r.assumptionDependent.length}</span>` : ""}${r.unknownCapacityOptions && r.unknownCapacityOptions.length ? `<span class="badge badge-muted">정원 미확인 옵션 ${r.unknownCapacityOptions.length}</span>` : ""}</div>
          <button class="btn btn-sm btn-outline mt-8" data-pick="${esc(r.actions.join(","))}">이 조합 선택</button>
        </div>`;
      const singles = Object.entries(result.singles).map(([id, r]) => `<tr><td>${esc(id)} ${esc(L.actions[id] || "")}</td><td class="num">${r ? objLabel(r) : "불가"}</td><td class="num">${r ? fmtWon(r.costWon) : "–"}</td><td class="num">${r ? (objVal(r) - objVal(base)) : "–"}</td></tr>`).join("");
      const syn = result.synergy;
      root.innerHTML = `
        ${v.unresolved.length ? `<div class="notice warn"><b>미확인 ${v.unresolved.length}건</b> — ${v.unresolved.map((u) => esc(u.text)).join(" · ")}. 미확인 정원은 확정 배정에서 제외되고, 미확인 비용이 있는 조합은 최선 조합으로 선택되지 않습니다.</div>` : ""}
        <div class="grid-3 mb-16">
          ${bundleCard(base, "현재 상태 (조치 없음)")}
          ${best ? bundleCard(best, "예산 내 최선 조합", "best") : '<div class="combo-card"><div class="title"><b>예산 내 최선 조합</b></div><p class="muted mt-8">예산·비용 조건을 만족하는 조합이 없습니다.</p></div>'}
          <div class="combo-card"><div class="title"><b>개별 효과 순 선택 결과</b><span class="big">${sc.mode === "capacity" ? fmtNum(g.objective) + "명" : fmtNum(g.objective) + "개 집단"}</span></div>
            <div class="combo-actions">${g.actions.length ? g.actions.map((a) => `<span class="chip">${esc(a)}</span>`).join("") : '<span class="chip off">선택된 조치 없음</span>'}</div>
            <p class="small muted mt-8">${syn ? (syn.hasSynergy ? `조치를 함께 시행할 때 추가 효과가 있습니다. 조합 효과 ${syn.comboGain}, 개별 효과 합계 ${syn.sumOfSingleGains}.` : `함께 시행해도 추가 효과는 없습니다. 조합 효과와 개별 효과 합계가 모두 ${syn.comboGain}입니다.`) : "비교할 조합이 없거나 조치가 1개입니다."}</p></div>
        </div>
        <div class="grid-2 mb-16">
          <div class="card card-pad"><div class="card-head"><h3>조치별 단독 효과</h3></div><div class="table-wrap"><table class="table"><thead><tr><th>조치</th><th class="num">결과</th><th class="num">비용</th><th class="num">증가</th></tr></thead><tbody>${singles}</tbody></table></div></div>
          <div class="card card-pad"><div class="card-head"><h3>상위 조합 <span class="faint">${result.bundles.length}개 표시</span></h3></div>
            <div class="table-wrap"><table class="table"><thead><tr><th>조치</th><th class="num">결과</th><th class="num">비용</th><th>상태</th><th></th></tr></thead><tbody>
            ${result.bundles.map((r) => `<tr><td>${r.actions.length ? r.actions.map(esc).join(" + ") : "(없음)"}</td><td class="num">${objLabel(r)}</td><td class="num">${fmtWon(r.costWon)}</td><td>${r.overBudget ? '<span class="badge badge-danger">예산 초과</span>' : ""}${r.budgetUndetermined ? '<span class="badge badge-warn">비용 미확인</span>' : ""}${!r.overBudget && !r.budgetUndetermined ? '<span class="badge badge-ok">예산 내</span>' : ""}</td><td><button class="btn btn-sm btn-ghost" data-pick="${esc(r.actions.join(","))}">선택</button></td></tr>`).join("")}
            </tbody></table></div></div>
        </div>
        <div class="card card-pad"><div class="card-head"><h3>제약 추적 <span class="faint">선택한 조합에서 어느 집단이 어느 옵션에 왜 막히는지</span></h3></div><div id="trace"></div></div>`;
      root.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => pick(b.dataset.pick ? b.dataset.pick.split(",") : [])));
      pick(best ? best.actions : []);
    } catch (e) {
      const d = e.data && e.data.detail;
      root.innerHTML = `<div class="notice error">${d && d.problems ? d.problems.map(esc).join("<br>") : esc(e.message)}</div>`;
    }
  }
  async function pick(actions) {
    selected = actions;
    root.querySelectorAll(".combo-card").forEach((c) => c.classList.toggle("best", c.dataset.actions === actions.join(",")));
    try { localStorage.setItem(SC_BUNDLE_KEY, JSON.stringify(actions)); } catch (e) {}
    toPlan.disabled = false;
    const r = await api.post("/api/scenarios/evaluate", { scenario: sc, selected: actions });
    const L = result.labels;
    const per = Object.entries(r.perGroup).map(([gid, p]) => `<li><b>${esc(L.groups[gid])}</b>: ${sc.mode === "capacity" ? `${p.assigned}/${p.size}명 배정` : ""} 연결 옵션 ${p.connectedOptions.length ? p.connectedOptions.map((o) => esc(L.options[o] || o)).join(", ") : "없음"}</li>`).join("");
    const blocked = r.blocked.map((b) => `<li><b>${esc(L.groups[b.groupId])}</b> → ${esc(L.options[b.optionId] || b.optionId)}: ${b.labels.map(esc).join(", ")}</li>`).join("");
    document.getElementById("trace").innerHTML = `<p class="small">선택 조합: ${actions.length ? actions.map((a) => `<span class="chip">${esc(a)} ${esc(L.actions[a] || "")}</span>`).join(" ") : "없음"} · ${objLabel(r)} · 비용 ${fmtWon(r.costWon)}</p>
      <div class="grid-2"><div><h4>집단별 결과</h4><ul class="trace">${per}</ul></div><div><h4>막힌 연결 ${r.blocked.length}건</h4><ul class="trace">${blocked || "<li>없음</li>"}</ul></div></div>`;
  }
  toPlan.addEventListener("click", () => { location.href = "/scenario/plan"; });
  run();
})();
