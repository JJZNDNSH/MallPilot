# Sprint 1 数据与持久化真实化设计

## 背景

MallPilot 已完成第一阶段 MVP：FastAPI 后端、SSE 聊天接口、意图路由、导购/问答/交易 mock Flow、混合检索雏形、可观测页面、SQLAlchemy 模型与仓储。当前不足是数据仍主要停留在内存 demo 和测试路径中，缺少真实数据库会话、迁移、命令行入库和后续 pgvector 检索所需的字段。

Sprint 1 的目标是把“可运行 demo”推进到“有真实数据底座”的工程状态，为后续数据库检索、真实 embedding、Trace 落库和前端联调提供稳定基础。

## 目标

1. 提供统一数据库连接模块，应用和脚本都通过同一套 `engine / SessionLocal / get_db` 访问数据库。
2. 引入 Alembic 迁移目录，首个 migration 创建商品、SKU、知识块和 Trace 表。
3. 为知识块增加文本向量字段，为商品增加图片向量字段，先用 JSON 存储向量，后续切到 pgvector 时迁移成本可控。
4. 提供可复用的商品入库 CLI，从 `/data/ecommerce_agent_dataset` 读取 JSON 并写入数据库。
5. 提供数据库版 Trace 服务，后续聊天链路可以把每轮 LLM、SSE、检索 Trace 持久化。
6. 保持现有 API 和 Flow 行为不破坏，第一阶段所有测试继续通过。

## 非目标

1. 本 Sprint 不接真实 LLM。
2. 本 Sprint 不实现真实 embedding 生成。
3. 本 Sprint 不把混合检索切到数据库查询。
4. 本 Sprint 不做正式聊天前端页面。
5. 本 Sprint 不要求本地必须启动 PostgreSQL；自动化测试使用 SQLite 内存库验证仓储和迁移核心逻辑。

## 推荐方案

采用“数据库底座先行”的方案：

- FastAPI 通过 `mallpilot.app.db.session` 暴露数据库依赖。
- Alembic 使用现有 SQLAlchemy `Base.metadata` 作为模型来源。
- CLI 脚本复用已有 `load_product_files()` 和 `persist_products()`，新增 `run_ingestion()` 负责编排数据库会话和事务。
- 向量字段先以 JSON 列表达，命名为 `text_embedding`、`image_embedding`，值为 `list[float] | None`。
- Trace 数据库服务封装 `TraceRepository`，提供与内存 `TraceService` 接近的 `record()` 和 `list_events()` 接口。

选择 JSON 而不是立刻引入 pgvector 类型，是为了让测试和开发不依赖本机 PostgreSQL 扩展，同时保留字段边界。后续切换 pgvector 时只需要调整模型列类型、migration 和检索查询实现。

## 组件设计

### 数据库连接

新增 `mallpilot/app/db/session.py`：

- `create_engine_from_settings(database_url: str | None = None) -> Engine`
- `create_session_factory(engine: Engine) -> sessionmaker[Session]`
- `get_db() -> Generator[Session, None, None]`

该模块只负责连接和会话生命周期，不包含业务写入逻辑。

### Alembic 迁移

新增：

- `alembic.ini`
- `migrations/env.py`
- `migrations/versions/202607120001_create_core_tables.py`

首个 migration 创建：

- `products`
- `product_skus`
- `knowledge_chunks`
- `trace_events`

迁移脚本必须与当前模型字段保持一致，并包含向量 JSON 字段。

### 模型扩展

修改：

- `mallpilot/app/models/product.py`

新增字段：

- `Product.image_embedding`
- `KnowledgeChunk.text_embedding`

字段类型先使用 JSON，可为空。

### 入库命令

修改：

- `scripts/ingest_products.py`

新增：

- `run_ingestion(database_url: str | None = None, dataset_dir: str | None = None) -> int`

行为：

1. 从配置读取默认数据库连接和数据目录。
2. 读取商品 JSON。
3. 创建数据库会话。
4. 调用 `persist_products()`。
5. 成功提交事务并返回导入商品数量。
6. 失败时回滚并抛出异常。

### Trace 数据库服务

新增：

- `mallpilot/app/services/db_trace_service.py`

接口：

- `record(event: TraceEvent) -> None`
- `list_events(turn_id: str) -> list[TraceEvent]`

它复用 `TraceRepository`，把数据库行还原成现有 Pydantic `TraceEvent`，不改变 API 层现有响应结构。

## 数据流

商品入库：

```text
/data JSON -> load_product_files -> build_knowledge_chunks -> ProductRepository -> database
```

Trace 落库：

```text
TraceEvent -> DbTraceService.record -> TraceRepository.save -> trace_events
```

后续检索预留：

```text
knowledge_chunks.text_embedding / products.image_embedding -> database retrieval -> RRF -> rerank
```

## 错误处理

1. 入库过程中任何异常都会回滚当前事务。
2. `get_db()` 在请求结束后关闭 session。
3. Trace 查询找不到轮次时返回空列表。
4. 配置缺失时使用 `Settings` 默认值，不在本 Sprint 引入复杂配置校验。

## 测试策略

1. 新增数据库 session 测试，验证 `get_db()` 能提供可用 session 并正确关闭。
2. 新增入库 CLI 测试，使用 SQLite 内存库验证 `run_ingestion()` 返回导入数量并写入商品。
3. 新增 migration 结构测试，验证首个 migration 包含核心表名和向量字段名。
4. 新增 Trace 数据库服务测试，验证事件可写入并按 `turn_id` 查询。
5. 运行全量 `pytest -v`，保证第一阶段 20 个测试继续通过。

## 验收标准

1. 所有新增测试先失败、实现后通过。
2. 全量测试通过。
3. 本 Sprint 每个独立任务都有对应提交。
4. `.idea/` 不进入提交。
5. 不改动现有 Flow 对外行为。

## 后续衔接

Sprint 1 完成后，下一阶段可以进入数据库检索真实化：

1. 为知识块生成真实文本 embedding。
2. 为商品图片生成图片 embedding。
3. 将 BM25 和向量召回从内存列表切到数据库候选。
4. 把可观测 Trace 从内存 Store 切到数据库 Store。
