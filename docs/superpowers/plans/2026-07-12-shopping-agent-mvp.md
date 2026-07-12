# Shopping Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python FastAPI shopping guide Agent MVP with hybrid retrieval, structured SSE events, cart simulation, and a web observability console.

**Architecture:** The backend is a modular FastAPI service. User chat enters `ChatService`, routes through `IntentRouter`, executes a focused `FlowHandler`, emits structured SSE display events, and persists detailed Trace events for the observability UI. Retrieval uses structured filters, BM25 keyword recall, text vector recall, optional image vector recall, RRF fusion, business scoring, and Cross-Encoder reranking.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL + pgvector, pytest, httpx, vanilla HTML/CSS/JavaScript for `/admin/observability`.

## Global Constraints

- Main backend language: Python.
- Web framework: FastAPI.
- Agent orchestration: self-built `IntentRouter + FlowHandler`; do not use LangGraph.
- Retrieval: structured filtering + BM25 keyword recall + vector semantic recall + optional image vector recall + RRF fusion + Cross-Encoder rerank.
- SSE events must be structured and renderable by event `type`.
- Observability UI is part of MVP, available at `/admin/observability`.
- User-facing `thinking` events must show public progress only, not hidden model reasoning.
- Order and after-sale execution are mock flows in MVP; real payment, fulfillment, and refunds are out of scope.
- Read product source data from `data/ecommerce_agent_dataset` as UTF-8.
- New or modified code must include Chinese comments for each property field, each method, and key logic.

---

## File Structure

Create the following project structure:

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
    test_text_chunker.py
    test_hybrid_retrieval.py
    test_router.py
    test_sse_events.py
    test_trace_service.py
    test_chat_api.py
```

---

### Task 1: Project Skeleton And Shared Schemas

**Files:**
- Create: `pyproject.toml`
- Create: `mallpilot/app/main.py`
- Create: `mallpilot/app/core/config.py`
- Create: `mallpilot/app/core/exceptions.py`
- Create: `mallpilot/app/agent/schemas.py`
- Test: `tests/test_sse_events.py`

**Interfaces:**
- Produces: `SseEvent`, `TraceEvent`, `IntentResult`, `ProductCandidate`, `ChatRequest`
- Produces: `create_app() -> FastAPI`
- Consumes: none

- [ ] **Step 1: Write failing schema tests**

```python
# tests/test_sse_events.py
from mallpilot.app.agent.schemas import SseEvent, TraceEvent


def test_sse_event_has_stable_envelope():
    event = SseEvent(
        type="thinking",
        chat_id="chat_1",
        turn_id="turn_1",
        seq=1,
        payload={"message": "正在检索商品"},
    )

    data = event.model_dump()

    assert data["type"] == "thinking"
    assert data["chat_id"] == "chat_1"
    assert data["turn_id"] == "turn_1"
    assert data["seq"] == 1
    assert "event_id" in data
    assert "timestamp" in data


def test_trace_event_records_stage_and_payload():
    event = TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type="router_decision",
        span_name="IntentRouter.route",
        payload={"intent": "guide"},
        status="ok",
    )

    assert event.event_type == "router_decision"
    assert event.payload["intent"] == "guide"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sse_events.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'mallpilot'`.

- [ ] **Step 3: Add project metadata**

```toml
# pyproject.toml
[project]
name = "mallpilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "pytest>=8.2",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Implement shared schemas**

```python
# mallpilot/app/agent/schemas.py
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # 用户会话 ID，前端首次请求时可以为空。
    chat_id: str | None = None
    # 用户 ID，MVP 阶段允许使用 anonymous。
    user_id: str = "anonymous"
    # 用户本轮输入文本。
    message: str
    # 附件列表，图片输入会放在这里。
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class SseEvent(BaseModel):
    # SSE 事件唯一 ID。
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    # 前端渲染使用的事件类型。
    type: str
    # 当前会话 ID。
    chat_id: str
    # 当前轮次 ID。
    turn_id: str
    # 当前轮次内递增序号。
    seq: int
    # 事件产生时间。
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # 事件业务载荷。
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    # Trace 事件唯一 ID。
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    # 当前会话 ID。
    chat_id: str
    # 当前轮次 ID。
    turn_id: str
    # Trace 事件类型。
    event_type: str
    # 代码执行阶段名称。
    span_name: str
    # Trace 详细载荷。
    payload: dict[str, Any] = Field(default_factory=dict)
    # 执行状态。
    status: Literal["ok", "error"] = "ok"
    # 错误信息。
    error_message: str | None = None
    # 耗时，单位毫秒。
    duration_ms: int | None = None
    # 事件产生时间。
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntentResult(BaseModel):
    # 路由意图。
    intent: Literal["guide", "product_qa", "compare", "cart", "order", "after_sale", "chitchat"]
    # 意图置信度。
    confidence: float
    # 路由原因摘要。
    reason: str
    # 抽取出的实体。
    entities: dict[str, Any] = Field(default_factory=dict)


class ProductCandidate(BaseModel):
    # 商品 ID。
    product_id: str
    # 商品标题。
    title: str
    # 商品品牌。
    brand: str | None = None
    # 商品品类。
    category: str | None = None
    # 商品价格。
    price: float | None = None
    # 商品图片 URL。
    image_url: str | None = None
    # 候选分数。
    score: float = 0.0
    # 候选命中的证据。
    evidence: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 5: Implement app factory**

```python
# mallpilot/app/main.py
from fastapi import FastAPI


# 创建 FastAPI 应用，后续任务会在这里注册路由。
def create_app() -> FastAPI:
    app = FastAPI(title="MallPilot", version="0.1.0")
    return app


app = create_app()
```

```python
# mallpilot/app/core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库连接字符串。
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/mallpilot"
    # 商品数据目录。
    dataset_dir: str = "data/ecommerce_agent_dataset"
    # 是否启用 mock LLM。
    use_mock_llm: bool = True


# 获取应用配置。
def get_settings() -> Settings:
    return Settings()
```

```python
# mallpilot/app/core/exceptions.py
class MallPilotError(Exception):
    # 业务错误编码。
    code: str = "mallpilot_error"

    # 初始化业务异常。
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ClarificationRequired(MallPilotError):
    # 需要用户补充信息。
    code = "clarification_required"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_sse_events.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml mallpilot/app/main.py mallpilot/app/core mallpilot/app/agent/schemas.py tests/test_sse_events.py
git commit -m "feat: add mallpilot backend skeleton"
```

---

### Task 2: Product Ingestion And Text Chunking

**Files:**
- Create: `mallpilot/app/retrieval/text_chunker.py`
- Create: `scripts/ingest_products.py`
- Test: `tests/test_text_chunker.py`

**Interfaces:**
- Consumes: `ProductCandidate`
- Produces: `load_product_files(dataset_dir: str) -> list[dict]`
- Produces: `build_knowledge_chunks(product: dict) -> list[dict]`

- [ ] **Step 1: Write failing chunker tests**

```python
# tests/test_text_chunker.py
from mallpilot.app.retrieval.text_chunker import build_knowledge_chunks


def test_build_knowledge_chunks_splits_faq_individually():
    product = {
        "product_id": "p_1",
        "title": "测试精华",
        "brand": "测试品牌",
        "category": "美妆护肤",
        "sub_category": "精华",
        "base_price": 199,
        "skus": [{"sku_id": "s_1", "properties": {"容量": "30ml"}, "price": 199}],
        "rag_knowledge": {
            "marketing_description": "主打保湿修护。",
            "official_faq": [{"question": "敏感肌能用吗？", "answer": "建议先做测试。"}],
            "user_reviews": [{"rating": 5, "content": "保湿不错。"}],
        },
    }

    chunks = build_knowledge_chunks(product)

    assert [chunk["chunk_type"] for chunk in chunks] == ["basic", "marketing", "faq", "review_summary"]
    assert chunks[2]["title"] == "敏感肌能用吗？"
    assert "建议先做测试" in chunks[2]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_text_chunker.py -v`

Expected: FAIL with import error or missing function.

- [ ] **Step 3: Implement chunker**

```python
# mallpilot/app/retrieval/text_chunker.py
from collections import Counter
from typing import Any


# 将 SKU 属性压缩成可检索文本。
def _format_skus(skus: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for sku in skus:
        properties = "，".join(f"{key}:{value}" for key, value in sku.get("properties", {}).items())
        parts.append(f"{sku.get('sku_id')} {properties} 价格:{sku.get('price')}")
    return "；".join(parts)


# 将评论聚合成第一版摘要，后续可替换为 LLM 摘要。
def _summarize_reviews(reviews: list[dict[str, Any]]) -> str:
    if not reviews:
        return "暂无用户评论。"
    ratings = Counter(review.get("rating") for review in reviews)
    contents = " ".join(str(review.get("content", "")) for review in reviews[:5])
    return f"评分分布:{dict(ratings)}。评论摘要:{contents}"


# 根据商品 JSON 生成可检索知识块。
def build_knowledge_chunks(product: dict[str, Any]) -> list[dict[str, Any]]:
    product_id = product["product_id"]
    rag = product.get("rag_knowledge", {})
    chunks: list[dict[str, Any]] = []

    # 基础信息块用于承接标题、品牌、价格和 SKU 检索。
    chunks.append({
        "product_id": product_id,
        "chunk_type": "basic",
        "title": product.get("title", ""),
        "content": (
            f"商品:{product.get('title')}。品牌:{product.get('brand')}。"
            f"品类:{product.get('category')}/{product.get('sub_category')}。"
            f"基础价格:{product.get('base_price')}。SKU:{_format_skus(product.get('skus', []))}"
        ),
        "metadata": {"source": "product_basic"},
    })

    # 营销描述块用于场景、功效和使用建议检索。
    chunks.append({
        "product_id": product_id,
        "chunk_type": "marketing",
        "title": product.get("title", ""),
        "content": rag.get("marketing_description", ""),
        "metadata": {"source": "marketing_description"},
    })

    # 每条 FAQ 独立成块，保证问答证据可追溯。
    for faq in rag.get("official_faq", []):
        chunks.append({
            "product_id": product_id,
            "chunk_type": "faq",
            "title": faq.get("question", ""),
            "content": f"问题:{faq.get('question', '')}\n回答:{faq.get('answer', '')}",
            "metadata": {"source": "official_faq", "question": faq.get("question", "")},
        })

    # 评论先做轻量摘要，避免大量原始评论噪声进入召回。
    chunks.append({
        "product_id": product_id,
        "chunk_type": "review_summary",
        "title": f"{product.get('title', '')} 用户评论摘要",
        "content": _summarize_reviews(rag.get("user_reviews", [])),
        "metadata": {"source": "user_reviews"},
    })

    return chunks
```

- [ ] **Step 4: Implement product loader**

```python
# scripts/ingest_products.py
import json
from pathlib import Path
from typing import Any


# 按 UTF-8 读取数据集中的全部商品 JSON。
def load_product_files(dataset_dir: str) -> list[dict[str, Any]]:
    root = Path(dataset_dir)
    products: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/data/*.json")):
        products.append(json.loads(path.read_text(encoding="utf-8")))
    return products


# 命令行入口，先输出数量用于校验数据集。
def main() -> None:
    products = load_product_files("data/ecommerce_agent_dataset")
    print(f"loaded_products={len(products)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests and loader**

Run: `pytest tests/test_text_chunker.py -v`

Expected: PASS.

Run: `python scripts/ingest_products.py`

Expected: `loaded_products=100`.

- [ ] **Step 6: Commit**

```bash
git add mallpilot/app/retrieval/text_chunker.py scripts/ingest_products.py tests/test_text_chunker.py
git commit -m "feat: add product ingestion and chunking"
```

---

### Task 3: Hybrid Retrieval Core

**Files:**
- Create: `mallpilot/app/retrieval/bm25_search.py`
- Create: `mallpilot/app/retrieval/vector_search.py`
- Create: `mallpilot/app/retrieval/image_search.py`
- Create: `mallpilot/app/retrieval/fusion.py`
- Create: `mallpilot/app/retrieval/cross_encoder_reranker.py`
- Create: `mallpilot/app/retrieval/product_search.py`
- Test: `tests/test_hybrid_retrieval.py`

**Interfaces:**
- Consumes: knowledge chunks from Task 2
- Produces: `HybridProductSearch.search(query: str, filters: dict, image_embedding: list[float] | None = None) -> list[ProductCandidate]`
- Produces trace stages: `bm25_result`, `text_vector_result`, `image_vector_result`, `rrf_fusion_result`, `cross_encoder_rerank_result`

- [ ] **Step 1: Write failing hybrid retrieval test**

```python
# tests/test_hybrid_retrieval.py
from mallpilot.app.retrieval.product_search import HybridProductSearch


def test_hybrid_search_uses_bm25_vector_rrf_and_cross_encoder():
    docs = [
        {"product_id": "p_1", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"},
        {"product_id": "p_2", "title": "运动鞋", "content": "跑步 缓震", "price": 499, "category": "服饰运动"},
    ]
    search = HybridProductSearch.from_documents(docs)

    results, trace = search.search(
        query="300元以内敏感肌修护精华",
        filters={"category": "美妆护肤", "budget_max": 300},
    )

    assert results[0].product_id == "p_1"
    assert [event["event_type"] for event in trace] == [
        "bm25_result",
        "text_vector_result",
        "rrf_fusion_result",
        "cross_encoder_rerank_result",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hybrid_retrieval.py -v`

Expected: FAIL with missing `HybridProductSearch`.

- [ ] **Step 3: Implement BM25 keyword search**

```python
# mallpilot/app/retrieval/bm25_search.py
import math
import re
from collections import Counter, defaultdict
from typing import Any


# 第一版轻量分词：中文按连续汉字/英文/数字切分，后续可替换为专业分词器。
def tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())


class BM25Search:
    # 初始化 BM25 索引。
    def __init__(self, documents: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        # 原始文档列表。
        self.documents = documents
        # BM25 k1 参数。
        self.k1 = k1
        # BM25 b 参数。
        self.b = b
        # 文档词频。
        self.term_freqs = [Counter(tokenize(doc.get("content", "") + " " + doc.get("title", ""))) for doc in documents]
        # 文档长度。
        self.doc_lengths = [sum(freq.values()) for freq in self.term_freqs]
        # 平均文档长度。
        self.avg_doc_length = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)
        # 包含某词的文档数量。
        self.doc_freq: dict[str, int] = defaultdict(int)
        for freq in self.term_freqs:
            for term in freq:
                self.doc_freq[term] += 1

    # 执行关键词召回。
    def search(self, query: str, filters: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
        query_terms = tokenize(query)
        scored: list[dict[str, Any]] = []
        for index, doc in enumerate(self.documents):
            if not _match_filters(doc, filters):
                continue
            score = self._score_document(query_terms, index)
            if score > 0:
                scored.append({"document": doc, "score": score})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    # 计算单篇文档 BM25 分数。
    def _score_document(self, query_terms: list[str], index: int) -> float:
        score = 0.0
        total_docs = len(self.documents)
        freqs = self.term_freqs[index]
        doc_len = self.doc_lengths[index]
        for term in query_terms:
            if term not in freqs:
                continue
            idf = math.log(1 + (total_docs - self.doc_freq[term] + 0.5) / (self.doc_freq[term] + 0.5))
            tf = freqs[term]
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1))
            score += idf * (tf * (self.k1 + 1)) / denominator
        return score


# 校验结构化过滤条件。
def _match_filters(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("category") and doc.get("category") != filters["category"]:
        return False
    if filters.get("budget_max") is not None and float(doc.get("price", 0)) > float(filters["budget_max"]):
        return False
    return True
```

- [ ] **Step 4: Implement vector, image, fusion, reranker, and facade**

```python
# mallpilot/app/retrieval/vector_search.py
from typing import Any


class VectorSearch:
    # 初始化轻量语义搜索，MVP 测试环境用词重合模拟向量相似度。
    def __init__(self, documents: list[dict[str, Any]]):
        # 原始文档列表。
        self.documents = documents

    # 执行文本向量召回。
    def search(self, query: str, filters: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
        terms = set(query.lower())
        scored: list[dict[str, Any]] = []
        for doc in self.documents:
            if filters.get("category") and doc.get("category") != filters["category"]:
                continue
            if filters.get("budget_max") is not None and float(doc.get("price", 0)) > float(filters["budget_max"]):
                continue
            content_terms = set((doc.get("title", "") + doc.get("content", "")).lower())
            score = len(terms & content_terms) / max(len(terms), 1)
            scored.append({"document": doc, "score": score})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]
```

```python
# mallpilot/app/retrieval/image_search.py
from typing import Any


class ImageSearch:
    # 初始化图片向量召回器，MVP 无图片时返回空。
    def __init__(self, documents: list[dict[str, Any]]):
        # 原始文档列表。
        self.documents = documents

    # 根据图片向量召回候选。
    def search(self, image_embedding: list[float] | None, filters: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
        if image_embedding is None:
            return []
        return [{"document": doc, "score": 0.1} for doc in self.documents[:top_k]]
```

```python
# mallpilot/app/retrieval/fusion.py
from typing import Any


# 使用 RRF 融合多路召回结果。
def reciprocal_rank_fusion(result_sets: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}
    for source_index, results in enumerate(result_sets):
        for rank, item in enumerate(results, start=1):
            doc = item["document"]
            product_id = doc["product_id"]
            if product_id not in fused:
                fused[product_id] = {"document": doc, "rrf_score": 0.0, "sources": []}
            fused[product_id]["rrf_score"] += 1 / (k + rank)
            fused[product_id]["sources"].append(source_index)
    merged = list(fused.values())
    merged.sort(key=lambda item: item["rrf_score"], reverse=True)
    return merged
```

```python
# mallpilot/app/retrieval/cross_encoder_reranker.py
from typing import Any


class CrossEncoderReranker:
    # 初始化 Cross-Encoder 精排器，MVP 先用可替换的轻量打分。
    def __init__(self):
        pass

    # 对融合候选进行精排。
    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        query_chars = set(query)
        for item in candidates:
            doc = item["document"]
            content = doc.get("title", "") + doc.get("content", "")
            cross_score = len(query_chars & set(content)) / max(len(query_chars), 1)
            final_score = cross_score * 0.7 + item.get("rrf_score", 0.0) * 0.3
            ranked.append({**item, "cross_encoder_score": cross_score, "final_score": final_score})
        ranked.sort(key=lambda item: item["final_score"], reverse=True)
        return ranked[:top_k]
```

```python
# mallpilot/app/retrieval/product_search.py
from typing import Any

from mallpilot.app.agent.schemas import ProductCandidate
from mallpilot.app.retrieval.bm25_search import BM25Search
from mallpilot.app.retrieval.cross_encoder_reranker import CrossEncoderReranker
from mallpilot.app.retrieval.fusion import reciprocal_rank_fusion
from mallpilot.app.retrieval.image_search import ImageSearch
from mallpilot.app.retrieval.vector_search import VectorSearch


class HybridProductSearch:
    # 初始化混合检索。
    def __init__(self, documents: list[dict[str, Any]]):
        # 原始检索文档。
        self.documents = documents
        # BM25 关键词召回器。
        self.bm25 = BM25Search(documents)
        # 文本向量召回器。
        self.vector = VectorSearch(documents)
        # 图片向量召回器。
        self.image = ImageSearch(documents)
        # Cross-Encoder 精排器。
        self.reranker = CrossEncoderReranker()

    # 从文档构建检索器。
    @classmethod
    def from_documents(cls, documents: list[dict[str, Any]]) -> "HybridProductSearch":
        return cls(documents)

    # 执行混合检索并返回候选与 Trace。
    def search(
        self,
        query: str,
        filters: dict[str, Any],
        image_embedding: list[float] | None = None,
    ) -> tuple[list[ProductCandidate], list[dict[str, Any]]]:
        bm25_results = self.bm25.search(query, filters)
        vector_results = self.vector.search(query, filters)
        image_results = self.image.search(image_embedding, filters)
        result_sets = [bm25_results, vector_results] + ([image_results] if image_results else [])
        fused = reciprocal_rank_fusion(result_sets)
        reranked = self.reranker.rerank(query, fused)

        candidates = [
            ProductCandidate(
                product_id=item["document"]["product_id"],
                title=item["document"]["title"],
                category=item["document"].get("category"),
                price=float(item["document"].get("price", 0)),
                score=float(item["final_score"]),
                evidence=[{"source": "hybrid_retrieval", "summary": item["document"].get("content", "")}],
            )
            for item in reranked
        ]
        trace = [
            {"event_type": "bm25_result", "payload": {"count": len(bm25_results)}},
            {"event_type": "text_vector_result", "payload": {"count": len(vector_results)}},
        ]
        if image_results:
            trace.append({"event_type": "image_vector_result", "payload": {"count": len(image_results)}})
        trace.extend([
            {"event_type": "rrf_fusion_result", "payload": {"count": len(fused)}},
            {"event_type": "cross_encoder_rerank_result", "payload": {"count": len(reranked)}},
        ])
        return candidates, trace
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_hybrid_retrieval.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mallpilot/app/retrieval tests/test_hybrid_retrieval.py
git commit -m "feat: add hybrid retrieval pipeline"
```

---

### Task 4: Trace Service And Event Bus

**Files:**
- Create: `mallpilot/app/services/trace_service.py`
- Create: `mallpilot/app/core/event_bus.py`
- Test: `tests/test_trace_service.py`

**Interfaces:**
- Consumes: `SseEvent`, `TraceEvent`
- Produces: `TraceService.record(event: TraceEvent) -> None`
- Produces: `TraceService.list_events(turn_id: str) -> list[TraceEvent]`
- Produces: `EventBus.emit(event: SseEvent) -> str`

- [ ] **Step 1: Write failing trace tests**

```python
# tests/test_trace_service.py
from mallpilot.app.agent.schemas import SseEvent, TraceEvent
from mallpilot.app.core.event_bus import EventBus
from mallpilot.app.services.trace_service import TraceService


def test_trace_service_records_events_by_turn():
    service = TraceService()
    event = TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type="bm25_result",
        span_name="BM25Search.search",
        payload={"count": 3},
    )

    service.record(event)

    assert service.list_events("turn_1")[0].payload["count"] == 3


def test_event_bus_serializes_sse_event():
    bus = EventBus()
    event = SseEvent(type="thinking", chat_id="chat_1", turn_id="turn_1", seq=1, payload={"message": "处理中"})

    text = bus.emit(event)

    assert text.startswith("event: message\n")
    assert '"type":"thinking"' in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace_service.py -v`

Expected: FAIL with missing modules.

- [ ] **Step 3: Implement trace service and event bus**

```python
# mallpilot/app/services/trace_service.py
from collections import defaultdict

from mallpilot.app.agent.schemas import TraceEvent


class TraceService:
    # 初始化内存 Trace Store，后续任务替换为数据库实现。
    def __init__(self):
        # 按 turn_id 保存 Trace 事件。
        self._events_by_turn: dict[str, list[TraceEvent]] = defaultdict(list)

    # 记录 Trace 事件。
    def record(self, event: TraceEvent) -> None:
        self._events_by_turn[event.turn_id].append(event)

    # 查询某一轮的 Trace 事件。
    def list_events(self, turn_id: str) -> list[TraceEvent]:
        return list(self._events_by_turn.get(turn_id, []))
```

```python
# mallpilot/app/core/event_bus.py
from mallpilot.app.agent.schemas import SseEvent


class EventBus:
    # 将业务事件序列化为 SSE 文本。
    def emit(self, event: SseEvent) -> str:
        payload = event.model_dump_json()
        return f"event: message\ndata: {payload}\n\n"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_trace_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/services/trace_service.py mallpilot/app/core/event_bus.py tests/test_trace_service.py
git commit -m "feat: add trace service and sse event bus"
```

---

### Task 5: Intent Router And Flow Contracts

**Files:**
- Create: `mallpilot/app/agent/router.py`
- Create: `mallpilot/app/agent/state.py`
- Create: `mallpilot/app/agent/flows/base.py`
- Test: `tests/test_router.py`

**Interfaces:**
- Consumes: `IntentResult`
- Produces: `IntentRouter.route(message: str) -> IntentResult`
- Produces: `FlowContext`
- Produces: `BaseFlow.run(context: FlowContext) -> list[SseEvent]`

- [ ] **Step 1: Write failing router tests**

```python
# tests/test_router.py
from mallpilot.app.agent.router import IntentRouter


def test_router_detects_guide_intent():
    router = IntentRouter()
    result = router.route("帮我找300元以内适合敏感肌的精华")

    assert result.intent == "guide"
    assert result.entities["budget_max"] == 300
    assert result.entities["category"] == "美妆护肤"


def test_router_detects_after_sale_intent():
    router = IntentRouter()
    result = router.route("我要退货，订单号是123")

    assert result.intent == "after_sale"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_router.py -v`

Expected: FAIL with missing `IntentRouter`.

- [ ] **Step 3: Implement router and flow contracts**

```python
# mallpilot/app/agent/router.py
import re

from mallpilot.app.agent.schemas import IntentResult


class IntentRouter:
    # 路由用户意图，MVP 先用规则实现，后续可替换为 LLM JSON 路由。
    def route(self, message: str) -> IntentResult:
        if any(word in message for word in ["退货", "退款", "售后", "取消订单"]):
            return IntentResult(intent="after_sale", confidence=0.9, reason="命中售后关键词", entities={})
        if any(word in message for word in ["下单", "购买", "结算"]):
            return IntentResult(intent="order", confidence=0.85, reason="命中下单关键词", entities={})
        if any(word in message for word in ["购物车", "加入", "加购"]):
            return IntentResult(intent="cart", confidence=0.85, reason="命中购物车关键词", entities={})
        if any(word in message for word in ["这款", "适合", "参数", "能用吗"]):
            entities = self._extract_entities(message)
            return IntentResult(intent="product_qa", confidence=0.7, reason="命中商品问答关键词", entities=entities)
        entities = self._extract_entities(message)
        return IntentResult(intent="guide", confidence=0.75, reason="默认导购推荐", entities=entities)

    # 抽取第一版常用实体。
    def _extract_entities(self, message: str) -> dict:
        entities: dict = {}
        budget_match = re.search(r"(\d+)\s*元?以内", message)
        if budget_match:
            entities["budget_max"] = int(budget_match.group(1))
        if any(word in message for word in ["精华", "敏感肌", "保湿", "护肤"]):
            entities["category"] = "美妆护肤"
        if "手机" in message or "iPhone" in message:
            entities["category"] = "数码电子"
        if "T恤" in message or "鞋" in message:
            entities["category"] = "服饰运动"
        if "咖啡" in message or "零食" in message:
            entities["category"] = "食品生活"
        return entities
```

```python
# mallpilot/app/agent/state.py
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowContext:
    # 当前会话 ID。
    chat_id: str
    # 当前轮次 ID。
    turn_id: str
    # 用户输入。
    message: str
    # Router 输出的实体。
    entities: dict[str, Any] = field(default_factory=dict)
    # 附件列表。
    attachments: list[dict[str, Any]] = field(default_factory=list)
```

```python
# mallpilot/app/agent/flows/base.py
from abc import ABC, abstractmethod

from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext


class BaseFlow(ABC):
    # 执行业务 Flow。
    @abstractmethod
    def run(self, context: FlowContext) -> list[SseEvent]:
        raise NotImplementedError
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_router.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/agent/router.py mallpilot/app/agent/state.py mallpilot/app/agent/flows/base.py tests/test_router.py
git commit -m "feat: add intent router and flow contracts"
```

---

### Task 6: Guide And Product QA Flows

**Files:**
- Create: `mallpilot/app/agent/flows/guide_flow.py`
- Create: `mallpilot/app/agent/flows/product_qa_flow.py`
- Create: `mallpilot/app/tools/product_tools.py`
- Test: `tests/test_guide_flow.py`

**Interfaces:**
- Consumes: `HybridProductSearch.search`
- Produces: `GuideFlow.run(context) -> list[SseEvent]`
- Produces: `ProductQaFlow.run(context) -> list[SseEvent]`

- [ ] **Step 1: Write failing flow tests**

```python
# tests/test_guide_flow.py
from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch


def test_guide_flow_emits_thinking_product_card_and_final():
    docs = [
        {"product_id": "p_1", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"}
    ]
    flow = GuideFlow(search=HybridProductSearch.from_documents(docs))
    context = FlowContext(
        chat_id="chat_1",
        turn_id="turn_1",
        message="帮我找300元以内适合敏感肌的精华",
        entities={"category": "美妆护肤", "budget_max": 300},
    )

    events = flow.run(context)

    assert [event.type for event in events] == ["thinking", "product_card", "final"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_guide_flow.py -v`

Expected: FAIL with missing `GuideFlow`.

- [ ] **Step 3: Implement product tools and flows**

```python
# mallpilot/app/tools/product_tools.py
from mallpilot.app.agent.schemas import ProductCandidate


# 将检索候选转成商品卡片 payload。
def build_product_card(candidate: ProductCandidate) -> dict:
    return {
        "product_id": candidate.product_id,
        "title": candidate.title,
        "brand": candidate.brand,
        "category": candidate.category,
        "price": candidate.price,
        "image_url": candidate.image_url,
        "reasons": [item.get("summary", "") for item in candidate.evidence[:2]],
        "evidence": candidate.evidence,
        "actions": [
            {"type": "view_detail", "label": "查看详情"},
            {"type": "add_to_cart", "label": "加入购物车"},
        ],
    }
```

```python
# mallpilot/app/agent/flows/guide_flow.py
from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch
from mallpilot.app.tools.product_tools import build_product_card


class GuideFlow(BaseFlow):
    # 初始化导购 Flow。
    def __init__(self, search: HybridProductSearch):
        # 混合检索服务。
        self.search = search

    # 执行导购推荐流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        events: list[SseEvent] = []
        seq = 1

        # 发送公开进度事件。
        events.append(SseEvent(
            type="thinking",
            chat_id=context.chat_id,
            turn_id=context.turn_id,
            seq=seq,
            payload={"message": "正在根据你的需求检索商品", "stage": "retrieval"},
        ))
        seq += 1

        candidates, _trace = self.search.search(context.message, context.entities)
        if not candidates:
            events.append(SseEvent(
                type="answer",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=seq,
                payload={"text": "没有找到完全满足条件的商品，可以放宽预算或减少限制。"},
            ))
            seq += 1
        else:
            events.append(SseEvent(
                type="product_card",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=seq,
                payload=build_product_card(candidates[0]),
            ))
            seq += 1

        events.append(SseEvent(
            type="final",
            chat_id=context.chat_id,
            turn_id=context.turn_id,
            seq=seq,
            payload={"status": "completed"},
        ))
        return events
```

```python
# mallpilot/app/agent/flows/product_qa_flow.py
from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.retrieval.product_search import HybridProductSearch


class ProductQaFlow(BaseFlow):
    # 初始化商品问答 Flow。
    def __init__(self, search: HybridProductSearch):
        # 混合检索服务。
        self.search = search

    # 执行商品问答流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        candidates, _trace = self.search.search(context.message, context.entities)
        answer = "没有找到足够证据回答这个商品问题。"
        if candidates:
            evidence = candidates[0].evidence[0].get("summary", "")
            answer = f"根据商品知识，{evidence}"
        return [
            SseEvent(type="answer", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload={"text": answer}),
            SseEvent(type="final", chat_id=context.chat_id, turn_id=context.turn_id, seq=2, payload={"status": "completed"}),
        ]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_guide_flow.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/agent/flows/guide_flow.py mallpilot/app/agent/flows/product_qa_flow.py mallpilot/app/tools/product_tools.py tests/test_guide_flow.py
git commit -m "feat: add guide and product qa flows"
```

---

### Task 7: Cart, Order, And After-Sale Mock Flows

**Files:**
- Create: `mallpilot/app/tools/cart_tools.py`
- Create: `mallpilot/app/tools/order_tools.py`
- Create: `mallpilot/app/tools/after_sale_tools.py`
- Create: `mallpilot/app/agent/flows/cart_flow.py`
- Create: `mallpilot/app/agent/flows/order_flow.py`
- Create: `mallpilot/app/agent/flows/after_sale_flow.py`
- Test: `tests/test_commerce_flows.py`

**Interfaces:**
- Produces: `CartStore.add_to_cart(product_id: str, sku_id: str | None, quantity: int) -> dict`
- Produces: `OrderFlow` emits `order_preview` before mock order creation
- Produces: `AfterSaleFlow` emits `after_sale_preview`

- [ ] **Step 1: Write failing commerce flow tests**

```python
# tests/test_commerce_flows.py
from mallpilot.app.agent.flows.cart_flow import CartFlow
from mallpilot.app.agent.flows.order_flow import OrderFlow
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.cart_tools import CartStore


def test_cart_flow_emits_clarification_when_product_missing():
    flow = CartFlow(cart_store=CartStore())
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="加入购物车")

    events = flow.run(context)

    assert events[0].type == "clarification"


def test_order_flow_emits_order_preview():
    flow = OrderFlow()
    context = FlowContext(chat_id="chat_1", turn_id="turn_1", message="下单")

    events = flow.run(context)

    assert events[0].type == "order_preview"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_commerce_flows.py -v`

Expected: FAIL with missing modules.

- [ ] **Step 3: Implement mock commerce tools and flows**

```python
# mallpilot/app/tools/cart_tools.py
from uuid import uuid4


class CartStore:
    # 初始化内存购物车。
    def __init__(self):
        # 购物车项列表。
        self.items: list[dict] = []

    # 加入购物车。
    def add_to_cart(self, product_id: str, sku_id: str | None, quantity: int) -> dict:
        item = {
            "cart_item_id": f"ci_{uuid4().hex}",
            "product_id": product_id,
            "sku_id": sku_id,
            "quantity": quantity,
            "status": "added",
        }
        self.items.append(item)
        return item
```

```python
# mallpilot/app/tools/order_tools.py
from uuid import uuid4


# 生成模拟订单预览。
def preview_order() -> dict:
    return {"items": [], "total_amount": 0, "requires_confirmation": True}


# 创建模拟订单。
def create_mock_order() -> dict:
    return {"order_id": f"ord_{uuid4().hex}", "status": "created"}
```

```python
# mallpilot/app/tools/after_sale_tools.py
from uuid import uuid4


# 生成模拟售后预览。
def preview_after_sale() -> dict:
    return {"policy": "MVP 模拟售后，真实规则后续接入。", "requires_confirmation": True}


# 创建模拟售后申请。
def create_mock_return_request() -> dict:
    return {"return_id": f"ret_{uuid4().hex}", "status": "submitted"}
```

```python
# mallpilot/app/agent/flows/cart_flow.py
from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.cart_tools import CartStore


class CartFlow(BaseFlow):
    # 初始化购物车 Flow。
    def __init__(self, cart_store: CartStore):
        # 购物车存储。
        self.cart_store = cart_store

    # 执行购物车流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        product_id = context.entities.get("product_id")
        if not product_id:
            return [SseEvent(
                type="clarification",
                chat_id=context.chat_id,
                turn_id=context.turn_id,
                seq=1,
                payload={"question": "你想把哪个商品加入购物车？", "required_slots": ["product_id"], "suggestions": []},
            )]
        item = self.cart_store.add_to_cart(product_id, context.entities.get("sku_id"), int(context.entities.get("quantity", 1)))
        return [SseEvent(type="cart_update", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload=item)]
```

```python
# mallpilot/app/agent/flows/order_flow.py
from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.order_tools import preview_order


class OrderFlow(BaseFlow):
    # 执行模拟下单流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        return [SseEvent(type="order_preview", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload=preview_order())]
```

```python
# mallpilot/app/agent/flows/after_sale_flow.py
from mallpilot.app.agent.flows.base import BaseFlow
from mallpilot.app.agent.schemas import SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.tools.after_sale_tools import preview_after_sale


class AfterSaleFlow(BaseFlow):
    # 执行模拟售后流程。
    def run(self, context: FlowContext) -> list[SseEvent]:
        return [SseEvent(type="after_sale_preview", chat_id=context.chat_id, turn_id=context.turn_id, seq=1, payload=preview_after_sale())]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_commerce_flows.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/tools/cart_tools.py mallpilot/app/tools/order_tools.py mallpilot/app/tools/after_sale_tools.py mallpilot/app/agent/flows/cart_flow.py mallpilot/app/agent/flows/order_flow.py mallpilot/app/agent/flows/after_sale_flow.py tests/test_commerce_flows.py
git commit -m "feat: add mock commerce flows"
```

---

### Task 8: Chat SSE API

**Files:**
- Create: `mallpilot/app/services/chat_service.py`
- Create: `mallpilot/app/api/chat.py`
- Modify: `mallpilot/app/main.py`
- Test: `tests/test_chat_api.py`

**Interfaces:**
- Consumes: Router and Flow classes
- Produces: `POST /api/chat/stream`
- Produces: `ChatService.stream(request: ChatRequest) -> Iterator[str]`

- [ ] **Step 1: Write failing chat API test**

```python
# tests/test_chat_api.py
from fastapi.testclient import TestClient

from mallpilot.app.main import create_app


def test_chat_stream_returns_sse_events():
    client = TestClient(create_app())

    response = client.post("/api/chat/stream", json={"message": "帮我找300元以内适合敏感肌的精华"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: message" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_api.py -v`

Expected: FAIL with 404.

- [ ] **Step 3: Implement chat service and API**

```python
# mallpilot/app/services/chat_service.py
from collections.abc import Iterator
from uuid import uuid4

from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.router import IntentRouter
from mallpilot.app.agent.schemas import ChatRequest, SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.core.event_bus import EventBus
from mallpilot.app.retrieval.product_search import HybridProductSearch


class ChatService:
    # 初始化 Chat 服务。
    def __init__(self):
        # 意图路由器。
        self.router = IntentRouter()
        # SSE 事件总线。
        self.event_bus = EventBus()
        # MVP 内置演示文档，后续替换为数据库检索。
        self.search = HybridProductSearch.from_documents([
            {"product_id": "p_demo", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"}
        ])

    # 流式返回 SSE 文本。
    def stream(self, request: ChatRequest) -> Iterator[str]:
        chat_id = request.chat_id or f"chat_{uuid4().hex}"
        turn_id = f"turn_{uuid4().hex}"
        intent = self.router.route(request.message)
        context = FlowContext(chat_id=chat_id, turn_id=turn_id, message=request.message, entities=intent.entities, attachments=request.attachments)

        # MVP 先接入导购 Flow，后续任务把其他 Flow 注册进来。
        flow = GuideFlow(search=self.search)
        for event in flow.run(context):
            yield self.event_bus.emit(event)
```

```python
# mallpilot/app/api/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from mallpilot.app.agent.schemas import ChatRequest
from mallpilot.app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


# 用户侧 Chat SSE 接口。
@router.post("/stream")
def stream_chat(request: ChatRequest) -> StreamingResponse:
    service = ChatService()
    return StreamingResponse(service.stream(request), media_type="text/event-stream")
```

```python
# mallpilot/app/main.py
from fastapi import FastAPI

from mallpilot.app.api.chat import router as chat_router


# 创建 FastAPI 应用，后续任务会在这里注册路由。
def create_app() -> FastAPI:
    app = FastAPI(title="MallPilot", version="0.1.0")
    app.include_router(chat_router)
    return app


app = create_app()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_chat_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mallpilot/app/services/chat_service.py mallpilot/app/api/chat.py mallpilot/app/main.py tests/test_chat_api.py
git commit -m "feat: add chat sse api"
```

---

### Task 9: Observability API And Web UI

**Files:**
- Create: `mallpilot/app/api/trace.py`
- Create: `mallpilot/app/api/admin.py`
- Create: `mallpilot/app/web/observability/index.html`
- Create: `mallpilot/app/web/observability/app.js`
- Create: `mallpilot/app/web/observability/style.css`
- Modify: `mallpilot/app/main.py`
- Test: `tests/test_observability_api.py`

**Interfaces:**
- Produces: `GET /api/trace/turns/{turn_id}/events`
- Produces: `GET /admin/observability`
- Produces: UI sections for sessions, timeline, detail JSON, LLM, retrieval, tools, SSE.

- [ ] **Step 1: Write failing observability tests**

```python
# tests/test_observability_api.py
from fastapi.testclient import TestClient

from mallpilot.app.main import create_app


def test_observability_page_loads():
    client = TestClient(create_app())

    response = client.get("/admin/observability")

    assert response.status_code == 200
    assert "MallPilot Observability" in response.text


def test_trace_events_api_returns_list():
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_1/events")

    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_observability_api.py -v`

Expected: FAIL with 404.

- [ ] **Step 3: Implement trace and admin routes**

```python
# mallpilot/app/api/trace.py
from fastapi import APIRouter

from mallpilot.app.services.trace_service import TraceService

router = APIRouter(prefix="/api/trace", tags=["trace"])
trace_service = TraceService()


# 查询某个 turn 的 Trace 事件。
@router.get("/turns/{turn_id}/events")
def list_turn_events(turn_id: str) -> list[dict]:
    return [event.model_dump(mode="json") for event in trace_service.list_events(turn_id)]
```

```python
# mallpilot/app/api/admin.py
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

router = APIRouter(prefix="/admin", tags=["admin"])
WEB_ROOT = Path(__file__).resolve().parents[1] / "web" / "observability"


# 可观测控制台页面。
@router.get("/observability")
def observability_page() -> HTMLResponse:
    return HTMLResponse((WEB_ROOT / "index.html").read_text(encoding="utf-8"))


# 控制台静态脚本。
@router.get("/static/app.js")
def observability_js() -> PlainTextResponse:
    return PlainTextResponse((WEB_ROOT / "app.js").read_text(encoding="utf-8"), media_type="application/javascript")


# 控制台样式。
@router.get("/static/style.css")
def observability_css() -> PlainTextResponse:
    return PlainTextResponse((WEB_ROOT / "style.css").read_text(encoding="utf-8"), media_type="text/css")
```

- [ ] **Step 4: Implement observability UI**

```html
<!-- mallpilot/app/web/observability/index.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>MallPilot Observability</title>
    <link rel="stylesheet" href="/admin/static/style.css" />
  </head>
  <body>
    <main class="layout">
      <section class="panel">
        <h1>MallPilot Observability</h1>
        <div id="sessions">会话列表</div>
      </section>
      <section class="panel">
        <h2>Timeline</h2>
        <div id="timeline"></div>
      </section>
      <section class="panel">
        <h2>Event Detail</h2>
        <pre id="detail">{}</pre>
      </section>
    </main>
    <script src="/admin/static/app.js"></script>
  </body>
</html>
```

```javascript
// mallpilot/app/web/observability/app.js
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

document.querySelector("#sessions").innerHTML = '<button onclick="loadTurn(\'turn_1\')">turn_1</button>';
```

```css
/* mallpilot/app/web/observability/style.css */
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
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  padding: 12px;
  min-height: 80vh;
}

.timeline-item {
  display: block;
  width: 100%;
  margin-bottom: 8px;
  padding: 8px;
  text-align: left;
}
```

- [ ] **Step 5: Register routers**

```python
# mallpilot/app/main.py
from fastapi import FastAPI

from mallpilot.app.api.admin import router as admin_router
from mallpilot.app.api.chat import router as chat_router
from mallpilot.app.api.trace import router as trace_router


# 创建 FastAPI 应用，注册用户侧和后台侧路由。
def create_app() -> FastAPI:
    app = FastAPI(title="MallPilot", version="0.1.0")
    app.include_router(chat_router)
    app.include_router(trace_router)
    app.include_router(admin_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_observability_api.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add mallpilot/app/api/trace.py mallpilot/app/api/admin.py mallpilot/app/web/observability mallpilot/app/main.py tests/test_observability_api.py
git commit -m "feat: add observability console"
```

---

### Task 10: Database Persistence And Full Integration

**Files:**
- Create: `mallpilot/app/models/product.py`
- Create: `mallpilot/app/models/trace.py`
- Create: `mallpilot/app/repositories/product_repo.py`
- Create: `mallpilot/app/repositories/trace_repo.py`
- Modify: `scripts/ingest_products.py`
- Test: `tests/test_ingestion_integration.py`

**Interfaces:**
- Consumes: Task 2 loader and chunker
- Produces: SQLAlchemy models for products, skus, chunks, images, sessions, turns, trace events
- Produces: repository methods used by retrieval and observability

- [ ] **Step 1: Write failing repository smoke test**

```python
# tests/test_ingestion_integration.py
from scripts.ingest_products import load_product_files


def test_dataset_loads_100_products():
    products = load_product_files("data/ecommerce_agent_dataset")

    assert len(products) == 100
    assert products[0]["product_id"].startswith("p_")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_ingestion_integration.py -v`

Expected: PASS if Task 2 is complete.

- [ ] **Step 3: Implement SQLAlchemy models**

```python
# mallpilot/app/models/product.py
from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    # 商品主表。
    __tablename__ = "products"

    # 商品 ID。
    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    # 商品标题。
    title: Mapped[str] = mapped_column(Text)
    # 商品品牌。
    brand: Mapped[str] = mapped_column(String)
    # 商品品类。
    category: Mapped[str] = mapped_column(String)
    # 商品二级品类。
    sub_category: Mapped[str] = mapped_column(String)
    # 基础价格。
    base_price: Mapped[float] = mapped_column(Numeric)
    # 图片路径。
    image_path: Mapped[str] = mapped_column(Text)


class ProductSku(Base):
    # SKU 表。
    __tablename__ = "product_skus"

    # SKU ID。
    sku_id: Mapped[str] = mapped_column(String, primary_key=True)
    # 商品 ID。
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    # SKU 属性。
    properties: Mapped[dict] = mapped_column(JSON)
    # SKU 价格。
    price: Mapped[float] = mapped_column(Numeric)
    # 模拟库存。
    stock: Mapped[int] = mapped_column(default=100)
    # SKU 状态。
    status: Mapped[str] = mapped_column(String, default="available")


class KnowledgeChunk(Base):
    # 商品知识块表。
    __tablename__ = "knowledge_chunks"

    # 知识块 ID。
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 商品 ID。
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    # 知识块类型。
    chunk_type: Mapped[str] = mapped_column(String)
    # 标题。
    title: Mapped[str] = mapped_column(Text)
    # 正文。
    content: Mapped[str] = mapped_column(Text)
    # 元数据。
    metadata_json: Mapped[dict] = mapped_column(JSON)
```

```python
# mallpilot/app/models/trace.py
from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mallpilot.app.models.product import Base


class TraceEventRow(Base):
    # Trace 事件表。
    __tablename__ = "trace_events"

    # Trace ID。
    trace_id: Mapped[str] = mapped_column(String, primary_key=True)
    # 会话 ID。
    chat_id: Mapped[str] = mapped_column(String)
    # 轮次 ID。
    turn_id: Mapped[str] = mapped_column(String)
    # 事件类型。
    event_type: Mapped[str] = mapped_column(String)
    # 阶段名称。
    span_name: Mapped[str] = mapped_column(String)
    # 事件载荷。
    payload: Mapped[dict] = mapped_column(JSON)
    # 状态。
    status: Mapped[str] = mapped_column(String)
    # 错误信息。
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Implement repositories**

```python
# mallpilot/app/repositories/product_repo.py
from sqlalchemy.orm import Session

from mallpilot.app.models.product import KnowledgeChunk, Product, ProductSku


class ProductRepository:
    # 初始化商品仓储。
    def __init__(self, session: Session):
        # 数据库会话。
        self.session = session

    # 保存商品和 SKU。
    def save_product(self, product: dict) -> None:
        self.session.merge(Product(
            product_id=product["product_id"],
            title=product["title"],
            brand=product["brand"],
            category=product["category"],
            sub_category=product["sub_category"],
            base_price=product["base_price"],
            image_path=product["image_path"],
        ))
        for sku in product.get("skus", []):
            self.session.merge(ProductSku(
                sku_id=sku["sku_id"],
                product_id=product["product_id"],
                properties=sku["properties"],
                price=sku["price"],
            ))

    # 保存知识块。
    def save_chunks(self, chunks: list[dict]) -> None:
        for chunk in chunks:
            self.session.add(KnowledgeChunk(
                product_id=chunk["product_id"],
                chunk_type=chunk["chunk_type"],
                title=chunk["title"],
                content=chunk["content"],
                metadata_json=chunk["metadata"],
            ))
```

```python
# mallpilot/app/repositories/trace_repo.py
from sqlalchemy.orm import Session

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.models.trace import TraceEventRow


class TraceRepository:
    # 初始化 Trace 仓储。
    def __init__(self, session: Session):
        # 数据库会话。
        self.session = session

    # 保存 Trace 事件。
    def save(self, event: TraceEvent) -> None:
        self.session.add(TraceEventRow(
            trace_id=event.trace_id,
            chat_id=event.chat_id,
            turn_id=event.turn_id,
            event_type=event.event_type,
            span_name=event.span_name,
            payload=event.payload,
            status=event.status,
            error_message=event.error_message,
        ))
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_ingestion_integration.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mallpilot/app/models mallpilot/app/repositories scripts/ingest_products.py tests/test_ingestion_integration.py
git commit -m "feat: add database models and repositories"
```

---

## Self-Review

Spec coverage:

- Python FastAPI backend: Tasks 1 and 8.
- No LangGraph, self-built Router/Flow: Tasks 5, 6, 7.
- Hybrid retrieval with BM25, vector, optional image, RRF, Cross-Encoder: Task 3.
- SSE structured event protocol: Tasks 1, 4, 8.
- Observability UI: Task 9.
- Product ingestion and UTF-8 data loading: Task 2.
- Cart, order, after-sale mock flows: Task 7.
- Persistence path: Task 10.

Placeholder scan:

- No placeholder markers or unspecified test-writing steps remain.

Type consistency:

- `SseEvent`, `TraceEvent`, `IntentResult`, `ProductCandidate`, `FlowContext`, and `HybridProductSearch.search` signatures are introduced before they are consumed.
