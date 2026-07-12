import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from mallpilot.app.repositories.product_repo import ProductRepository
from mallpilot.app.retrieval.text_chunker import build_knowledge_chunks


# 按 UTF-8 读取数据集中的全部商品 JSON。
def load_product_files(dataset_dir: str) -> list[dict[str, Any]]:
    root = Path(dataset_dir)
    products: list[dict[str, Any]] = []

    # 数据集按品类目录组织，每个品类下的 data 目录保存商品 JSON。
    for path in sorted(root.glob("*/data/*.json")):
        products.append(json.loads(path.read_text(encoding="utf-8")))
    return products


# 将商品列表持久化为商品、SKU 和知识块。
def persist_products(session: Session, products: list[dict[str, Any]]) -> None:
    # 商品仓储封装具体 ORM 写入逻辑，脚本只负责编排导入流程。
    repository = ProductRepository(session)

    for product in products:
        # 每个商品先写基础信息和 SKU，再用最新解析结果替换知识块。
        repository.save_product(product)
        repository.delete_chunks_for_product(product["product_id"])
        repository.save_chunks(build_knowledge_chunks(product))


# 命令行入口，先输出数量用于校验数据集。
def main() -> None:
    products = load_product_files("data/ecommerce_agent_dataset")
    print(f"loaded_products={len(products)}")


if __name__ == "__main__":
    main()
