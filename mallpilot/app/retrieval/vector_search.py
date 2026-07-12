from typing import Any

from mallpilot.app.retrieval.bm25_search import match_filters


class VectorSearch:
    # 初始化轻量语义搜索，MVP 测试环境用字符重合模拟向量相似度。
    def __init__(self, documents: list[dict[str, Any]]):
        # 原始文档列表。
        self.documents = documents

    # 执行文本向量召回。
    def search(self, query: str, filters: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
        query_chars = set(query.lower())
        scored: list[dict[str, Any]] = []

        # MVP 阶段用可替换的轻量相关性打分，接口保持向量召回形态。
        for doc in self.documents:
            if not match_filters(doc, filters):
                continue
            content = (doc.get("title", "") + doc.get("content", "")).lower()
            score = len(query_chars & set(content)) / max(len(query_chars), 1)
            scored.append({"document": doc, "score": score})

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]
