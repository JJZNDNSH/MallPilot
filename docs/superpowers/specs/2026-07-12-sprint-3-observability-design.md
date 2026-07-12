# Sprint 3 Observability 调用链面板设计

## 背景

Sprint 2 已经把 MallPilot 推进到真实导购链路：运行时接入数据库商品检索、百炼 embedding、百炼 rerank、百炼 Chat LLM、SSE 聊天流、数据库 Trace 持久化，并新增 LLM Router 用于真实意图识别。当前系统已经能跑通真实模型和真实商品库参与导购的主链路，但观测页面仍停留在 MVP 状态：只有固定 `turn_1` 入口、平铺事件列表和原始 JSON 详情。

Sprint 3 的目标不是继续扩大业务功能，而是把每轮 Agent 执行链路看清楚。只有先看清 Router、Retrieval、Rerank、LLM 和 SSE 的执行过程，后续优化检索质量、路由质量和交易流程才有可靠依据。

## 用户确认的方向

本阶段采用“Turn 级调用链面板 + summary API”方案。

核心原则：

1. 聚焦单个 `turn_id` 的完整调用链。
2. 新增后端聚合接口，前端消费聚合结果。
3. 保留现有 `/api/trace/turns/{turn_id}/events` 接口，避免破坏聊天页和已有测试。
4. 不引入前端框架或图表库，继续使用原生 HTML/CSS/JS。
5. 不做全局后台管理系统，不做完整会话搜索。

## 目标

1. 新增 `GET /api/trace/turns/{turn_id}/summary`，返回单轮 Trace 的聚合摘要。
2. 将 Trace 事件按阶段分组：`router`、`retrieval`、`rerank`、`llm`、`sse`、`error`、`other`。
3. 每组展示事件数量、错误数量、耗时汇总和最新状态。
4. 前端支持输入 `turn_id` 后加载该轮调用链。
5. Timeline 按时间顺序展示事件，并高亮错误事件和高耗时事件。
6. 右侧详情区展示选中事件的摘要字段和完整 payload。
7. 数据库不可用或 turn 不存在时，页面给出可恢复的空状态，而不是崩溃。
8. 为 summary API、分组逻辑和前端渲染补充测试。

## 非目标

1. 本阶段不做最近会话列表和最近 turn 列表。
2. 本阶段不做跨 turn 搜索、筛选或分页。
3. 本阶段不引入图表库，不做复杂瀑布图组件。
4. 本阶段不改 ChatService 的业务 Flow。
5. 本阶段不优化检索算法、LLM Router prompt 或交易流程。
6. 本阶段不接入外部 APM、日志平台或指标系统。

## 方案选择

### 方案 A：前端-only 分组

前端继续调用现有 `/events` 接口，并在浏览器中完成分组、耗时汇总和错误统计。

优点是实现最快，后端不用新增接口。缺点是聚合逻辑只能在观测页使用，后续如果聊天页、测试工具或脚本也要读取摘要，需要重复实现。

### 方案 B：完整 Observability 后台

一次性实现最近 turns、会话列表、搜索、筛选、瀑布图、错误面板和调用链详情。

优点是产品形态完整。缺点是范围过大，会把当前 Sprint 从“调试真实 Agent 链路”扩大成“后台管理系统”，不利于快速验证。

### 方案 C：summary API + Turn 级调用链面板（采用）

后端新增 summary API，负责标准化分组和摘要；前端负责呈现 turn 输入、阶段分组、timeline 和详情。

优点是边界清楚、可测试、可复用，并且足够支撑后续调试 LLM Router 和检索链路。缺点是暂时不能浏览最近会话，需要用户从聊天页或日志中拿到 `turn_id`。

本 Sprint 采用方案 C。

## 后端设计

### API

新增接口：

```text
GET /api/trace/turns/{turn_id}/summary
```

返回结构：

```json
{
  "turn_id": "turn_x",
  "event_count": 8,
  "error_count": 1,
  "total_duration_ms": 1200,
  "groups": [
    {
      "name": "retrieval",
      "event_count": 3,
      "error_count": 0,
      "duration_ms": 240,
      "status": "ok",
      "events": []
    }
  ],
  "events": []
}
```

`events` 使用现有 `TraceEvent.model_dump(mode="json")` 兼容格式，避免前端同时处理两套事件模型。

### 分组规则

分组由 `event_type` 前缀决定：

- `router.*` -> `router`
- `retrieval.*` -> `retrieval`
- `rerank.*` -> `rerank`
- `llm.*` -> `llm`
- `sse.*` -> `sse`
- `status == error` 或 `*.error` -> `error`
- 其他事件 -> `other`

错误事件进入 `error` 组，同时仍保留在原始 `events` 时间线中。为了避免同一事件在分组摘要中重复展示，事件详情仍以 timeline 为准，分组卡只展示数量、状态和耗时摘要。

### 聚合逻辑

新增轻量聚合函数或服务方法，输入 `list[TraceEvent]`，输出 summary dict。

聚合规则：

1. `event_count` 是事件总数。
2. `error_count` 是 `status == "error"` 的事件数。
3. `total_duration_ms` 是所有非空 `duration_ms` 的求和。
4. 组级 `duration_ms` 是该组非空耗时求和。
5. 组级 `status` 只要有错误就是 `error`，否则为 `ok`。
6. 事件按 `timestamp` 升序保留。

数据库不可用时，summary API 返回空摘要：

```json
{
  "turn_id": "turn_x",
  "event_count": 0,
  "error_count": 0,
  "total_duration_ms": 0,
  "groups": [],
  "events": []
}
```

## 前端设计

页面仍为三栏布局，但内容升级：

左侧：

- `turn_id` 输入框。
- 加载按钮。
- 当前 turn 摘要：事件数、错误数、总耗时。
- 空状态和错误提示。

中间：

- 阶段分组卡片：`router`、`retrieval`、`rerank`、`llm`、`sse`、`error`、`other`。
- Timeline 事件列表，按时间顺序展示。
- 错误事件使用明显但克制的红色边框或状态标识。
- 高耗时事件使用轻量标识，例如 `slow` 标签。默认阈值为 `duration_ms >= 1000`。

右侧：

- 选中事件的核心字段：`event_type`、`span_name`、`status`、`duration_ms`、`timestamp`。
- `error_message` 单独展示。
- `payload` 使用格式化 JSON 展示。

页面不使用营销式说明文案，不引入图表库，不做大面积装饰。

## 数据流

```text
用户输入 turn_id
-> 前端调用 GET /api/trace/turns/{turn_id}/summary
-> Trace API 读取 DbTraceService.list_events(turn_id)
-> 聚合函数构造 summary
-> 前端渲染摘要、阶段分组、timeline
-> 用户点击事件
-> 右侧详情区展示事件字段和 payload
```

## 错误处理

1. 数据库连接失败：summary API 返回空摘要，前端展示“未找到事件或数据源不可用”的状态。
2. turn 不存在：返回空摘要，HTTP 状态仍为 200。
3. payload 不是对象：前端按 JSON 值格式化展示。
4. 事件缺少耗时：聚合时按 0 处理，前端显示 `-`。
5. 前端请求失败：保留当前页面结构，展示加载失败提示。

## 测试策略

1. 聚合单元测试：构造 router、retrieval、rerank、llm、sse、error 事件，验证分组、数量、错误数和耗时。
2. API 测试：mock `trace_service.list_events()`，验证 `/summary` 返回稳定结构。
3. 空状态测试：mock 返回空列表，验证 summary 为空但结构完整。
4. 前端静态测试：验证 observability JS 包含 summary API 调用、阶段分组渲染、错误高亮和事件详情渲染逻辑。
5. 回归测试：保留现有 `/events` API 测试，确保旧接口不变。
6. 全量测试：运行 `pytest -v`。

## 验收标准

1. `/admin/observability` 可以输入任意 `turn_id` 并加载 summary。
2. `/api/trace/turns/{turn_id}/summary` 返回聚合后的调用链摘要。
3. 页面能清楚区分 router、retrieval、rerank、llm、sse 和 error 阶段。
4. 错误事件和高耗时事件在 timeline 中有明显标识。
5. 点击 timeline 事件后，右侧详情区展示摘要字段和 payload。
6. turn 不存在或数据库不可用时，页面不崩溃。
7. 现有 `/api/trace/turns/{turn_id}/events` 接口保持兼容。
8. 新增和既有测试全部通过。

## 风险与处理

1. Trace 事件类型继续扩展后分组不完整：未知事件统一进入 `other`，后续按需补分组规则。
2. 当前部分事件没有 `duration_ms`：聚合逻辑允许缺失耗时，前端显示 `-`。
3. 错误事件同时属于业务阶段和 error 阶段：本 Sprint 优先保证 error 汇总清楚，timeline 保留原始事件顺序。
4. 没有最近 turn 列表导致输入不便：本 Sprint 先从聊天页 Trace 入口或手动 turn_id 调试，最近 turn 列表放到后续阶段。

## 后续衔接

Sprint 3 完成后，可以继续做：

1. 最近 turns 列表和按 chat_id 查询。
2. 检索质量优化：pgvector SQL 召回、中文分词、多 chunk 去重。
3. LLM Router 评估集和路由准确率面板。
4. 更完整的调用瀑布图和耗时趋势。
