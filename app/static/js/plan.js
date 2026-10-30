(function () {
  const sc = loadScenario();
  let selected = [];
  try { selected = JSON.parse(localStorage.getItem(SC_BUNDLE_KEY) || "[]"); } catch (e) {}
  const root = document.getElementById("plan-root");
  if (!sc) { root.innerHTML = '<div class="notice warn">시나리오가 없습니다. <a href="/scenario">편집 화면</a>에서 시나리오를 작성해 주세요.</div>'; return; }
  let facts = null;
  function mdToHtml(md) {
    return esc(md).replace(/^### (.*)$/gm, "<h4>$1</h4>").replace(/^## (.*)$/gm, "<h3>$1</h3>").replace(/^# (.*)$/gm, "<h2>$1</h2>")
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/_(.+?)_/g, "<i>$1</i>").replace(/^- (.*)$/gm, "• $1");
  }
  function render(d) {
    facts = d.facts;
    root.innerHTML = `
      ${d.guard && d.guard.length ? `<div class="notice error" data-tooltip="문서에 근거 데이터와 대조되지 않은 숫자·이름이 발견되었습니다. 문서를 그대로 사용하지 말고 원문과 계산 근거를 확인하세요."><b>숫자·이름 근거 대조에서 확인 필요</b>: ${d.guard.map(esc).join(", ")}</div>` : `<div class="notice" data-tooltip="문서의 숫자와 이름을 계산 근거 데이터와 대조했습니다. 사실관계·실제 영업·가맹 승인이나 정책 효과의 검증은 아닙니다.">숫자·이름 근거 대조 완료 · 출처 ${d.source === "llm" ? "AI 초안(근거 대조 완료)" : "기본 서식"} · <span class="watermark">자동 생성 초안, 담당자 검토 전</span></div>`}
      <div class="grid-2">
        <div class="card card-pad"><div class="card-head"><h3 data-tooltip="선택한 조합과 입력 조건에서 자동 작성한 협의 준비용 문서입니다. 확인 필요·가정값 사용 항목을 검토한 뒤 사용하세요.">문서 초안</h3><button class="btn btn-sm btn-ghost" id="copy-md" data-tooltip="문서 초안 원문을 마크다운 형식으로 복사합니다. 문서 편집기에 붙여 넣어 수정할 수 있습니다.">마크다운 복사</button></div><div class="doc-preview" id="doc">${mdToHtml(d.draft)}</div></div>
        <div>
          <div class="card card-pad mb-16"><div class="card-head"><h3 data-tooltip="미확인 정원·가맹·출석 조건 등 시설이나 기관에 확인할 항목입니다. 확인한 값으로 다시 계산하면 결과가 달라질 수 있습니다.">확인 필요 ${facts.unresolved.length}건</h3></div><ul class="small stack">${facts.unresolved.map((u) => `<li>• ${esc(u)}</li>`).join("") || "<li>없음</li>"}</ul>
            ${facts.assumed.length ? `<h4 class="mt-16" data-tooltip="실제 확인값 대신 모의 계산용 가정값을 사용한 항목입니다. 해당 값이 실제로 확보 가능한지 확인해야 합니다.">가정값 사용 ${facts.assumed.length}건</h4><ul class="small stack">${facts.assumed.map((u) => `<li>• ${esc(u)}</li>`).join("")}</ul>` : ""}</div>
          <div class="card card-pad"><div class="card-head"><h3 data-tooltip="선택 조합의 수요·조치·배정·비용과 확인 상태를 담은 구조화된 계산 근거입니다. 공개 원본 데이터 전체가 아닙니다.">계산 근거(JSON)</h3><button class="btn btn-sm btn-ghost" id="copy-json" data-tooltip="문서 작성에 사용한 계산 근거를 JSON 형식으로 복사합니다. 입력한 집단·시설·비용 정보가 포함될 수 있습니다.">복사</button></div><pre class="mono small" style="white-space:pre-wrap;max-height:50vh;overflow:auto">${esc(JSON.stringify(facts, null, 2))}</pre></div>
        </div>
      </div>`;
    document.getElementById("copy-md").addEventListener("click", () => navigator.clipboard.writeText(d.draft).then(() => showSnackbar("복사했습니다", "success")));
    document.getElementById("copy-json").addEventListener("click", () => navigator.clipboard.writeText(JSON.stringify(facts, null, 2)).then(() => showSnackbar("복사했습니다", "success")));
  }
  async function load() {
    try { render(await api.post("/api/scenarios/plan-draft", { scenario: sc, selected })); }
    catch (e) { root.innerHTML = `<div class="notice error">${esc(e.message)}</div>`; }
  }
  document.getElementById("print-btn").addEventListener("click", () => window.print());
  const llmBtn = document.getElementById("llm-btn");
  if (llmBtn) llmBtn.addEventListener("click", async () => {
    llmBtn.disabled = true; llmBtn.textContent = "생성 중…";
    try { render(await api.post("/api/llm/plan-doc", { scenario: sc, selected })); showSnackbar("AI 초안을 검증했습니다", "success"); }
    catch (e) { showSnackbar(e.message, "error"); }
    finally { llmBtn.disabled = false; llmBtn.textContent = "AI로 문장 다듬기"; }
  });
  load();
})();
