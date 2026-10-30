(() => {
  const root = document.querySelector(".suggestions-page");
  if (!root) return;
  const endpoint = `/api/suggestions/${root.dataset.board}`;
  const admin = root.dataset.board === "admin";
  const list = document.getElementById("suggestion-list");
  const prev = document.getElementById("suggestion-prev");
  const next = document.getElementById("suggestion-next");
  const message = document.getElementById("suggestion-message");
  let page = 1, loading = false;

  async function load() {
    if (loading) return;
    loading = true;
    prev.disabled = next.disabled = true;
    list.setAttribute("aria-busy", "true");
    try {
      let data = await api.get(`${endpoint}?page=${page}`);
      const lastPage = Math.max(1, Math.ceil(data.total / data.pageSize));
      if (page > lastPage) {
        page = lastPage;
        data = await api.get(`${endpoint}?page=${page}`);
      }
      document.getElementById("suggestion-total").textContent = `${data.total}건`;
      document.getElementById("suggestion-page").textContent = `${page} / ${lastPage}`;
      list.replaceChildren();
      if (!data.items.length) {
        const empty = document.createElement("p");
        empty.className = "empty-state";
        empty.textContent = "아직 등록된 제안이 없습니다. 첫 의견을 남겨 주세요.";
        list.append(empty);
      }
      for (const post of data.items) {
        const article = document.createElement("article");
        article.className = "suggestion-post";
        const heading = document.createElement("h3");
        heading.textContent = post.title;
        const meta = document.createElement("p");
        meta.className = "suggestion-meta";
        const date = new Date(post.createdAt);
        const time = document.createElement("time");
        time.dateTime = post.createdAt;
        time.textContent = date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
        meta.append(document.createTextNode(admin ? `${post.authorName} (${post.authorUsername}) · ` : "익명 · "), time);
        const content = document.createElement("p");
        content.className = "suggestion-content";
        content.textContent = post.content;
        article.append(heading, meta, content);
        if (data.canModerate) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "btn btn-ghost btn-sm";
          button.textContent = "삭제";
          button.dataset.tooltip = "최고 관리자 권한으로 이 게시글을 삭제합니다. 삭제한 글은 복구할 수 없습니다.";
          button.addEventListener("click", async () => {
            if (!confirm("이 제안을 삭제하시겠습니까? 삭제한 글은 복구할 수 없습니다.")) return;
            button.disabled = true;
            try { await api.del(`${endpoint}/${post.id}`, {}); await load(); }
            catch (error) { showSnackbar(error.message, "error"); button.disabled = false; }
          });
          article.append(button);
        }
        list.append(article);
      }
      prev.disabled = page <= 1;
      next.disabled = page >= lastPage;
    } catch (error) {
      list.textContent = error.message;
      showSnackbar(error.message, "error");
    } finally { loading = false; list.removeAttribute("aria-busy"); }
  }

  document.getElementById("suggestion-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (loading) return;
    const button = document.getElementById("suggestion-submit");
    if (button.disabled) return;
    const body = {
      title: document.getElementById("suggestion-title").value.trim(),
      content: document.getElementById("suggestion-content").value.trim(),
    };
    if (admin) body.authorName = document.getElementById("suggestion-name").value.trim();
    button.disabled = true;
    message.textContent = "등록 중입니다.";
    try {
      await api.post(endpoint, body);
      document.getElementById("suggestion-title").value = "";
      document.getElementById("suggestion-content").value = "";
      message.textContent = "제안을 등록했습니다.";
      showSnackbar(message.textContent, "success");
      page = 1;
      await load();
    } catch (error) { message.textContent = error.message; showSnackbar(error.message, "error"); }
    finally { button.disabled = false; }
  });
  prev.addEventListener("click", () => { if (!loading && page > 1) { page--; load(); } });
  next.addEventListener("click", () => { if (!loading) { page++; load(); } });
  document.getElementById("suggestion-refresh").addEventListener("click", () => { if (!loading) { page = 1; load(); } });
  load();
})();
