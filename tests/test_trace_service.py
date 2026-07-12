from mallpilot.app.agent.schemas import SseEvent, TraceEvent
from mallpilot.app.core.event_bus import EventBus
from mallpilot.app.services.trace_service import TraceService


# 验证 Trace 事件能按 turn_id 记录和查询。
def test_trace_service_records_events_by_turn():
    service = TraceService()
    event = TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type="bm25_result",
        span_name="BM25Search.search",
        payload={"count": 3},
    )

    service.record(event)

    assert service.list_events("turn_1")[0].payload["count"] == 3


# 验证 EventBus 会把结构化事件序列化为 SSE 文本。
def test_event_bus_serializes_sse_event():
    bus = EventBus()
    event = SseEvent(type="thinking", chat_id="chat_1", turn_id="turn_1", seq=1, payload={"message": "处理中"})

    text = bus.emit(event)

    assert text.startswith("event: message\n")
    assert '"type":"thinking"' in text
