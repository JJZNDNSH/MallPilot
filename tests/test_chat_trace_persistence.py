from sqlalchemy import create_engine

from mallpilot.app.agent.schemas import ChatRequest, TraceEvent
from mallpilot.app.db.session import create_session_factory
from mallpilot.app.models.base import Base
from mallpilot.app.services.chat_service import ChatService
from mallpilot.app.services.db_trace_service import DbTraceService


class RecordingTraceService:
    # 记录 ChatService 写入的 Trace。
    def __init__(self):
        # 已记录的 Trace 事件。
        self.events: list[TraceEvent] = []

    # 记录 Trace 事件。
    def record(self, event: TraceEvent) -> None:
        self.events.append(event)

    # 按 turn_id 查询 Trace 事件。
    def list_events(self, turn_id: str) -> list[TraceEvent]:
        return [event for event in self.events if event.turn_id == turn_id]


# 验证 ChatService 会记录路由和 SSE 发送 Trace。
def test_chat_service_records_router_and_sse_trace_events():
    trace_service = RecordingTraceService()
    service = ChatService(trace_service=trace_service)

    list(service.stream(ChatRequest(message="帮我找300元以内适合敏感肌的精华")))

    event_types = [event.event_type for event in trace_service.events]
    user_events = [event for event in trace_service.events if event.event_type == "user.message"]
    sse_events = [event for event in trace_service.events if event.event_type == "sse.emit"]

    assert user_events[0].payload["message"] == "帮我找300元以内适合敏感肌的精华"
    assert "router.intent" in event_types
    assert event_types.count("sse.emit") >= 2
    assert any(event.payload["type"] == "thinking" and event.payload["summary"]["message"] for event in sse_events)
    assert any(event.payload["type"] == "product_card" and event.payload["summary"]["title"] for event in sse_events)
    assert all("api_key" not in event.payload for event in trace_service.events)


# 验证闲聊请求不会触发商品检索 Trace。
def test_chat_service_chitchat_does_not_search_products():
    trace_service = RecordingTraceService()
    service = ChatService(trace_service=trace_service)

    payload = "".join(service.stream(ChatRequest(message="你好")))

    event_types = [event.event_type for event in trace_service.events]
    assert "你好，我是 MallPilot" in payload
    assert "retrieval.bm25" not in event_types
    assert "retrieval.vector" not in event_types


# 验证数据库版 TraceService 可以持久化并按 turn_id 查询。
def test_db_trace_service_records_and_lists_events():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    service = DbTraceService(session_factory=create_session_factory(engine))
    event = TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type="llm.bailian",
        span_name="guide",
        payload={"model": "qwen-plus"},
        duration_ms=10,
    )

    service.record(event)
    events = service.list_events("turn_1")

    assert len(events) == 1
    assert events[0].trace_id == event.trace_id
    assert events[0].payload["model"] == "qwen-plus"
