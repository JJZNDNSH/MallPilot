from mallpilot.app.retrieval.product_search import HybridProductSearch


# 验证混合检索会执行 BM25、文本向量、RRF 融合和 Cross-Encoder 精排。
def test_hybrid_search_uses_bm25_vector_rrf_and_cross_encoder():
    docs = [
        {"product_id": "p_1", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"},
        {"product_id": "p_2", "title": "运动鞋", "content": "跑步 缓震", "price": 499, "category": "服饰运动"},
    ]
    search = HybridProductSearch.from_documents(docs)

    results, trace = search.search(
        query="300元以内敏感肌修护精华",
        filters={"category": "美妆护肤", "budget_max": 300},
    )

    assert results[0].product_id == "p_1"
    assert [event["event_type"] for event in trace] == [
        "bm25_result",
        "text_vector_result",
        "rrf_fusion_result",
        "cross_encoder_rerank_result",
    ]


# 验证用户传入图片向量时，图片召回也会进入 Trace。
def test_hybrid_search_adds_image_vector_trace_when_image_embedding_exists():
    docs = [
        {"product_id": "p_1", "title": "白色运动鞋", "content": "白色 跑步 缓震", "price": 399, "category": "服饰运动"},
        {"product_id": "p_2", "title": "黑色T恤", "content": "黑色 纯棉", "price": 99, "category": "服饰运动"},
    ]
    search = HybridProductSearch.from_documents(docs)

    results, trace = search.search(
        query="找类似图片的白色鞋",
        filters={"category": "服饰运动", "budget_max": 500},
        image_embedding=[0.1, 0.2, 0.3],
    )

    assert results
    assert "image_vector_result" in [event["event_type"] for event in trace]
