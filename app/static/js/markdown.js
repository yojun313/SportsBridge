/* 에이전트 답변용 작은 마크다운 렌더러. 외부 라이브러리 없이 동작하며, 입력을 먼저 HTML 이스케이프한 뒤 변환하므로
   원문에 태그가 섞여 있어도 실행되지 않습니다. 지원: 제목(#~######), 목록(-, *, 1.), 중첩 목록(2칸 들여쓰기),
   표(| a | b |), 코드 블록(```), 인라인 코드, 굵게, 기울임, 링크(http/https만), 인용(>), 구분선(---), 문단. */
(function () {
  const escHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function inline(s) {
    // s는 이미 이스케이프된 문자열
    s = s.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }

  function renderTable(lines) {
    const rows = lines.map((l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()));
    const head = rows[0], body = rows.slice(2);
    let html = '<div class="table-wrap"><table class="table md-table"><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead>";
    if (body.length) html += "<tbody>" + body.map((r) => "<tr>" + head.map((_, i) => `<td>${inline(r[i] || "")}</td>`).join("") + "</tr>").join("") + "</tbody>";
    return html + "</table></div>";
  }

  function renderList(items) {
    // items: [{indent, ordered, text}] — 들여쓰기로 중첩
    let html = "", stack = [];
    const close = (toDepth) => { while (stack.length > toDepth) html += `</li></${stack.pop()}>`; };
    for (const it of items) {
      const depth = Math.floor(it.indent / 2) + 1, tag = it.ordered ? "ol" : "ul";
      if (depth > stack.length) { html += `<${tag}><li>${inline(it.text)}`; stack.push(tag); }
      else {
        close(depth);
        if (stack[depth - 1] !== tag) { close(depth - 1); html += `<${tag}><li>${inline(it.text)}`; stack.push(tag); }  // ul→ol 전환
        else html += `</li><li>${inline(it.text)}`;
      }
    }
    close(0);
    return html;
  }

  function renderMarkdown(text) {
    const lines = escHtml(text || "").replace(/\r\n?/g, "\n").split("\n");
    const out = []; let i = 0, para = [], list = [];
    const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join("<br>"))}</p>`); para = []; } };
    const flushList = () => { if (list.length) { out.push(renderList(list)); list = []; } };
    const isTableLine = (l) => /^\s*\|.*\|\s*$/.test(l);
    const isSepLine = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
    while (i < lines.length) {
      const line = lines[i];
      if (/^\s*```/.test(line)) {                       // 코드 블록
        flushPara(); flushList(); const buf = []; i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) buf.push(lines[i++]);
        i++; out.push(`<pre><code>${buf.join("\n")}</code></pre>`); continue;
      }
      const h = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
      if (h) { flushPara(); flushList(); const lv = Math.min(h[1].length + 2, 6); out.push(`<h${lv}>${inline(h[2])}</h${lv}>`); i++; continue; }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flushPara(); flushList(); out.push("<hr>"); i++; continue; }
      if (isTableLine(line) && i + 1 < lines.length && isSepLine(lines[i + 1])) {
        flushPara(); flushList(); const buf = [line, lines[i + 1]]; i += 2;
        while (i < lines.length && isTableLine(lines[i])) buf.push(lines[i++]);
        out.push(renderTable(buf)); continue;
      }
      const li = line.match(/^(\s*)([-*•]|\d+[.)])\s+(.+)$/);
      if (li) { flushPara(); list.push({ indent: li[1].length, ordered: /\d/.test(li[2]), text: li[3] }); i++; continue; }
      if (list.length && /^\s{2,}\S/.test(line)) { list[list.length - 1].text += " " + line.trim(); i++; continue; }
      if (/^\s*&gt;\s?/.test(line)) {                    // 인용
        flushPara(); flushList(); const buf = [];
        while (i < lines.length && /^\s*&gt;\s?/.test(lines[i])) buf.push(lines[i++].replace(/^\s*&gt;\s?/, ""));
        out.push(`<blockquote>${inline(buf.join("<br>"))}</blockquote>`); continue;
      }
      if (!line.trim()) { flushPara(); flushList(); i++; continue; }
      flushList(); para.push(line.trim()); i++;
    }
    flushPara(); flushList();
    return `<div class="md">${out.join("")}</div>`;
  }

  window.renderMarkdown = renderMarkdown;
})();
