from typing import Any

from mallpilot.app.retrieval.bm25_search import match_filters


class ImageSearch:
    # 初始化图片向量召回器。
    def __init__(self, documents: list[dict[str, Any]]):
        # 原始文档列表。
        self.documents = documents

    # 根据图片向量召回候选；无图片向量时不参与召回。
    def search(self, image_embedding: list[float] | None, filters: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
        if image_embedding is None:
            return []

        scored: list[dict[str, Any]] = []
        # MVP 阶段先用稳定分数占位，后续替换为真实图片向量相似度。
        for doc in self.documents:
            if match_filters(doc, filters):
                scored.append({"document": doc, "score": 0.1})

        return scored[:top_k]
