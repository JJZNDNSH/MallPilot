from collections.abc import Iterator
from time import perf_counter
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from mallpilot.app.agent.flows.after_sale_flow import AfterSaleFlow
from mallpilot.app.agent.flows.cart_flow import CartFlow
from mallpilot.app.agent.flows.chitchat_flow import ChitchatFlow
from mallpilot.app.agent.flows.guide_flow import GuideFlow
from mallpilot.app.agent.flows.order_flow import OrderFlow
from mallpilot.app.agent.flows.product_qa_flow import ProductQaFlow
from mallpilot.app.agent.router import IntentRouter, LlmIntentRouter
from mallpilot.app.agent.schemas import ChatRequest, ProductCandidate, SseEvent, TraceEvent
from mallpilot.app.agent.state import FlowContext
from mallpilot.app.core.config import Settings, get_settings
from mallpilot.app.core.event_bus import EventBus
from mallpilot.app.db.session import get_session_factory
from mallpilot.app.retrieval.db_product_search import DatabaseProductSearch
from mallpilot.app.retrieval.product_search import HybridProductSearch
from mallpilot.app.services.db_trace_service import DbTraceService
from mallpilot.app.services.llm_service import LlmService
from mallpilot.app.services.trace_service import TraceService
from mallpilot.app.tools.cart_tools import CartStore


class ChatService:
    # 初始化 Chat 服务。
    def __init__(
        self,
        router: IntentRouter | None = None,
        event_bus: EventBus | None = None,
        search: Any | None = None,
        cart_store: CartStore | None = None,
        trace_service: Any | None = None,
        llm_service: Any | None = None,
        session_factory: sessionmaker[Session] | None = None,
        settings: Settings | None = None,
    ):
        # 应用配置，用于判断是否启用真实模型服务。
        self.settings = settings or get_settings()
        # 意图路由器。
        self.router = router or IntentRouter()
        # SSE 事件总线。
        self.event_bus = event_bus or EventBus()
        # 可注入检索服务，单元测试可传入 fake。
        self.search = search
        # MVP 内存购物车。
        self.cart_store = cart_store or CartStore()
        # Trace 服务，运行时可切换为数据库持久化实现。
        self.trace_service = trace_service or TraceService()
        # 可选 LLM 服务，真实模式下用于生成导购总结和问答答案。
        self.llm_service = llm_service
        # 数据库会话工厂，运行时用于创建真实商品检索器。
        self.session_factory = session_factory
        # 演示检索器，数据库不可用时用于保证聊天链路仍可响应。
        self.demo_search = HybridProductSearch.from_documents([
            {
                "product_id": "p_demo",
                "title": "敏感肌修护精华",
                "content": "敏感肌 保湿 修护",
                "price": 199,
                "category": "美妆护肤",
            }
        ])

    # 构建真实运行时 Chat 服务。
    @classmethod
    def from_runtime(cls) -> "ChatService":
        settings = get_settings()
        session_factory = get_session_factory()
        trace_service = DbTraceService(session_factory=session_factory)
        llm_service = None if settings.use_mock_llm else LlmService()
        # 真实模型模式下使用 LLM 路由；mock 模式保留规则路由，避免测试和本地无 key 场景误打外网。
        router = IntentRouter() if settings.use_mock_llm else LlmIntentRouter()

        return cls(
            router=router,
            trace_service=trace_service,
            llm_service=llm_service,
            session_factory=session_factory,
            settings=settings,
        )

    # 流式返回 SSE 文本。
    def stream(self, request: ChatRequest) -> Iterator[str]:
        chat_id = request.chat_id or f"chat_{uuid4().hex}"
        turn_id = f"turn_{uuid4().hex}"
        self._record_user_message(chat_id, turn_id, request.message)
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

        # 每一轮请求独立创建数据库 session，保证流式响应结束后释放连接。
        if self.session_factory is None:
            search = self._build_traceable_search(self.search or self.demo_search, chat_id, turn_id)
            yield from self._stream_with_search(intent.intent, context, search, chat_id, turn_id)
            return

        with self.session_factory() as session:
            database_search = DatabaseProductSearch(session=session)
            search = self._build_traceable_search(database_search, chat_id, turn_id, fallback=self.demo_search)
            yield from self._stream_with_search(intent.intent, context, search, chat_id, turn_id)

    # 使用指定检索器执行对应业务 Flow。
    def _stream_with_search(
        self,
        intent: str,
        context: FlowContext,
        search: Any,
        chat_id: str,
        turn_id: str,
    ) -> Iterator[str]:
        llm_service = self._build_traceable_llm(chat_id, turn_id)

        # 根据 Router 结果选择对应 Flow。
        for event in self._select_flow(intent, search, llm_service).run(context):
            self._record_sse_event(event)
            yield self.event_bus.emit(event)

    # 选择业务 Flow。
    def _select_flow(self, intent: str, search: Any, llm_service: Any | None):
        if intent == "product_qa":
            return ProductQaFlow(search=search, llm_service=llm_service)
        if intent == "cart":
            return CartFlow(cart_store=self.cart_store)
        if intent == "order":
            return OrderFlow()
        if intent == "after_sale":
            return AfterSaleFlow()
        if intent == "chitchat":
            return ChitchatFlow()
        return GuideFlow(search=search, llm_service=llm_service)

    # 构建带 Trace 的检索代理。
    def _build_traceable_search(self, search: Any, chat_id: str, turn_id: str, fallback: Any | None = None) -> Any:
        return TraceableSearch(
            search=search,
            trace_service=self.trace_service,
            chat_id=chat_id,
            turn_id=turn_id,
            fallback=fallback,
        )

    # 构建带 Trace 的 LLM 代理。
    def _build_traceable_llm(self, chat_id: str, turn_id: str) -> Any | None:
        if self.llm_service is None:
            return None
        return TraceableLlmService(
            llm_service=self.llm_service,
            trace_service=self.trace_service,
            chat_id=chat_id,
            turn_id=turn_id,
        )

    # 记录用户本轮原始输入，供观测页固定展示在调用链顶部。
    def _record_user_message(self, chat_id: str, turn_id: str, message: str) -> None:
        self._record_trace(chat_id, turn_id, "user.message", "user", {"message": message})

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
            {
                "type": event.type,
                "seq": event.seq,
                "summary": self._summarize_sse_event(event),
            },
        )

    # 为 SSE 事件生成安全、可读的摘要，避免观测页只展示原始 payload。
    def _summarize_sse_event(self, event: SseEvent) -> dict[str, Any]:
        payload = event.payload
        if event.type == "thinking":
            return {"message": payload.get("message"), "stage": payload.get("stage")}
        if event.type == "product_card":
            return {
                "product_id": payload.get("product_id"),
                "title": payload.get("title"),
                "price": payload.get("price"),
                "reason": _shorten_trace_text(payload.get("reason", "")),
            }
        if event.type == "answer":
            return {"text": _shorten_trace_text(payload.get("text", ""))}
        if event.type in {"order_preview", "after_sale_preview"}:
            return {"status": payload.get("status"), "title": payload.get("title")}
        if event.type == "final":
            return {"status": payload.get("status")}
        return {"keys": sorted(payload.keys())}


class TraceableSearch:
    # 初始化检索 Trace 代理。
    def __init__(
        self,
        search: Any,
        trace_service: Any,
        chat_id: str,
        turn_id: str,
        fallback: Any | None = None,
    ):
        # 实际检索服务。
        self.delegate = search
        # Trace 记录服务。
        self.trace_service = trace_service
        # 当前会话 ID。
        self.chat_id = chat_id
        # 当前轮次 ID。
        self.turn_id = turn_id
        # 检索失败时的降级检索服务。
        self.fallback = fallback

    # 执行检索并记录检索 Trace。
    def search(self, query: str, filters: dict[str, Any], image_embedding: list[float] | None = None):
        try:
            candidates, trace = self.delegate.search(query, filters, image_embedding=image_embedding)
        except TypeError:
            # 兼容测试 fake search 只接受 query 和 filters 的简化签名。
            candidates, trace = self.delegate.search(query, filters)
        except Exception as exc:
            self._record_error(exc)
            if self.fallback is None:
                raise
            candidates, trace = self.fallback.search(query, filters)

        # 把检索器返回的内部 trace 统一落到当前 chat/turn。
        for event in trace:
            self._record_trace_event(event)
        return candidates, trace

    # 记录检索器返回的 Trace 事件。
    def _record_trace_event(self, event: TraceEvent | dict[str, Any]) -> None:
        if isinstance(event, TraceEvent):
            event_type = event.event_type
            span_name = event.span_name
            payload = event.payload
            status = event.status
            error_message = event.error_message
            duration_ms = event.duration_ms
        else:
            event_type = str(event.get("event_type", "retrieval.event"))
            span_name = str(event.get("span_name", "retrieval"))
            payload = dict(event.get("payload", {}))
            status = str(event.get("status", "ok"))
            error_message = event.get("error_message")
            duration_ms = event.get("duration_ms")

        self.trace_service.record(TraceEvent(
            chat_id=self.chat_id,
            turn_id=self.turn_id,
            event_type=event_type,
            span_name=span_name,
            payload=payload,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        ))

    # 记录真实检索失败事件。
    def _record_error(self, exc: Exception) -> None:
        self.trace_service.record(TraceEvent(
            chat_id=self.chat_id,
            turn_id=self.turn_id,
            event_type="retrieval.error",
            span_name="database_product_search",
            payload={"message": str(exc.__class__.__name__)},
            status="error",
            error_message=str(exc),
        ))


class TraceableLlmService:
    # 初始化 LLM Trace 代理。
    def __init__(self, llm_service: Any, trace_service: Any, chat_id: str, turn_id: str):
        # 实际 LLM 服务。
        self.llm_service = llm_service
        # Trace 记录服务。
        self.trace_service = trace_service
        # 当前会话 ID。
        self.chat_id = chat_id
        # 当前轮次 ID。
        self.turn_id = turn_id

    # 生成导购总结并记录 LLM 调用。
    def generate_guide_summary(self, message: str, candidates: list[ProductCandidate]) -> str:
        return self._record_llm_call(
            span_name="guide_summary",
            payload={"candidate_count": len(candidates)},
            action=lambda: self.llm_service.generate_guide_summary(message, candidates),
        )

    # 生成商品问答答案并记录 LLM 调用。
    def answer_product_question(self, message: str, evidence: list[dict]) -> str:
        return self._record_llm_call(
            span_name="product_qa",
            payload={"evidence_count": len(evidence)},
            action=lambda: self.llm_service.answer_product_question(message, evidence),
        )

    # 执行 LLM 调用并记录耗时、状态和安全 payload。
    def _record_llm_call(self, span_name: str, payload: dict[str, Any], action: Any) -> str:
        started_at = perf_counter()
        try:
            result = action()
        except Exception as exc:
            duration_ms = int((perf_counter() - started_at) * 1000)
            self.trace_service.record(TraceEvent(
                chat_id=self.chat_id,
                turn_id=self.turn_id,
                event_type="llm.bailian",
                span_name=span_name,
                payload=payload,
                status="error",
                error_message=str(exc),
                duration_ms=duration_ms,
            ))
            raise

        duration_ms = int((perf_counter() - started_at) * 1000)
        self.trace_service.record(TraceEvent(
            chat_id=self.chat_id,
            turn_id=self.turn_id,
            event_type="llm.bailian",
            span_name=span_name,
            payload=payload,
            duration_ms=duration_ms,
        ))
        return result


# 压缩 Trace 展示文本，避免长回答撑开观测面板。
def _shorten_trace_text(value: Any, max_length: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."
