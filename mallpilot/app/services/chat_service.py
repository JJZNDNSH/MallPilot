from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from mallpilot.app.agent.flows.after_sale_flow import AfterSaleFlow
from mallpilot.app.agent.flows.cart_flow import CartFlow
from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.flows.order_flow import OrderFlow
from mallpilot.app.agent.flows.product_qa_flow import ProductQaFlow
from mallpilot.app.agent.router import IntentRouter
from mallpilot.app.agent.schemas import ChatRequest, SseEvent, TraceEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.core.event_bus import EventBus
from mallpilot.app.retrieval.product_search import HybridProductSearch
from mallpilot.app.services.llm_service import LlmService
from mallpilot.app.services.trace_service import TraceService
from mallpilot.app.tools.cart_tools import CartStore


class ChatService:
    # 初始化 Chat 服务。
    def __init__(
        self,
        router: IntentRouter | None = None,
        event_bus: EventBus | None = None,
        search: HybridProductSearch | Any | None = None,
        cart_store: CartStore | None = None,
        trace_service: TraceService | Any | None = None,
        llm_service: LlmService | Any | None = None,
    ):
        # 意图路由器。
        self.router = router or IntentRouter()
        # SSE 事件总线。
        self.event_bus = event_bus or EventBus()
        # MVP 内置演示文档，后续替换为数据库检索。
        self.search = search or HybridProductSearch.from_documents([
            {"product_id": "p_demo", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"}
        ])
        # MVP 内存购物车。
        self.cart_store = cart_store or CartStore()
        # Trace 服务，默认使用内存实现，后续应用装配可切换数据库实现。
        self.trace_service = trace_service or TraceService()
        # 可选 LLM 服务，真实模式下由应用装配传入。
        self.llm_service = llm_service

    # 流式返回 SSE 文本。
    def stream(self, request: ChatRequest) -> Iterator[str]:
        chat_id = request.chat_id or f"chat_{uuid4().hex}"
        turn_id = f"turn_{uuid4().hex}"
        intent = self.router.route(request.message)
        self._record_trace(chat_id, turn_id, "router.intent", "router", {
            "intent": intent.intent,
            "confidence": intent.confidence,
            "entities": intent.entities,
        })
        context = FlowContext(
            chat_id=chat_id,
            turn_id=turn_id,
            message=request.message,
            entities=intent.entities,
            attachments=request.attachments,
        )

        # 根据 Router 结果选择对应 Flow。
        for event in self._select_flow(intent.intent).run(context):
            self._record_sse_event(event)
            yield self.event_bus.emit(event)

    # 选择业务 Flow。
    def _select_flow(self, intent: str):
        if intent == "product_qa":
            return ProductQaFlow(search=self.search, llm_service=self.llm_service)
        if intent == "cart":
            return CartFlow(cart_store=self.cart_store)
        if intent == "order":
            return OrderFlow()
        if intent == "after_sale":
            return AfterSaleFlow()
        return GuideFlow(search=self.search, llm_service=self.llm_service)

    # 记录普通 Trace 事件。
    def _record_trace(self, chat_id: str, turn_id: str, event_type: str, span_name: str, payload: dict[str, Any]) -> None:
        self.trace_service.record(TraceEvent(
            chat_id=chat_id,
            turn_id=turn_id,
            event_type=event_type,
            span_name=span_name,
            payload=payload,
        ))

    # 记录 SSE 发送 Trace。
    def _record_sse_event(self, event: SseEvent) -> None:
        self._record_trace(
            event.chat_id,
            event.turn_id,
            "sse.emit",
            "event_bus",
            {"type": event.type, "seq": event.seq},
        )
