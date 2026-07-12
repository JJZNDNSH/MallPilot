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

        # 图片召回只有在用户上传图片时才进入 RRF。
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
