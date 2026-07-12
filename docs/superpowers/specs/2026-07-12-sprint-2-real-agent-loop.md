# Sprint 2 真实 Agent 导购链路规格说明

## 背景

Sprint 1 已完成数据入库、PostgreSQL + pgvector、基础前端、SSE 事件流和 Trace 骨架。Sprint 2 的目标是把 MallPilot 从“能跑的原型”推进到“真实模型和真实商品库参与导购”的状态，让用户在 `/chat` 页面输入自然语言需求时，可以触发真实检索、真实重排、真实 LLM 总结，并在观测侧看到每轮 chat 的执行链路。

## Sprint 2 总体目标

1. 聊天接口默认接入真实数据库商品检索，不再依赖内置 `p_demo`。
2. 检索链路使用真实 query embedding、RRF 融合和百炼 rerank。
3. 导购结果通过 SSE 返回 `thinking`、`product_card`、`answer`、`final` 等事件。
4. 商品卡展示真实商品字段，包括品牌、品类、子品类、价格、SKU 摘要和短推荐理由。
5. 真实 LLM Chat 在 `USE_MOCK_LLM=false` 时生成导购总结和商品问答答案。
6. 每轮 chat 的 Router、Retrieval、Rerank、LLM、SSE 事件写入数据库 Trace。
7. 非购物闲聊不进入商品检索流，例如“你好”不推荐商品。

## 已完成内容

### 真实运行时接线

`ChatService.from_runtime()` 负责组装真实运行时依赖：

- `DbTraceService`
- `DatabaseProductSearch`
- `LlmService`
- 数据库 `session_factory`

运行时聊天流程：

```text
/api/chat/stream
-> ChatService.from_runtime()
-> IntentRouter.route()
-> FlowContext
-> DatabaseProductSearch
-> GuideFlow / ProductQaFlow / CartFlow / OrderFlow / AfterSaleFlow / ChitchatFlow
-> EventBus.emit()
-> SSE 返回前端
-> DbTraceService 持久化 Trace
```

测试和局部单元仍可通过 `ChatService(search=FakeSearch(), llm_service=FakeLlmService())` 注入 fake，不强制调用外部网络。

### 数据库检索

`DatabaseProductSearch` 已成为导购检索的主要入口。

当前检索步骤：

```text
用户 query
-> Router 抽取结构化 filters
-> 数据库侧过滤 category / sub_category / brand / budget_max
-> BM25 关键词召回
-> 百炼 query embedding
-> chunk embedding 余弦相似召回
-> RRF 融合
-> 百炼 rerank 精排
-> ProductCandidate
```

当前已支持过滤字段：

- `category`
- `sub_category`
- `brand`
- `budget_max`

当前保留但尚未完全实现的能力：

- 图片 embedding 检索接口形态保留
- PostgreSQL 原生 pgvector SQL 排序可后续替换当前 Python 余弦计算

### 百炼模型接入

已接入三类百炼调用：

- Chat LLM：`qwen-plus`
- Text embedding：`text-embedding-v4`
- Rerank：`qwen3-rerank`

配置字段：

```text
BAILIAN_API_KEY
DASHSCOPE_API_KEY
BAILIAN_BASE_URL
BAILIAN_LLM_MODEL
BAILIAN_EMBEDDING_MODEL
BAILIAN_RERANK_BASE_URL
BAILIAN_RERANK_MODEL
BAILIAN_RERANK_INSTRUCT
USE_MOCK_LLM
```

注意：`.env` 不进入 git，文档和测试只记录变量名，不记录真实 key。

Rerank 调用方式已对齐百炼业务空间 endpoint：

```text
POST {BAILIAN_RERANK_BASE_URL}/reranks
```

请求体包含：

```json
{
  "model": "qwen3-rerank",
  "query": "...",
  "documents": ["..."],
  "top_n": 5,
  "instruct": "Given a web search query, retrieve relevant passages that answer the query."
}
```

真实验证结果：Trace 中 `rerank.bailian` 状态为 `ok`。

### LLM 导购总结

当 `.env` 中配置：

```text
USE_MOCK_LLM=false
```

导购 Flow 会在商品卡之后调用 `LlmService.generate_guide_summary()`，通过百炼 Chat LLM 生成简短推荐总结。

真实验证输入：

```text
预算7000以内，推荐一部拍照好续航强的手机
```

验证结果：

- 返回 3 个 `product_card`
- 返回 1 个 `answer`
- Trace 包含 `llm.bailian`
- `llm.bailian` 状态为 `ok`

### 商品卡优化

商品卡 payload 由 `build_product_card()` 生成。

当前字段：

```text
product_id
title
brand
category
sub_category
price
image_url
reason
reasons
sku_summary
evidence
actions
```

优化点：

1. `reason` 使用检索层压缩后的短摘要，避免前端显示大段 raw chunk。
2. `sku_summary` 从商品原始 JSON 中抽取前 3 个 SKU 的规格和价格。
3. 前端展示品牌、品类、子品类、价格、SKU 摘要。

前端商品卡展示逻辑位于：

```text
mallpilot/app/web/chat/app.js
mallpilot/app/web/chat/style.css
```

### SSE 事件渲染

聊天前端已按事件类型分流渲染：

- `thinking`：展示处理状态
- `product_card`：展示商品卡
- `clarification`：展示补充信息提示
- `answer`：展示自然语言回答
- `order_preview`：展示订单预览
- `after_sale_preview`：展示售后预览
- `final`：标记本轮完成并拉取 Trace

右侧 Trace 点击后展示 payload 详情，不再把原始 JSON 混入聊天消息区。

### Trace 持久化

Trace API 已改为读取数据库版 TraceService。

主要事件类型：

- `router.intent`
- `retrieval.bm25`
- `retrieval.vector`
- `retrieval.rrf`
- `rerank.bailian`
- `rerank.error`
- `llm.bailian`
- `sse.emit`

每轮 chat 通过 `turn_id` 查询 Trace：

```text
GET /api/trace/turns/{turn_id}/events
```

### 闲聊意图

已新增 `ChitchatFlow`。

当前行为：

- `你好`
- `您好`
- `在吗`
- `早上好`
- `下午好`
- `晚上好`
- `hello`
- `hi`

这些输入会走 `chitchat`，不会触发商品检索和商品卡。

当前正在补齐的点：

- `1+1等于几` 这类基础数学问题应归为非购物问题，不应触发导购。
- Router 已开始扩展该识别逻辑。
- `ChitchatFlow` 还需要补直接回答简单算术的逻辑。

## 当前路由规则

当前 Router 是规则路由，不是 LLM Router。

识别顺序：

```text
售后关键词 -> after_sale
下单关键词 -> order
购物车关键词 -> cart
商品问答关键词 -> product_qa
闲聊/非购物问题 -> chitchat
其他输入 -> guide
```

实体抽取字段：

- `budget_max`
- `brand`
- `category`
- `sub_category`
- `preferences`

示例：

```text
预算3000以内，想买苹果手机，拍照好续航强
```

抽取结果：

```json
{
  "budget_max": 3000,
  "brand": "Apple 苹果",
  "category": "数码电子",
  "sub_category": "智能手机",
  "preferences": ["拍照", "续航"]
}
```

## 当前测试覆盖

最近一次全量测试：

```text
pytest -v
52 passed
```

重点测试文件：

- `tests/test_bailian_client.py`
- `tests/test_chat_api.py`
- `tests/test_chat_frontend.py`
- `tests/test_chat_trace_persistence.py`
- `tests/test_db_product_search.py`
- `tests/test_product_card.py`
- `tests/test_router.py`
- `tests/test_settings_and_db.py`

## 已知限制

1. Router 仍是规则实现，复杂自然语言意图可能误判。
2. 非购物问题识别正在补齐，简单数学问题需要继续完成 `ChitchatFlow` 回答逻辑。
3. 检索的向量相似度当前在 Python 中计算，后续应迁移到 PostgreSQL pgvector SQL 排序。
4. BM25 中文分词仍较粗，中文长句主要依赖向量召回。
5. 下单、加购、售后仍是流程骨架，没有接真实订单系统。
6. Observability 页面能查看 Trace，但还未完成分组、耗时高亮、错误高亮和调用瀑布图。

## 下一步建议

### Sprint 2 收尾

1. 完成非购物问题处理：
   - `1+1等于几` -> `chitchat`
   - 直接回答 `1+1=2`
   - 不触发 `retrieval.*`
   - 不返回 `product_card`

2. 补测试：
   - Router 判断简单数学为 `chitchat`
   - ChatService 不产生检索 Trace
   - ChitchatFlow 回答包含正确结果

3. 整理 git：
   - `.idea/` 加入 `.gitignore`
   - 提交 Sprint 2 改动
   - push 到 `origin/main`

### Sprint 3 候选目标

1. Observability 面板增强：
   - 按 `router / retrieval / rerank / llm / sse` 分组
   - 显示耗时
   - 错误状态高亮
   - 展示当前 turn 的完整调用链

2. LLM JSON Router：
   - 保留规则路由处理强确定性动作
   - 用 LLM 处理复杂导购意图和约束抽取
   - 输出结构化 JSON，包括 intent、slots、confidence、clarification_need

3. 检索质量优化：
   - pgvector SQL 召回
   - 更细粒度中文分词
   - 偏好字段参与 rerank prompt
   - 多商品去重，避免同一商品多个 chunk 占满结果

4. 交易流程增强：
   - 商品选择上下文
   - 加购确认
   - 下单预览
   - 售后原因收集与状态流转
