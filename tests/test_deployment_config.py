from pathlib import Path

from mallpilot.app.core.config import Settings


# 验证默认数据库地址已经指向虚拟机 PostgreSQL。
def test_settings_default_database_url_points_to_vm():
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://postgres:postgres@192.168.154.128:5432/mallpilot"


# 验证 docker-compose 使用 pgvector 镜像并暴露标准端口。
def test_docker_compose_uses_pgvector_image():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "pgvector/pgvector:pg16" in compose
    assert "\"5432:5432\"" in compose
    assert "POSTGRES_DB: mallpilot" in compose


# 验证 README 记录了虚拟机数据库地址和启动步骤。
def test_readme_documents_vm_database_setup():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "192.168.154.128" in readme
    assert "docker compose up -d" in readme
    assert "alembic upgrade head" in readme
