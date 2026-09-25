(function () {
  const $ = (id) => document.getElementById(id);
  let editingKey = null;
  function fmtBytes(b) { if (b == null) return "–"; return b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : (b / 1024).toFixed(0) + " KB"; }
  function renderJob(j) {
    $("job-bar").style.width = (j.percent || 0) + "%";
    $("job-bar").className = "progress-bar " + (j.status === "failed" ? "failed" : (j.status === "done" ? "done" : ""));
    $("job-pct").textContent = (j.percent || 0) + "%";
    $("job-step").textContent = j.status === "running" ? `${j.stepLabel || "시작"} — ${j.message || ""}` : (j.status === "done" ? `완료 · ${j.message || ""}` : (j.status === "failed" ? j.message : "대기 중 (마지막 적재 없음)"));
    $("job-meta").textContent = j.status === "idle" ? "" : `${j.status} · ${j.elapsedSec || 0}초${j.startedAt ? " · 시작 " + j.startedAt.slice(0, 19).replace("T", " ") : ""}`;
    $("job-log").innerHTML = (j.log || []).map((l) => `<li>[${l.t}s] ${esc(l.label)} — ${esc(l.message || "")}</li>`).join("");
    $("import-btn").disabled = j.status === "running";
    $("import-btn").textContent = j.status === "running" ? "적재 중…" : "전체 다시 적재";
  }
  async function load() {
    try {
      const d = await api.get("/api/data/sources");
      renderJob(d.job);
      $("src-body").innerHTML = d.rows.map((r) => `
        <tr>
          <td class="name" data-label="데이터"><b>${esc(r.title)}</b><span class="sub">${esc(r.fileName)} · ${esc(r.provider)} · ${esc(r.cycle)} 갱신${r.required ? ' · <span class="badge">필수</span>' : ""}</span></td>
          <td data-label="역할"><span class="small">${esc(r.role)}</span>${r.note ? `<span class="sub">${esc(r.note)}</span>` : ""}</td>
          <td data-label="출처"><a href="${esc(r.url)}" target="_blank" rel="noopener" class="small">상품 페이지</a>${r.asOf ? `<span class="sub">기준일 ${esc(r.asOf)}</span>` : ""}<br><button class="btn btn-sm btn-ghost mt-8" data-edit="${esc(r.key)}">출처 편집</button></td>
          <td data-label="파일">${r.present ? `${fmtBytes(r.bytes)}<span class="sub">수정 ${esc((r.modifiedAt || "").slice(0, 16).replace("T", " "))}</span>` : '<span class="badge badge-danger">없음</span>'}</td>
          <td data-label="적재">${r.importedSha256 ? `<span class="mono small">${esc(r.importedSha256.slice(0, 10))}…</span>${r.changedSinceImport ? '<span class="sub"><span class="badge badge-warn">파일 변경됨 · 재적재 필요</span></span>' : '<span class="sub"><span class="badge badge-ok">적재됨</span></span>'}` : '<span class="badge badge-muted">미적재</span>'}</td>
          <td data-label="교체"><label class="btn btn-sm btn-outline" for="up-${esc(r.key)}">CSV 올리기</label><input type="file" id="up-${esc(r.key)}" accept=".csv" data-upload="${esc(r.key)}" hidden /><div class="progress mt-8" id="upbar-${esc(r.key)}" hidden><div class="progress-bar"></div></div></td>
        </tr>`).join("");
      const STEP_LABELS = { regions: "시군구", voucher_facilities: "가맹시설 병합", courses: "강좌·시간표 결합", all_facilities: "전체시설·안전·교통 결합", voucher_transit: "가맹시설 정류장 결합", matching: "가맹↔전체시설 매칭", aggregates: "시군구 집계" };
      const KEY_LABELS = { count: "건수", unmappedRegions: "지역 미매핑", unique: "시간표 유일 결합", ambiguous: "시간표 후보 여럿(모호)", no_schedule: "시간표 없음", course_table_rows: "강좌 데이터 행", monthlyDocs: "월별 이용현황 문서", allFacilities: "전체시설", safetyJoined: "안전점검 결합", safetyRows: "안전점검 행", transitJoined: "정류장 결합", joined: "정류장 결합", none: "미매칭", exact_name_addr: "이름+주소 일치", exact_tel_region: "지역 내 전화 일치", exact_name_region: "지역 내 유일 이름", candidates: "검토 후보(AI·사람 판정)", dataMaxMonth: "최신 강좌월" };
      const stepDetail = (steps) => Object.entries(steps).map(([k, v]) => `<div class="step-block"><b>${esc(STEP_LABELS[k] || k)}</b><ul>${Object.entries(v || {}).map(([kk, vv]) => `<li>${esc(KEY_LABELS[kk] || kk)}: <span class="mono">${typeof vv === "number" ? fmtNum(vv) : esc(String(vv))}</span></li>`).join("")}</ul></div>`).join("");
      $("ver-body").innerHTML = d.versions.map((v) => { const s = (v.log || {}).steps || {}; return `<tr><td class="mono">${esc(v.datasetVersion)}</td><td>${v.status === "active" ? '<span class="badge badge-ok">활성</span>' : esc(v.status)}</td><td>${esc((v.importedAt || "").slice(0, 19).replace("T", " "))}</td><td class="num">${fmtNum((s.voucher_facilities || {}).count)}</td><td class="num">${fmtNum((s.courses || {}).count)}</td><td class="num">${fmtNum((s.all_facilities || {}).allFacilities)}</td><td class="num">${(v.log || {}).elapsedSec ? (v.log || {}).elapsedSec + "s" : "–"}</td></tr>${Object.keys(s).length ? `<tr class="ver-detail"><td colspan="7"><details class="expandable" ${v.status === "active" ? "open" : ""}><summary>단계별 건수 (${esc(v.datasetVersion)})</summary><div class="step-grid">${stepDetail(s)}</div></details></td></tr>` : ""}`; }).join("") || '<tr><td colspan="7" class="empty-state">이력 없음</td></tr>';
      $("src-body").querySelectorAll("[data-upload]").forEach((inp) => inp.addEventListener("change", () => upload(inp)));
      $("src-body").querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => { const r = d.rows.find((x) => x.key === b.dataset.edit); editingKey = r.key; $("src-dialog-title").textContent = r.title + " 출처"; $("src-url").value = r.url || ""; $("src-asof").value = r.asOf || ""; $("src-note").value = r.note || ""; openDialog("src-dialog"); }));
    } catch (e) { showSnackbar(e.message, "error"); }
  }
  function upload(inp) {
    const file = inp.files[0]; if (!file) return;
    const key = inp.dataset.upload; const bar = $("upbar-" + key); bar.hidden = false; const fill = bar.querySelector(".progress-bar"); fill.style.width = "0%";
    const xhr = new XMLHttpRequest(); const fd = new FormData(); fd.append("file", file, file.name);
    xhr.open("POST", "/api/data/upload/" + key);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) fill.style.width = Math.round(e.loaded / e.total * 100) + "%"; };
    xhr.onload = () => { if (xhr.status === 200) { showSnackbar("파일을 교체했습니다. '전체 다시 적재'를 누르세요.", "success"); load(); } else { let m = "업로드 실패"; try { m = JSON.parse(xhr.responseText).detail || m; } catch (e) {} showSnackbar(m, "error"); bar.hidden = true; } inp.value = ""; };
    xhr.onerror = () => { showSnackbar("업로드 중 연결 오류", "error"); bar.hidden = true; };
    xhr.send(fd);
  }
  $("import-btn").addEventListener("click", async () => {
    if (!confirm("원본 10종을 다시 읽어 새 버전으로 적재합니다. 약 1~2분 걸리며 끝나면 모든 화면이 새 버전을 씁니다. 진행할까요?")) return;
    try { const r = await api.post("/api/data/import"); renderJob(r.job); } catch (e) { showSnackbar(e.message, "error"); }
  });
  $("src-save").addEventListener("click", async () => {
    try { await api.put("/api/data/sources/" + editingKey, { url: $("src-url").value, asOf: $("src-asof").value, note: $("src-note").value }); closeDialog("src-dialog"); showSnackbar("저장했습니다", "success"); load(); } catch (e) { showSnackbar(e.message, "error"); }
  });
  // 실시간: SSE + 폴링 보조
  try {
    const es = new EventSource("/events");
    es.onmessage = (m) => { let d; try { d = JSON.parse(m.data); } catch (e) { return; } if (d.type === "import_progress") { renderJob({ ...d, log: [] }); if (d.status === "done" || d.status === "failed") setTimeout(load, 800); } };
  } catch (e) {}
  setInterval(async () => { if (document.hidden) return; try { const j = await api.get("/api/data/import/status"); if (j.status === "running") renderJob(j); } catch (e) {} }, 5000);
  load();
})();
