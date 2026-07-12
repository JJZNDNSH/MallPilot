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
