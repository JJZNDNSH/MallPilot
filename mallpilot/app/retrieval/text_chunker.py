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
