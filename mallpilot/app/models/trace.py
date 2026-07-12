from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from mallpilot.app.models.base import Base


class TraceEventRow(Base):
    # Trace 事件表名。
    __tablename__ = "trace_events"

    # Trace 事件唯一 ID。
    trace_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    # 当前会话 ID。
    chat_id: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    # 当前轮次 ID。
    turn_id: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    # Trace 事件类型，例如 llm_call、retrieval、sse_emit。
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Trace 所属执行阶段名称。
    span_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Trace 业务载荷。
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # Trace 执行状态。
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    # Trace 错误信息。
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Trace 耗时，单位毫秒。
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    # Trace 事件产生时间。
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
