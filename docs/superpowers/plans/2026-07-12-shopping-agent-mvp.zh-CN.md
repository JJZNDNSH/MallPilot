# 导购 Agent MVP 中文实现计划

> **给执行 Agent 的要求：** 实现本计划时，推荐使用 `superpowers:subagent-driven-development`，也可以使用 `superpowers:executing-plans`。每个任务都应按复选框逐步执行、测试、提交。

**目标：** 实现一个基于 Python FastAPI 的导购 Agent 后端 MVP，支持混合检索、结构化 SSE 事件、购物车模拟、订单/售后模拟，以及 Web 可观测界面。

**架构：** 用户请求进入 `ChatService` 后，由 `IntentRouter` 判断意图，再分发到对应 `FlowHandler`。Flow 执行过程中调用检索、工具和 LLM 客户端，通过 SSE 向用户前端发送结构化展示事件，同时把 LLM 调用、检索过程、工具调用和 SSE 事件写入 Trace Store，供可观测界面查看。

**技术栈：** Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2、PostgreSQL + pgvector、pytest、httpx、原生 HTML/CSS/JavaScript。

## 全局约束

- 主后端使用 Python。
- Web 框架使用 FastAPI。
- Agent 编排使用自研 `IntentRouter + FlowHandler`，不使用 LangGraph。
- 检索链路使用：结构化过滤 + BM25 关键词召回 + 向量语义召回 + 可选图片向量召回 + RRF 融合 + Cross-Encoder 精排。
- SSE 事件必须是结构化事件，前端根据 `type` 渲染不同组件。
- 可观测界面是 MVP 核心交付，路径为 `/admin/observability`。
- 用户侧 `thinking` 事件只能展示公开业务进度，不能输出隐藏推理链。
- 第一版订单、售后均为模拟流程，不接真实支付、履约、退款。
- 商品源数据从 `data/ecommerce_agent_dataset` 读取，统一使用 UTF-8。
- 新增或修改代码时，字段、方法、关键逻辑需添加中文注释。

---

## 一、推荐文件结构

```text
mallpilot/
  app/
    main.py
    api/
      chat.py
      products.py
      cart.py
      trace.py
      admin.py
    core/
      config.py
      event_bus.py
      exceptions.py
    agent/
      schemas.py
      state.py
      router.py
      flows/
        base.py
        guide_flow.py
        product_qa_flow.py
        cart_flow.py
        order_flow.py
        after_sale_flow.py
    retrieval/
      text_chunker.py
      bm25_search.py
      vector_search.py
      image_search.py
      fusion.py
      cross_encoder_reranker.py
      product_search.py
    tools/
      registry.py
      product_tools.py
      cart_tools.py
      order_tools.py
      after_sale_tools.py
    models/
      product.py
      trace.py
    repositories/
      product_repo.py
      trace_repo.py
      cart_repo.py
    services/
      chat_service.py
      trace_service.py
      llm_client.py
    web/
      observability/
        index.html
        app.js
        style.css
  scripts/
    ingest_products.py
    build_text_index.py
  tests/
```

---

## 任务 1：项目骨架与共享 Schema

**目标：** 搭出 FastAPI 项目骨架，定义 Chat、SSE、Trace、Intent、ProductCandidate 等基础数据结构。

**创建文件：**

- `pyproject.toml`
- `mallpilot/app/main.py`
- `mallpilot/app/core/config.py`
- `mallpilot/app/core/exceptions.py`
- `mallpilot/app/agent/schemas.py`
- `tests/test_sse_events.py`

**核心接口：**

- `create_app() -> FastAPI`
- `ChatRequest`
- `SseEvent`
- `TraceEvent`
- `IntentResult`
- `ProductCandidate`

**执行步骤：**

- [ ] 编写 `tests/test_sse_events.py`，验证 `SseEvent` 有稳定 envelope：`event_id`、`type`、`chat_id`、`turn_id`、`seq`、`timestamp`、`payload`。
- [ ] 编写 `TraceEvent` 测试，验证可以记录 `event_type`、`span_name`、`payload`、`status`。
- [ ] 运行 `pytest tests/test_sse_events.py -v`，确认失败。
- [ ] 创建 `pyproject.toml`，声明 FastAPI、Pydantic、SQLAlchemy、pytest、httpx 等依赖。
- [ ] 实现 `schemas.py` 中的基础 Pydantic 模型。
- [ ] 实现 `create_app()`，先返回一个空 FastAPI app。
- [ ] 运行 `pytest tests/test_sse_events.py -v`，确认通过。
- [ ] 提交：`git commit -m "feat: add mallpilot backend skeleton"`。

**验收标准：**

- 测试通过。
- `SseEvent.model_dump()` 中包含稳定字段。
- `TraceEvent` 可以表达 Router、检索、LLM、工具、SSE 等阶段。

---

## 任务 2：商品数据读取与知识块切分

**目标：** 从 `data/ecommerce_agent_dataset` 读取 100 个商品 JSON，并切分成可检索知识块。

**创建文件：**

- `mallpilot/app/retrieval/text_chunker.py`
- `scripts/ingest_products.py`
- `tests/test_text_chunker.py`

**核心接口：**

- `load_product_files(dataset_dir: str) -> list[dict]`
- `build_knowledge_chunks(product: dict) -> list[dict]`

**知识块类型：**

- `basic`：标题、品牌、品类、价格、SKU 摘要。
- `marketing`：商品营销描述。
- `faq`：每条官方 FAQ 独立切块。
- `review_summary`：评论聚合摘要。

**执行步骤：**

- [ ] 编写测试，验证一条商品会切出 `basic`、`marketing`、`faq`、`review_summary`。
- [ ] 运行 `pytest tests/test_text_chunker.py -v`，确认失败。
- [ ] 实现 `build_knowledge_chunks()`。
- [ ] 实现 `load_product_files()`，按 UTF-8 读取 `*/data/*.json`。
- [ ] 运行 `python scripts/ingest_products.py`，期望输出 `loaded_products=100`。
- [ ] 运行 `pytest tests/test_text_chunker.py -v`，确认通过。
- [ ] 提交：`git commit -m "feat: add product ingestion and chunking"`。

**验收标准：**

- 能读取 100 个商品。
- FAQ 每条独立成块。
- 评论不会直接原样大量进入检索，而是先生成摘要。

---

## 任务 3：混合检索核心

**目标：** 实现导购检索主链路：结构化过滤、BM25、文本向量、图片向量、RRF 融合、Cross-Encoder 精排。

**创建文件：**

- `mallpilot/app/retrieval/bm25_search.py`
- `mallpilot/app/retrieval/vector_search.py`
- `mallpilot/app/retrieval/image_search.py`
- `mallpilot/app/retrieval/fusion.py`
- `mallpilot/app/retrieval/cross_encoder_reranker.py`
- `mallpilot/app/retrieval/product_search.py`
- `tests/test_hybrid_retrieval.py`

**核心接口：**

```python
HybridProductSearch.search(
    query: str,
    filters: dict,
    image_embedding: list[float] | None = None,
) -> tuple[list[ProductCandidate], list[dict]]
```

**检索流程：**

```text
结构化过滤
  -> BM25 关键词召回
  -> 文本向量语义召回
  -> 有图片时追加图片向量召回
  -> RRF 融合
  -> Cross-Encoder 精排
  -> 返回 ProductCandidate
```

**Trace 阶段：**

- `bm25_result`
- `text_vector_result`
- `image_vector_result`
- `rrf_fusion_result`
- `cross_encoder_rerank_result`

**执行步骤：**

- [ ] 编写测试：输入“300元以内敏感肌修护精华”，期望召回美妆商品，并产生 BM25、向量、RRF、Cross-Encoder Trace。
- [ ] 实现轻量 BM25 搜索。
- [ ] 实现第一版文本向量召回占位逻辑，后续可接真实 embedding。
- [ ] 实现图片向量召回接口，有图片 embedding 时启用，无图片时返回空。
- [ ] 实现 `reciprocal_rank_fusion()`。
- [ ] 实现 `CrossEncoderReranker`，第一版可用轻量打分，后续替换真实模型。
- [ ] 实现 `HybridProductSearch` 门面类。
- [ ] 运行 `pytest tests/test_hybrid_retrieval.py -v`。
- [ ] 提交：`git commit -m "feat: add hybrid retrieval pipeline"`。

**验收标准：**

- BM25 和向量召回都参与结果。
- RRF 能融合多路候选并去重。
- Cross-Encoder 精排输出最终排序。
- Trace 能展示每一路召回数量和精排结果。

---

## 任务 4：Trace Service 与 SSE EventBus

**目标：** 实现事件总线和 Trace 记录服务，让用户侧事件和调试侧事件都可追踪。

**创建文件：**

- `mallpilot/app/services/trace_service.py`
- `mallpilot/app/core/event_bus.py`
- `tests/test_trace_service.py`

**核心接口：**

- `TraceService.record(event: TraceEvent) -> None`
- `TraceService.list_events(turn_id: str) -> list[TraceEvent]`
- `EventBus.emit(event: SseEvent) -> str`

**执行步骤：**

- [ ] 编写测试，验证 Trace 可以按 `turn_id` 查询。
- [ ] 编写测试，验证 `SseEvent` 能序列化成标准 SSE 文本。
- [ ] 实现内存版 `TraceService`。
- [ ] 实现 `EventBus.emit()`。
- [ ] 运行 `pytest tests/test_trace_service.py -v`。
- [ ] 提交：`git commit -m "feat: add trace service and sse event bus"`。

**验收标准：**

- SSE 文本格式为 `event: message\ndata: {...}\n\n`。
- Trace 事件可以按单轮对话查询。

---

## 任务 5：IntentRouter 与 Flow 合约

**目标：** 建立全局意图路由，不让所有请求都进入导购检索流。

**创建文件：**

- `mallpilot/app/agent/router.py`
- `mallpilot/app/agent/state.py`
- `mallpilot/app/agent/flows/base.py`
- `tests/test_router.py`

**意图类型：**

- `guide`
- `product_qa`
- `compare`
- `cart`
- `order`
- `after_sale`
- `chitchat`

**核心接口：**

- `IntentRouter.route(message: str) -> IntentResult`
- `FlowContext`
- `BaseFlow.run(context: FlowContext) -> list[SseEvent]`

**执行步骤：**

- [ ] 编写测试，验证“帮我找300元以内适合敏感肌的精华”识别为 `guide`。
- [ ] 编写测试，验证“我要退货，订单号是123”识别为 `after_sale`。
- [ ] 实现规则版 Router。
- [ ] 实现 `FlowContext`。
- [ ] 实现 `BaseFlow` 抽象类。
- [ ] 运行 `pytest tests/test_router.py -v`。
- [ ] 提交：`git commit -m "feat: add intent router and flow contracts"`。

**验收标准：**

- 导购、购物车、下单、售后能分流。
- 下单和售后不走导购检索链路。

---

## 任务 6：GuideFlow 与 ProductQaFlow

**目标：** 实现导购推荐和商品问答两个核心 Flow。

**创建文件：**

- `mallpilot/app/agent/flows/guide_flow.py`
- `mallpilot/app/agent/flows/product_qa_flow.py`
- `mallpilot/app/tools/product_tools.py`
- `tests/test_guide_flow.py`

**GuideFlow 状态：**

```text
START
  -> EXTRACT_CONSTRAINTS
  -> NEED_CLARIFICATION?
  -> RETRIEVE_PRODUCTS
  -> RERANK_PRODUCTS
  -> BUILD_RECOMMENDATION
  -> EMIT_PRODUCT_CARDS
  -> FINAL
```

**ProductQaFlow 状态：**

```text
START
  -> LOCATE_PRODUCT
  -> RETRIEVE_EVIDENCE
  -> GENERATE_ANSWER
  -> EMIT_ANSWER
  -> FINAL
```

**执行步骤：**

- [ ] 编写测试，验证 GuideFlow 至少发出 `thinking`、`product_card`、`final`。
- [ ] 实现 `build_product_card()`，把 `ProductCandidate` 转成前端商品卡片 payload。
- [ ] 实现 `GuideFlow.run()`。
- [ ] 实现 `ProductQaFlow.run()`。
- [ ] 运行 `pytest tests/test_guide_flow.py -v`。
- [ ] 提交：`git commit -m "feat: add guide and product qa flows"`。

**验收标准：**

- GuideFlow 可以输出商品卡片。
- ProductQaFlow 回答必须绑定 evidence。
- 商品卡片包含 `product_id`、`title`、`price`、`image_url`、`reasons`、`actions`。

---

## 任务 7：购物车、订单、售后模拟 Flow

**目标：** 实现购物车工具和订单/售后模拟状态机。

**创建文件：**

- `mallpilot/app/tools/cart_tools.py`
- `mallpilot/app/tools/order_tools.py`
- `mallpilot/app/tools/after_sale_tools.py`
- `mallpilot/app/agent/flows/cart_flow.py`
- `mallpilot/app/agent/flows/order_flow.py`
- `mallpilot/app/agent/flows/after_sale_flow.py`
- `tests/test_commerce_flows.py`

**事件类型：**

- 购物车：`cart_update`
- 下单预览：`order_preview`
- 售后预览：`after_sale_preview`
- 信息不足：`clarification`

**执行步骤：**

- [ ] 编写测试，验证商品不明确时 CartFlow 返回 `clarification`。
- [ ] 编写测试，验证 OrderFlow 先返回 `order_preview`。
- [ ] 实现内存版 `CartStore`。
- [ ] 实现 `preview_order()` 和 `create_mock_order()`。
- [ ] 实现 `preview_after_sale()` 和 `create_mock_return_request()`。
- [ ] 实现三个 Flow。
- [ ] 运行 `pytest tests/test_commerce_flows.py -v`。
- [ ] 提交：`git commit -m "feat: add mock commerce flows"`。

**验收标准：**

- 加购必须能处理商品/SKU 不明确的情况。
- 下单必须先预览，不直接创建订单。
- 售后必须先预览，不直接创建退货申请。

---

## 任务 8：Chat SSE API

**目标：** 暴露用户侧聊天流式接口。

**创建/修改文件：**

- `mallpilot/app/services/chat_service.py`
- `mallpilot/app/api/chat.py`
- `mallpilot/app/main.py`
- `tests/test_chat_api.py`

**接口：**

```http
POST /api/chat/stream
Content-Type: application/json
Accept: text/event-stream
```

**请求示例：**

```json
{
  "chat_id": "chat_xxx",
  "user_id": "anonymous",
  "message": "帮我找 300 元以内适合敏感肌的精华",
  "attachments": []
}
```

**执行步骤：**

- [ ] 编写测试，验证 `/api/chat/stream` 返回 `text/event-stream`。
- [ ] 实现 `ChatService.stream()`。
- [ ] 实现 `api/chat.py`。
- [ ] 在 `main.py` 注册 chat router。
- [ ] 运行 `pytest tests/test_chat_api.py -v`。
- [ ] 提交：`git commit -m "feat: add chat sse api"`。

**验收标准：**

- 接口返回 SSE。
- 至少能返回 `thinking`、`product_card`、`final`。
- 每个事件都包含 `chat_id`、`turn_id`、`seq`。

---

## 任务 9：可观测 API 与 Web 界面

**目标：** 实现 `/admin/observability` 可观测控制台。

**创建/修改文件：**

- `mallpilot/app/api/trace.py`
- `mallpilot/app/api/admin.py`
- `mallpilot/app/web/observability/index.html`
- `mallpilot/app/web/observability/app.js`
- `mallpilot/app/web/observability/style.css`
- `mallpilot/app/main.py`
- `tests/test_observability_api.py`

**页面能力：**

- 会话列表。
- 单轮 Timeline。
- 当前事件详情 JSON。
- LLM 调用面板。
- 检索 Trace 面板。
- 工具调用面板。
- SSE 事件流面板。

**接口：**

- `GET /api/trace/turns/{turn_id}/events`
- `GET /admin/observability`
- `GET /admin/static/app.js`
- `GET /admin/static/style.css`

**执行步骤：**

- [ ] 编写测试，验证 `/admin/observability` 能打开。
- [ ] 编写测试，验证 Trace API 返回列表。
- [ ] 实现 `api/trace.py`。
- [ ] 实现 `api/admin.py`。
- [ ] 实现原生 HTML/CSS/JS 控制台。
- [ ] 在 `main.py` 注册 trace 和 admin router。
- [ ] 运行 `pytest tests/test_observability_api.py -v`。
- [ ] 提交：`git commit -m "feat: add observability console"`。

**验收标准：**

- 可以打开 `/admin/observability`。
- 可以点击 turn 查看 Trace Timeline。
- 可以查看 BM25、文本向量、图片向量、RRF、Cross-Encoder 等检索阶段。
- 可以查看 SSE 事件 payload。

---

## 任务 10：数据库持久化与集成

**目标：** 把商品、SKU、知识块、Trace 事件落到数据库，为后续真实运行做准备。

**创建/修改文件：**

- `mallpilot/app/models/product.py`
- `mallpilot/app/models/trace.py`
- `mallpilot/app/repositories/product_repo.py`
- `mallpilot/app/repositories/trace_repo.py`
- `scripts/ingest_products.py`
- `tests/test_ingestion_integration.py`

**核心表：**

- `products`
- `product_skus`
- `knowledge_chunks`
- `product_images`
- `chat_sessions`
- `chat_turns`
- `trace_events`

**执行步骤：**

- [ ] 编写集成测试，验证数据集能读取 100 个商品。
- [ ] 实现 SQLAlchemy `Product`、`ProductSku`、`KnowledgeChunk`。
- [ ] 实现 SQLAlchemy `TraceEventRow`。
- [ ] 实现 `ProductRepository.save_product()`。
- [ ] 实现 `ProductRepository.save_chunks()`。
- [ ] 实现 `TraceRepository.save()`。
- [ ] 改造 `scripts/ingest_products.py`，支持入库。
- [ ] 运行 `pytest tests/test_ingestion_integration.py -v`。
- [ ] 提交：`git commit -m "feat: add database models and repositories"`。

**验收标准：**

- 商品和 SKU 可以入库。
- 知识块可以入库。
- Trace 事件可以持久化。
- 检索层后续可从数据库读取候选。

---

## 推荐执行顺序

1. 项目骨架与 Schema。
2. 商品数据读取与知识块切分。
3. 混合检索核心。
4. Trace Service 与 SSE EventBus。
5. IntentRouter 与 Flow 合约。
6. GuideFlow 与 ProductQaFlow。
7. 购物车、订单、售后模拟 Flow。
8. Chat SSE API。
9. 可观测 API 与 Web 界面。
10. 数据库持久化与集成。

---

## 自检结果

- 已覆盖设计文档中的 Python FastAPI 主后端。
- 已覆盖“不使用 LangGraph，自研 Router/Flow”。
- 已覆盖 BM25、向量召回、图片向量、RRF、Cross-Encoder。
- 已覆盖 SSE 结构化事件。
- 已覆盖可观测界面。
- 已覆盖购物车、订单、售后模拟流程。
- 已覆盖商品数据读取和 UTF-8 编码要求。

