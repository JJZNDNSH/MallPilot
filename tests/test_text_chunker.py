from mallpilot.app.retrieval.text_chunker import build_knowledge_chunks
from scripts.ingest_products import load_product_files


# 验证商品知识会被拆成基础、营销、FAQ、评论摘要四类块。
def test_build_knowledge_chunks_splits_faq_individually():
    product = {
        "product_id": "p_1",
        "title": "测试精华",
        "brand": "测试品牌",
        "category": "美妆护肤",
        "sub_category": "精华",
        "base_price": 199,
        "skus": [{"sku_id": "s_1", "properties": {"容量": "30ml"}, "price": 199}],
        "rag_knowledge": {
            "marketing_description": "主打保湿修护。",
            "official_faq": [{"question": "敏感肌能用吗？", "answer": "建议先做测试。"}],
            "user_reviews": [{"rating": 5, "content": "保湿不错。"}],
        },
    }

    chunks = build_knowledge_chunks(product)

    assert [chunk["chunk_type"] for chunk in chunks] == ["basic", "marketing", "faq", "review_summary"]
    assert chunks[2]["title"] == "敏感肌能用吗？"
    assert "建议先做测试" in chunks[2]["content"]


# 验证本地数据集以 UTF-8 读取时能得到完整 100 个商品。
def test_load_product_files_reads_all_dataset_products():
    products = load_product_files("data/ecommerce_agent_dataset")

    assert len(products) == 100
    assert products[0]["product_id"].startswith("p_")
