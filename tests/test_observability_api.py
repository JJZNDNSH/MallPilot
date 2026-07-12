from fastapi.testclient import TestClient

from mallpilot.app.main import create_app


# 验证可观测控制台页面可以打开。
def test_observability_page_loads():
    client = TestClient(create_app())

    response = client.get("/admin/observability")

    assert response.status_code == 200
    assert "MallPilot Observability" in response.text


# 验证 Trace 事件查询接口返回列表。
def test_trace_events_api_returns_list():
    client = TestClient(create_app())

    response = client.get("/api/trace/turns/turn_1/events")

    assert response.status_code == 200
    assert response.json() == []
