(function () {
  const sc = loadScenario();
  let selected = [];
  try { selected = JSON.parse(localStorage.getItem(SC_BUNDLE_KEY) || "[]"); } catch (e) {}
  const root = document.getElementById("plan-root");
  if (!sc) { root.innerHTML = '<div class="notice warn">시나리오가 없습니다. <a href="/scenario">편집 화면</a>에서 만드세요.</div>'; return; }
  let facts = null;
  function mdToHtml(md) {
    return esc(md).replace(/^### (.*)$/gm, "<h4>$1</h4>").replace(/^## (.*)$/gm, "<h3>$1</h3>").replace(/^# (.*)$/gm, "<h2>$1</h2>")
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/_(.+?)_/g, "<i>$1</i>").replace(/^- (.*)$/gm, "• $1");
  }
  function render(d) {
    facts = d.facts;
    root.innerHTML = `
      ${d.guard && d.guard.length ? `<div class="notice error"><b>숫자 검증 실패</b>: ${d.guard.map(esc).join(", ")}</div>` : `<div class="notice">숫자·이름 검증 통과 · 출처 ${d.source === "llm" ? "AI 초안(후검증 통과)" : "결정적 템플릿"} · <span class="watermark">자동 생성 초안, 담당자 검토 전</span></div>`}
      <div class="grid-2">
        <div class="card card-pad"><div class="card-head"><h3>문서 초안</h3><button class="btn btn-sm btn-ghost" id="copy-md">마크다운 복사</button></div><div class="doc-preview" id="doc">${mdToHtml(d.draft)}</div></div>
        <div>
          <div class="card card-pad mb-16"><div class="card-head"><h3>확인 필요 ${facts.unresolved.length}건</h3></div><ul class="small stack">${facts.unresolved.map((u) => `<li>• ${esc(u)}</li>`).join("") || "<li>없음</li>"}</ul>
            ${facts.assumed.length ? `<h4 class="mt-16">가정 의존 ${facts.assumed.length}건</h4><ul class="small stack">${facts.assumed.map((u) => `<li>• ${esc(u)}</li>`).join("")}</ul>` : ""}</div>
          <div class="card card-pad"><div class="card-head"><h3>근거 JSON</h3><button class="btn btn-sm btn-ghost" id="copy-json">복사</button></div><pre class="mono small" style="white-space:pre-wrap;max-height:50vh;overflow:auto">${esc(JSON.stringify(facts, null, 2))}</pre></div>
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
    finally { llmBtn.disabled = false; llmBtn.textContent = "AI로 다듬기 (GPT-5.6 Luna)"; }
  });
  load();
})();
