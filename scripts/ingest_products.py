import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from mallpilot.app.core.config import get_settings
from mallpilot.app.db.session import create_engine_from_settings, create_session_factory
from mallpilot.app.repositories.product_repo import ProductRepository
from mallpilot.app.retrieval.text_chunker import build_knowledge_chunks
from mallpilot.app.services.embedding_service import EmbeddingService


# 按 UTF-8 读取数据集中的全部商品 JSON。
def load_product_files(dataset_dir: str) -> list[dict[str, Any]]:
    root = Path(dataset_dir)
    products: list[dict[str, Any]] = []

    # 数据集按品类目录组织，每个品类下的 data 目录保存商品 JSON。
    for path in sorted(root.glob("*/data/*.json")):
        products.append(json.loads(path.read_text(encoding="utf-8")))
    return products


# 将商品列表持久化为商品、SKU 和知识块。
def persist_products(
    session: Session,
    products: list[dict[str, Any]],
    embedding_service: EmbeddingService | None = None,
) -> None:
    # 商品仓储封装具体 ORM 写入逻辑，脚本只负责编排导入流程。
    repository = ProductRepository(session)

    for product in products:
        # 每个商品先写基础信息和 SKU，再用最新解析结果替换知识块。
        repository.save_product(product)
        repository.delete_chunks_for_product(product["product_id"])
        chunks = build_knowledge_chunks(product)

        if embedding_service is None:
            # 未提供 embedding 服务时保持旧行为，便于单元测试和轻量导入。
            repository.save_chunks(chunks)
            continue

        # 提供 embedding 服务时把 chunk 正文向量化后写入 pgvector 字段。
        embeddings = embedding_service.embed_chunks(chunks)
        repository.save_chunks_with_embeddings(chunks, embeddings)


# 运行商品入库流程并返回导入商品数量。
def run_ingestion(
    database_url: str | None = None,
    dataset_dir: str | None = None,
    embedding_service: EmbeddingService | None = None,
) -> int:
    settings = get_settings()
    products = load_product_files(dataset_dir or settings.dataset_dir)
    engine = create_engine_from_settings(database_url or settings.database_url)
    SessionLocal = create_session_factory(engine)
    service = embedding_service or EmbeddingService(settings=settings)

    with SessionLocal() as session:
        try:
            # 入库事务内完成商品、SKU、chunk 和 embedding 写入。
            persist_products(session, products, embedding_service=service)
            session.commit()
        except Exception:
            session.rollback()
            raise

    return len(products)


# 命令行入口，执行真实入库并输出导入数量。
def main() -> None:
    imported_count = run_ingestion()
    print(f"ingested_products={imported_count}")


if __name__ == "__main__":
    main()
