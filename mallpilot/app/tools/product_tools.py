from mallpilot.app.agent.schemas import ProductCandidate


# 将检索候选转成商品卡片 payload。
def build_product_card(candidate: ProductCandidate) -> dict:
    # 取第一条证据作为商品卡推荐理由和辅助信息来源。
    primary_evidence = candidate.evidence[0] if candidate.evidence else {}
    # 优先使用检索层压缩后的摘要，避免前端展示过长原始 chunk。
    reason = primary_evidence.get("summary", "")
    return {
        "product_id": candidate.product_id,
        "title": candidate.title,
        "brand": candidate.brand,
        "category": candidate.category,
        "sub_category": primary_evidence.get("sub_category"),
        "price": candidate.price,
        "image_url": candidate.image_url,
        "reason": reason,
        "reasons": [item.get("summary", "") for item in candidate.evidence[:2] if item.get("summary")],
        "sku_summary": primary_evidence.get("sku_summary"),
        "evidence": candidate.evidence,
        "actions": [
            {"type": "view_detail", "label": "查看详情"},
            {"type": "add_to_cart", "label": "加入购物车"},
        ],
    }
