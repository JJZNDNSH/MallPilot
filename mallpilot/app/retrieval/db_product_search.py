import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mallpilot.app.agent.schemas import ProductCandidate, TraceEvent
from mallpilot.app.llm.bailian_client import BailianClient
from mallpilot.app.llm.schemas import RerankScore
from mallpilot.app.models.product import KnowledgeChunk, Product
from mallpilot.app.retrieval.bm25_search import BM25Search
from mallpilot.app.retrieval.fusion import reciprocal_rank_fusion


class DatabaseProductSearch:
    # 初始化数据库混合检索门面。
    def __init__(self, session: Session, bailian_client: BailianClient | Any | None = None):
        # 当前数据库会话。
        self.session = session
        # 百炼客户端用于 query embedding 和 rerank，测试可注入 fake。
        self.bailian_client = bailian_client or BailianClient()
        # 最近一次 rerank 错误，写入 Trace 方便观测面板排查。
        self.last_rerank_error: str | None = None

    # 执行数据库混合检索。
    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        image_embedding: list[float] | None = None,
        top_k: int = 5,
    ) -> tuple[list[ProductCandidate], list[TraceEvent]]:
        active_filters = filters or {}
        # 每次检索开始前清理上一轮 rerank 错误。
        self.last_rerank_error = None
        documents = self._load_documents(active_filters)
        bm25_results = BM25Search(documents).search(query, active_filters, top_k=top_k * 4)
        vector_results = self._vector_search(query, documents, top_k=top_k * 4)

        # 图片向量在本任务只保留接口形态，真实图片 embedding 后续接入。
        result_sets = [bm25_results, vector_results]
        fused = reciprocal_rank_fusion(result_sets)[: top_k * 4]
        reranked = self._rerank(query, fused, top_k)
        candidates = self._to_candidates(reranked[:top_k])
        trace = self._build_trace(len(bm25_results), len(vector_results), len(fused), len(reranked))
        return candidates, trace

    # 从数据库加载符合结构化约束的知识块文档。
    def _load_documents(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        statement = select(Product, KnowledgeChunk).join(KnowledgeChunk, Product.product_id == KnowledgeChunk.product_id)

        # 结构化过滤先在数据库侧完成，减少后续召回候选规模。
        if filters.get("category"):
            statement = statement.where(Product.category == filters["category"])
        if filters.get("sub_category"):
            statement = statement.where(Product.sub_category == filters["sub_category"])
        if filters.get("brand"):
            statement = statement.where(Product.brand == filters["brand"])
        if filters.get("budget_max") is not None:
            statement = statement.where(Product.base_price <= float(filters["budget_max"]))

        documents: list[dict[str, Any]] = []
        for product, chunk in self.session.execute(statement).all():
            documents.append({
                "product_id": product.product_id,
                "title": product.title,
                "brand": product.brand,
                "category": product.category,
                "sub_category": product.sub_category,
                "price": float(product.base_price or 0),
                "image_url": product.image_url,
                "content": chunk.content,
                "chunk_type": chunk.chunk_type,
                "embedding": chunk.embedding,
                "sku_summary": _build_sku_summary(product.raw_json),
            })
        return documents

    # 使用 query embedding 和 chunk embedding 做语义召回。
    def _vector_search(self, query: str, documents: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if not documents:
            return []

        query_embedding = self.bailian_client.embed_texts([query], text_type="query")[0]
        scored: list[dict[str, Any]] = []
        for document in documents:
            embedding = document.get("embedding")
            if not embedding:
                continue

            # SQLite 测试中在 Python 计算余弦相似度；PostgreSQL 可在后续替换为 pgvector SQL。
            score = _cosine_similarity(query_embedding, embedding)
            scored.append({"document": document, "score": score})

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    # 使用百炼 rerank 对 RRF 融合结果精排。
    def _rerank(self, query: str, fused: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if not fused:
            return []

        documents = [item["document"].get("content", "") for item in fused]
        try:
            # 百炼 rerank 失败时不影响召回结果展示，后续通过 Trace 暴露错误。
            scores = self.bailian_client.rerank(query, documents, top_n=top_k)
        except Exception as exc:
            self.last_rerank_error = str(exc.__class__.__name__)
            return [{**item, "final_score": float(item.get("rrf_score", 0.0))} for item in fused]

        if not scores:
            return [{**item, "final_score": float(item.get("rrf_score", 0.0))} for item in fused]

        reranked: list[dict[str, Any]] = []
        for score in scores:
            if score.index >= len(fused):
                continue
            item = fused[score.index]
            reranked.append({**item, "final_score": score.score})
        return reranked

    # 将检索内部结构转换为导购候选商品。
    def _to_candidates(self, items: list[dict[str, Any]]) -> list[ProductCandidate]:
        candidates: list[ProductCandidate] = []
        for item in items:
            document = item["document"]
            candidates.append(ProductCandidate(
                product_id=document["product_id"],
                title=document["title"],
                brand=document.get("brand"),
                category=document.get("category"),
                price=float(document.get("price") or 0),
                image_url=document.get("image_url"),
                score=float(item.get("final_score", item.get("rrf_score", 0.0))),
                evidence=[{
                    "source": "database_retrieval",
                    "summary": _shorten_summary(document.get("content", "")),
                    "raw_summary": document.get("content", ""),
                    "sub_category": document.get("sub_category"),
                    "sku_summary": document.get("sku_summary"),
                }],
            ))
        return candidates

    # 构造检索 Trace。
    def _build_trace(self, bm25_count: int, vector_count: int, fused_count: int, rerank_count: int) -> list[TraceEvent]:
        trace = [
            _trace("retrieval.bm25", {"count": bm25_count}),
            _trace("retrieval.vector", {"count": vector_count}),
            _trace("retrieval.rrf", {"count": fused_count}),
            _trace("rerank.bailian", {"count": rerank_count}),
        ]
        if self.last_rerank_error is not None:
            # rerank 失败不阻塞推荐，但要在 Trace 中显式标记。
            trace.append(TraceEvent(
                chat_id="retrieval",
                turn_id="retrieval",
                event_type="rerank.error",
                span_name="database_product_search",
                payload={"message": self.last_rerank_error},
                status="error",
            ))
        return trace


# 计算两个向量的余弦相似度。
def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


# 构造 SKU 摘要，避免前端商品卡直接展示完整 raw_json。
def _build_sku_summary(raw_json: dict[str, Any]) -> str:
    skus = raw_json.get("skus", []) if raw_json else []
    if not skus:
        return ""

    summaries: list[str] = []
    for sku in skus[:3]:
        # SKU 属性通常包含容量、存储、版本等导购关键信息。
        properties = sku.get("properties", {})
        property_text = "，".join(f"{key}:{value}" for key, value in properties.items())
        price_text = f"¥{float(sku.get('price', 0)):.0f}" if sku.get("price") is not None else "价格待确认"
        summaries.append(f"{property_text} {price_text}".strip())
    return "；".join(summaries)


# 压缩证据摘要，保证商品卡理由短而可读。
def _shorten_summary(content: str, max_length: int = 96) -> str:
    text = " ".join(str(content).split())
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


# 创建检索 Trace 事件。
def _trace(event_type: str, payload: dict[str, Any]) -> TraceEvent:
    return TraceEvent(
        chat_id="retrieval",
        turn_id="retrieval",
        event_type=event_type,
        span_name="database_product_search",
        payload=payload,
    )
