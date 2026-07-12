from pathlib import Path

from sqlalchemy import create_engine

from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk


# 验证知识块模型暴露 pgvector 向量字段。
def test_knowledge_chunk_has_embedding_column_on_metadata():
    assert "embedding" in KnowledgeChunk.__table__.columns


# 验证测试环境可以用 SQLite 创建包含向量字段的表。
def test_sqlite_metadata_can_create_vector_backed_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    assert "knowledge_chunks" in Base.metadata.tables


# 验证迁移脚本启用 pgvector 并创建 embedding 字段。
def test_migration_enables_pgvector_and_embedding_column():
    migration = Path("migrations/versions/202607120002_pgvector_core.py").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "knowledge_chunks" in migration
    assert "embedding" in migration
    assert "VECTOR(1024)" in migration
