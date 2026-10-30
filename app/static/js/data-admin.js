(function () {
  const $ = (id) => document.getElementById(id);
  function sourceLink(raw) {
    try {
      const url = new URL(raw);
      if (url.protocol === "http:" || url.protocol === "https:") return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer" class="small" data-tooltip="제공기관의 원본 데이터 소개 페이지를 새 탭으로 엽니다.">원문 페이지</a>`;
    } catch (e) {}
    return '<span class="faint" data-tooltip="http 또는 https 형식의 유효한 출처 주소가 저장되지 않았습니다. 출처 편집에서 확인합니다.">출처 주소 확인 필요</span>';
  }
  let editingKey = null;
  function fmtBytes(b) { if (b == null) return "–"; return b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : (b / 1024).toFixed(0) + " KB"; }
  function renderJob(j) {
    $("job-bar").style.width = (j.percent || 0) + "%";
    $("job-bar").className = "progress-bar " + (j.status === "failed" ? "failed" : (j.status === "done" ? "done" : ""));
    $("job-pct").textContent = (j.percent || 0) + "%";
    $("job-step").textContent = j.status === "running" ? `${j.stepLabel || "시작"} — ${j.message || ""}` : (j.status === "done" ? `완료 · ${j.message || ""}` : (j.status === "failed" ? j.message : "대기 중 (반영 작업 기록 없음)"));
    $("job-meta").textContent = j.status === "idle" ? "" : `${({idle:"대기",running:"반영 중",done:"반영 완료",failed:"반영 실패"})[j.status] || "상태 확인 필요"} · ${j.elapsedSec || 0}초${j.startedAt ? " · 시작 " + j.startedAt.slice(0, 19).replace("T", " ") : ""}`;
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
          <td class="name" data-label="데이터" data-tooltip="원본 데이터 이름과 서버 파일명·제공기관·갱신 주기입니다. 갱신 주기는 서비스 데이터 반영 주기와 다를 수 있습니다."><b>${esc(r.title)}</b><span class="sub">${esc(r.fileName)} · ${esc(r.provider)} · ${esc(r.cycle)} 갱신${r.required ? ' · <span class="badge" data-tooltip="데이터 반영 작업에 필요한 필수 원본입니다. 원본 파일이 없으면 작업을 완료하지 못할 수 있습니다.">필수 원본</span>' : ""}</span></td>
          <td data-label="역할" data-tooltip="이 원본을 서비스의 어떤 조회·계산에 활용하는지 설명합니다."><span class="small">${esc(r.role)}</span>${r.note ? `<span class="sub">${esc(r.note)}</span>` : ""}</td>
          <td data-label="출처">${sourceLink(r.url)}${r.asOf ? `<span class="sub">기준일 ${esc(r.asOf)}</span>` : ""}<br><button class="btn btn-sm btn-ghost mt-8" data-edit="${esc(r.key)}" data-tooltip="출처 주소·원본 기준일·설명 메모를 수정합니다. CSV와 조회 데이터는 바뀌지 않습니다.">출처 편집</button></td>
          <td data-label="원본 파일" data-tooltip="서버 원본 파일의 크기와 수정 시각입니다. 수정 시각은 원본 자료의 기준일과 다릅니다.">${r.present ? `${fmtBytes(r.bytes)}<span class="sub">수정 ${esc((r.modifiedAt || "").slice(0, 16).replace("T", " "))}</span>` : '<span class="badge badge-danger" data-tooltip="서버에서 이 데이터의 원본 CSV 또는 압축 CSV 파일을 찾지 못했습니다.">원본 없음</span>'}</td>
          <td data-label="서비스 반영">${r.importedSha256 ? `<span class="mono small" data-tooltip="현재 사용 버전에 반영한 원본 파일의 SHA-256 식별값 앞 10자리입니다. 현재 서버 파일 내용을 다시 비교한 결과는 아닙니다.">${esc(r.importedSha256.slice(0, 10))}…</span>${r.changedSinceImport ? '<span class="sub"><span class="badge badge-warn" data-tooltip="현재 원본과 마지막 반영 파일의 크기가 달라 변경으로 판단했습니다. 전체 다시 적재를 실행해야 조회 데이터에 반영됩니다.">원본 크기 변경 · 재반영 필요</span></span>' : '<span class="sub"><span class="badge badge-ok" data-tooltip="현재 버전에 이 원본의 반영 기록이 있으며 파일 크기 차이는 감지되지 않았습니다. 같은 크기의 내용 변경 여부까지 확인한 것은 아닙니다.">반영 기록 있음</span></span>'}` : '<span class="badge badge-muted" data-tooltip="현재 사용 버전에서 이 원본의 반영 기록을 확인할 수 없습니다. 원본이 없거나 조회 데이터 전체가 비었다는 의미는 아닙니다.">반영 기록 없음</span>'}</td>
          <td data-label="원본 교체"><label class="btn btn-sm btn-outline" for="up-${esc(r.key)}" data-tooltip="UTF-8 CSV 파일로 이 원본을 교체합니다. 파일당 약 1.2GB까지 지원하며 교체 후 전체 다시 적재가 필요합니다.">CSV 올리기</label><input type="file" id="up-${esc(r.key)}" accept=".csv" data-upload="${esc(r.key)}" hidden /><div class="progress mt-8" id="upbar-${esc(r.key)}" hidden><div class="progress-bar"></div></div></td>
        </tr>`).join("");
      const STEP_LABELS = { regions: "시군구", voucher_facilities: "가맹시설 병합", courses: "강좌·시간표 결합", all_facilities: "전체시설·안전·교통 결합", voucher_transit: "가맹시설 정류장 결합", matching: "가맹·전체 시설 목록 연결", aggregates: "시군구 집계" };
      const KEY_LABELS = { count: "건수", unmappedRegions: "지역 연결 미확인", unique: "시간표 단일 후보 연결", ambiguous: "시간표 확인 필요", no_schedule: "시간표 없음", course_table_rows: "강좌 데이터 행", monthlyDocs: "월별 이용현황 기록", allFacilities: "전체시설", safetyJoined: "안전점검 결합", safetyRows: "안전점검 행", transitJoined: "정류장 결합", joined: "정류장 결합", none: "동일 시설 연결 안 됨", exact_name_addr: "이름+주소 일치", exact_tel_region: "지역 내 전화 일치", exact_name_region: "지역 내 유일 이름", candidates: "동일 시설 확인 후보", dataMaxMonth: "최신 강좌 기록월" };
      const stepDetail = (steps) => Object.entries(steps).map(([k, v]) => `<div class="step-block"><b>${esc(STEP_LABELS[k] || k)}</b><ul>${Object.entries(v || {}).map(([kk, vv]) => `<li data-tooltip="이 반영 단계에서 처리한 원본·연결·통계 건수입니다. 행 수·강좌 수·시설 수는 집계 단위가 다르며 실제 참여 인원이 아닙니다.">${esc(KEY_LABELS[kk] || kk)}: <span class="mono">${typeof vv === "number" ? fmtNum(vv) : esc(String(vv))}</span></li>`).join("")}</ul></div>`).join("");
      $("ver-body").innerHTML = d.versions.map((v) => { const s = (v.log || {}).steps || {}; return `<tr><td class="mono">${esc(v.datasetVersion)}</td><td>${v.status === "active" ? '<span class="badge badge-ok" data-tooltip="서비스 조회에 현재 적용 중인 데이터 버전입니다.">사용 중</span>' : `<span class="badge badge-muted" data-tooltip="이전 버전은 새 버전으로 교체된 기록입니다. 반영 중·실패는 해당 버전 작업 상태입니다. 이 표에서 과거 버전을 재적용할 수는 없습니다.">${esc(({archived:"이전 버전",failed:"반영 실패",staging:"반영 준비·진행 중",importing:"반영 중"})[v.status] || "상태 확인 필요")}</span>`}</td><td>${esc((v.importedAt || "").slice(0, 19).replace("T", " "))}</td><td class="num">${fmtNum((s.voucher_facilities || {}).count)}</td><td class="num">${fmtNum((s.courses || {}).count)}</td><td class="num">${fmtNum((s.all_facilities || {}).allFacilities)}</td><td class="num">${(v.log || {}).elapsedSec ? (v.log || {}).elapsedSec + "초" : "–"}</td></tr>${Object.keys(s).length ? `<tr class="ver-detail"><td colspan="7"><details class="expandable" ${v.status === "active" ? "open" : ""}><summary data-tooltip="원본별 처리 건수와 연결 결과를 펼칩니다. 단위가 다른 항목을 합산해 시설 수나 참여 인원으로 해석하지 않습니다.">단계별 처리 건수 (${esc(v.datasetVersion)})</summary><div class="step-grid">${stepDetail(s)}</div></details></td></tr>` : ""}`; }).join("") || '<tr><td colspan="7" class="empty-state">이력 없음</td></tr>';
      $("src-body").querySelectorAll("[data-upload]").forEach((inp) => inp.addEventListener("change", () => upload(inp)));
      $("src-body").querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => { const r = d.rows.find((x) => x.key === b.dataset.edit); editingKey = r.key; $("src-dialog-title").textContent = r.title + " 출처"; $("src-url").value = r.url || ""; $("src-asof").value = r.asOf || ""; $("src-note").value = r.note || ""; openDialog("src-dialog"); }));
    } catch (e) { showSnackbar(e.message, "error"); }
  }
  function upload(inp) {
    const file = inp.files[0]; if (!file) return;
    const key = inp.dataset.upload; const bar = $("upbar-" + key); bar.hidden = false; const fill = bar.querySelector(".progress-bar"); fill.style.width = "0%";
    const xhr = new XMLHttpRequest(); const fd = new FormData(); fd.append("file", file, file.name);
    xhr.open("POST", "/api/data/upload/" + key);
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) fill.style.width = Math.round(e.loaded / e.total * 100) + "%"; };
    xhr.onload = () => { if (xhr.status === 200) { showSnackbar("파일이 교체되었습니다. '전체 다시 적재'를 선택해 주세요.", "success"); load(); } else { let m = "업로드 실패"; try { m = JSON.parse(xhr.responseText).detail || m; } catch (e) {} showSnackbar(m, "error"); bar.hidden = true; } inp.value = ""; };
    xhr.onerror = () => { showSnackbar("업로드 중 연결 오류", "error"); bar.hidden = true; };
    xhr.send(fd);
  }
  $("import-btn").addEventListener("click", async () => {
    if (!confirm("원본 10종을 다시 읽어 새 버전으로 적재합니다. 완료되면 새 조회 데이터 버전이 적용됩니다. 소요 시간은 파일 크기와 서버 환경에 따라 다릅니다. 진행할까요?")) return;
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
