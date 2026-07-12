from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # 用户会话 ID，前端首次请求时可以为空。
    chat_id: str | None = None
    # 用户 ID，MVP 阶段允许使用 anonymous。
    user_id: str = "anonymous"
    # 用户本轮输入文本。
    message: str
    # 附件列表，图片输入会放在这里。
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class SseEvent(BaseModel):
    # SSE 事件唯一 ID。
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    # 前端渲染使用的事件类型。
    type: str
    # 当前会话 ID。
    chat_id: str
    # 当前轮次 ID。
    turn_id: str
    # 当前轮次内递增序号。
    seq: int
    # 事件产生时间。
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # 事件业务载荷。
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    # Trace 事件唯一 ID。
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    # 当前会话 ID。
    chat_id: str
    # 当前轮次 ID。
    turn_id: str
    # Trace 事件类型。
    event_type: str
    # 代码执行阶段名称。
    span_name: str
    # Trace 详细载荷。
    payload: dict[str, Any] = Field(default_factory=dict)
    # 执行状态。
    status: Literal["ok", "error"] = "ok"
    # 错误信息。
    error_message: str | None = None
    # 耗时，单位毫秒。
    duration_ms: int | None = None
    # 事件产生时间。
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntentResult(BaseModel):
    # 路由意图。
    intent: Literal["guide", "product_qa", "compare", "cart", "order", "after_sale", "chitchat"]
    # 意图置信度。
    confidence: float
    # 路由原因摘要。
    reason: str
    # 抽取出的实体。
    entities: dict[str, Any] = Field(default_factory=dict)


class ProductCandidate(BaseModel):
    # 商品 ID。
    product_id: str
    # 商品标题。
    title: str
    # 商品品牌。
    brand: str | None = None
    # 商品品类。
    category: str | None = None
    # 商品价格。
    price: float | None = None
    # 商品图片 URL。
    image_url: str | None = None
    # 候选分数。
    score: float = 0.0
    # 候选命中的证据。
    evidence: list[dict[str, Any]] = Field(default_factory=list)
