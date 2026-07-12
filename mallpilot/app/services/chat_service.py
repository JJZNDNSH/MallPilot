from collections.abc import Iterator
from uuid import uuid4

from mallpilot.app.agent.flows.after_sale_flow import AfterSaleFlow
from mallpilot.app.agent.flows.cart_flow import CartFlow
from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.flows.order_flow import OrderFlow
from mallpilot.app.agent.flows.product_qa_flow import ProductQaFlow
from mallpilot.app.agent.router import IntentRouter
from mallpilot.app.agent.schemas import ChatRequest, SseEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.core.event_bus import EventBus
from mallpilot.app.retrieval.product_search import HybridProductSearch
from mallpilot.app.tools.cart_tools import CartStore


class ChatService:
    # 初始化 Chat 服务。
    def __init__(self):
        # 意图路由器。
        self.router = IntentRouter()
        # SSE 事件总线。
        self.event_bus = EventBus()
        # MVP 内置演示文档，后续替换为数据库检索。
        self.search = HybridProductSearch.from_documents([
            {"product_id": "p_demo", "title": "敏感肌修护精华", "content": "敏感肌 保湿 修护", "price": 199, "category": "美妆护肤"}
        ])
        # MVP 内存购物车。
        self.cart_store = CartStore()

    # 流式返回 SSE 文本。
    def stream(self, request: ChatRequest) -> Iterator[str]:
        chat_id = request.chat_id or f"chat_{uuid4().hex}"
        turn_id = f"turn_{uuid4().hex}"
        intent = self.router.route(request.message)
        context = FlowContext(
            chat_id=chat_id,
            turn_id=turn_id,
            message=request.message,
            entities=intent.entities,
            attachments=request.attachments,
        )

        # 根据 Router 结果选择对应 Flow。
        for event in self._select_flow(intent.intent).run(context):
            yield self.event_bus.emit(event)

    # 选择业务 Flow。
    def _select_flow(self, intent: str):
        if intent == "product_qa":
            return ProductQaFlow(search=self.search)
        if intent == "cart":
            return CartFlow(cart_store=self.cart_store)
        if intent == "order":
            return OrderFlow()
        if intent == "after_sale":
            return AfterSaleFlow()
        return GuideFlow(search=self.search)
