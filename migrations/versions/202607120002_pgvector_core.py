from alembic import op
import sqlalchemy as sa


# Alembic 版本号。
revision = "202607120002"
# 上一个版本号；本仓库此前没有 Alembic migration。
down_revision = None
# 分支标签。
branch_labels = None
# 依赖版本。
depends_on = None


# 创建 PostgreSQL + pgvector 核心表。
def upgrade() -> None:
    # 启用 pgvector 扩展，允许 knowledge_chunks.embedding 使用 VECTOR(1024)。
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "products",
        sa.Column("product_id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("sub_category", sa.String(length=128), nullable=True),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "product_skus",
        sa.Column("sku_id", sa.String(length=64), primary_key=True),
        sa.Column("product_id", sa.String(length=64), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
    )
    op.create_index("ix_product_skus_product_id", "product_skus", ["product_id"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.String(length=64), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("chunk_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # PostgreSQL 迁移中把 embedding 列调整为 pgvector 类型。
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE VECTOR(1024) USING embedding::vector")
    op.create_index("ix_knowledge_chunks_product_id", "knowledge_chunks", ["product_id"])
    op.create_index("ix_knowledge_chunks_chunk_type", "knowledge_chunks", ["chunk_type"])

    op.create_table(
        "trace_events",
        sa.Column("trace_id", sa.String(length=96), primary_key=True),
        sa.Column("chat_id", sa.String(length=96), nullable=False),
        sa.Column("turn_id", sa.String(length=96), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("span_name", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trace_events_chat_id", "trace_events", ["chat_id"])
    op.create_index("ix_trace_events_turn_id", "trace_events", ["turn_id"])
    op.create_index("ix_trace_events_event_type", "trace_events", ["event_type"])


# 删除 PostgreSQL + pgvector 核心表。
def downgrade() -> None:
    # 按外键依赖反向删除表和索引。
    op.drop_index("ix_trace_events_event_type", table_name="trace_events")
    op.drop_index("ix_trace_events_turn_id", table_name="trace_events")
    op.drop_index("ix_trace_events_chat_id", table_name="trace_events")
    op.drop_table("trace_events")

    op.drop_index("ix_knowledge_chunks_chunk_type", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_product_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("ix_product_skus_product_id", table_name="product_skus")
    op.drop_table("product_skus")
    op.drop_table("products")
