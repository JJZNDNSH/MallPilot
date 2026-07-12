from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk, Product, ProductSku
from mallpilot.app.models.trace import TraceEventRow
from mallpilot.app.repositories.trace_repo import TraceRepository
from scripts.ingest_products import persist_products


# 验证商品导入流程会持久化商品、SKU 和知识块。
def test_persist_products_saves_product_skus_and_chunks():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    product = {
        "product_id": "p_1",
        "title": "测试精华",
        "brand": "测试品牌",
        "category": "美妆护肤",
        "sub_category": "精华",
        "base_price": 199,
        "image_url": "https://example.com/p_1.jpg",
        "skus": [{"sku_id": "s_1", "properties": {"容量": "30ml"}, "price": 199}],
        "rag_knowledge": {
            "marketing_description": "主打保湿修护。",
            "official_faq": [{"question": "敏感肌能用吗？", "answer": "建议先做测试。"}],
            "user_reviews": [{"rating": 5, "content": "保湿不错。"}],
        },
    }

    with Session(engine) as session:
        persist_products(session, [product])
        session.commit()

        saved_product = session.get(Product, "p_1")
        sku_count = session.scalar(select(func.count()).select_from(ProductSku))
        chunk_count = session.scalar(select(func.count()).select_from(KnowledgeChunk))

    assert saved_product is not None
    assert saved_product.title == "测试精华"
    assert sku_count == 1
    assert chunk_count == 4


# 验证 Trace 仓储会持久化可观测事件。
def test_trace_repository_saves_trace_events():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    event = TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type="llm_call",
        span_name="router",
        payload={"model": "mock"},
        duration_ms=12,
    )

    with Session(engine) as session:
        TraceRepository(session).save(event)
        session.commit()

        saved_event = session.get(TraceEventRow, event.trace_id)

    assert saved_event is not None
    assert saved_event.payload["model"] == "mock"
    assert saved_event.duration_ms == 12
