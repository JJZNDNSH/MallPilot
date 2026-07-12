const SLOW_THRESHOLD_MS = 1000;

const state = {
  turns: [],
  summary: null,
};

// 格式化耗时展示。
function formatDuration(durationMs) {
  if (!durationMs) {
    return "-";
  }
  return `${durationMs}ms`;
}

// 转义展示文本，避免 Trace 内容被当成 HTML 执行。
function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// 加载可观测轮次列表。
async function loadTurns() {
  const response = await fetch('/api/trace/turns');
  const data = await response.json();
  state.turns = data.turns || [];
  renderTurnOptions();
  if (state.turns.length > 0) {
    await loadSummary(state.turns[0].turn_id);
  } else {
    renderEmptyState();
  }
}

// 渲染轮次下拉框。
function renderTurnOptions() {
  const select = document.querySelector("#turnSelect");
  select.innerHTML = "";
  state.turns.forEach((turn) => {
    const option = document.createElement("option");
    option.value = turn.turn_id;
    option.textContent = turn.label;
    select.appendChild(option);
  });
}

// 加载指定轮次的聚合摘要。
async function loadSummary(turnId) {
  const response = await fetch(`/api/trace/turns/${turnId}/summary`);
  state.summary = await response.json();
  renderSummary(state.summary);
  renderUserInput(state.summary.input);
  renderGroups(state.summary.groups || []);
  renderTimeline(state.summary.events || []);
  document.querySelector("#detail").className = "detail-empty";
  document.querySelector("#detail").textContent = "请选择一条事件";
}

// 渲染空状态。
function renderEmptyState() {
  document.querySelector("#summary").textContent = "暂无可观测轮次";
  document.querySelector("#userInput").textContent = "暂无用户输入";
  document.querySelector("#groups").innerHTML = "";
  document.querySelector("#timeline").innerHTML = "";
  document.querySelector("#detail").className = "detail-empty";
  document.querySelector("#detail").textContent = "请选择一条事件";
}

// 渲染固定在顶部的用户输入。
function renderUserInput(input) {
  const container = document.querySelector("#userInput");
  if (!input || !input.message) {
    container.textContent = "暂无用户输入";
    return;
  }
  container.innerHTML = `
    <strong>用户输入</strong>
    <p>${escapeHtml(input.message)}</p>
    <small>${escapeHtml(input.timestamp || "")}</small>
  `;
}

// 渲染当前轮次摘要。
function renderSummary(summary) {
  document.querySelector("#summary").innerHTML = `
    <dl class="summary-grid">
      <div><dt>事件</dt><dd>${summary.event_count}</dd></div>
      <div><dt>错误</dt><dd>${summary.error_count}</dd></div>
      <div><dt>耗时</dt><dd>${formatDuration(summary.total_duration_ms)}</dd></div>
    </dl>
  `;
}

// 渲染阶段分组卡片。
function renderGroups(groups) {
  const container = document.querySelector("#groups");
  container.innerHTML = "";
  groups.forEach((group) => {
    const card = document.createElement("article");
    card.className = `group-card ${group.status === "error" ? "is-error" : ""}`;
    card.innerHTML = `
      <strong>${group.name}</strong>
      <span>${group.event_count} events</span>
      <span>${formatDuration(group.duration_ms)}</span>
    `;
    container.appendChild(card);
  });
}

// 渲染事件时间线。
function renderTimeline(events) {
  const timeline = document.querySelector("#timeline");
  timeline.innerHTML = "";
  events.forEach((event) => {
    const item = document.createElement("button");
    const isSlow = (event.duration_ms || 0) >= SLOW_THRESHOLD_MS;
    item.className = [
      "timeline-item",
      event.status === "error" ? "is-error" : "",
      isSlow ? "is-slow" : "",
    ].filter(Boolean).join(" ");
    item.type = "button";
    item.innerHTML = `
      <span>${escapeHtml(eventTitle(event))}</span>
      <small>${escapeHtml(eventSummary(event))} · ${formatDuration(event.duration_ms)}</small>
    `;
    item.onclick = () => renderDetail(event);
    timeline.appendChild(item);
  });
}

// 将 Trace 事件类型转成业务可读标题。
function eventTitle(event) {
  if (event.event_type === "router.intent") {
    return "意图路由";
  }
  if (event.event_type === "sse.emit") {
    return outputTitle(event.payload.type);
  }
  if (event.event_type.startsWith("retrieval.")) {
    return "检索调用";
  }
  if (event.event_type.startsWith("rerank.")) {
    return "重排调用";
  }
  if (event.event_type.startsWith("llm.")) {
    return "模型调用";
  }
  return event.event_type;
}

// 将 SSE 输出类型转成业务可读标题。
function outputTitle(type) {
  const titles = {
    thinking: "思考过程",
    product_card: "商品卡输出",
    answer: "回答输出",
    order_preview: "订单预览",
    after_sale_preview: "售后预览",
    final: "本轮结束",
  };
  return titles[type] || `输出事件 ${type}`;
}

// 生成 Trace 事件的短摘要，保持真实时间线顺序不变。
function eventSummary(event) {
  if (event.event_type === "router.intent") {
    return `${event.payload.intent || "-"} · confidence ${event.payload.confidence ?? "-"}`;
  }
  if (event.event_type === "sse.emit") {
    const summary = event.payload.summary || {};
    return summary.title || summary.text || summary.message || summary.status || event.payload.type;
  }
  if (event.status === "error") {
    return event.error_message || event.span_name;
  }
  return event.span_name;
}

// 渲染选中事件详情。
function renderDetail(event) {
  const detail = document.querySelector("#detail");
  detail.className = "detail";
  detail.innerHTML = `
    <dl class="detail-meta">
      <div><dt>类型</dt><dd>${escapeHtml(event.event_type)}</dd></div>
      <div><dt>阶段</dt><dd>${escapeHtml(event.span_name)}</dd></div>
      <div><dt>状态</dt><dd>${escapeHtml(event.status)}</dd></div>
      <div><dt>耗时</dt><dd>${formatDuration(event.duration_ms)}</dd></div>
      <div><dt>时间</dt><dd>${escapeHtml(event.timestamp)}</dd></div>
    </dl>
    ${event.error_message ? `<p class="error-message">${escapeHtml(event.error_message)}</p>` : ""}
    <pre>${JSON.stringify(event.payload, null, 2)}</pre>
  `;
}

document.querySelector("#refreshTurns").addEventListener("click", loadTurns);
document.querySelector("#turnSelect").addEventListener("change", (event) => {
  loadSummary(event.target.value);
});

loadTurns().catch(() => {
  renderEmptyState();
});
