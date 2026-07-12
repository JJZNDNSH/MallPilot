from fastapi.testclient import TestClient

from mallpilot.app.agent.schemas import ProductCandidate
from mallpilot.app.main import create_app
from mallpilot.app.services.chat_service import ChatService


class FakeSearch:
    # 返回稳定候选商品，避免 API 合同测试依赖真实数据库。
    def search(self, query: str, filters: dict):
        return (
            [
                ProductCandidate(
                    product_id="p_1",
                    title="保湿修护精华",
                    category="美妆护肤",
                    price=199,
                    evidence=[{"source": "test", "summary": "适合敏感肌"}],
                )
            ],
            [],
        )


# 验证 Chat 流式接口会返回标准 SSE 响应。
def test_chat_stream_returns_sse_events(monkeypatch):
    # API 测试只验证 SSE 合同，运行时依赖用 fake search 固定住。
    monkeypatch.setattr(ChatService, "from_runtime", classmethod(lambda cls: ChatService(search=FakeSearch())))
    client = TestClient(create_app())

    response = client.post("/api/chat/stream", json={"message": "帮我找300元以内适合敏感肌的精华"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: message" in response.text
    assert '"type":"thinking"' in response.text
    assert '"type":"final"' in response.text
