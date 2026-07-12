from datetime import datetime, timezone

from fastapi.testclient import TestClient

from mallpilot.app.agent.schemas import TraceEvent
from mallpilot.app.api import trace as trace_api
from mallpilot.app.main import create_app


# 构造 API 测试 Trace 事件。
def make_trace_event(turn_id: str, event_type: str, duration_ms: int | None = None, status: str = "ok") -> TraceEvent:
    return TraceEvent(
        chat_id="chat_1",
        turn_id=turn_id,
        event_type=event_type,
        span_name=event_type.replace(".", "_"),
        payload={"event_type": event_type},
        status=status,
        duration_ms=duration_ms,
        timestamp=datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc),
    )


# 验证可观测控制台页面可以打开。
def test_observability_page_loads():
    client = TestClient(create_app())

    response = client.get("/admin/observability")

    assert response.status_code == 200
    assert "MallPilot Observability" in response.text


# 验证 Trace 事件查询接口返回列表。
def test_trace_events_api_returns_list(monkeypatch):
    # API 合同测试固定 Trace 查询结果，避免依赖外部 PostgreSQL 状态。
    monkeypatch.setattr(trace_api.trace_service, "list_events", lambda turn_id: [])
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_1/events")

    assert response.status_code == 200
    assert response.json() == []


# 验证轮次列表接口返回可用于下拉框的标签。
def test_trace_turns_api_returns_dropdown_options(monkeypatch):
    monkeypatch.setattr(trace_api.trace_service, "list_turns", lambda limit=50: [
        {
            "label": "第 1 轮",
            "turn_id": "turn_1",
            "chat_id": "chat_1",
            "event_count": 2,
            "started_at": "2026-07-12T10:00:00+00:00",
        }
    ])
    client = TestClient(create_app())

    response = client.get("/api/trace/turns")

    assert response.status_code == 200
    assert response.json()["turns"][0]["label"] == "第 1 轮"
    assert response.json()["turns"][0]["turn_id"] == "turn_1"


# 验证 summary 接口返回分组后的调用链摘要。
def test_trace_summary_api_returns_grouped_summary(monkeypatch):
    monkeypatch.setattr(trace_api.trace_service, "list_events", lambda turn_id: [
        make_trace_event(turn_id, "router.intent", duration_ms=5),
        make_trace_event(turn_id, "llm.bailian", duration_ms=1200),
    ])
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_1/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["turn_id"] == "turn_1"
    assert data["event_count"] == 2
    assert data["total_duration_ms"] == 1205
    assert [group["name"] for group in data["groups"]] == ["router", "llm"]


# 验证 summary 接口在查询失败时返回空摘要。
def test_trace_summary_api_returns_empty_summary_when_trace_service_fails(monkeypatch):
    def raise_error(turn_id: str):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(trace_api.trace_service, "list_events", raise_error)
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_missing/summary")

    assert response.status_code == 200
    assert response.json() == {
        "turn_id": "turn_missing",
        "event_count": 0,
        "error_count": 0,
        "total_duration_ms": 0,
        "groups": [],
        "events": [],
    }
