// 모바일 뷰포트 처리 (prompts/templates/viewport.js 기반): 키보드 대응 · 핀치 확대 막기 · kb-open 표시
(function () {
  'use strict';
  const coarse = matchMedia('(pointer: coarse)').matches;
  const isEditable = (el) => !!el && (el.tagName === 'TEXTAREA' || el.isContentEditable
    || (el.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit', 'file', 'range'].includes(el.type)));
  let lastVisible = 0;

  function syncViewport() {
    const vv = window.visualViewport;
    const root = document.documentElement;
    const typing = coarse && isEditable(document.activeElement);
    const visible = vv ? vv.height : innerHeight;
    const keyboard = !!vv && (typing || innerHeight - vv.height > 80);
    root.style.setProperty('--app-h', keyboard ? `${Math.round(visible)}px` : '100%');
    root.style.setProperty('--vv-h', `${Math.round(visible)}px`);
    root.style.setProperty('--vv-top', keyboard && vv ? `${Math.round(vv.offsetTop)}px` : '0px');
    root.classList.toggle('kb-open', typing);
    if (visible < lastVisible && typing) {
      const el = document.activeElement;
      requestAnimationFrame(() => el.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
    }
    lastVisible = visible;
  }

  syncViewport();
  if (window.visualViewport) {
    visualViewport.addEventListener('resize', syncViewport);
    visualViewport.addEventListener('scroll', syncViewport);
  }
  addEventListener('resize', syncViewport);

  if (coarse) {
    const soon = () => [0, 100, 300, 600].forEach((ms) => setTimeout(syncViewport, ms));
    document.addEventListener('focusin', soon);
    document.addEventListener('focusout', soon);
    addEventListener('orientationchange', soon);
    ['gesturestart', 'gesturechange', 'gestureend'].forEach((t) => document.addEventListener(t, (e) => e.preventDefault(), { passive: false }));
    document.addEventListener('touchmove', (e) => { if (e.touches.length > 1) e.preventDefault(); }, { passive: false });
  }

  // 하단 탭바 '더보기' 시트
  const more = document.getElementById('tab-more');
  const sheet = document.getElementById('more-sheet');
  if (more && sheet) {
    const open = () => { sheet.hidden = false; more.setAttribute('aria-expanded', 'true'); history.pushState({ sheet: 1 }, ''); };
    const close = (fromPop) => { if (sheet.hidden) return; sheet.hidden = true; more.setAttribute('aria-expanded', 'false'); if (!fromPop && history.state && history.state.sheet) history.back(); };
    more.addEventListener('click', (e) => { e.preventDefault(); sheet.hidden ? open() : close(false); });
    sheet.addEventListener('click', (e) => { if (e.target === sheet || e.target.closest('[data-sheet-close]')) close(false); });
    addEventListener('popstate', () => close(true));
    addEventListener('keydown', (e) => { if (e.key === 'Escape') close(false); });
  }
})();
