from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from mallpilot.app.models.product import KnowledgeChunk, Product, ProductSku


class ProductRepository:
    # 初始化商品仓储。
    def __init__(self, session: Session):
        # 当前数据库会话。
        self.session = session

    # 保存或更新商品基础信息和 SKU。
    def save_product(self, product: dict[str, Any]) -> None:
        # 商品主表使用 merge 支持重复导入时覆盖基础字段。
        self.session.merge(Product(
            product_id=product["product_id"],
            title=product.get("title", ""),
            brand=product.get("brand"),
            category=product.get("category"),
            sub_category=product.get("sub_category"),
            base_price=product.get("base_price"),
            image_url=product.get("image_url"),
            raw_json=product,
        ))

        # SKU 也使用 merge，确保同一个 sku_id 再导入时更新价格和属性。
        for sku in product.get("skus", []):
            self.session.merge(ProductSku(
                sku_id=sku["sku_id"],
                product_id=product["product_id"],
                properties=sku.get("properties", {}),
                price=sku.get("price"),
            ))

    # 删除某个商品的旧知识块。
    def delete_chunks_for_product(self, product_id: str) -> None:
        self.session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.product_id == product_id))

    # 保存商品知识块。
    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        for chunk in chunks:
            # 知识块使用新增记录，导入流程会先删除旧块再写入新块。
            self.session.add(KnowledgeChunk(
                product_id=chunk["product_id"],
                chunk_type=chunk["chunk_type"],
                title=chunk.get("title", ""),
                content=chunk.get("content", ""),
                metadata_json=chunk.get("metadata", {}),
            ))
