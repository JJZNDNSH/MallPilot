from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from mallpilot.app.core.config import get_settings
from mallpilot.app.models.base import Base
from mallpilot.app.models.product import KnowledgeChunk, Product, ProductSku
from mallpilot.app.models.trace import TraceEventRow

# Alembic 配置对象。
config = context.config

# 初始化 Alembic 日志配置。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 显式引用模型，确保 metadata 包含所有表。
_metadata_models = (Product, ProductSku, KnowledgeChunk, TraceEventRow)
# 自动迁移对比使用的 SQLAlchemy 元数据。
target_metadata = Base.metadata


# 获取数据库连接字符串。
def get_url() -> str:
    return get_settings().database_url


# 离线模式生成 SQL。
def run_migrations_offline() -> None:
    # 离线迁移只需要 URL，不创建数据库连接。
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


# 在线模式执行迁移。
def run_migrations_online() -> None:
    # Alembic 使用应用配置中的数据库连接字符串。
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
