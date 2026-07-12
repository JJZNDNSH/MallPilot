from typing import Any


class CrossEncoderReranker:
    # 初始化 Cross-Encoder 精排器，MVP 先用可替换的轻量打分。
    def __init__(self):
        pass

    # 对融合候选进行精排。
    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        query_chars = set(query)

        # 用 query 与候选文本的字符重合模拟 Cross-Encoder 相关性。
        for item in candidates:
            doc = item["document"]
            content = doc.get("title", "") + doc.get("content", "")
            cross_score = len(query_chars & set(content)) / max(len(query_chars), 1)
            final_score = cross_score * 0.7 + item.get("rrf_score", 0.0) * 0.3
            ranked.append({**item, "cross_encoder_score": cross_score, "final_score": final_score})

        ranked.sort(key=lambda item: item["final_score"], reverse=True)
        return ranked[:top_k]
