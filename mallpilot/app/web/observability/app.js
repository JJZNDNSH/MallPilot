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
  renderGroups(state.summary.groups || []);
  renderTimeline(state.summary.events || []);
  document.querySelector("#detail").className = "detail-empty";
  document.querySelector("#detail").textContent = "请选择一条事件";
}

// 渲染空状态。
function renderEmptyState() {
  document.querySelector("#summary").textContent = "暂无可观测轮次";
  document.querySelector("#groups").innerHTML = "";
  document.querySelector("#timeline").innerHTML = "";
  document.querySelector("#detail").className = "detail-empty";
  document.querySelector("#detail").textContent = "请选择一条事件";
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
      <span>${event.event_type}</span>
      <small>${event.span_name} · ${formatDuration(event.duration_ms)}</small>
    `;
    item.onclick = () => renderDetail(event);
    timeline.appendChild(item);
  });
}

// 渲染选中事件详情。
function renderDetail(event) {
  const detail = document.querySelector("#detail");
  detail.className = "detail";
  detail.innerHTML = `
    <dl class="detail-meta">
      <div><dt>类型</dt><dd>${event.event_type}</dd></div>
      <div><dt>阶段</dt><dd>${event.span_name}</dd></div>
      <div><dt>状态</dt><dd>${event.status}</dd></div>
      <div><dt>耗时</dt><dd>${formatDuration(event.duration_ms)}</dd></div>
      <div><dt>时间</dt><dd>${event.timestamp}</dd></div>
    </dl>
    ${event.error_message ? `<p class="error-message">${event.error_message}</p>` : ""}
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
