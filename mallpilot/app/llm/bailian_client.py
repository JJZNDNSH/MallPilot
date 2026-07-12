from typing import Any

import httpx

from mallpilot.app.core.config import Settings
from mallpilot.app.llm.schemas import LlmMessage, LlmResult, RerankScore


class BailianClient:
    # 初始化百炼模型客户端。
    def __init__(
        self,
        settings: Settings | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        rerank_base_url: str | None = None,
        http_client: httpx.Client | None = None,
    ):
        # 应用配置，默认读取 .env 和环境变量。
        self.settings = settings or Settings()
        # 百炼 API Key，优先使用显式传入值，再读取 DashScope 和 Bailian 环境变量。
        self.api_key = api_key or self.settings.dashscope_api_key or self.settings.bailian_api_key
        # OpenAI 兼容 Chat 和 Embedding 接口基础地址。
        self.base_url = (base_url or self.settings.bailian_base_url).rstrip("/")
        # Qwen3 Rerank 使用业务空间 compatible-api 地址，允许测试或 .env 覆盖。
        configured_rerank_url = rerank_base_url or self.settings.bailian_rerank_base_url
        self.rerank_base_url = (configured_rerank_url or self.base_url.replace("compatible-mode", "compatible-api")).rstrip("/")
        # HTTP 客户端可由测试注入 fake transport。
        self.http_client = http_client or httpx.Client(timeout=30)

    # 调用百炼 Chat Completions。
    def chat(self, messages: list[LlmMessage]) -> LlmResult:
        response = self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.settings.bailian_llm_model,
                "messages": [message.model_dump() for message in messages],
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return LlmResult(content=content, model=data.get("model", self.settings.bailian_llm_model), raw=data)

    # 调用百炼文本向量接口。
    def embed_texts(self, texts: list[str], text_type: str = "document") -> list[list[float]]:
        response = self.http_client.post(
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            json={
                "model": self.settings.bailian_embedding_model,
                "input": texts,
                "dimensions": self.settings.embedding_dimension,
                "encoding_format": "float",
                "text_type": text_type,
            },
        )
        response.raise_for_status()
        data = response.json()
        ordered = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        return [[float(value) for value in item["embedding"]] for item in ordered]

    # 调用百炼重排接口。
    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[RerankScore]:
        payload: dict[str, Any] = {
            "model": self.settings.bailian_rerank_model,
            "query": query,
            "documents": documents,
            "instruct": self.settings.bailian_rerank_instruct,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        response = self.http_client.post(f"{self.rerank_base_url}/reranks", headers=self._headers(), json=payload)
        response.raise_for_status()
        data = response.json()

        scores: list[RerankScore] = []
        for item in data.get("results", []):
            # 兼容不同 rerank 响应字段命名。
            score = item.get("relevance_score", item.get("score", 0.0))
            scores.append(RerankScore(index=int(item["index"]), score=float(score)))
        return scores

    # 构造认证请求头。
    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("BAILIAN_API_KEY or DASHSCOPE_API_KEY is required")

        # 密钥只进入 HTTP Header，不进入请求体、Trace 或日志。
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
