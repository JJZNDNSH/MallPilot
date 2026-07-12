# Sprint 1 真实导购闭环设计

## 背景

MallPilot 第一阶段已经完成后端 MVP：FastAPI、SSE 聊天接口、意图路由、导购/问答/交易 Flow、混合检索雏形、可观测页面、SQLAlchemy 模型与仓储。当前仍是 demo 形态：商品检索主要在内存中完成，LLM、embedding、rerank 都是轻量占位，前端也只有可观测控制台。

Sprint 1 的新目标是把系统推进到“真实导购闭环”：商品数据切成知识块后写入 PostgreSQL + pgvector，通过百炼平台完成 LLM、文本 embedding 和 rerank，前端提供正式聊天界面，并继续保留可观测 Trace。

## 用户确认的范围

1. 本阶段直接把商品 chunk 写入 pgvector，不再用 JSON 字段临时存向量。
2. 本阶段接入真实 LLM、真实 embedding 和真实 rerank。
3. 大模型、embedding 模型、重排模型都使用百炼平台。
4. API key 存放在本地 `.env`，`.env` 必须被 `.gitignore` 忽略。
5. 本阶段要做正式前端界面，而不只做后端 API。

## 目标

1. 提供统一数据库连接模块，应用、脚本和测试都通过同一套 `engine / SessionLocal / get_db` 访问数据库。
2. 引入 Alembic 迁移，创建商品、SKU、知识块、Trace 表，并启用 pgvector 扩展。
3. 将商品 JSON 切成知识块，为每个 chunk 调用百炼 embedding，并写入 `knowledge_chunks.embedding vector`。
4. 为图片输入预留图片向量检索接口；如果百炼侧图片 embedding 未在当前 SDK/HTTP 接口中启用，先保留结构和事件 Trace。
5. 接入百炼 LLM，用于意图增强、澄清问题、导购总结、商品问答和售后话术。
6. 接入百炼 rerank，把混合召回结果交给 rerank 模型精排。
7. 将检索从内存 demo 逐步切到数据库：结构化约束 + BM25/关键词候选 + pgvector 语义候选 + RRF + 百炼 rerank。
8. 提供正式聊天前端，支持 SSE 事件分流渲染：`thinking`、`product_card`、`clarification`、`answer`、`order_preview`、`after_sale_preview`、`final`。
9. 让每轮 chat 的 LLM 调用、SSE 事件、检索 Trace 能在可观测界面中查看。
10. 保持第一阶段已有测试继续通过。

## 非目标

1. 本阶段不接真实支付、真实订单和真实售后系统，订单/售后仍使用 mock 工具。
2. 本阶段不做用户登录、权限和多租户。
3. 本阶段不做大规模生产级索引调优，只实现可运行、可观测、可迭代的真实链路。
4. 本阶段不把 API key 写入代码、测试或提交历史。

## 方案选择

### 方案 A：一次性真实闭环（推荐）

一次性完成数据库、pgvector、百炼模型、检索切换和正式前端，但按任务拆分提交。优点是能尽快形成可演示产品闭环；缺点是 Sprint 变大，需要严格 TDD 和阶段性验收。

### 方案 B：后端真实化优先，前端后置

先完成 pgvector 和百炼模型，前端仍使用接口测试。优点是后端风险更集中；缺点是用户看不到完整体验，SSE 事件设计不容易被真实界面验证。

### 方案 C：前端优先，模型继续 mock

先做聊天界面和事件渲染，再替换真实模型。优点是界面反馈快；缺点是检索和答案质量仍不可信。

本 Sprint 采用方案 A，但执行上拆成小任务：安全配置、数据库迁移、百炼客户端、embedding 入库、数据库检索、rerank、LLM Flow、前端、Trace 串联。每个任务必须有测试和提交。

## 安全与配置

`.env` 存放本地密钥，禁止提交。配置字段：

```text
BAILIAN_API_KEY
DASHSCOPE_API_KEY
BAILIAN_LLM_MODEL
BAILIAN_EMBEDDING_MODEL
BAILIAN_RERANK_MODEL
DATABASE_URL
```

应用通过 `Settings` 读取配置。代码、测试、文档示例只出现变量名，不出现真实 key。

## 数据库设计

数据库使用 PostgreSQL + pgvector。

核心表：

- `products`：商品主表，保存商品基础信息、主图、原始 JSON。
- `product_skus`：SKU 表，保存规格、价格和商品关联。
- `knowledge_chunks`：知识块表，保存 chunk 类型、标题、正文、元数据和 `embedding vector`。
- `trace_events`：Trace 表，保存每轮 chat 的 LLM、检索、SSE、工具调用事件。

`knowledge_chunks.embedding` 使用 pgvector 类型。embedding 维度从百炼 embedding 模型配置中固定，迁移脚本和向量校验保持一致。

## 百炼集成

新增模型客户端层，隔离外部平台细节：

- `BailianClient.chat(messages, trace_context) -> LlmResult`
- `BailianClient.embed_texts(texts, trace_context) -> list[list[float]]`
- `BailianClient.rerank(query, documents, trace_context) -> list[RerankScore]`

客户端职责：

1. 读取 `.env` 配置。
2. 发送 HTTP 请求到百炼兼容接口。
3. 记录模型名、耗时、token 或返回摘要到 Trace。
4. 屏蔽 key，不写入日志和 Trace。
5. 在测试中通过 fake transport 或 monkeypatch 验证请求结构，不调用真实外网。

## 入库流程

商品入库流程：

```text
/data 商品 JSON
-> load_product_files()
-> build_knowledge_chunks()
-> BailianClient.embed_texts()
-> ProductRepository.save_product()
-> ProductRepository.save_chunks_with_embeddings()
-> PostgreSQL + pgvector
```

入库 CLI 提供：

```text
python -m scripts.ingest_products
```

默认读取 `Settings.dataset_dir` 和 `Settings.database_url`。失败时事务回滚，并输出失败原因。

## 检索流程

导购意图走数据库检索：

```text
用户消息
-> Router 识别 guide/product_qa
-> 约束抽取
-> 结构化过滤候选
-> BM25/关键词候选
-> pgvector 语义候选
-> 图片向量候选（有图片时）
-> RRF 融合
-> 百炼 rerank
-> ProductCandidate
-> GuideFlow / ProductQaFlow
```

如果缺少关键约束，例如预算、品类、使用场景，Flow 发 `clarification` SSE 事件，而不是强行推荐。

## 前端设计

新增正式聊天界面，第一屏就是可用聊天工作台，不做营销落地页。

页面区域：

1. 左侧：会话列表和新建会话。
2. 中间：聊天消息流，按 SSE 事件渲染。
3. 右侧：当前轮 Trace 摘要、检索阶段、LLM 调用摘要。

事件渲染：

- `thinking`：显示模型正在分析的轻量状态。
- `product_card`：展示商品图、标题、价格、推荐理由和证据。
- `clarification`：展示需要用户补充的信息。
- `answer`：展示商品问答答案。
- `order_preview`：展示 mock 订单预览。
- `after_sale_preview`：展示 mock 售后预览。
- `final`：结束当前轮输出。

前端可以先使用原生 HTML/CSS/JS 扩展现有 FastAPI 静态页，也可以在后续 Sprint 切到 React/Vue。当前 Sprint 以少依赖、可运行为优先。

## 可观测设计

每轮 chat 至少记录：

1. `router.intent`：意图、置信度、实体。
2. `retrieval.constraints`：约束抽取结果。
3. `retrieval.bm25`：关键词候选。
4. `retrieval.vector`：pgvector 候选。
5. `retrieval.rrf`：融合结果。
6. `rerank.bailian`：重排请求摘要和结果排序。
7. `llm.bailian`：LLM 调用摘要、耗时、模型名。
8. `sse.emit`：前端事件类型和序号。

Trace 不记录 API key，不记录完整敏感请求头。

## 测试策略

1. 配置测试：验证 `.env` 字段能被 `Settings` 读取，且 `.env` 在 `.gitignore` 中。
2. Alembic 测试：验证 migration 包含 pgvector 扩展、核心表和 `embedding` 字段。
3. 百炼客户端测试：使用 fake HTTP 响应验证 chat、embedding、rerank 的请求解析与返回映射。
4. 入库测试：使用 fake embedding 生成固定维度向量，验证 chunk 会携带 embedding 写入仓储。
5. 检索测试：使用可控候选验证数据库检索门面会产出 BM25、vector、RRF、rerank Trace。
6. Flow 测试：验证导购和问答会调用真实模型接口抽象，而不是旧 mock 文案。
7. 前端 API 测试：验证聊天页面可打开，SSE 返回可被事件类型分流。
8. 全量测试：运行 `pytest -v`，确保第一阶段能力不回退。

## 验收标准

1. `.env` 已在本地创建，`.gitignore` 忽略 `.env`。
2. 数据库 migration 支持 PostgreSQL + pgvector。
3. 商品 chunk 入库时写入真实 embedding。
4. 导购检索链路使用数据库候选和百炼 rerank。
5. 导购回复和问答回复通过百炼 LLM 生成。
6. 正式聊天前端能通过浏览器访问，并正确渲染至少 `thinking`、`product_card`、`clarification`、`final`。
7. 可观测页面能查看 LLM、检索、SSE Trace。
8. 所有新增代码有测试，且全量测试通过。

## 风险与处理

1. 百炼接口细节可能和预期不一致：客户端层集中封装，先用测试锁定内部接口，真实调用问题单点修复。
2. pgvector 本地环境可能未安装：migration 明确启用扩展，测试用脚本静态校验，真实运行前给出数据库准备命令。
3. Sprint 范围较大：按任务小步提交，每完成一个子闭环就跑对应测试和全量关键测试。
4. API key 泄露风险：只放 `.env`，不提交，不写入 Trace，不在终端输出。

## 后续衔接

Sprint 1 完成后，下一阶段可以继续做：

1. 图片 embedding 的真实模型接入和图片向量检索。
2. 订单、售后接真实电商系统。
3. 前端工程化为 React/Vue。
4. 检索评测集、召回率和重排质量评估。
