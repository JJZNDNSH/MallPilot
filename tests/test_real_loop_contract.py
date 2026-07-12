from pathlib import Path

from fastapi.testclient import TestClient

from mallpilot.app.agent.router import LlmIntentRouter
from mallpilot.app.agent.schemas import ChatRequest, ProductCandidate
from mallpilot.app.main import app
from mallpilot.app.services.chat_service import ChatService


class FakeSearch:
    # 返回稳定候选商品。
    def search(self, query: str, filters: dict):
        return (
            [
                ProductCandidate(
                    product_id="p_1",
                    title="保湿修护精华",
                    category="美妆护肤",
                    price=199,
                    score=0.9,
                    evidence=[{"source": "test", "summary": "适合敏感肌保湿修护"}],
                )
            ],
            [],
        )


class FakeLlmService:
    # 生成导购总结。
    def generate_guide_summary(self, message: str, candidates: list[ProductCandidate]) -> str:
        return "LLM 推荐总结"


# 验证正式闭环需要的路由已经注册。
def test_app_registers_real_loop_routes(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    # 路由注册测试只验证 HTTP 合同，运行时依赖用 fake search 固定住。
    monkeypatch.setattr(ChatService, "from_runtime", classmethod(lambda cls: ChatService(search=FakeSearch())))
    client = TestClient(app)

    assert client.get("/chat").status_code == 200
    assert client.get("/admin/observability").status_code == 200
    assert client.post("/api/chat/stream", json={"message": "推荐保湿精华"}).status_code == 200


# 验证 ChatService 会把 LLM 服务注入导购 Flow，且输出不包含密钥形态。
def test_chat_service_wires_llm_service_without_leaking_secrets():
    service = ChatService(search=FakeSearch(), llm_service=FakeLlmService())

    payload = "".join(service.stream(ChatRequest(message="推荐保湿精华")))

    assert "LLM 推荐总结" in payload
    assert "sk-" not in payload


# 验证真实模型模式下运行时默认使用 LLM 路由器。
def test_chat_service_runtime_uses_llm_router(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "false")
    service = ChatService.from_runtime()

    assert isinstance(service.router, LlmIntentRouter)


# 验证 README 提供真实运行闭环命令。
def test_readme_documents_real_loop_commands_without_secret():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "alembic upgrade head" in readme
    assert "python -m scripts.ingest_products" in readme
    assert "uvicorn mallpilot.app.main:app" in readme
    assert "http://127.0.0.1:8000/chat" in readme
    assert "sk-" not in readme
