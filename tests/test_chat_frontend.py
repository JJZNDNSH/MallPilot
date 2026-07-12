from fastapi.testclient import TestClient

from mallpilot.app.main import app


# 验证正式聊天界面可以打开并引用静态资源。
def test_chat_page_loads_with_static_assets():
    client = TestClient(app)

    response = client.get("/chat")

    assert response.status_code == 200
    assert "MallPilot" in response.text
    assert "/chat/static/app.js" in response.text
    assert "/chat/static/style.css" in response.text


# 验证聊天前端脚本包含 SSE 事件分流渲染入口。
def test_chat_app_javascript_supports_sse_event_types():
    client = TestClient(app)

    response = client.get("/chat/static/app.js")

    assert response.status_code == 200
    assert "product_card" in response.text
    assert "clarification" in response.text
    assert "thinking" in response.text
    assert "after_sale_preview" in response.text


# 验证 Trace 详情会渲染到右侧面板，而不是混入聊天消息。
def test_chat_app_keeps_trace_payload_out_of_conversation():
    client = TestClient(app)

    response = client.get("/chat/static/app.js")

    assert response.status_code == 200
    assert "traceDetail" in response.text
    assert 'appendMessage("assistant subtle", JSON.stringify' not in response.text
