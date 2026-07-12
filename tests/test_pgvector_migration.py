from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql

from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk
from mallpilot.app.models.vector import Vector


# 验证知识块模型暴露了 embedding 向量字段。
def test_knowledge_chunk_has_embedding_column_on_metadata():
    assert "embedding" in KnowledgeChunk.__table__.columns


# 验证 SQLite 测试环境可以创建包含向量字段的表。
def test_sqlite_metadata_can_create_vector_backed_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    assert "knowledge_chunks" in Base.metadata.tables


# 验证迁移脚本启用了 pgvector 并声明了 embedding 列。
def test_migration_enables_pgvector_and_embedding_column():
    migration = Path("migrations/versions/202607120002_pgvector_core.py").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "knowledge_chunks" in migration
    assert "embedding" in migration
    assert "VECTOR(1024)" in migration


# 验证 PostgreSQL 下会通过 pgvector 官方绑定处理器生成可写入的文本格式。
def test_vector_binds_pgvector_literal_for_postgresql():
    processor = Vector(3).bind_processor(postgresql.dialect())
    value = processor([1, 2, 3]) if processor else None

    assert value == "[1.0,2.0,3.0]"


# 验证 PostgreSQL 下会解析为 pgvector 官方 VECTOR 类型。
def test_vector_uses_pgvector_type_engine_for_postgresql():
    compiled_type = str(Vector(3).type_engine(postgresql.dialect()))

    assert compiled_type == "VECTOR(3)"
