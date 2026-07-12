from pathlib import Path

from sqlalchemy import text

from mallpilot.app.core.config import Settings
from mallpilot.app.db.session import create_engine_from_settings, create_session_factory


# 验证本地环境变量文件不会被提交。
def test_env_file_is_gitignored():
    assert ".env" in Path(".gitignore").read_text(encoding="utf-8")


# 验证百炼和向量相关配置有安全默认值。
def test_settings_expose_bailian_and_embedding_defaults(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "test-key")
    monkeypatch.setenv("BAILIAN_RERANK_MODEL", "qwen3-rerank")
    settings = Settings()

    assert settings.bailian_api_key == "test-key"
    assert settings.bailian_llm_model == "qwen-plus"
    assert settings.bailian_embedding_model == "text-embedding-v4"
    assert settings.bailian_rerank_model == "qwen3-rerank"
    assert settings.bailian_rerank_instruct
    assert settings.embedding_dimension == 1024


# 验证数据库会话工厂可以执行基础查询。
def test_create_session_factory_runs_sqlite_query():
    engine = create_engine_from_settings("sqlite+pysqlite:///:memory:")
    SessionLocal = create_session_factory(engine)

    with SessionLocal() as session:
        assert session.execute(text("select 1")).scalar_one() == 1
