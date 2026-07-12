from typing import Any

from mallpilot.app.core.config import Settings
from mallpilot.app.llm.bailian_client import BailianClient


class EmbeddingService:
    # 初始化文本向量服务。
    def __init__(self, client: BailianClient | None = None, settings: Settings | None = None):
        # 应用配置，用于校验向量维度。
        self.settings = settings or Settings()
        # 百炼客户端，未传入时使用真实配置创建。
        self.client = client or BailianClient(settings=self.settings)

    # 为知识块批量生成 embedding。
    def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[list[float]]:
        # 只把知识块正文送入 embedding 模型，标题和元数据保留给检索展示。
        texts = [str(chunk.get("content", "")) for chunk in chunks]
        embeddings = self.client.embed_texts(texts, text_type="document")

        # 校验返回数量，避免错位写入知识块。
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding count does not match chunk count")

        for embedding in embeddings:
            # 校验维度，避免 pgvector 写入阶段才失败。
            if len(embedding) != self.settings.embedding_dimension:
                raise ValueError("Embedding dimension does not match settings")
        return embeddings
