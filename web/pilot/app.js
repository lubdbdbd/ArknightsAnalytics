const state = { config: null, startedAt: Date.now(), clicked: new Set() };

function postJson(url, payload) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(async response => {
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "请求失败");
    return body;
  });
}

function sourceChannel() {
  const source = new URLSearchParams(location.search).get("source");
  return source || document.querySelector('[name="source_channel"]')?.value || "direct";
}

function scale(name) {
  return [1, 2, 3, 4, 5].map(value => `
    <label class="radio-chip">
      <input type="radio" name="${name}" value="${value}" required>
      <span>${value}</span>
    </label>`).join("");
}

function candidateCard(candidate) {
  const prices = candidate.price_options.map(price => `
    <label class="radio-chip">
      <input type="radio" name="price_${candidate.candidate_id}" value="${price}" required>
      <span>¥${price}</span>
    </label>`).join("");
  return `
    <article class="panel candidate-card" data-candidate="${candidate.candidate_id}">
      <div class="concept-art" aria-label="待替换为授权商品素材"></div>
      <div class="card-body">
        <span class="tag">${candidate.positioning}</span>
        <h2>${candidate.category}</h2>
        <p>${candidate.description}</p>
        <button type="button" class="card-click" data-click="${candidate.candidate_id}">我会考虑这个方案</button>
        <fieldset><legend>购买意愿（1=完全不会，5=非常愿意）</legend><div class="scale">${scale(`intent_${candidate.candidate_id}`)}</div></fieldset>
        <fieldset><legend>你能接受的价格</legend><div class="price-options">${prices}</div></fieldset>
        <label>最长可接受的预售等待天数
          <input type="number" name="preorder_${candidate.candidate_id}" min="0" max="365" required placeholder="例如：30">
        </label>
      </div>
    </article>`;
}

async function loadConfig() {
  const source = encodeURIComponent(sourceChannel());
  const response = await fetch(`/api/config?source=${source}`, { cache: "no-store" });
  state.config = await response.json();
  document.querySelector('[data-scale="role_affinity"]').innerHTML = scale("role_affinity");
  document.getElementById("candidateGrid").innerHTML = state.config.candidates.map(candidateCard).join("");
  document.getElementById("preferredOptions").innerHTML = state.config.candidates.map(candidate => `
    <label class="radio-chip">
      <input type="radio" name="preferred_candidate" value="${candidate.candidate_id}" required>
      <span>${candidate.category}</span>
    </label>`).join("");
  await Promise.all(state.config.candidates.map(candidate => postJson("/api/events", {
    candidate_id: candidate.candidate_id,
    event_type: "impression",
    source_channel: sourceChannel(),
  })));
  document.querySelectorAll("[data-click]").forEach(button => {
    button.addEventListener("click", async () => {
      const candidateId = button.dataset.click;
      if (!state.clicked.has(candidateId)) {
        await postJson("/api/events", {
          candidate_id: candidateId,
          event_type: "click",
          source_channel: sourceChannel(),
        });
        state.clicked.add(candidateId);
      }
      button.textContent = "已记录关注，可继续填写评价";
    });
  });
}

document.getElementById("startButton").addEventListener("click", () => {
  document.getElementById("surveyForm").classList.remove("hidden");
  document.getElementById("startButton").closest(".intro").classList.add("hidden");
  document.getElementById("surveyForm").scrollIntoView({ behavior: "smooth" });
});

document.getElementById("surveyForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.getElementById("formMessage");
  if (!form.reportValidity()) return;
  const values = new FormData(form);
  const answers = {};
  for (const candidate of state.config.candidates) {
    answers[candidate.candidate_id] = {
      purchase_intent: Number(values.get(`intent_${candidate.candidate_id}`)),
      accepted_price: Number(values.get(`price_${candidate.candidate_id}`)),
      preorder_tolerance_days: Number(values.get(`preorder_${candidate.candidate_id}`)),
    };
  }
  const payload = {
    consent: values.get("consent") === "on",
    experience_months: Number(values.get("experience_months")),
    role_affinity: Number(values.get("role_affinity")),
    prior_buyer: values.get("prior_buyer") === "on",
    preferred_candidate: values.get("preferred_candidate"),
    completed_seconds: Math.max(10, Math.round((Date.now() - state.startedAt) / 1000)),
    source_channel: values.get("source_channel"),
    answers,
  };
  message.classList.remove("error");
  message.textContent = "正在匿名提交……";
  try {
    const result = await postJson("/api/intents", payload);
    form.querySelectorAll("input, select, button").forEach(element => element.disabled = true);
    message.textContent = `提交成功，匿名记录号：${result.response_id.slice(-8)}`;
  } catch (error) {
    message.classList.add("error");
    message.textContent = error.message;
  }
});

loadConfig().catch(error => {
  const message = document.getElementById("formMessage");
  message.classList.add("error");
  message.textContent = `页面初始化失败：${error.message}`;
});
