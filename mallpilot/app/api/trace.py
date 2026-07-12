from fastapi import APIRouter

from mallpilot.app.services.db_trace_service import DbTraceService
from mallpilot.app.services.trace_summary import build_empty_trace_summary, build_trace_summary

router = APIRouter(prefix="/api/trace", tags=["trace"])
# Trace 查询接口使用数据库持久化实现，保证与 ChatService 写入的事件一致。
trace_service = DbTraceService()


# 查询可供下拉选择的 Trace 轮次。
@router.get("/turns")
def list_turns() -> dict:
    try:
        # 数据库可用时返回真实轮次列表。
        turns = trace_service.list_turns()
    except Exception:
        # 数据库尚未启动或迁移未执行时，观测页面显示空状态。
        turns = []
    return {"turns": turns}


# 查询某个 turn 的聚合调用链摘要。
@router.get("/turns/{turn_id}/summary")
def get_turn_summary(turn_id: str) -> dict:
    try:
        # 数据库可用时基于真实 Trace 事件构造 summary。
        events = trace_service.list_events(turn_id)
    except Exception:
        # 数据库不可用时返回稳定空摘要。
        return build_empty_trace_summary(turn_id)
    return build_trace_summary(turn_id, events)


# 查询某个 turn 的 Trace 事件。
@router.get("/turns/{turn_id}/events")
def list_turn_events(turn_id: str) -> list[dict]:
    try:
        # 数据库可用时返回真实持久化 Trace。
        events = trace_service.list_events(turn_id)
    except Exception:
        # 数据库尚未启动或迁移未执行时，观测页面先保持可用。
        events = []
    return [event.model_dump(mode="json") for event in events]
