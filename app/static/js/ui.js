function showSnackbar(message, type) {
  const root = document.getElementById("snackbar-root");
  if (!root) return;
  const el = document.createElement("div");
  el.className = "snackbar" + (type ? " " + type : "");
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtNum(n, digits) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  if (digits !== undefined) return Number(n).toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
  return Number(n).toLocaleString("ko-KR");
}

function fmtPct(x, digits) {
  if (x === null || x === undefined) return "–";
  return (x * 100).toFixed(digits === undefined ? 0 : digits) + "%";
}

function fmtWon(n) {
  if (n === null || n === undefined) return "–";
  return Number(n).toLocaleString("ko-KR") + "원";
}

function fmtTime(min) {
  if (min === null || min === undefined) return "–";
  const h = Math.floor(min / 60), m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

const DOW = ["월", "화", "수", "목", "금", "토", "일"];

function fmtSessions(sessions) {
  if (!sessions || !sessions.length) return "시간 미확인";
  const groups = {};
  sessions.forEach((s) => {
    const k = `${s.startMinute}-${s.endMinute}`;
    (groups[k] = groups[k] || []).push(s.weekday);
  });
  return Object.entries(groups).map(([k, days]) => {
    const [a, b] = k.split("-").map(Number);
    return `${days.sort((x, y) => x - y).map((d) => DOW[d]).join("·")} ${fmtTime(a)}~${fmtTime(b)}`;
  }).join(", ");
}

const PROV_LABEL = { public: "공공자료", llm_extracted: "AI추출·미검토", llm_reviewed: "AI추출·검토완료", confirmed: "담당자확인", assumed: "가정", rule: "규칙" };

function provBadge(p) {
  const label = PROV_LABEL[p] || p || "미상";
  return `<span class="prov prov-${esc(p || "unknown")}">${esc(label)}</span>`;
}

function openDialog(id) { const el = document.getElementById(id); if (el) el.classList.add("open"); }
function closeDialog(id) { const el = document.getElementById(id); if (el) el.classList.remove("open"); }

document.addEventListener("click", (e) => {
  const help = e.target.closest("[data-help]");
  if (help) {
    const dialog = document.getElementById("help-dialog");
    const title = document.getElementById("help-title");
    const body = document.getElementById("help-body");
    if (dialog && title && body) {
      title.textContent = help.dataset.helpTitle || "기능 안내";
      body.textContent = help.dataset.help;
      dialog.hidden = false;
      dialog.classList.add("open");
      dialog.querySelector("[data-dialog-close]")?.focus();
    }
    return;
  }
  document.querySelectorAll(".dialog-backdrop.open").forEach((backdrop) => {
    if (e.target === backdrop) { backdrop.classList.remove("open"); if (backdrop.id === "help-dialog") backdrop.hidden = true; }
  });
  const closeBtn = e.target.closest("[data-dialog-close]");
  if (closeBtn) {
    const backdrop = closeBtn.closest(".dialog-backdrop");
    if (backdrop) { backdrop.classList.remove("open"); if (backdrop.id === "help-dialog") backdrop.hidden = true; }
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const dialog = document.getElementById("help-dialog");
    if (dialog && dialog.classList.contains("open")) { dialog.classList.remove("open"); dialog.hidden = true; }
  }
});

function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
  const s = p.toString();
  return s ? "?" + s : "";
}

document.addEventListener("DOMContentLoaded", () => {
  const navToggle = document.getElementById("nav-toggle");
  const navLinks = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      navToggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    });
    document.addEventListener("click", (e) => {
      if (!navLinks.contains(e.target) && !navToggle.contains(e.target)) {
        navLinks.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
      }
    });
  }
});


/* 데이터 적재 진행 바 — 어느 페이지에서든 같은 서버 상태를 보여줍니다.
 * SSE를 페이지마다 열면 브라우저의 호스트당 연결 한도(6개)를 잡아먹어 탭이 여럿일 때
 * 페이지 이동이 느려지므로, 여기서는 가벼운 폴링만 씁니다(적재 중 2초, 평소 15초). */
(function () {
  const bar = document.getElementById("global-import-bar");
  if (!bar) return;
  const fill = document.getElementById("global-import-fill"), text = document.getElementById("global-import-text");
  let wasRunning = false, timer = null;
  function render(j) {
    if (j.status === "running") { bar.hidden = false; fill.style.width = (j.percent || 0) + "%"; text.textContent = `데이터 적재 중 ${j.percent || 0}% · ${j.stepLabel || ""}${j.message ? " — " + j.message : ""}`; wasRunning = true; }
    else if (wasRunning) { bar.hidden = false; fill.style.width = "100%"; text.textContent = j.status === "done" ? `적재 완료 · 새 버전 ${j.version || ""} 적용. 새로고침하면 반영됩니다.` : `적재 실패: ${j.message || ""}`; wasRunning = false; setTimeout(() => { bar.hidden = true; }, 12000); }
    else bar.hidden = true;
    schedule(j.status === "running" ? 2000 : 15000);
  }
  function schedule(ms) { clearTimeout(timer); timer = setTimeout(poll, ms); }
  async function poll() {
    if (document.hidden) { schedule(15000); return; }
    try { render(await api.get("/api/data/import/status")); } catch (e) { schedule(20000); }
  }
  poll();
})();
