# 导购 Agent 后端 MVP 实现方案

## 1. 文档目标

本文档用于指导 `MallPilot` 从零实现第一版导购 Agent 后端 MVP。目标不是先做一个完整电商平台，而是先把“能理解购物需求、能检索商品、能解释推荐、能展示过程、能完成加购模拟”的核心链路跑通。

第一版采用以下技术方向：

1. 使用 `Python + FastAPI` 实现后端服务。
2. 使用自研 `IntentRouter + FlowHandler` 做 Agent 编排，不引入 `LangGraph`。
3. 使用 `PostgreSQL + pgvector` 承载商品结构化数据、文本向量、图片向量和 Trace 数据。
4. 使用 `SSE` 向前端推送结构化事件，让不同事件渲染不同组件。
5. 内置 Web 可观测界面，追踪每轮 chat 的 LLM 调用、SSE 事件、检索 Trace、工具调用和错误。

## 2. 当前数据基础

当前数据位于：

```text
data/ecommerce_agent_dataset
```

数据集包含：

| 品类 | 商品数 | 图片数 | SKU 特点 |
| --- | ---: | ---: | --- |
| 美妆护肤 | 25 | 25 | SKU 较少，适合验证功效、肤质、规格推荐 |
| 数码电子 | 25 | 25 | SKU 复杂，适合验证存储、颜色、版本、预算约束 |
| 服饰运动 | 25 | 25 | SKU 最复杂，适合验证尺码、颜色、款式、图片搜同款 |
| 食品生活 | 25 | 25 | 适合验证口味、包装、数量、价格带推荐 |

每个商品 JSON 包含：

1. 商品主数据：`product_id`、`title`、`brand`、`category`、`sub_category`、`base_price`、`image_path`
2. SKU 数据：`sku_id`、`properties`、`price`
3. RAG 知识：`marketing_description`、`official_faq`、`user_reviews`

需要修正已有粗略方案中的一个判断：这些 JSON 文件以 `UTF-8` 读取时可以正常解析，当前更主要的问题不是数据损坏，而是部分终端默认编码导致中文显示乱码。实现时应统一使用 `UTF-8` 读取和写入。

## 3. MVP 边界

第一版 MVP 必须完成：

1. 商品数据入库。
2. 商品知识块切分与文本向量化。
3. 商品图片资源管理，并预留图片向量化能力。
4. 导购推荐流程。
5. 商品问答流程。
6. 商品对比流程。
7. 购物车模拟流程。
8. SSE 结构化事件流。
9. Trace Store 持久化。
10. Web 可观测界面。

第一版 MVP 暂不做：

1. 真实支付。
2. 真实库存锁定。
3. 真实订单履约。
4. 真实退款。
5. 复杂用户画像和长期个性化推荐。
6. 大规模分布式任务调度。

下单和售后退货在第一版中保留状态机、接口契约和模拟工具，真实业务执行放到第二阶段。

## 4. 总体架构

```text
Frontend Chat UI
  -> /api/chat/stream
      -> ChatSessionService
      -> IntentRouter
      -> FlowHandler
          -> GuideFlow
          -> ProductQaFlow
          -> CartFlow
          -> OrderFlow
          -> AfterSaleFlow
      -> Retriever / Reranker / ToolExecutor / LLMClient
      -> EventBus
          -> SSE 展示事件
          -> Trace Store

Observability UI
  -> /admin/observability
  -> Trace API
      -> 会话列表
      -> 单轮 Timeline
      -> LLM Trace
      -> Retrieval Trace
      -> Tool Trace
      -> SSE Event Trace
```

核心原则：

1. 用户前端只接收业务展示事件，不暴露模型内部思维链。
2. 可观测界面接收完整 Trace，用于调试路由、检索、工具和 LLM 调用。
3. Router 只决定走哪条业务 Flow，不在 Router 内执行复杂业务。
4. Flow 是显式状态机，每一步都有输入、输出、失败处理和 Trace。
5. ToolExecutor 是唯一可执行购物车、订单、售后动作的入口。

## 5. 推荐工程结构

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
      logging.py
      event_bus.py
      exceptions.py
    agent/
      router.py
      schemas.py
      state.py
      flows/
        guide_flow.py
        product_qa_flow.py
        cart_flow.py
        order_flow.py
        after_sale_flow.py
      prompts/
        intent_router.md
        constraint_extractor.md
        recommendation.md
        product_qa.md
    retrieval/
      index_builder.py
      text_chunker.py
      embedding_client.py
      bm25_search.py
      vector_search.py
      product_search.py
      image_search.py
      fusion.py
      cross_encoder_reranker.py
    tools/
      registry.py
      product_tools.py
      cart_tools.py
      order_tools.py
      after_sale_tools.py
    models/
      product.py
      sku.py
      knowledge_chunk.py
      cart.py
      order.py
      trace.py
    repositories/
      product_repo.py
      cart_repo.py
      trace_repo.py
    services/
      chat_service.py
      llm_client.py
      trace_service.py
      observability_service.py
    web/
      observability/
        index.html
        app.js
        style.css
  scripts/
    ingest_products.py
    build_text_index.py
    build_image_index.py
  tests/
    test_router.py
    test_guide_flow.py
    test_product_search.py
    test_sse_events.py
```

## 6. 数据模型设计

### 6.1 商品主表 `products`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID / bigint | 内部主键 |
| `product_id` | varchar | 数据集中的商品 ID |
| `title` | text | 商品标题 |
| `brand` | varchar | 品牌 |
| `category` | varchar | 一级品类 |
| `sub_category` | varchar | 二级品类 |
| `base_price` | numeric | 基础价格 |
| `image_path` | text | 本地图片路径 |
| `normalized_doc` | text | 可检索的商品规范化文本 |
| `created_at` | timestamp | 创建时间 |
| `updated_at` | timestamp | 更新时间 |

### 6.2 SKU 表 `product_skus`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID / bigint | 内部主键 |
| `sku_id` | varchar | 数据集中的 SKU ID |
| `product_id` | varchar | 商品 ID |
| `properties` | jsonb | SKU 属性，如颜色、尺码、容量、存储 |
| `price` | numeric | SKU 价格 |
| `stock` | int | 模拟库存，第一版可默认生成 |
| `status` | varchar | `available` / `sold_out` / `offline` |

### 6.3 知识块表 `knowledge_chunks`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID / bigint | 内部主键 |
| `product_id` | varchar | 商品 ID |
| `chunk_type` | varchar | `basic` / `marketing` / `faq` / `review_summary` |
| `title` | text | 知识块标题 |
| `content` | text | 知识块正文 |
| `metadata` | jsonb | FAQ 问题、评分、来源等 |
| `embedding` | vector | 文本向量 |

### 6.4 图片资源表 `product_images`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID / bigint | 内部主键 |
| `product_id` | varchar | 商品 ID |
| `image_path` | text | 本地图片路径 |
| `image_url` | text | 前端访问 URL |
| `caption` | text | 图片说明，可由多模态模型生成 |
| `visual_tags` | jsonb | 颜色、风格、材质、外观标签 |
| `embedding` | vector | 图片向量 |

### 6.5 会话与 Trace 表

`chat_sessions`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `chat_id` | varchar | 会话 ID |
| `user_id` | varchar | 用户 ID，MVP 可使用匿名用户 |
| `created_at` | timestamp | 创建时间 |
| `updated_at` | timestamp | 更新时间 |

`chat_turns`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `turn_id` | varchar | 单轮对话 ID |
| `chat_id` | varchar | 会话 ID |
| `user_message` | text | 用户输入 |
| `intent` | varchar | Router 判断出的意图 |
| `status` | varchar | `running` / `completed` / `failed` |
| `started_at` | timestamp | 开始时间 |
| `finished_at` | timestamp | 结束时间 |

`trace_events`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `trace_id` | varchar | Trace ID |
| `chat_id` | varchar | 会话 ID |
| `turn_id` | varchar | 单轮 ID |
| `event_type` | varchar | Trace 事件类型 |
| `span_name` | varchar | 执行阶段名称 |
| `payload` | jsonb | 事件内容 |
| `started_at` | timestamp | 开始时间 |
| `ended_at` | timestamp | 结束时间 |
| `duration_ms` | int | 耗时 |
| `status` | varchar | `ok` / `error` |
| `error_message` | text | 错误信息 |

## 7. 检索与索引设计

### 7.1 文本知识块生成

每个商品生成以下知识块：

1. `basic`：标题、品牌、品类、价格、SKU 摘要。
2. `marketing`：商品营销描述。
3. `faq`：每条官方 FAQ 独立一个 chunk。
4. `review_summary`：用户评论摘要，按正向评价、负向评价、常见问题聚合。

不要把整份 JSON 直接丢进向量库。这样会导致 SKU、FAQ、评论、营销话术混在一起，检索证据不可控。

### 7.2 混合检索链路

导购推荐使用“硬过滤 + 多路召回 + RRF 融合 + Cross-Encoder 精排”的链路：

```text
约束抽取
  -> 结构化过滤
  -> BM25 关键词召回
  -> 文本向量语义召回
  -> 如果用户发了图片，再执行图片向量召回
  -> RRF 融合多路候选
  -> 业务规则补充分
  -> Cross-Encoder 精排
  -> 推荐解释
```

结构化过滤负责硬约束，必须在召回前先执行：

1. 品类
2. 品牌
3. 价格区间
4. SKU 属性
5. 模拟库存
6. 上架状态

BM25 关键词召回负责字面匹配和强词命中：

1. 商品标题，如“小棕瓶”“iPhone”“AIRism”。
2. 品牌词，如“雅诗兰黛”“Apple”“优衣库”。
3. SKU 词，如“50ml”“M 码”“512GB”“混合口味”。
4. 功效词和参数词，如“保湿”“抗初老”“续航”“快充”。
5. FAQ 中的问法，如“敏感肌能不能用”“会不会缩水”。

文本向量语义召回负责语义相关：

1. 场景需求，如“通勤穿”“熬夜修护”“送礼”
2. 功效需求，如“保湿”“抗初老”“续航好”
3. 风格需求，如“简约”“运动”“高级感”
4. 问题需求，如“敏感肌能不能用”“尺码怎么选”

图片向量召回只在用户上传图片时启用，负责外观、风格、颜色、形态相似：

1. 以图搜同款或相似款。
2. 图片加文本联合筛选，如“类似这双鞋，预算 500 以内”。
3. 外观偏好匹配，如颜色、包装、款式、材质。

RRF 融合用于把 BM25、文本向量、图片向量三路召回结果合并为统一候选集。推荐使用 Reciprocal Rank Fusion：

```text
rrf_score(d) = sum(1 / (k + rank_i(d)))
```

其中：

1. `rank_i(d)` 是商品或知识块在第 `i` 路召回中的排名。
2. `k` 建议从 `60` 开始，降低单一路径极端排名对最终结果的影响。
3. BM25、文本向量、图片向量都只负责召回，不直接决定最终排序。

业务规则补充分负责电商偏好：

1. 是否满足用户明确约束。
2. 价格是否接近预算。
3. 评论中正负反馈是否匹配用户关心点。
4. SKU 是否可选且库存可用。
5. 是否有足够证据支撑推荐理由。

Cross-Encoder 精排负责最终相关性判断。它接收用户 query、候选商品摘要、命中的知识证据，输出更精细的相关性分数。第一版可以只对 RRF 融合后的 Top 20 到 Top 50 候选做 Cross-Encoder，避免成本过高。

最终排序建议：

```text
final_score = cross_encoder_score * 0.7
            + business_score * 0.2
            + rrf_score_normalized * 0.1
```

权重不是固定真理，第一版先写成配置项，并在可观测界面中展示每个商品的分数构成。

### 7.3 多模态检索

第一版可以分两步：

1. MVP 初期：先把图片作为商品卡片展示资源，不强制实现图片 embedding。
2. MVP 完整版：增加图片 embedding，支持以图搜同款、图片加文本筛选、外观相似商品。

图片检索流程：

```text
用户上传图片
  -> 生成图片 embedding
  -> 图片向量召回候选商品
  -> 与 BM25 关键词召回、文本向量召回一起进入 RRF 融合
  -> Cross-Encoder 精排
  -> 返回相似商品卡片
```

### 7.4 检索实现建议

第一版可以把检索实现拆成四个清晰模块：

1. `BM25Search`：负责关键词召回，输入 query 和结构化过滤条件，输出带关键词分数的候选商品或知识块。
2. `VectorSearch`：负责文本向量召回，输入 query embedding 和过滤条件，输出语义相似候选。
3. `ImageSearch`：负责图片向量召回，仅在用户上传图片时启用。
4. `RetrievalFusion`：负责 RRF 融合和候选去重。
5. `CrossEncoderReranker`：负责对融合后的 TopK 候选做精排。

BM25 引擎第一版可以先选择轻量实现，保证快速跑通；后续如果商品量扩大，再替换成 Elasticsearch、OpenSearch、Tantivy 或其他支持 BM25 的检索引擎。无论底层实现如何变化，对上层 Flow 只暴露统一的 `search_products` 工具。

## 8. Agent 编排设计

### 8.1 全局意图路由

`IntentRouter` 是所有用户输入的第一层入口。它只输出结构化路由结果，不直接执行工具。

意图枚举：

| 意图 | 说明 | 目标 Flow |
| --- | --- | --- |
| `guide` | 找商品、推荐、场景化购买建议 | `GuideFlow` |
| `product_qa` | 问某个商品的功效、参数、适用性 | `ProductQaFlow` |
| `compare` | 比较多个商品 | `GuideFlow` 或 `ProductQaFlow` |
| `cart` | 加购、查看购物车、修改数量、删除 | `CartFlow` |
| `order` | 下单、订单预览、订单确认 | `OrderFlow` |
| `after_sale` | 取消、退货、退款、售后政策 | `AfterSaleFlow` |
| `chitchat` | 闲聊或无法识别 | 兜底回复 |

Router 输出示例：

```json
{
  "intent": "guide",
  "confidence": 0.86,
  "reason": "用户表达了预算和使用场景，希望系统推荐商品",
  "entities": {
    "category": "美妆护肤",
    "budget_max": 300,
    "scenario": "敏感肌修护"
  }
}
```

### 8.2 GuideFlow

适用场景：

1. “帮我找 300 元以内适合敏感肌的精华。”
2. “有没有适合通勤的白色 T 恤？”
3. “送朋友的咖啡礼盒推荐一下。”
4. “这张图里类似的鞋有没有？”

状态机：

```text
START
  -> EXTRACT_CONSTRAINTS
  -> NEED_CLARIFICATION?
      -> CLARIFY
      -> WAIT_USER_REPLY
  -> RETRIEVE_PRODUCTS
  -> RERANK_PRODUCTS
  -> BUILD_RECOMMENDATION
  -> EMIT_PRODUCT_CARDS
  -> FINAL
```

缺少关键信息时发送 `clarification` 事件，例如：

1. 服饰缺少尺码或身高体重。
2. 美妆缺少肤质或预算。
3. 数码缺少预算或核心用途。
4. 食品缺少口味偏好或送礼/自用场景。

### 8.3 ProductQaFlow

适用场景：

1. “这款小棕瓶适合敏感肌吗？”
2. “iPhone 这个 256GB 够用吗？”
3. “这件 T 恤会不会缩水？”

状态机：

```text
START
  -> LOCATE_PRODUCT
  -> RETRIEVE_EVIDENCE
  -> GENERATE_ANSWER
  -> EMIT_ANSWER
  -> OPTIONAL_RELATED_PRODUCTS
  -> FINAL
```

回答必须绑定证据来源，如 FAQ、营销描述、评论摘要。不能凭空编造商品参数。

### 8.4 CartFlow

适用场景：

1. “把第二个加入购物车。”
2. “我要白色 M 码。”
3. “购物车里那件 T 恤改成 2 件。”

状态机：

```text
START
  -> RESOLVE_PRODUCT
  -> RESOLVE_SKU
  -> VALIDATE_QUANTITY
  -> CALL_CART_TOOL
  -> EMIT_CART_UPDATE
  -> FINAL
```

如果商品或 SKU 不明确，发送 `clarification` 事件。

### 8.5 OrderFlow

第一版只做模拟，不接真实支付。

状态机：

```text
START
  -> RESOLVE_CART_OR_PRODUCT
  -> VALIDATE_SKU_AND_PRICE
  -> BUILD_ORDER_PREVIEW
  -> EMIT_ORDER_PREVIEW
  -> WAIT_CONFIRMATION
  -> CREATE_MOCK_ORDER
  -> FINAL
```

下单必须二次确认，不能因为用户一句“帮我买”就直接创建订单。

### 8.6 AfterSaleFlow

第一版只做模拟状态机和政策问答。

状态机：

```text
START
  -> RESOLVE_ORDER
  -> CHECK_ORDER_STATUS
  -> CHECK_RETURN_POLICY
  -> COLLECT_REASON
  -> EMIT_AFTER_SALE_PREVIEW
  -> WAIT_CONFIRMATION
  -> CREATE_MOCK_AFTER_SALE_REQUEST
  -> FINAL
```

售后流不能走导购检索链路。它依赖订单状态、签收时间、退货窗口、商品类型和售后原因。

## 9. 工具设计

### 9.1 商品工具

| 工具 | 作用 |
| --- | --- |
| `search_products` | 根据结构化条件和语义 query 搜索商品 |
| `get_product_detail` | 获取商品详情、SKU、FAQ、评论摘要 |
| `get_sku_options` | 获取可选 SKU |
| `compare_products` | 比较多个商品 |
| `find_similar_products` | 找相似商品 |

### 9.2 购物车工具

| 工具 | 作用 |
| --- | --- |
| `get_cart` | 获取购物车 |
| `add_to_cart` | 加入购物车 |
| `update_cart_item` | 修改数量或 SKU |
| `remove_cart_item` | 删除购物车项 |
| `clear_cart` | 清空购物车 |

### 9.3 订单工具

| 工具 | 作用 |
| --- | --- |
| `preview_order` | 生成订单预览 |
| `create_mock_order` | 创建模拟订单 |
| `get_order_detail` | 查询模拟订单 |
| `cancel_mock_order` | 取消模拟订单 |

### 9.4 售后工具

| 工具 | 作用 |
| --- | --- |
| `get_return_policy` | 获取退货政策 |
| `create_mock_return_request` | 创建模拟退货申请 |
| `get_return_status` | 查询退货状态 |

工具调用必须记录 Trace：

```json
{
  "event_type": "tool_call_finished",
  "span_name": "add_to_cart",
  "payload": {
    "tool_name": "add_to_cart",
    "arguments": {
      "product_id": "p_clothes_001",
      "sku_id": "s_p_clothes_001_5",
      "quantity": 1
    },
    "result": {
      "cart_item_id": "ci_xxx",
      "status": "added"
    }
  },
  "duration_ms": 42,
  "status": "ok"
}
```

## 10. SSE 事件协议

### 10.1 事件基础结构

所有 SSE 展示事件使用统一 envelope：

```json
{
  "event_id": "evt_xxx",
  "type": "product_card",
  "chat_id": "chat_xxx",
  "turn_id": "turn_xxx",
  "seq": 8,
  "timestamp": "2026-07-12T10:00:00+08:00",
  "payload": {}
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `event_id` | 事件 ID |
| `type` | 事件类型 |
| `chat_id` | 会话 ID |
| `turn_id` | 单轮 ID |
| `seq` | 当前 turn 内递增序号 |
| `timestamp` | 事件时间 |
| `payload` | 事件载荷 |

### 10.2 展示事件类型

| 事件 | 前端展示 |
| --- | --- |
| `thinking` | 公开进度，如“正在检索商品” |
| `clarification` | 追问用户补充信息 |
| `answer` | 普通文本回答 |
| `product_card` | 商品卡片 |
| `product_compare` | 商品对比表 |
| `cart_update` | 购物车变化 |
| `order_preview` | 订单预览 |
| `after_sale_preview` | 售后申请预览 |
| `error` | 错误提示 |
| `final` | 本轮结束 |

### 10.3 前端渲染映射

用户侧聊天前端不应该把 SSE 响应当成纯文本流处理，而应该根据 `type` 分发到不同组件。

| SSE 类型 | 推荐前端组件 | 展示方式 |
| --- | --- | --- |
| `thinking` | `ThinkingIndicator` | 展示当前处理阶段，可被后续事件替换或折叠 |
| `clarification` | `ClarificationCard` | 展示问题、必填槽位和快捷选项，等待用户继续输入 |
| `answer` | `AssistantMessage` | 展示自然语言回答 |
| `product_card` | `ProductCardList` | 追加商品卡片，支持查看详情、对比、加购 |
| `product_compare` | `ProductCompareTable` | 展示商品横向对比表 |
| `cart_update` | `CartSummary` | 展示购物车当前状态和变化 |
| `order_preview` | `OrderPreviewPanel` | 展示订单预览和确认按钮 |
| `after_sale_preview` | `AfterSalePanel` | 展示售后申请预览和确认按钮 |
| `error` | `ErrorNotice` | 展示可恢复错误 |
| `final` | `TurnDoneMarker` | 标记本轮完成，解除输入框锁定 |

前端事件处理伪代码：

```text
onSseMessage(event):
  data = parse(event.data)
  switch data.type:
    case "thinking": renderThinking(data.payload)
    case "clarification": renderClarification(data.payload)
    case "product_card": appendProductCard(data.payload)
    case "product_compare": renderCompareTable(data.payload)
    case "cart_update": updateCart(data.payload)
    case "final": markTurnCompleted(data.payload)
```

### 10.4 `thinking` 事件

`thinking` 只展示业务进度，不展示模型内部推理链。

```json
{
  "type": "thinking",
  "payload": {
    "message": "正在根据你的预算和肤质筛选商品",
    "stage": "retrieval"
  }
}
```

### 10.5 `clarification` 事件

```json
{
  "type": "clarification",
  "payload": {
    "question": "你更关注预算、肤质还是功效？",
    "required_slots": ["budget", "skin_type"],
    "suggestions": ["300元以内", "敏感肌", "淡纹紧致"],
    "allow_free_text": true
  }
}
```

### 10.6 `product_card` 事件

```json
{
  "type": "product_card",
  "payload": {
    "product_id": "p_beauty_001",
    "title": "雅诗兰黛特润修护肌活精华露淡纹紧致保湿夜间修护抗初老精华30ml",
    "brand": "雅诗兰黛",
    "category": "美妆护肤",
    "price": 720,
    "image_url": "/assets/products/1_美妆护肤/images/p_beauty_001_live.jpg",
    "reasons": ["夜间修护", "保湿", "适合抗初老需求"],
    "evidence": [
      {
        "source": "marketing_description",
        "summary": "商品描述中强调夜间肌底修护、保湿和抗初老。"
      }
    ],
    "actions": [
      {
        "type": "view_detail",
        "label": "查看详情"
      },
      {
        "type": "add_to_cart",
        "label": "加入购物车"
      }
    ]
  }
}
```

### 10.7 `product_compare` 事件

```json
{
  "type": "product_compare",
  "payload": {
    "columns": ["商品", "价格", "适合人群", "优点", "注意点"],
    "rows": [
      {
        "product_id": "p_beauty_001",
        "values": ["雅诗兰黛小棕瓶", "720", "抗初老", "修护和保湿强", "敏感肌需先测试"]
      }
    ]
  }
}
```

### 10.8 `final` 事件

```json
{
  "type": "final",
  "payload": {
    "status": "completed",
    "summary": "已为你推荐 3 款商品，并给出对比。"
  }
}
```

## 11. Trace 与可观测界面

### 11.1 Trace 事件类型

| Trace 事件 | 说明 |
| --- | --- |
| `chat_started` | 会话轮次开始 |
| `router_decision` | Router 意图判断 |
| `constraint_extracted` | 约束抽取结果 |
| `retrieval_started` | 检索开始 |
| `bm25_result` | BM25 关键词召回结果 |
| `text_vector_result` | 文本向量语义召回结果 |
| `image_vector_result` | 图片向量召回结果，仅图片输入时产生 |
| `rrf_fusion_result` | RRF 融合结果 |
| `cross_encoder_rerank_result` | Cross-Encoder 精排结果 |
| `llm_call_started` | LLM 调用开始 |
| `llm_call_finished` | LLM 调用结束 |
| `tool_call_started` | 工具调用开始 |
| `tool_call_finished` | 工具调用结束 |
| `sse_event_sent` | SSE 事件已发送 |
| `chat_finished` | 会话轮次结束 |
| `error` | 错误 |

### 11.2 可观测界面页面

第一版 Web 可观测控制台路径：

```text
/admin/observability
```

页面结构：

1. 左侧：会话列表，支持按时间、状态、意图筛选。
2. 中间：单轮 chat 时间线。
3. 右侧：当前事件详情 JSON。
4. 底部或 Tab：LLM 调用、检索 Trace、工具调用、SSE 事件流。

### 11.3 可观测界面技术方案

第一版建议直接由 FastAPI 提供后台页面和静态资源，降低前后端联调成本：

```text
GET /admin/observability
  -> 返回 HTML 页面

GET /admin/static/app.js
  -> 返回控制台前端脚本

GET /admin/static/style.css
  -> 返回控制台样式
```

控制台前端可以先使用原生 HTML、CSS、JavaScript 实现，不需要一开始引入复杂前端工程。等后续功能变多，再迁移到 React、Vue 或独立管理后台。

控制台页面必须具备三个交互能力：

1. 点击会话列表后加载该会话的 turn。
2. 点击某个 turn 后加载完整 Trace Timeline。
3. 点击 Timeline 中的任意事件后，在详情面板展示 payload JSON。

### 11.4 会话列表

展示字段：

1. `chat_id`
2. `last_user_message`
3. `intent`
4. `status`
5. `turn_count`
6. `duration_ms`
7. `created_at`

### 11.5 单轮 Timeline

Timeline 示例：

```text
00ms    chat_started
18ms    router_decision: guide
120ms   constraint_extracted
260ms   retrieval_started
330ms   bm25_result: 12 candidates
390ms   text_vector_result: 20 candidates
450ms   rrf_fusion_result: 24 candidates
620ms   cross_encoder_rerank_result: top 5
900ms   llm_call_finished: recommendation
940ms   sse_event_sent: product_card
980ms   sse_event_sent: final
```

### 11.6 LLM 调用详情

展示：

1. 模型名称。
2. 调用阶段，如 `intent_router`、`constraint_extractor`、`recommendation_writer`。
3. prompt 摘要。
4. request JSON。
5. response JSON。
6. token 用量。
7. 耗时。
8. 错误信息。

### 11.7 检索 Trace

展示：

1. 用户 query。
2. 抽取出的结构化条件。
3. SQL 过滤条件。
4. BM25 关键词召回 TopK。
5. 文本向量召回 TopK。
6. 图片向量召回 TopK，仅图片输入时展示。
7. RRF 融合后的候选列表。
8. Cross-Encoder 精排前后排序。
9. 每个候选商品的分数构成。
10. 最终被发送到前端的商品卡片。

检索 Trace 示例：

```json
{
  "query": "300元以内适合敏感肌的修护精华",
  "filters": {
    "category": "美妆护肤",
    "budget_max": 300,
    "skin_type": "敏感肌"
  },
  "bm25_candidates": [
    {
      "product_id": "p_beauty_014",
      "rank": 1,
      "score": 12.4,
      "matched_terms": ["敏感肌", "修护", "精华"]
    }
  ],
  "text_vector_candidates": [
    {
      "product_id": "p_beauty_014",
      "rank": 3,
      "score": 0.82,
      "matched_chunks": ["faq", "marketing"]
    }
  ],
  "rrf_fused": [
    {
      "product_id": "p_beauty_014",
      "rank": 1,
      "rrf_score": 0.0318,
      "sources": ["bm25", "text_vector"]
    }
  ],
  "cross_encoder_reranked": [
    {
      "product_id": "p_beauty_014",
      "rank": 1,
      "cross_encoder_score": 0.91,
      "business_score": 0.75,
      "final_score": 0.84,
      "reason": "满足预算，FAQ 提到敏感肌注意事项"
    }
  ]
}
```

### 11.8 SSE 事件流

展示：

1. 发送时间。
2. `seq`。
3. 事件类型。
4. payload。
5. 是否发送成功。

这样可以排查“后端已经检索到商品，但前端没有展示卡片”这类问题。

## 12. API 设计

### 12.1 Chat SSE 接口

```http
POST /api/chat/stream
Content-Type: application/json
Accept: text/event-stream
```

请求：

```json
{
  "chat_id": "chat_xxx",
  "user_id": "anonymous",
  "message": "帮我找 300 元以内适合敏感肌的精华",
  "attachments": []
}
```

响应为 SSE：

```text
event: message
data: {"type":"thinking","payload":{"message":"正在理解你的需求"}}

event: message
data: {"type":"product_card","payload":{"product_id":"p_beauty_014"}}

event: message
data: {"type":"final","payload":{"status":"completed"}}
```

### 12.2 商品接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/products` | 商品列表 |
| `GET /api/products/{product_id}` | 商品详情 |
| `GET /api/products/{product_id}/skus` | SKU 列表 |

### 12.3 购物车接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/cart` | 查看购物车 |
| `POST /api/cart/items` | 加购 |
| `PATCH /api/cart/items/{item_id}` | 修改数量 |
| `DELETE /api/cart/items/{item_id}` | 删除 |

### 12.4 Trace 接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/trace/chats` | 查询会话列表 |
| `GET /api/trace/chats/{chat_id}/turns` | 查询会话轮次 |
| `GET /api/trace/turns/{turn_id}` | 查询单轮 Trace |
| `GET /api/trace/turns/{turn_id}/events` | 查询 Trace 事件 |
| `GET /api/trace/turns/{turn_id}/sse` | 查询 SSE 事件 |

## 13. 错误处理

### 13.1 用户输入不足

返回 `clarification`，不直接失败。

典型场景：

1. “帮我买个手机”缺预算和用途。
2. “加入购物车”缺商品或 SKU。
3. “我要退货”缺订单号。

### 13.2 检索无结果

返回 `answer` + 可放宽条件建议。

示例：

```json
{
  "type": "answer",
  "payload": {
    "text": "没有找到完全满足条件的商品。你可以放宽预算到 500 元，或取消品牌限制。"
  }
}
```

### 13.3 工具执行失败

返回 `error`，并在 Trace 中记录完整异常。

### 13.4 LLM 输出不可解析

Router 和约束抽取都必须要求模型输出 JSON。如果解析失败：

1. 记录 `llm_parse_error`。
2. 重试一次。
3. 仍失败则走兜底意图或 clarification。

## 14. 安全与风控

1. 模型不能直接修改购物车、订单、售后状态，必须经过 ToolExecutor。
2. 下单、取消、退货、退款必须二次确认。
3. 价格、库存、SKU 状态必须以工具返回为准，不能使用模型生成值。
4. SSE 的 `thinking` 事件只能展示业务进度，不输出隐藏推理链。
5. Trace 后台第一版可以不做复杂权限，但必须与用户侧页面分离。
6. 涉及地址、支付、退款等敏感字段时，Trace 中需要做脱敏。

## 15. MVP 验收标准

### 15.1 导购推荐

输入：

```text
帮我找 300 元以内适合敏感肌的精华
```

验收：

1. Router 识别为 `guide`。
2. 抽取出预算、品类、肤质。
3. 检索时先过滤价格和品类。
4. 返回商品卡片。
5. 推荐理由引用商品描述、FAQ 或评论摘要。
6. Trace 中能看到 BM25、文本向量、RRF 融合和 Cross-Encoder 精排过程。

### 15.2 商品问答

输入：

```text
这款小棕瓶适合敏感肌吗？
```

验收：

1. Router 识别为 `product_qa`。
2. 能定位商品。
3. 回答引用相关 FAQ 或商品描述。
4. 不编造商品不存在的信息。

### 15.3 购物车

输入：

```text
把第二个商品加入购物车，选 50ml
```

验收：

1. 能解析上下文中的第二个商品。
2. 能匹配 SKU。
3. 能调用 `add_to_cart`。
4. 前端收到 `cart_update`。
5. Trace 中能看到工具参数和结果。

### 15.4 可观测界面

验收：

1. 能看到会话列表。
2. 能打开某个 turn 的完整时间线。
3. 能查看 Router 输出。
4. 能查看 LLM 调用记录。
5. 能查看检索候选和重排结果。
6. 能查看 SSE 事件流。
7. 能查看工具调用参数和返回值。

## 16. 分阶段实施路线

### 阶段一：数据与检索

交付：

1. 数据库 schema。
2. 商品 JSON 入库脚本。
3. 知识块切分脚本。
4. 文本 embedding 入库。
5. BM25 关键词索引。
6. 商品搜索 API。
7. RRF 融合模块。
8. Cross-Encoder 精排模块。
9. 检索 Trace 记录。

### 阶段二：Agent 编排与 SSE

交付：

1. `IntentRouter`。
2. `GuideFlow`。
3. `ProductQaFlow`。
4. `CartFlow`。
5. SSE EventBus。
6. 展示事件协议。

### 阶段三：可观测界面

交付：

1. Trace Store。
2. Trace 查询 API。
3. `/admin/observability` 页面。
4. 单轮 Timeline。
5. LLM、检索、工具、SSE 四类详情面板。

### 阶段四：订单与售后模拟

交付：

1. `OrderFlow` 状态机。
2. 订单预览事件。
3. 模拟订单工具。
4. `AfterSaleFlow` 状态机。
5. 模拟退货申请工具。

### 阶段五：多模态增强

交付：

1. 图片 embedding。
2. 以图搜商品。
3. 图片加文本联合检索。
4. 图片检索 Trace。

## 17. 推荐实现顺序

建议按下面顺序实现，避免一开始被界面或 Agent 复杂度拖住：

1. 搭 FastAPI 项目骨架。
2. 建 PostgreSQL schema。
3. 商品数据入库。
4. 文本知识块切分和 embedding。
5. BM25 关键词召回。
6. 文本向量召回。
7. RRF 融合。
8. Cross-Encoder 精排。
9. 商品搜索 API。
10. Trace Store 基础表。
11. SSE EventBus。
12. `IntentRouter`。
13. `GuideFlow`。
14. `ProductQaFlow`。
15. `CartFlow`。
16. 可观测界面第一版。
17. 订单和售后模拟。
18. 图片检索。

## 18. 关键设计结论

1. MallPilot 第一版应使用 Python 主服务，而不是 Java 主服务。
2. 第一版不使用 LangGraph，使用自研轻量 Router 和显式 Flow 状态机。
3. 意图识别是全局 Router，不是导购流程内部步骤。
4. 导购、问答、购物车、下单、售后必须拆成不同 Flow。
5. 下单和售后是强状态任务，不能走导购检索链路。
6. SSE 事件必须结构化，前端根据事件类型渲染不同组件。
7. 可观测界面是 MVP 核心交付，必须追踪 LLM、SSE、检索、rerank 和工具调用。
8. 检索必须采用“结构化过滤 -> BM25 关键词召回 + 向量语义召回 -> RRF 融合 -> Cross-Encoder 精排”，用户发图片时再加入图片向量召回，不能只做单一路径 RAG。
9. 商品推荐必须绑定证据，避免 Agent 编造推荐理由。
10. 第一版先做可演示、可调试、可扩展的导购闭环，再逐步接入真实交易系统。
