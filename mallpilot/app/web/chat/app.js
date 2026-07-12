const messages = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#messageInput");
const turnStatus = document.querySelector("#turnStatus");
const traceList = document.querySelector("#traceList");
const traceCount = document.querySelector("#traceCount");
const traceDetail = document.querySelector("#traceDetail");
const newChat = document.querySelector("#newChat");

let chatId = localStorage.getItem("mallpilot.chatId") || null;
let currentTurnId = null;
let traceEvents = [];

// 创建一个聊天气泡。
function appendMessage(role, content) {
  const row = document.createElement("div");
  row.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;
  row.appendChild(bubble);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

// 渲染商品卡片。
function appendProductCard(payload) {
  const row = document.createElement("div");
  row.className = "message assistant";
  const card = document.createElement("article");
  card.className = "product-card";
  const image = document.createElement("div");
  image.className = "product-image";

  if (payload.image_url) {
    image.style.backgroundImage = `url("${payload.image_url}")`;
  } else {
    image.textContent = "MP";
  }

  const body = document.createElement("div");
  body.className = "product-body";
  const reasons = Array.isArray(payload.reasons) ? payload.reasons.filter(Boolean) : [];
  const reasonText = payload.reason || reasons[0] || payload.evidence?.[0]?.summary || "已匹配你的需求";
  const categoryText = [payload.brand, payload.category, payload.sub_category].filter(Boolean).join(" / ");
  body.innerHTML = `
    <h3>${escapeHtml(payload.title || "商品")}</h3>
    <p>${escapeHtml(reasonText)}</p>
    <div class="product-tags">
      <span>${escapeHtml(categoryText || "商品信息待补充")}</span>
    </div>
    ${payload.sku_summary ? `<small class="sku-summary">${escapeHtml(payload.sku_summary)}</small>` : ""}
    <div class="product-meta">
      <span>${payload.price ? `¥${payload.price}` : "价格待确认"}</span>
      <span>${escapeHtml(payload.product_id || "")}</span>
    </div>
  `;

  card.append(image, body);
  row.appendChild(card);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
}

// 按 SSE 类型分流渲染。
function renderEvent(event) {
  currentTurnId = event.turn_id || currentTurnId;
  mergeTraceEvent({ type: event.type, seq: event.seq, payload: event.payload || {}, source: "sse" });

  if (event.type === "thinking") {
    turnStatus.textContent = event.payload?.stage || "thinking";
    appendMessage("assistant subtle", event.payload?.message || "正在处理");
    return;
  }
  if (event.type === "product_card") {
    appendProductCard(event.payload || {});
    return;
  }
  if (event.type === "clarification") {
    appendMessage("assistant clarify", event.payload?.question || event.payload?.text || "需要补充信息");
    return;
  }
  if (event.type === "answer") {
    appendMessage("assistant", event.payload?.text || "");
    return;
  }
  if (event.type === "order_preview") {
    appendMessage("assistant", `订单预览：${event.payload?.summary || "已生成"}`);
    return;
  }
  if (event.type === "after_sale_preview") {
    appendMessage("assistant", `售后预览：${event.payload?.summary || "已生成"}`);
    return;
  }
  if (event.type === "final") {
    turnStatus.textContent = "completed";
    loadTraceFromApi();
  }
}

// 合并 Trace 事件，避免 SSE 事件和持久化事件重复刷屏。
function mergeTraceEvent(item) {
  const key = `${item.source || "runtime"}:${item.type}:${item.seq || "-"}:${JSON.stringify(item.payload || {})}`;
  if (traceEvents.some((event) => event.key === key)) {
    return;
  }
  traceEvents.push({ ...item, key });
  renderTrace();
}

// 渲染右侧 Trace 列表。
function renderTrace() {
  traceCount.textContent = String(traceEvents.length);
  traceList.innerHTML = "";
  for (const item of traceEvents) {
    const node = document.createElement("button");
    node.className = "trace-item";
    node.type = "button";
    node.innerHTML = `<span>${escapeHtml(item.type)}</span><small>#${item.seq || "-"}</small>`;
    node.addEventListener("click", () => renderTraceDetail(item));
    traceList.appendChild(node);
  }
}

// 在右侧详情区展示 Trace payload。
function renderTraceDetail(item) {
  if (!traceDetail) {
    return;
  }
  traceDetail.textContent = JSON.stringify(
    {
      type: item.type,
      seq: item.seq,
      source: item.source,
      payload: item.payload,
    },
    null,
    2,
  );
}

// 从后端 Trace API 补充持久化事件。
async function loadTraceFromApi() {
  if (!currentTurnId) {
    return;
  }
  const response = await fetch(`/api/trace/turns/${currentTurnId}/events`);
  if (!response.ok) {
    return;
  }
  const rows = await response.json();
  for (const row of rows) {
    mergeTraceEvent({
      type: row.event_type,
      seq: row.payload?.seq,
      payload: row.payload || {},
      source: row.span_name || "trace",
    });
  }
}

// 发送聊天请求并解析 SSE。
async function sendMessage(message) {
  appendMessage("user", message);
  turnStatus.textContent = "streaming";
  traceEvents = [];
  renderTrace();
  renderTraceDetail({ type: "turn.start", payload: { message }, source: "ui" });

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, message }),
  });

  if (!response.ok || !response.body) {
    appendMessage("assistant clarify", "服务暂时不可用，请稍后再试。");
    turnStatus.textContent = "error";
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      parseSseFrame(frame);
    }
  }
}

// 解析单个 SSE frame。
function parseSseFrame(frame) {
  const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
  if (!dataLine) {
    return;
  }
  const event = JSON.parse(dataLine.slice(6));
  if (event.chat_id) {
    chatId = event.chat_id;
    localStorage.setItem("mallpilot.chatId", chatId);
  }
  renderEvent(event);
}

// 转义 HTML，避免 payload 文本破坏页面结构。
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) {
    return;
  }
  input.value = "";
  await sendMessage(message);
});

newChat.addEventListener("click", () => {
  chatId = null;
  currentTurnId = null;
  localStorage.removeItem("mallpilot.chatId");
  messages.innerHTML = "";
  traceEvents = [];
  renderTrace();
  renderTraceDetail({ type: "ready", payload: {}, source: "ui" });
  appendMessage("assistant", "告诉我预算、品类、使用场景，我来筛选商品。");
});
