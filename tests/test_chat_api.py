from fastapi.testclient import TestClient

from mallpilot.app.main import create_app


# 验证 Chat 流式接口会返回标准 SSE 响应。
def test_chat_stream_returns_sse_events():
    client = TestClient(create_app())

    response = client.post("/api/chat/stream", json={"message": "帮我找300元以内适合敏感肌的精华"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: message" in response.text
    assert '"type":"thinking"' in response.text
    assert '"type":"final"' in response.text
