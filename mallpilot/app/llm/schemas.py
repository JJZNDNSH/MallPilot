from typing import Any, Literal

from pydantic import BaseModel, Field


class LlmMessage(BaseModel):
    # 消息角色，遵循 OpenAI 兼容格式。
    role: Literal["system", "user", "assistant"]
    # 消息正文。
    content: str


class LlmResult(BaseModel):
    # 模型生成的文本内容。
    content: str
    # 实际返回的模型名称。
    model: str
    # 原始响应，便于 Trace 记录非敏感摘要。
    raw: dict[str, Any] = Field(default_factory=dict)


class RerankScore(BaseModel):
    # 文档在原始候选列表中的下标。
    index: int
    # 重排模型返回的相关性分数。
    score: float
