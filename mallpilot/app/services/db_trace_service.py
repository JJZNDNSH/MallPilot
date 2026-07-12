from sqlalchemy.orm import Session, sessionmaker

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.db.session import get_session_factory
from mallpilot.app.repositories.trace_repo import TraceRepository


class DbTraceService:
    # 初始化数据库版 Trace 服务。
    def __init__(self, session_factory: sessionmaker[Session] | None = None):
        # 数据库会话工厂，测试可注入 SQLite 工厂。
        self.session_factory = session_factory or get_session_factory()

    # 持久化 Trace 事件。
    def record(self, event: TraceEvent) -> None:
        with self.session_factory() as session:
            # 单个 Trace 独立提交，避免聊天流中某个事件丢失整轮记录。
            TraceRepository(session).save(event)
            session.commit()

    # 查询某一轮的 Trace 事件。
    def list_events(self, turn_id: str) -> list[TraceEvent]:
        with self.session_factory() as session:
            return TraceRepository(session).list_by_turn(turn_id)
