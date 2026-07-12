from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mallpilot.app.llm.schemas import RerankScore
from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk, Product
from mallpilot.app.retrieval.db_product_search import DatabaseProductSearch


class FakeBailianClient:
    # 为测试生成固定查询向量。
    def embed_texts(self, texts: list[str], text_type: str = "query") -> list[list[float]]:
        return [[1.0] * 1024 for _text in texts]

    # 为测试返回稳定重排结果。
    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[RerankScore]:
        return [RerankScore(index=0, score=0.99)]


# 写入测试商品和知识块。
def _seed_products(session: Session) -> None:
    session.add_all([
        Product(
            product_id="p_1",
            title="普通面霜",
            brand="测试品牌A",
            category="美妆护肤",
            sub_category="面霜",
            base_price=99,
            image_url="https://example.com/p_1.jpg",
            raw_json={"skus": [{"sku_id": "s_1", "properties": {"容量": "50g"}, "price": 99}]},
        ),
        Product(
            product_id="p_2",
            title="保湿修护精华",
            brand="测试品牌B",
            category="美妆护肤",
            sub_category="精华",
            base_price=199,
            image_url="https://example.com/p_2.jpg",
            raw_json={"skus": [{"sku_id": "s_2", "properties": {"容量": "30ml"}, "price": 199}]},
        ),
    ])
    session.add_all([
        KnowledgeChunk(
            product_id="p_1",
            chunk_type="marketing",
            title="普通面霜",
            content="基础滋润面霜",
            embedding=[0.0] * 1024,
            metadata_json={"source": "test"},
        ),
        KnowledgeChunk(
            product_id="p_2",
            chunk_type="marketing",
            title="保湿修护精华",
            content="适合敏感肌的保湿修护精华",
            embedding=[1.0] * 1024,
            metadata_json={"source": "test"},
        ),
    ])
    session.commit()


# 验证数据库检索会执行关键词、向量、RRF 和百炼重排。
def test_database_product_search_returns_candidates_and_trace():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        _seed_products(session)
        search = DatabaseProductSearch(session=session, bailian_client=FakeBailianClient())

        candidates, trace = search.search("敏感肌保湿精华", filters={"category": "美妆护肤"}, top_k=1)

    assert candidates[0].product_id == "p_2"
    assert candidates[0].score == 0.99
    assert candidates[0].evidence[0]["source"] == "database_retrieval"
    assert candidates[0].evidence[0]["summary"] == "适合敏感肌的保湿修护精华"
    assert candidates[0].evidence[0]["sku_summary"] == "容量:30ml ¥199"
    assert [event.event_type for event in trace] == [
        "retrieval.bm25",
        "retrieval.vector",
        "retrieval.rrf",
        "rerank.bailian",
    ]


# 验证数据库检索会应用品牌过滤条件。
def test_database_product_search_filters_by_brand():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        _seed_products(session)
        search = DatabaseProductSearch(session=session, bailian_client=FakeBailianClient())

        candidates, _trace = search.search("保湿精华", filters={"category": "美妆护肤", "brand": "测试品牌B"}, top_k=1)

    assert candidates[0].product_id == "p_2"
    assert candidates[0].brand == "测试品牌B"
