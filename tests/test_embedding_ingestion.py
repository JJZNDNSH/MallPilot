import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk, Product
from scripts.ingest_products import persist_products, run_ingestion


class FakeEmbeddingService:
    # 为测试生成固定维度的向量。
    def embed_chunks(self, chunks: list[dict]) -> list[list[float]]:
        return [[float(index)] * 1024 for index, _chunk in enumerate(chunks)]


# 构造最小商品数据。
def _sample_product(product_id: str = "p_1") -> dict:
    return {
        "product_id": product_id,
        "title": "测试精华",
        "brand": "测试品牌",
        "category": "美妆护肤",
        "sub_category": "精华",
        "base_price": 199,
        "image_url": "https://example.com/p_1.jpg",
        "skus": [{"sku_id": f"s_{product_id}", "properties": {"容量": "30ml"}, "price": 199}],
        "rag_knowledge": {
            "marketing_description": "主打保湿修护。",
            "official_faq": [{"question": "敏感肌能用吗？", "answer": "建议先做测试。"}],
            "user_reviews": [{"rating": 5, "content": "保湿不错。"}],
        },
    }


# 验证商品持久化时会把 embedding 写入每个知识块。
def test_persist_products_saves_chunk_embeddings():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        persist_products(session, [_sample_product()], embedding_service=FakeEmbeddingService())
        session.commit()

        chunks = session.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.chunk_id)).all()

    assert len(chunks) == 4
    assert chunks[0].embedding == [0.0] * 1024
    assert chunks[1].embedding == [1.0] * 1024


# 验证入库命令会读取数据目录并返回导入商品数量。
def test_run_ingestion_reads_dataset_and_returns_imported_count(tmp_path: Path):
    dataset_root = tmp_path / "dataset"
    data_dir = dataset_root / "beauty" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "p_1.json").write_text(json.dumps(_sample_product(), ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "mallpilot.db"
    database_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    imported_count = run_ingestion(
        database_url=database_url,
        dataset_dir=str(dataset_root),
        embedding_service=FakeEmbeddingService(),
    )

    with Session(engine) as session:
        product_count = session.scalar(select(func.count()).select_from(Product))
        chunk_count = session.scalar(select(func.count()).select_from(KnowledgeChunk))

    assert imported_count == 1
    assert product_count == 1
    assert chunk_count == 4
