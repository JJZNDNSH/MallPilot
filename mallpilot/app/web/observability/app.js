// 加载指定 turn 的 Trace 事件并渲染时间线。
async function loadTurn(turnId) {
  const response = await fetch(`/api/trace/turns/${turnId}/events`);
  const events = await response.json();
  const timeline = document.querySelector("#timeline");
  timeline.innerHTML = "";
  events.forEach((event) => {
    const item = document.createElement("button");
    item.className = "timeline-item";
    item.textContent = `${event.event_type} - ${event.span_name}`;
    item.onclick = () => {
      document.querySelector("#detail").textContent = JSON.stringify(event, null, 2);
    };
    timeline.appendChild(item);
  });
}

// MVP 阶段提供固定入口，后续替换为真实会话列表。
document.querySelector("#sessions").innerHTML = '<button onclick="loadTurn(\'turn_1\')">turn_1</button>';
