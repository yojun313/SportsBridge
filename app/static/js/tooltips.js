/* Shared explanations for static pages and dynamically rendered results. */
(function () {
  const selector = "[data-tooltip], [data-gap-tip], [data-help]";
  const tooltip = document.createElement("div");
  tooltip.id = "app-tooltip";
  tooltip.className = "app-tooltip";
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  document.body.append(tooltip);
  let active = null, pending = null, timer = null, keyboardMode = false;

  function description(el) {
    if (!el) return "";
    return el.dataset.tooltip || el.dataset.gapTip || (el.dataset.help?.length > 350
      ? "선택하면 이 기능의 자세한 사용 방법과 확인 사항을 볼 수 있습니다."
      : el.dataset.help) || "";
  }
  function hide() {
    clearTimeout(timer); timer = null; pending = null;
    tooltip.hidden = true;
    if (active) {
      const ids = (active.getAttribute("aria-describedby") || "").split(/\s+/).filter((id) => id && id !== tooltip.id);
      if (ids.length) active.setAttribute("aria-describedby", ids.join(" "));
      else active.removeAttribute("aria-describedby");
    }
    active = null;
  }
  function show(el) {
    hide();
    if (!el.isConnected || !el.getClientRects().length || !description(el)) return;
    active = el;
    tooltip.textContent = description(el);
    tooltip.hidden = false;
    const ids = new Set((el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
    ids.add(tooltip.id); el.setAttribute("aria-describedby", [...ids].join(" "));
    const rect = el.getBoundingClientRect();
    const width = tooltip.offsetWidth, height = tooltip.offsetHeight;
    tooltip.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - width - 8))}px`;
    const below = rect.bottom + 8;
    tooltip.style.top = `${Math.max(8, Math.min(below + height <= innerHeight - 8 ? below : rect.top - height - 8, innerHeight - height - 8))}px`;
  }
  function target(node) { return node instanceof Element ? node.closest(selector) : null; }
  document.addEventListener("mouseover", (e) => {
    const el = target(e.target);
    if (el && (el === active || el === pending)) return;
    hide();
    if (description(el)) { pending = el; timer = setTimeout(() => show(el), 700); }
  });
  document.addEventListener("mouseout", (e) => {
    const el = target(e.target);
    if (el && el !== target(e.relatedTarget)) hide();
  });
  document.addEventListener("pointerdown", () => { keyboardMode = false; hide(); }, true);
  document.addEventListener("keydown", (e) => {
    keyboardMode = true;
    if (e.key === "Escape") hide();
  });
  document.addEventListener("focusin", (e) => { if (keyboardMode) { const el = target(e.target); if (el) show(el); } });
  document.addEventListener("focusout", hide);
  document.addEventListener("click", hide);
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
  window.addEventListener("blur", hide);
  document.addEventListener("visibilitychange", hide);

  function prepare(scope) {
    if (!(scope instanceof Element || scope instanceof Document)) return;
    const elements = [...scope.querySelectorAll(`${selector}, [title]`)];
    if (scope instanceof Element && scope.matches(`${selector}, [title]`)) elements.unshift(scope);
    elements.forEach((el) => {
      // Remove native titles so the browser cannot show a second, differently timed tooltip.
      if (el.hasAttribute("title")) {
        if (!el.dataset.tooltip && !el.dataset.gapTip && el.title) el.dataset.tooltip = el.title;
        el.removeAttribute("title");
      }
      if (!description(el)) return;
      if (el.matches("label") && el.control && !el.control.matches(selector)) el.control.dataset.tooltip = description(el);
      if (el.matches("span, th, h2, h3, h4, .label, .value, .badge, .prov") && !el.querySelector("a, button, input, select, textarea, summary") && !el.hasAttribute("tabindex")) el.tabIndex = 0;
    });
    if (active && (!active.isConnected || !active.getClientRects().length)) hide();
  }
  window.refreshTooltips = prepare;
  prepare(document);
  const observer = new MutationObserver((records) => {
    records.forEach((record) => {
      if (record.type === "attributes") prepare(record.target);
      else record.addedNodes.forEach((node) => { if (node instanceof Element && node !== tooltip) prepare(node); });
    });
    if ((active && !active.isConnected) || (pending && !pending.isConnected)) hide();
  });
  observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["title", "data-tooltip", "data-gap-tip", "data-help"] });

  // A click-accessible list gives touch users the same descriptions without requiring hover.
  document.getElementById("page-help-button")?.addEventListener("click", () => {
    hide();
    const entries = new Map();
    document.querySelectorAll(`main ${selector}, .site-header ${selector}`).forEach((el) => {
      if (!el.getClientRects().length || el.closest("[hidden]")) return;
      const text = description(el);
      if (!text || entries.has(text)) return;
      const controlLabel = el.labels?.[0]?.textContent.trim();
      const label = el.dataset.helpTitle || el.getAttribute("aria-label") || controlLabel || el.textContent.trim() || el.getAttribute("placeholder") || "입력 항목";
      entries.set(text, `${label.replace(/\s+/g, " ").slice(0, 90)}\n${text}`);
    });
    const dialog = document.getElementById("help-dialog");
    document.getElementById("help-title").textContent = "이 화면의 기능·용어 안내";
    document.getElementById("help-body").textContent = entries.size ? [...entries.values()].join("\n\n") : "각 화면의 서비스 안내에서 사용 방법과 데이터 기준을 확인할 수 있습니다.";
    dialog.hidden = false; dialog.classList.add("open");
    dialog.querySelector("[data-dialog-close]")?.focus();
  });
})();
