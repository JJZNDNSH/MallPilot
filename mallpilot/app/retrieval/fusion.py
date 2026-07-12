from typing import Any


# 使用 RRF 融合多路召回结果。
def reciprocal_rank_fusion(result_sets: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}

    # 每一路召回按排名给同一商品累加 RRF 分。
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
