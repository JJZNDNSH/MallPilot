from datetime import datetime, timezone

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.services.trace_summary import build_empty_trace_summary, build_trace_summary, trace_group_name


# 构造测试 Trace 事件。
def make_event(event_type: str, status: str = "ok", duration_ms: int | None = None) -> TraceEvent:
    return TraceEvent(
        chat_id="chat_1",
        turn_id="turn_1",
        event_type=event_type,
        span_name=event_type.replace(".", "_"),
        payload={"sample": event_type},
        status=status,
        duration_ms=duration_ms,
        timestamp=datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc),
    )


# 验证事件类型会映射到观测阶段分组。
def test_trace_group_name_maps_known_event_types():
    assert trace_group_name(make_event("router.intent")) == "router"
    assert trace_group_name(make_event("retrieval.vector")) == "retrieval"
    assert trace_group_name(make_event("rerank.bailian")) == "rerank"
    assert trace_group_name(make_event("llm.bailian")) == "llm"
    assert trace_group_name(make_event("sse.emit")) == "sse"
    assert trace_group_name(make_event("custom.event")) == "other"


# 验证错误事件会进入 error 分组。
def test_trace_group_name_maps_error_events_to_error():
    assert trace_group_name(make_event("retrieval.error", status="error")) == "error"
    assert trace_group_name(make_event("llm.bailian", status="error")) == "error"


# 验证空摘要结构稳定。
def test_build_empty_trace_summary_returns_stable_shape():
    summary = build_empty_trace_summary("turn_missing")

    assert summary == {
        "turn_id": "turn_missing",
        "event_count": 0,
        "error_count": 0,
        "total_duration_ms": 0,
        "groups": [],
        "events": [],
    }


# 验证 summary 汇总数量、错误数、耗时和分组。
def test_build_trace_summary_groups_events_and_sums_duration():
    events = [
        make_event("router.intent", duration_ms=5),
        make_event("retrieval.vector", duration_ms=80),
        make_event("rerank.bailian", duration_ms=120),
        make_event("llm.bailian", duration_ms=1100),
        make_event("sse.emit"),
        make_event("retrieval.error", status="error", duration_ms=10),
    ]

    summary = build_trace_summary("turn_1", events)

    assert summary["turn_id"] == "turn_1"
    assert summary["event_count"] == 6
    assert summary["error_count"] == 1
    assert summary["total_duration_ms"] == 1315
    groups = {group["name"]: group for group in summary["groups"]}
    assert groups["router"]["event_count"] == 1
    assert groups["retrieval"]["duration_ms"] == 80
    assert groups["error"]["status"] == "error"
    assert len(summary["events"]) == 6
