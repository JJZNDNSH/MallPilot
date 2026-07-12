from fastapi import APIRouter

from mallpilot.app.services.trace_service import TraceService

router = APIRouter(prefix="/api/trace", tags=["trace"])
trace_service = TraceService()


# 查询某个 turn 的 Trace 事件。
@router.get("/turns/{turn_id}/events")
def list_turn_events(turn_id: str) -> list[dict]:
    return [event.model_dump(mode="json") for event in trace_service.list_events(turn_id)]
