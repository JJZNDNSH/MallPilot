from typing import Any

from sqlalchemy import func, select
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

    # 按 turn_id 查询 Trace 事件。
    def list_by_turn(self, turn_id: str) -> list[TraceEvent]:
        statement = select(TraceEventRow).where(TraceEventRow.turn_id == turn_id).order_by(TraceEventRow.timestamp)
        rows = self.session.scalars(statement).all()

        return [
            TraceEvent(
                trace_id=row.trace_id,
                chat_id=row.chat_id,
                turn_id=row.turn_id,
                event_type=row.event_type,
                span_name=row.span_name,
                payload=row.payload,
                status=row.status,
                error_message=row.error_message,
                duration_ms=row.duration_ms,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    # 查询最近可观测轮次，供前端下拉框选择。
    def list_turns(self, limit: int = 50) -> list[dict[str, Any]]:
        statement = (
            select(
                TraceEventRow.turn_id,
                TraceEventRow.chat_id,
                func.count(TraceEventRow.trace_id).label("event_count"),
                func.min(TraceEventRow.timestamp).label("started_at"),
            )
            .group_by(TraceEventRow.turn_id, TraceEventRow.chat_id)
            .order_by(func.min(TraceEventRow.timestamp))
            .limit(limit)
        )
        rows = self.session.execute(statement).all()

        turns: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            # 前端只展示 label，turn_id 作为内部加载 summary 的值。
            turns.append({
                "label": f"第 {index} 轮",
                "turn_id": row.turn_id,
                "chat_id": row.chat_id,
                "event_count": int(row.event_count),
                "started_at": row.started_at.isoformat() if row.started_at else None,
            })
        return turns
