from mallpilot.app.agent.schemas import SseEvent, TraceEvent


def test_sse_event_has_stable_envelope():
    event = SseEvent(
        type="thinking",
        chat_id="chat_1",
        turn_id="turn_1",
        seq=1,
        payload={"message": "正在检索商品"},
    )

    data = event.model_dump()

    assert data["type"] == "thinking"
    assert data["chat_id"] == "chat_1"
    assert data["turn_id"] == "turn_1"
    assert data["seq"] == 1
    assert "event_id" in data
    assert "timestamp" in data


def test_trace_event_records_stage_and_payload():
    event = TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type="router_decision",
        span_name="IntentRouter.route",
        payload={"intent": "guide"},
        status="ok",
    )

    assert event.event_type == "router_decision"
    assert event.payload["intent"] == "guide"
