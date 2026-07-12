from mallpilot.app.agent.schemas import ProductCandidate
from mallpilot.app.tools.product_tools import build_product_card


# 验证商品卡 payload 包含前端导购展示所需的精简字段。
def test_build_product_card_uses_short_reason_and_sku_summary():
    candidate = ProductCandidate(
        product_id="p_1",
        title="测试手机",
        brand="测试品牌",
        category="数码电子",
        price=2999,
        evidence=[{
            "summary": "适合拍照和长续航",
            "raw_summary": "很长的原始证据",
            "sub_category": "智能手机",
            "sku_summary": "12GB+256GB ¥2999",
        }],
    )

    card = build_product_card(candidate)

    assert card["reason"] == "适合拍照和长续航"
    assert card["sub_category"] == "智能手机"
    assert card["sku_summary"] == "12GB+256GB ¥2999"
    assert card["brand"] == "测试品牌"
