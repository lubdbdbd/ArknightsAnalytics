let summary = null;

async function requestJson(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "请求失败");
  return body;
}

function renderSummary(data) {
  summary = data;
  document.getElementById("summaryCards").innerHTML = data.candidates.map(candidate => `
    <article class="summary-card">
      <h3>${candidate.category}</h3>
      <p class="muted">${candidate.candidate_id} · ${candidate.positioning}</p>
      <div class="metric-row">
        <div class="metric"><strong>${candidate.impressions}</strong>曝光UV</div>
        <div class="metric"><strong>${candidate.clicks}</strong>点击</div>
        <div class="metric"><strong>${candidate.ctr_pct}%</strong>CTR</div>
        <div class="metric"><strong>${candidate.intent_count}</strong>意向记录</div>
        <div class="metric"><strong>${candidate.qualified_count}/30</strong>有效意向</div>
        <div class="metric"><strong>${candidate.verified_supplier_count}/3</strong>授权供应商</div>
      </div>
    </article>`).join("");
  const select = document.getElementById("quoteCandidate");
  if (!select.options.length) {
    select.innerHTML = data.candidates.map(candidate =>
      `<option value="${candidate.candidate_id}">${candidate.category}（${candidate.candidate_id}）</option>`
    ).join("");
  }
}

async function refresh() {
  const message = document.getElementById("summaryMessage");
  try {
    renderSummary(await requestJson("/api/summary"));
    message.textContent = `当前共回收 ${summary.response_count} 份匿名答卷。`;
  } catch (error) {
    message.classList.add("error");
    message.textContent = error.message;
  }
}

document.getElementById("refreshButton").addEventListener("click", refresh);

document.getElementById("quoteForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const message = document.getElementById("quoteMessage");
  const payload = Object.fromEntries(values.entries());
  payload.rights_verified = values.get("rights_verified") === "on";
  for (const key of ["moq", "unit_cost", "sample_cost", "lead_time_days", "defect_allowance_pct"]) {
    payload[key] = Number(payload[key]);
  }
  try {
    const result = await requestJson("/api/admin/supplier-quotes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    message.classList.remove("error");
    message.textContent = `报价已保存：${result.quote_id}`;
    form.reset();
    await refresh();
  } catch (error) {
    message.classList.add("error");
    message.textContent = error.message;
  }
});

document.getElementById("exportButton").addEventListener("click", async () => {
  const message = document.getElementById("exportMessage");
  message.textContent = "正在校验并导出……";
  try {
    const result = await requestJson("/api/admin/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_channel: "local_admin" }),
    });
    message.classList.remove("error");
    message.textContent = `导出完成：${result.counts.campaigns}个Campaign、${result.counts.intent_leads}条意向、${result.counts.supplier_quotes}条报价。`;
  } catch (error) {
    message.classList.add("error");
    message.textContent = error.message;
  }
});

refresh();
