from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from mallpilot.app.core.config import get_settings


# 根据配置创建数据库引擎。
def create_engine_from_settings(database_url: str | None = None) -> Engine:
    # 允许测试传入 SQLite URL，生产环境默认读取 Settings.database_url。
    url = database_url or get_settings().database_url
    return create_engine(url, future=True)


# 根据数据库引擎创建会话工厂。
def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False 让 API 层提交后仍可读取对象字段。
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


# 应用默认数据库引擎，首次使用时再创建，避免测试导入时要求本机 PostgreSQL 驱动可用。
engine: Engine | None = None
# 应用默认数据库会话工厂，首次使用时再创建。
SessionLocal: sessionmaker[Session] | None = None


# 获取默认会话工厂。
def get_session_factory() -> sessionmaker[Session]:
    global engine, SessionLocal

    # 延迟创建默认 engine，避免模块导入阶段连接真实数据库。
    if engine is None:
        engine = create_engine_from_settings()
    if SessionLocal is None:
        SessionLocal = create_session_factory(engine)
    return SessionLocal


# FastAPI 数据库依赖，负责请求结束时关闭会话。
def get_db() -> Iterator[Session]:
    # 每次请求创建独立 session，避免跨请求共享事务状态。
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
