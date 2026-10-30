(function () {
  const sc = loadScenario();
  const root = document.getElementById("cmp-root");
  const sub = document.getElementById("cmp-sub");
  const toPlan = document.getElementById("to-plan");
  if (!sc || !sc.demandGroups || !sc.demandGroups.length) { root.innerHTML = '<div class="notice warn">시나리오가 없습니다. <a href="/scenario">편집 화면</a>에서 시나리오를 작성해 주세요.</div>'; return; }
  let result = null, selected = null;
  const objLabel = (r) => sc.mode === "capacity" ? `${fmtNum(r.assigned)}명 배정` : `${fmtNum(r.connectedGroups)}개 집단 연결`;
  const objVal = (r) => sc.mode === "capacity" ? r.assigned : r.connectedGroups;

  const resultHelp = {
    "현재 상태": "추가 조치 없이 입력된 기존 강좌·정원·시간·이동·가맹 조건으로 계산한 결과입니다. 미확인 정원이나 맞지 않는 시간 때문에 0명일 수 있습니다.",
    "예산 내 최선 조합": "예산과 선행·동시 선택 불가 조건을 지키면서 배정 인원(정원 미적용 비교는 연결 집단 수)이 가장 많은 조합입니다. 동률이면 비용, 조치 수가 적은 순입니다.",
    "개별 효과 순 선택 결과": "현재 선택 상태에서 효과를 가장 크게 늘리는 조치를 하나씩 추가한 결과입니다. 단독 효과가 없는 선행 조치나 결합 효과가 필요한 조합을 놓칠 수 있습니다.",
    "조치별 단독 효과": "각 조치를 하나만 선택한 결과와 현재 상태 대비 증가량입니다. 필요한 선행 조치가 빠지면 불가로 표시합니다.",
    "상위 조합": "배정 인원 또는 연결 집단 수가 많은 순으로 최대 12개를 표시합니다. 예산 초과·비용 미확인 조합도 검토용으로 포함될 수 있습니다.",
    "배정 조건 확인": "선택한 조합에서 집단별 배정 결과와 강좌를 이용할 수 없는 종목·시간·연령·이동·가맹·정원 조건을 확인합니다.",
    "조치": "선택한 개선 조치의 ID입니다. 위 카드나 지원 방안 편집 화면에서 조치 이름과 내용을 확인할 수 있습니다.",
    "결과": "정원·비용 모드에서는 배정 가능한 인원, 정원 미적용 비교에서는 연결 가능한 집단 수입니다. 실제 참여 인원이 아닙니다.",
    "비용": "이 조합의 확인되거나 가정한 조치 비용 합계입니다. 미확인 비용이 있으면 표시 합계만으로 전체 비용을 판단할 수 없습니다.",
    "증가": "해당 조치 결과에서 현재 상태 결과를 뺀 증가량입니다. 인원 또는 집단 수 단위는 계산 방식에 따라 달라집니다.",
    "상태": "입력 예산과 비용 확인 여부에 따른 상태입니다. 사업 승인이나 실제 집행 가능 여부를 뜻하지 않습니다.",
    "예산 초과": "입력한 개선 조치 예산을 초과하여 최선 조합에서 제외됩니다. 검토를 위해 선택할 수 있으므로 계획서 사용 전 확인하세요.",
    "비용 미확인": "선택 조치 중 비용을 입력하지 않은 항목이 있어 전체 비용을 확정할 수 없습니다. 최선 조합에서는 제외됩니다.",
    "예산 내": "입력한 비용 합계가 예산 조건을 충족합니다. 비용의 정확성이나 실제 예산 집행 승인을 보장하지 않습니다.",
    "가정값 사용": "계산에 가정으로 입력한 정원·비용·조건이 포함됩니다. 실제 확인값으로 수정하면 결과가 달라질 수 있습니다.",
    "추가 수용 인원 미확인 강좌": "추가 배정 정원을 알 수 없어 정원·비용 계산에서 배정 대상에서 제외된 강좌 수입니다.",
    "집단별 결과": "집단 인원 대비 배정 인원과 조건상 연결 가능한 강좌를 표시합니다. 연결 가능이어도 강좌 정원이 0이거나 다른 집단에 배정되면 인원은 0일 수 있습니다.",
    "이용 불가 사유": "집단과 강좌의 연결을 막는 조건입니다. 모든 연결이 막히지 않아도 정원이 부족하면 일부 인원은 배정되지 않을 수 있습니다."
  };
  function explainResults() {
    root.querySelectorAll("h3, h4, th, .title b, .badge").forEach(el => {
      const text = el.textContent.trim();
      const key = Object.keys(resultHelp).sort((a,b)=>b.length-a.length).find(k => text === k || text.startsWith(k + " "));
      if (key) el.dataset.tooltip = resultHelp[key];
    });
    root.querySelectorAll("table").forEach(table => {
      const headers = [...table.querySelectorAll("thead th")];
      table.querySelectorAll("tbody tr").forEach(row => [...row.cells].forEach((cell,i) => {
        if (headers[i]?.dataset.tooltip) cell.dataset.tooltip = headers[i].dataset.tooltip;
      }));
    });
    root.querySelectorAll("[data-pick]").forEach(el => el.dataset.tooltip = "이 조합을 검토 대상으로 선택합니다. 아래 집단별 결과와 이용 불가 사유가 갱신되며 협의 계획서에도 이 선택이 사용됩니다. 예산 초과·비용 미확인 상태를 함께 확인하세요.");
    root.querySelectorAll(".big").forEach(el => el.dataset.tooltip = resultHelp["결과"]);
    root.querySelectorAll(".combo-actions .chip").forEach(el => el.dataset.tooltip = "이 조합에서 선택한 개선 조치입니다. 조치 ID와 이름은 지원 방안 편집 화면에서 확인할 수 있습니다.");
  }

  async function run() {
    try {
      result = await api.post("/api/scenarios/compare", sc);
      const L = result.labels;
      sub.textContent = `${sc.title || "제목 없음"} · 지역 ${sc.regionCode} · 종목 ${sc.sport || "–"} · 수요 ${result.baseline.totalDemand}명 · 조치 ${sc.actions.length}개 → 평가한 조합 ${result.evaluated}개 (불가 ${result.infeasible}, 예산 초과 ${result.overBudget}) · 모드: ${sc.mode === "capacity" ? "정원·비용" : "정원 미적용 비교"}`;
      const base = result.baseline, best = result.best, g = result.greedy;
      const v = result.validation;
      const bundleCard = (r, tag, cls) => `
        <div class="combo-card ${cls || ""}" data-actions="${esc(r.actions.join(","))}">
          <div class="title"><b>${esc(tag)}</b><span class="big">${objLabel(r)}</span></div>
          <div class="combo-actions">${r.actions.length ? r.actions.map((a) => `<span class="chip">${esc(a)} ${esc(L.actions[a] || "")}</span>`).join("") : '<span class="chip off">조치 없음(현재 상태)</span>'}</div>
          <div class="row mt-8 small muted"><span>비용 ${fmtWon(r.costWon)}${r.unknownCostActions && r.unknownCostActions.length ? ` + 미확인 ${r.unknownCostActions.length}건` : ""}</span>${r.overBudget ? '<span class="badge badge-danger">예산 초과</span>' : ""}${r.budgetUndetermined ? '<span class="badge badge-warn">비용 미확인</span>' : ""}${r.assumptionDependent && r.assumptionDependent.length ? `<span class="badge badge-warn">가정값 사용 ${r.assumptionDependent.length}건</span>` : ""}${r.unknownCapacityOptions && r.unknownCapacityOptions.length ? `<span class="badge badge-muted">추가 수용 인원 미확인 강좌 ${r.unknownCapacityOptions.length}개</span>` : ""}</div>
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
        <div class="card card-pad"><div class="card-head"><h3>배정 조건 확인 <span class="faint">선택한 조합에서 어느 집단이 어느 강좌를 이용할 수 없는지와 그 이유</span></h3></div><div id="trace"></div></div>`;
      explainResults();
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
    const per = Object.entries(r.perGroup).map(([gid, p]) => `<li><b>${esc(L.groups[gid])}</b>: ${sc.mode === "capacity" ? `${p.assigned}/${p.size}명 배정` : ""} 연결 가능한 강좌 ${p.connectedOptions.length ? p.connectedOptions.map((o) => esc(L.options[o] || o)).join(", ") : "없음"}</li>`).join("");
    const blocked = r.blocked.map((b) => `<li><b>${esc(L.groups[b.groupId])}</b> → ${esc(L.options[b.optionId] || b.optionId)}: ${b.labels.map(esc).join(", ")}</li>`).join("");
    document.getElementById("trace").innerHTML = `<p class="small">선택 조합: ${actions.length ? actions.map((a) => `<span class="chip">${esc(a)} ${esc(L.actions[a] || "")}</span>`).join(" ") : "없음"} · ${objLabel(r)} · 비용 ${fmtWon(r.costWon)}</p>
      <div class="grid-2"><div><h4>집단별 결과</h4><ul class="trace">${per}</ul></div><div><h4>이용 불가 사유 ${r.blocked.length}건</h4><ul class="trace">${blocked || "<li>없음</li>"}</ul></div></div>`;
    explainResults();
  }
  toPlan.addEventListener("click", () => { location.href = "/scenario/plan"; });
  run();
})();
