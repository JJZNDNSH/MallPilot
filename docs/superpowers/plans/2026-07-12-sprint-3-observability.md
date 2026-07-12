# Sprint 3 Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a turn-level Observability panel where users choose “第 N 轮” from a dropdown and inspect grouped router/retrieval/rerank/llm/sse/error trace details.

**Architecture:** Keep Trace storage unchanged. Add a small backend aggregation module that converts existing `TraceEvent` rows into turn options and per-turn summaries, expose those through `/api/trace/turns` and `/api/trace/turns/{turn_id}/summary`, then upgrade the existing vanilla HTML/CSS/JS page to consume those APIs.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Pydantic, pytest, vanilla HTML/CSS/JS.

## Global Constraints

- 只修改 Sprint 3 Observability 相关文件，不修改检索、LLM Router、交易 Flow 或聊天业务 Flow。
- 新增或修改的 Python 属性字段必须有中文注释。
- 新增或修改的方法前必须有中文注释。
- 新增或修改的关键逻辑前必须有中文注释。
- 保留现有 `/api/trace/turns/{turn_id}/events` 接口兼容。
- 前端不暴露 `turn_id` 手动输入，只通过下拉框选择“第 N 轮”。
- 不引入前端框架、图表库、外部 APM、日志平台或指标系统。
- 数据库不可用、没有轮次或 turn 不存在时，页面不崩溃。
- 每个任务完成后运行该任务相关测试并提交。

---

## File Structure

- Create `mallpilot/app/services/trace_summary.py`
  - Owns pure aggregation functions for turn dropdown options and per-turn summaries.
  - Does not access the database.

- Modify `mallpilot/app/repositories/trace_repo.py`
  - Adds SQL query for recent turn metadata.
  - Keeps existing `list_by_turn()` behavior unchanged.

- Modify `mallpilot/app/services/db_trace_service.py`
  - Adds `list_turns()` delegating to `TraceRepository`.

- Modify `mallpilot/app/api/trace.py`
  - Adds `/api/trace/turns` and `/api/trace/turns/{turn_id}/summary`.
  - Keeps `/api/trace/turns/{turn_id}/events`.

- Modify `mallpilot/app/web/observability/index.html`
  - Replaces fixed `turn_1` entry with dropdown-driven layout.

- Modify `mallpilot/app/web/observability/app.js`
  - Loads turns API, renders dropdown, loads summary API, renders groups/timeline/details.

- Modify `mallpilot/app/web/observability/style.css`
  - Adds stable layout, grouped stage cards, error and slow-event states.

- Modify `tests/test_observability_api.py`
  - Adds API tests for turns and summary.

- Create `tests/test_trace_summary.py`
  - Unit tests for aggregation and grouping.

- Create `tests/test_observability_frontend.py`
  - Static tests validate frontend API usage and CSS state classes.

---

### Task 1: Trace Summary Pure Aggregation

**Files:**
- Create: `mallpilot/app/services/trace_summary.py`
- Test: `tests/test_trace_summary.py`

**Interfaces:**
- Consumes: `mallpilot.app.agent.schemas.TraceEvent`
- Produces:
  - `build_empty_trace_summary(turn_id: str) -> dict[str, Any]`
  - `trace_group_name(event: TraceEvent) -> str`
  - `build_trace_summary(turn_id: str, events: list[TraceEvent]) -> dict[str, Any]`

- [ ] **Step 1: Write failing aggregation tests**

Create `tests/test_trace_summary.py` with:

```python
from datetime import datetime, timezone

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.services.trace_summary import build_empty_trace_summary, build_trace_summary, trace_group_name


# 构造测试 Trace 事件。
def make_event(event_type: str, status: str = "ok", duration_ms: int | None = None) -> TraceEvent:
    return TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type=event_type,
        span_name=event_type.replace(".", "_"),
        payload={"sample": event_type},
        status=status,
        duration_ms=duration_ms,
        timestamp=datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc),
    )


# 验证事件类型会映射到观测阶段分组。
def test_trace_group_name_maps_known_event_types():
    assert trace_group_name(make_event("router.intent")) == "router"
    assert trace_group_name(make_event("retrieval.vector")) == "retrieval"
    assert trace_group_name(make_event("rerank.bailian")) == "rerank"
    assert trace_group_name(make_event("llm.bailian")) == "llm"
    assert trace_group_name(make_event("sse.emit")) == "sse"
    assert trace_group_name(make_event("custom.event")) == "other"


# 验证错误事件会进入 error 分组。
def test_trace_group_name_maps_error_events_to_error():
    assert trace_group_name(make_event("retrieval.error", status="error")) == "error"
    assert trace_group_name(make_event("llm.bailian", status="error")) == "error"


# 验证空摘要结构稳定。
def test_build_empty_trace_summary_returns_stable_shape():
    summary = build_empty_trace_summary("turn_missing")

    assert summary == {
        "turn_id": "turn_missing",
        "event_count": 0,
        "error_count": 0,
        "total_duration_ms": 0,
        "groups": [],
        "events": [],
    }


# 验证 summary 汇总数量、错误数、耗时和分组。
def test_build_trace_summary_groups_events_and_sums_duration():
    events = [
        make_event("router.intent", duration_ms=5),
        make_event("retrieval.vector", duration_ms=80),
        make_event("rerank.bailian", duration_ms=120),
        make_event("llm.bailian", duration_ms=1100),
        make_event("sse.emit"),
        make_event("retrieval.error", status="error", duration_ms=10),
    ]

    summary = build_trace_summary("turn_1", events)

    assert summary["turn_id"] == "turn_1"
    assert summary["event_count"] == 6
    assert summary["error_count"] == 1
    assert summary["total_duration_ms"] == 1315
    groups = {group["name"]: group for group in summary["groups"]}
    assert groups["router"]["event_count"] == 1
    assert groups["retrieval"]["duration_ms"] == 80
    assert groups["error"]["status"] == "error"
    assert len(summary["events"]) == 6
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
pytest -v tests/test_trace_summary.py
```

Expected: FAIL with `ModuleNotFoundError` for `mallpilot.app.services.trace_summary`.

- [ ] **Step 3: Implement aggregation module**

Create `mallpilot/app/services/trace_summary.py`:

```python
from typing import Any

from mallpilot.app.agent.schemas import TraceEvent


# Trace 阶段展示顺序。
GROUP_ORDER = ["router", "retrieval", "rerank", "llm", "sse", "error", "other"]


# 构造空 Trace 摘要。
def build_empty_trace_summary(turn_id: str) -> dict[str, Any]:
    return {
        "turn_id": turn_id,
        "event_count": 0,
        "error_count": 0,
        "total_duration_ms": 0,
        "groups": [],
        "events": [],
    }


# 根据事件类型判断观测阶段。
def trace_group_name(event: TraceEvent) -> str:
    if event.status == "error" or event.event_type.endswith(".error"):
        return "error"
    prefix = event.event_type.split(".", maxsplit=1)[0]
    if prefix in {"router", "retrieval", "rerank", "llm", "sse"}:
        return prefix
    return "other"


# 将 Trace 事件聚合成前端可直接渲染的 summary。
def build_trace_summary(turn_id: str, events: list[TraceEvent]) -> dict[str, Any]:
    if not events:
        return build_empty_trace_summary(turn_id)

    sorted_events = sorted(events, key=lambda event: event.timestamp)
    groups: dict[str, dict[str, Any]] = {}

    for event in sorted_events:
        group_name = trace_group_name(event)
        if group_name not in groups:
            # 初始化阶段分组摘要。
            groups[group_name] = {
                "name": group_name,
                "event_count": 0,
                "error_count": 0,
                "duration_ms": 0,
                "status": "ok",
                "events": [],
            }

        group = groups[group_name]
        duration_ms = event.duration_ms or 0
        group["event_count"] += 1
        group["duration_ms"] += duration_ms
        group["events"].append(event.model_dump(mode="json"))
        if event.status == "error":
            group["error_count"] += 1
            group["status"] = "error"

    ordered_groups = [groups[name] for name in GROUP_ORDER if name in groups]
    return {
        "turn_id": turn_id,
        "event_count": len(sorted_events),
        "error_count": sum(1 for event in sorted_events if event.status == "error"),
        "total_duration_ms": sum(event.duration_ms or 0 for event in sorted_events),
        "groups": ordered_groups,
        "events": [event.model_dump(mode="json") for event in sorted_events],
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
pytest -v tests/test_trace_summary.py
```

Expected: PASS, 4 tests passed.

- [ ] **Step 5: Commit**

```powershell
git add -- mallpilot/app/services/trace_summary.py tests/test_trace_summary.py
git commit -m "feat: add trace summary aggregation"
```

---

### Task 2: Turns List and Summary APIs

**Files:**
- Modify: `mallpilot/app/repositories/trace_repo.py`
- Modify: `mallpilot/app/services/db_trace_service.py`
- Modify: `mallpilot/app/api/trace.py`
- Modify: `tests/test_observability_api.py`

**Interfaces:**
- Consumes:
  - `TraceRepository.list_by_turn(turn_id: str) -> list[TraceEvent]`
  - `build_trace_summary(turn_id: str, events: list[TraceEvent]) -> dict[str, Any]`
  - `build_empty_trace_summary(turn_id: str) -> dict[str, Any]`
- Produces:
  - `TraceRepository.list_turns(limit: int = 50) -> list[dict[str, Any]]`
  - `DbTraceService.list_turns(limit: int = 50) -> list[dict[str, Any]]`
  - `GET /api/trace/turns`
  - `GET /api/trace/turns/{turn_id}/summary`

- [ ] **Step 1: Write failing API tests**

Append to `tests/test_observability_api.py`:

```python
from datetime import datetime, timezone

from mallpilot.app.agent.schemas import TraceEvent


# 构造 API 测试 Trace 事件。
def make_trace_event(turn_id: str, event_type: str, duration_ms: int | None = None, status: str = "ok") -> TraceEvent:
    return TraceEvent(
        chat_id="chat_1",
        turn_id=turn_id,
        event_type=event_type,
        span_name=event_type.replace(".", "_"),
        payload={"event_type": event_type},
        status=status,
        duration_ms=duration_ms,
        timestamp=datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc),
    )


# 验证轮次列表接口返回可用于下拉框的标签。
def test_trace_turns_api_returns_dropdown_options(monkeypatch):
    monkeypatch.setattr(trace_api.trace_service, "list_turns", lambda limit=50: [
        {
            "label": "第 1 轮",
            "turn_id": "turn_1",
            "chat_id": "chat_1",
            "event_count": 2,
            "started_at": "2026-07-12T10:00:00+00:00",
        }
    ])
    client = TestClient(create_app())

    response = client.get("/api/trace/turns")

    assert response.status_code == 200
    assert response.json()["turns"][0]["label"] == "第 1 轮"
    assert response.json()["turns"][0]["turn_id"] == "turn_1"


# 验证 summary 接口返回分组后的调用链摘要。
def test_trace_summary_api_returns_grouped_summary(monkeypatch):
    monkeypatch.setattr(trace_api.trace_service, "list_events", lambda turn_id: [
        make_trace_event(turn_id, "router.intent", duration_ms=5),
        make_trace_event(turn_id, "llm.bailian", duration_ms=1200),
    ])
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_1/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["turn_id"] == "turn_1"
    assert data["event_count"] == 2
    assert data["total_duration_ms"] == 1205
    assert [group["name"] for group in data["groups"]] == ["router", "llm"]


# 验证 summary 接口在查询失败时返回空摘要。
def test_trace_summary_api_returns_empty_summary_when_trace_service_fails(monkeypatch):
    def raise_error(turn_id: str):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(trace_api.trace_service, "list_events", raise_error)
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_missing/summary")

    assert response.status_code == 200
    assert response.json() == {
        "turn_id": "turn_missing",
        "event_count": 0,
        "error_count": 0,
        "total_duration_ms": 0,
        "groups": [],
        "events": [],
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
pytest -v tests/test_observability_api.py
```

Expected: FAIL because `/api/trace/turns` and `/summary` routes are missing.

- [ ] **Step 3: Add repository turn listing**

Modify `mallpilot/app/repositories/trace_repo.py` imports:

```python
from typing import Any

from sqlalchemy import func, select
```

Add this method to `TraceRepository`:

```python
    # 查询最近可观测轮次，供前端下拉框选择。
    def list_turns(self, limit: int = 50) -> list[dict[str, Any]]:
        statement = (
            select(
                TraceEventRow.turn_id,
                TraceEventRow.chat_id,
                func.count(TraceEventRow.trace_id).label("event_count"),
                func.min(TraceEventRow.timestamp).label("started_at"),
            )
            .group_by(TraceEventRow.turn_id, TraceEventRow.chat_id)
            .order_by(func.min(TraceEventRow.timestamp))
            .limit(limit)
        )
        rows = self.session.execute(statement).all()

        turns: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            # 前端只展示 label，turn_id 作为内部加载 summary 的值。
            turns.append({
                "label": f"第 {index} 轮",
                "turn_id": row.turn_id,
                "chat_id": row.chat_id,
                "event_count": int(row.event_count),
                "started_at": row.started_at.isoformat() if row.started_at else None,
            })
        return turns
```

- [ ] **Step 4: Add service turn listing**

Add this method to `mallpilot/app/services/db_trace_service.py`:

```python
    # 查询最近轮次列表，供观测页下拉框使用。
    def list_turns(self, limit: int = 50) -> list[dict]:
        with self.session_factory() as session:
            return TraceRepository(session).list_turns(limit=limit)
```

- [ ] **Step 5: Add trace API routes**

Modify `mallpilot/app/api/trace.py` imports:

```python
from mallpilot.app.services.trace_summary import build_empty_trace_summary, build_trace_summary
```

Add these routes above `list_turn_events()`:

```python
# 查询可供下拉选择的 Trace 轮次。
@router.get("/turns")
def list_turns() -> dict:
    try:
        # 数据库可用时返回真实轮次列表。
        turns = trace_service.list_turns()
    except Exception:
        # 数据库尚未启动或迁移未执行时，观测页面显示空状态。
        turns = []
    return {"turns": turns}


# 查询某个 turn 的聚合调用链摘要。
@router.get("/turns/{turn_id}/summary")
def get_turn_summary(turn_id: str) -> dict:
    try:
        # 数据库可用时基于真实 Trace 事件构造 summary。
        events = trace_service.list_events(turn_id)
    except Exception:
        # 数据库不可用时返回稳定空摘要。
        return build_empty_trace_summary(turn_id)
    return build_trace_summary(turn_id, events)
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
pytest -v tests/test_observability_api.py tests/test_trace_summary.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- mallpilot/app/repositories/trace_repo.py mallpilot/app/services/db_trace_service.py mallpilot/app/api/trace.py tests/test_observability_api.py
git commit -m "feat: add trace turns summary api"
```

---

### Task 3: Observability Frontend Dropdown and Timeline

**Files:**
- Modify: `mallpilot/app/web/observability/index.html`
- Modify: `mallpilot/app/web/observability/app.js`
- Modify: `mallpilot/app/web/observability/style.css`
- Create: `tests/test_observability_frontend.py`

**Interfaces:**
- Consumes:
  - `GET /api/trace/turns -> {"turns": list[dict]}`
  - `GET /api/trace/turns/{turn_id}/summary -> dict`
- Produces:
  - Dropdown for “第 N 轮”
  - Group cards
  - Timeline with `.is-error` and `.is-slow`
  - Detail panel with selected event fields and payload

- [ ] **Step 1: Write failing frontend static tests**

Create `tests/test_observability_frontend.py`:

```python
from pathlib import Path


OBSERVABILITY_ROOT = Path("mallpilot/app/web/observability")


# 验证观测页提供轮次下拉容器。
def test_observability_page_has_turn_selector():
    html = (OBSERVABILITY_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="turnSelect"' in html
    assert 'id="refreshTurns"' in html
    assert 'id="summary"' in html
    assert 'id="groups"' in html


# 验证观测页脚本调用 turns 和 summary API。
def test_observability_script_uses_turns_and_summary_api():
    script = (OBSERVABILITY_ROOT / "app.js").read_text(encoding="utf-8")

    assert "fetch('/api/trace/turns')" in script
    assert "fetch(`/api/trace/turns/${turnId}/summary`)" in script
    assert "renderTurnOptions" in script
    assert "renderGroups" in script
    assert "renderTimeline" in script
    assert "renderDetail" in script


# 验证样式包含错误和慢事件状态。
def test_observability_styles_include_error_and_slow_states():
    css = (OBSERVABILITY_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".timeline-item.is-error" in css
    assert ".timeline-item.is-slow" in css
    assert ".group-card.is-error" in css
```

- [ ] **Step 2: Run frontend tests to verify failure**

Run:

```powershell
pytest -v tests/test_observability_frontend.py
```

Expected: FAIL because selectors/functions are not present.

- [ ] **Step 3: Replace observability HTML structure**

Replace `mallpilot/app/web/observability/index.html` body content with:

```html
<body>
  <main class="layout">
    <section class="panel sidebar">
      <h1>MallPilot Observability</h1>
      <label class="field-label" for="turnSelect">观测轮次</label>
      <div class="turn-picker">
        <select id="turnSelect"></select>
        <button id="refreshTurns" type="button">刷新</button>
      </div>
      <div id="summary" class="summary">暂无可观测轮次</div>
    </section>
    <section class="panel timeline-panel">
      <h2>调用链</h2>
      <div id="groups" class="groups"></div>
      <div id="timeline" class="timeline"></div>
    </section>
    <section class="panel detail-panel">
      <h2>事件详情</h2>
      <div id="detail" class="detail-empty">请选择一条事件</div>
    </section>
  </main>
  <script src="/admin/static/app.js"></script>
</body>
```

Keep the existing `<head>` with title and stylesheet link unchanged.

- [ ] **Step 4: Replace observability JS**

Replace `mallpilot/app/web/observability/app.js` with:

```javascript
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
```

- [ ] **Step 5: Replace observability CSS**

Replace `mallpilot/app/web/observability/style.css` with:

```css
body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f6f7f9;
  color: #1f2937;
}

.layout {
  display: grid;
  grid-template-columns: 280px 1fr 420px;
  gap: 12px;
  padding: 12px;
}

.panel {
  min-height: 80vh;
  padding: 12px;
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 6px;
}

.field-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #4b5563;
}

.turn-picker {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

select,
button {
  min-height: 34px;
}

.summary {
  margin-top: 16px;
}

.summary-grid,
.detail-meta {
  display: grid;
  gap: 8px;
}

.summary-grid div,
.detail-meta div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

dt {
  color: #6b7280;
}

dd {
  margin: 0;
  font-weight: 700;
}

.groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.group-card {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  background: #f9fafb;
}

.group-card.is-error {
  border-color: #dc2626;
  background: #fef2f2;
}

.timeline-item {
  display: block;
  width: 100%;
  margin-bottom: 8px;
  padding: 10px;
  text-align: left;
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 6px;
}

.timeline-item small {
  display: block;
  margin-top: 4px;
  color: #6b7280;
}

.timeline-item.is-error {
  border-color: #dc2626;
}

.timeline-item.is-slow {
  box-shadow: inset 3px 0 0 #d97706;
}

.detail-empty {
  color: #6b7280;
}

.detail pre {
  overflow: auto;
  max-height: 55vh;
  padding: 10px;
  background: #111827;
  color: #f9fafb;
  border-radius: 6px;
}

.error-message {
  padding: 8px;
  color: #991b1b;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
}
```

- [ ] **Step 6: Run frontend tests**

Run:

```powershell
pytest -v tests/test_observability_frontend.py tests/test_observability_api.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- mallpilot/app/web/observability/index.html mallpilot/app/web/observability/app.js mallpilot/app/web/observability/style.css tests/test_observability_frontend.py
git commit -m "feat: add observability turn selector UI"
```

---

### Task 4: Full Regression and Documentation Check

**Files:**
- Modify: `docs/superpowers/specs/2026-07-12-sprint-3-observability-design.md` only if implementation reveals a mismatch.

**Interfaces:**
- Consumes all outputs from Tasks 1-3.
- Produces a verified working Sprint 3 implementation.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
pytest -v
```

Expected: PASS with all tests passing. A single existing Starlette deprecation warning is acceptable if the suite passes.

- [ ] **Step 2: Check route compatibility**

Run:

```powershell
pytest -v tests/test_observability_api.py::test_trace_events_api_returns_list
```

Expected: PASS, confirming `/api/trace/turns/{turn_id}/events` still works.

- [ ] **Step 3: Review changed files**

Run:

```powershell
git diff -- mallpilot/app/services/trace_summary.py mallpilot/app/repositories/trace_repo.py mallpilot/app/services/db_trace_service.py mallpilot/app/api/trace.py mallpilot/app/web/observability/index.html mallpilot/app/web/observability/app.js mallpilot/app/web/observability/style.css tests/test_trace_summary.py tests/test_observability_api.py tests/test_observability_frontend.py
```

Expected: Diff only contains Sprint 3 Observability implementation and tests.

- [ ] **Step 4: Commit final verification note if docs changed**

If `docs/superpowers/specs/2026-07-12-sprint-3-observability-design.md` changed during implementation, commit it:

```powershell
git add -- docs/superpowers/specs/2026-07-12-sprint-3-observability-design.md
git commit -m "docs: align sprint 3 observability spec"
```

If the spec did not change, do not create a documentation-only commit.

- [ ] **Step 5: Report completion**

Final report must include:

```text
Implemented Sprint 3 Observability turn selector and summary panel.
Validation: pytest -v passed.
Key endpoints: /api/trace/turns, /api/trace/turns/{turn_id}/summary, /api/trace/turns/{turn_id}/events.
```

---

## Self-Review

- Spec coverage: The plan covers the turns dropdown, summary API, grouping, slow/error highlighting, event detail rendering, empty states, API tests, frontend static tests, and `/events` compatibility.
- Deferred-marker scan: The plan contains no deferred implementation markers, no undefined follow-up implementation slots, and each code-changing step includes concrete code.
- Type consistency: Function names are consistent across tasks: `build_empty_trace_summary`, `trace_group_name`, `build_trace_summary`, `list_turns`, `list_turn_events`, and `get_turn_summary`.
