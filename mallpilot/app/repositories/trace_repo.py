from sqlalchemy.orm import Session

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.models.trace import TraceEventRow


class TraceRepository:
    # 初始化 Trace 仓储。
    def __init__(self, session: Session):
        # 当前数据库会话。
        self.session = session

    # 保存 Trace 事件。
    def save(self, event: TraceEvent) -> None:
        self.session.add(TraceEventRow(
            trace_id=event.trace_id,
            chat_id=event.chat_id,
            turn_id=event.turn_id,
            event_type=event.event_type,
            span_name=event.span_name,
            payload=event.payload,
            status=event.status,
            error_message=event.error_message,
            duration_ms=event.duration_ms,
            timestamp=event.timestamp,
        ))
