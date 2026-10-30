(() => {
  const $ = (id) => document.getElementById(id);
  const now = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit' }).format(new Date());
  $('pl-start').value = now.slice(0, 4) + '-01';
  $('pl-reference').value = now;
  let attempted = false, requestSequence = 0, currentPage = 1;
  const fields = ['pl-type', 'pl-cap', 'pl-start', 'pl-months', 'pl-reference', 'pl-price'];
  try {
    const saved = JSON.parse(localStorage.getItem('sb_planner') || 'null');
    if (saved && typeof saved === 'object') {
      if (saved.start) $('pl-start').value = saved.start;
      if (saved.months != null) $('pl-months').value = saved.months;
      const type = String(saved.type ?? saved.sup);
      if (['105000', '110000'].includes(type)) $('pl-type').value = type;
      $('pl-cap').value = saved.cap ?? saved.sup ?? $('pl-type').value;
      if (saved.price != null && saved.price !== '') $('pl-price').value = saved.price;
    }
  } catch (_) {}

  function calculate() {
    attempted = true;
    const out = $('pl-out');
    try {
      const input = { start: $('pl-start').value, reference: $('pl-reference').value, months: $('pl-months').value, cap: $('pl-cap').value, price: $('pl-price').value };
      const result = PlannerCalculator.calculate(input);
      out.className = 'planner-result mt-16';
      const status = result.status === 'before' ? '지원 시작 전' : result.status === 'ended' ? '지원 종료' : '지원 기간 내';
      out.innerHTML = `<div class="planner-result-head"><b>${status} · ${result.remaining}개월 계산</b><span>${esc(input.reference)} 기준 · 종료 ${esc(result.endMonth)}</span></div>
        <dl class="planner-amounts">
          <div><dt data-tooltip="매월 수강료와 월 지원 한도 중 작은 금액입니다. 실제 카드 잔액이나 확정 지원액은 아닙니다.">월 예상 지원액</dt><dd>${fmtWon(result.monthlySupport)}</dd></div>
          <div><dt data-tooltip="매월 수강료에서 지원 한도를 초과하는 금액입니다. 기간이 종료되었을 때의 0개월 합계와는 별개인 월별 요금 비교입니다.">월 예상 본인부담금</dt><dd>${fmtWon(result.monthlyOwn)}</dd></div>
          <div><dt data-tooltip="월 예상 지원액에 계산 대상 개월 수를 곱한 값입니다. 매월 같은 강좌·수강료를 가정합니다.">남은 기간 예상 지원액</dt><dd>${fmtWon(result.totalSupport)}</dd></div>
          <div><dt data-tooltip="월 예상 본인부담금에 계산 대상 개월 수를 곱한 값입니다. 기준 월을 포함하며 이미 결제한 내역은 조회하지 않습니다.">남은 기간 본인부담금</dt><dd>${fmtWon(result.totalOwn)}</dd></div>
        </dl>
        <p class="small">남은 기간 수강료 합계 ${fmtWon(result.totalPrice)} = 예상 지원액 ${fmtWon(result.totalSupport)} + 본인부담금 ${fmtWon(result.totalOwn)}</p>
        <p class="hint">남은 기간 지원 한도 합계 ${fmtWon(result.remainingCap)}은 수강료에 실제 적용할 예상 지원액과 구분됩니다.</p>
        ${result.monthlyUnused > 0 ? `<p class="hint">월 한도에서 수강료를 제외한 ${fmtWon(result.monthlyUnused)}은 이 강좌에 적용되지 않습니다. 잔액·현금 환급액으로 계산하지 않습니다.</p>` : ''}
        ${result.status === 'ended' ? '<p class="hint">계산 기준 월이 지원 종료 월 이후이므로 남은 기간의 금액은 0원입니다. 월별 금액은 수강료와 한도의 비교입니다.</p>' : ''}`;
      try { localStorage.setItem('sb_planner', JSON.stringify({ ...input, type: $('pl-type').value, sup: Number(input.cap) })); } catch (_) {}
      return true;
    } catch (error) {
      out.className = 'notice error mt-16';
      out.textContent = error.message;
      return false;
    }
  }
  $('pl-form').addEventListener('submit', (event) => { event.preventDefault(); calculate(); });
  fields.forEach((id) => $(id).addEventListener('input', () => {
    if (id === 'pl-type') $('pl-cap').value = $('pl-type').value;
    if (id === 'pl-price') $('pl-source').textContent = '직접 입력한 월 수강료로 계산합니다.';
    if (attempted) calculate();
  }));

  function knownPrice(price) { return typeof price === 'number' && Number.isSafeInteger(price) && price >= 0 && price <= 5000000; }
  function applyPrice(course) {
    if (!knownPrice(course.priceWon)) return;
    $('pl-price').value = course.priceWon;
    $('pl-source').textContent = `${course.facility || course.facilityName || ''} · ${course.name}의 수강료를 적용했습니다. 현재 요금은 시설에 확인하세요.`;
    calculate();
    $('pl-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
    showSnackbar('강좌 수강료를 적용했습니다.', 'success');
  }
  function applyButton(course) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'btn btn-sm btn-outline';
    button.textContent = knownPrice(course.priceWon) ? '수강료 적용' : '수강료 확인 필요';
    button.disabled = !knownPrice(course.priceWon);
    button.dataset.tooltip = button.disabled ? '공개 자료 또는 저장 정보의 수강료가 미확인이거나 입력 범위를 벗어나 적용할 수 없습니다. 시설에 확인한 요금을 계산기에 직접 입력하세요. 미확인을 무료로 계산하지 않습니다.' : '이 강좌의 월 수강료를 계산기에 입력하고 현재 지원 기간·한도로 다시 계산합니다. 강좌를 신청하거나 결제하지 않습니다.';
    button.addEventListener('click', () => applyPrice(course));
    return button;
  }
  function favoriteList() {
    try { const list = JSON.parse(localStorage.getItem('sb_favorites') || '[]'); return Array.isArray(list) ? list.filter((course) => course && typeof course === 'object') : []; } catch (_) { return []; }
  }
  function renderFavorites() {
    const favorites = favoriteList(), container = $('pl-favs');
    container.replaceChildren(); $('pl-clear').disabled = !favorites.length;
    if (!favorites.length) { container.innerHTML = '<p class="muted">강좌 찾기에서 ☆ 저장한 강좌가 여기에 표시됩니다. 위의 강좌 검색은 저장 없이 사용할 수 있습니다.</p>'; return; }
    favorites.forEach((course, index) => {
      const item = document.createElement('article'); item.className = 'planner-course';
      item.innerHTML = `<h3>${esc(course.name)}</h3><p class="small">${esc(course.facility || '')} · ${esc(course.sport || '')}</p><p class="small">${esc(course.sessions || '시간 미확인')} · 월 ${knownPrice(course.priceWon) ? fmtWon(course.priceWon) : '수강료 미확인'}</p><p class="hint">${esc(course.address || '')} · 저장 ${esc(course.savedAt || '')}</p>`;
      const actions = document.createElement('div'); actions.className = 'row'; actions.append(applyButton(course));
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'btn btn-ghost btn-sm'; remove.textContent = '저장 해제';
      remove.dataset.tooltip = '이 브라우저의 관심 강좌에서 이 항목만 지웁니다. 계산에 적용한 수강료와 실제 수강 신청에는 영향을 주지 않습니다.';
      remove.addEventListener('click', () => {
        try { const list = favoriteList(); list.splice(index, 1); localStorage.setItem('sb_favorites', JSON.stringify(list)); renderFavorites(); }
        catch (_) { showSnackbar('브라우저 저장소를 사용할 수 없어 삭제하지 못했습니다.', 'error'); }
      });
      actions.append(remove); item.append(actions); container.append(item);
    });
  }
  $('pl-clear').addEventListener('click', () => {
    if (!confirm('저장한 강좌를 모두 지우시겠습니까?')) return;
    try { localStorage.removeItem('sb_favorites'); renderFavorites(); } catch (_) { showSnackbar('브라우저 저장소를 사용할 수 없습니다.', 'error'); }
  });
  window.addEventListener('storage', (event) => { if (event.key === 'sb_favorites' || event.key === null) renderFavorites(); });
  renderFavorites();

  function resetSearch() {
    requestSequence++; currentPage = 1;
    $('pl-results').replaceChildren(); $('pl-pages').hidden = true; $('pl-search').disabled = false;
    $('pl-search-summary').textContent = '조건을 변경했습니다. 강좌 검색을 눌러 주세요.';
  }
  ['p-sido', 'p-sigungu', 'pl-sport'].forEach((id) => $(id).addEventListener('change', resetSearch));
  $('pl-query').addEventListener('input', resetSearch);
  async function search(page = 1) {
    const sequence = ++requestSequence;
    const region = window.currentRegion();
    $('pl-results').replaceChildren(); $('pl-pages').hidden = true;
    if (!region) { $('pl-search-summary').textContent = '시도와 시군구를 선택해 주세요.'; return; }
    $('pl-search').disabled = true; $('pl-search-summary').textContent = '강좌를 검색하는 중입니다.';
    try {
      const data = await api.get('/api/user/planner/courses' + qs({ region, sport: $('pl-sport').value, q: $('pl-query').value.trim(), page }));
      if (sequence !== requestSequence) return;
      currentPage = page;
      $('pl-search-summary').textContent = `${window.currentRegionName()} · ${data.total.toLocaleString('ko-KR')}개 강좌${data.cutoff ? ` · ${data.cutoff} 이후 기록 기준` : ''}. 현재 수강료·모집 여부와 지원 유형별 결제 가능 여부는 시설에 확인하세요.`;
      if (!data.items.length) $('pl-results').innerHTML = '<p class="empty-state">검색 결과가 없습니다. 지역·종목·검색어를 변경해 보세요.</p>';
      data.items.forEach((course) => {
        const item = document.createElement('article'); item.className = 'planner-course';
        item.innerHTML = `<h3>${esc(course.name)}</h3><p class="small">${esc(course.facilityName || '시설명 미확인')} · ${esc(course.sport || '')}</p><p class="small">${esc(fmtSessions(course.sessions || []))}${course.scheduleAmbiguous ? ' · 시간표 확인 필요' : ''}</p><p class="small"><b>월 ${knownPrice(course.priceWon) ? fmtWon(course.priceWon) : '수강료 미확인'}</b> · 마지막 기록 ${esc(course.lastMonth || '미확인')}</p><p class="hint">${esc(course.address || '')}</p>`;
        item.append(applyButton(course)); $('pl-results').append(item);
      });
      const totalPages = Math.max(1, Math.ceil(data.total / data.pageSize));
      $('pl-pages').hidden = totalPages <= 1; $('pl-page').textContent = `${page} / ${totalPages}`;
      $('pl-prev').disabled = page <= 1; $('pl-next').disabled = page >= totalPages;
    } catch (error) { if (sequence === requestSequence) $('pl-search-summary').textContent = error.message; }
    finally { if (sequence === requestSequence) $('pl-search').disabled = false; }
  }
  $('pl-search-form').addEventListener('submit', (event) => { event.preventDefault(); search(); });
  $('pl-prev').addEventListener('click', () => search(Math.max(1, currentPage - 1)));
  $('pl-next').addEventListener('click', () => search(currentPage + 1));
})();
