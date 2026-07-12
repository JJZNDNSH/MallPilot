from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mallpilot.app.models.base import Base


class Product(Base):
    # 商品主表名。
    __tablename__ = "products"

    # 商品唯一 ID，对应数据集中的 product_id。
    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 商品标题，用于展示和检索召回。
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 商品品牌，用于筛选和展示。
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 一级品类，用于意图约束和结构化过滤。
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 二级品类，用于更细粒度过滤。
    sub_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 商品基础价格，用于预算约束。
    base_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # 商品主图 URL，用于前端商品卡片。
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 商品原始 JSON，保留导入时未结构化字段。
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # 创建时间，用于后台排查数据导入批次。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 更新时间，用于后续增量导入。
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # 商品关联的 SKU 列表。
    skus: Mapped[list["ProductSku"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    # 商品关联的知识块列表。
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductSku(Base):
    # SKU 表名。
    __tablename__ = "product_skus"

    # SKU 唯一 ID，对应数据集中的 sku_id。
    sku_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # SKU 所属商品 ID。
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False, index=True)
    # SKU 属性，例如容量、颜色、规格。
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # SKU 售价，用于预算和规格选择。
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # SKU 所属商品对象。
    product: Mapped[Product] = relationship(back_populates="skus")


class KnowledgeChunk(Base):
    # 商品知识块表名。
    __tablename__ = "knowledge_chunks"

    # 知识块自增 ID。
    chunk_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 知识块所属商品 ID。
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False, index=True)
    # 知识块类型，例如 basic、marketing、faq、review_summary。
    chunk_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 知识块标题，用于 Trace 和后台查看。
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 知识块正文，用于 BM25、向量化和精排证据。
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 知识块元数据，保留来源、FAQ 问题等辅助信息。
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # 知识块创建时间。
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 知识块所属商品对象。
    product: Mapped[Product] = relationship(back_populates="chunks")
