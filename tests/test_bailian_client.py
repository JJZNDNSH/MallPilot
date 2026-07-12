import json

import httpx

from mallpilot.app.core.config import Settings
from mallpilot.app.llm.bailian_client import BailianClient
from mallpilot.app.llm.schemas import LlmMessage


# 验证百炼 Chat 响应会映射为内部 LLM 结果。
def test_bailian_client_chat_maps_openai_compatible_response():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "model": "qwen-plus",
                "choices": [{"message": {"role": "assistant", "content": "你好，我是 MallPilot"}}],
            },
        )

    client = BailianClient(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.chat([LlmMessage(role="user", content="你好")])

    assert result.content == "你好，我是 MallPilot"
    assert result.model == "qwen-plus"
    assert captured[0].url.path == "/compatible-mode/v1/chat/completions"
    assert captured[0].headers["Authorization"] == "Bearer test-key"


# 验证百炼 Embedding 响应会按 index 顺序映射为向量列表。
def test_bailian_client_embed_texts_maps_embeddings():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "text-embedding-v4"
        assert body["dimensions"] == 1024
        assert body["encoding_format"] == "float"
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
            },
        )

    client = BailianClient(
        api_key="test-key",
        base_url="https://example.com/compatible-mode/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    vectors = client.embed_texts(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


# 验证百炼 Rerank 响应会映射为排序分数，且请求体不会包含密钥。
def test_bailian_client_rerank_maps_scores_without_leaking_key():
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen3-rerank",
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.23},
                ],
            },
        )

    client = BailianClient(
        settings=Settings(bailian_rerank_model="qwen3-rerank"),
        api_key="test-key",
        rerank_base_url="https://example.com/compatible-api/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    scores = client.rerank("保湿精华", ["普通描述", "保湿修护精华"], top_n=2)

    assert [score.index for score in scores] == [1, 0]
    assert [score.score for score in scores] == [0.91, 0.23]
    assert captured_body["model"] == "qwen3-rerank"
    assert "test-key" not in json.dumps(captured_body, ensure_ascii=False)
