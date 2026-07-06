"""
MallPilot 多 Agent 路由与编排模块。

这个模块负责在导购、订单、售后三类 Agent 之间做动态路由、并行协作和失败降级。
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from core.intent_recognizer import IntentCategory, IntentRecognizer, UrgencyLevel

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """MallPilot Agent 类型枚举。"""

    GUIDE = "guide"  # 导购 Agent，负责商品推荐与选购建议。
    ORDER = "order"  # 订单 Agent，负责订单、物流、支付与发票咨询。
    AFTER_SALES = "after_sales"  # 售后 Agent，负责退款、退货、换货与投诉处理。
    ESCALATION = "escalation"  # 升级占位类型，只用于标记转人工。


@dataclass
class AgentStats:
    """Agent 在线表现统计。"""

    total: int = 0  # 总调用次数，用于计算成功率。
    success: int = 0  # 成功次数，用于计算成功率。
    total_ms: float = 0.0  # 总耗时毫秒数，用于计算平均延迟。
    monitor_penalty: float = 0.0  # 监控降权系数，用于动态影响路由。

    # 做什么：返回 Agent 成功率。
    # 为什么：供监控与路由评分统一复用。
    @property
    def success_rate(self) -> float:
        return self.success / self.total if self.total else 1.0

    # 做什么：返回 Agent 平均耗时。
    # 为什么：让性能路由能够避开明显过慢的实例。
    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.total if self.total else 0.0

    # 做什么：根据成功率与延迟计算综合路由评分。
    # 为什么：让表现更稳定的 Agent 被优先选择。
    def routing_score(self) -> float:
        latency_score = 1.0 / (1.0 + self.avg_ms / 1000)
        base_score = self.success_rate * 0.7 + latency_score * 0.3
        return base_score * max(0.0, 1.0 - self.monitor_penalty)


@dataclass
class AgentResponse:
    """单个 Agent 的执行结果。"""

    agent_type: AgentType  # 当前响应来源的 Agent 类型。
    content: str  # Agent 生成的回复内容。
    success: bool  # 当前调用是否成功。
    confidence: float = 1.0  # 当前调用的置信度占位字段。
    latency_ms: float = 0.0  # 当前调用的耗时。
    escalate: bool = False  # 当前回复是否建议升级到人工。


@dataclass
class Request:
    """编排器入参。"""

    message: str  # 用户原始消息。
    user_id: str  # 当前用户标识。
    conv_id: str  # 当前会话标识。
    context: str = ""  # 记忆、知识库和结构化数据拼接后的上下文。
    history: Optional[List[Dict[str, str]]] = None  # 最近对话历史，用于意图识别。
    intent: Optional[IntentCategory] = None  # 调用方可提前注入的意图结果。
    urgency: Optional[UrgencyLevel] = None  # 调用方可提前注入的紧急度结果。
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])  # 当前请求 ID。


@dataclass
class OrchestratorResult:
    """编排后的统一返回结果。"""

    request_id: str  # 当前请求 ID。
    response: str  # 最终返回给用户的回复。
    agent_type: AgentType  # 主响应 Agent 类型。
    intent: Optional[IntentCategory]  # 本轮识别出的意图。
    escalated: bool = False  # 是否触发升级标记。
    latency_ms: float = 0.0  # 本轮完整编排耗时。


class BaseAgent:
    """MallPilot Agent 基类。"""

    agent_type: AgentType
    system_prompt: str

    # 做什么：初始化通用 LLM 客户端、模型与 Skill 管理器。
    # 为什么：让不同业务 Agent 共用统一的调用与统计逻辑。
    def __init__(self, client: AsyncAnthropic, model: str, skill_manager: Optional[Any] = None):
        self._client = client
        self._model = model
        self._skill_manager = skill_manager
        self.stats = AgentStats()

    # 做什么：执行 Agent 并更新在线统计。
    # 为什么：让编排器始终通过统一入口调用单个 Agent。
    async def handle(self, req: Request) -> AgentResponse:
        t0 = time.monotonic()
        self.stats.total += 1
        try:
            content = await self._call_llm(req)
            latency_ms = (time.monotonic() - t0) * 1000
            self.stats.success += 1
            self.stats.total_ms += latency_ms
            return AgentResponse(
                agent_type=self.agent_type,
                content=content,
                success=True,
                latency_ms=latency_ms,
                escalate=self._needs_escalation(content),
            )
        except Exception as ex:
            latency_ms = (time.monotonic() - t0) * 1000
            self.stats.total_ms += latency_ms
            logger.error("%s 处理失败: %s", self.agent_type.value, ex)
            return AgentResponse(
                agent_type=self.agent_type,
                content="抱歉，我暂时没能完成这一步处理。你可以补充商品、订单或售后信息，我继续帮你判断。",
                success=False,
                latency_ms=latency_ms,
            )

    # 做什么：构造 LLM 对话消息并发起调用。
    # 为什么：把上下文、Skill 与用户消息统一拼成一次模型请求。
    async def _call_llm(self, req: Request) -> str:
        messages: List[Dict[str, str]] = []
        if req.context:
            messages.append({"role": "user", "content": f"[背景信息]\n{self._clean(req.context)}"})
            messages.append({"role": "assistant", "content": "好的，我会结合背景信息回答。"})
        messages.append({"role": "user", "content": self._clean(req.message)})

        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=self._build_system_prompt(req),
            messages=messages,
        )
        return resp.content[0].text

    # 做什么：把动态 Skill 规则注入到系统提示词。
    # 为什么：让业务规范可以热加载，而不需要改动 Agent 主逻辑。
    def _build_system_prompt(self, req: Request) -> str:
        if self._skill_manager is None:
            return self.system_prompt
        skill_prompt = self._skill_manager.prompt_for(req.message, self.agent_type.value)
        if not skill_prompt:
            return self.system_prompt
        return f"{self.system_prompt}\n\n[动态 Skills]\n{skill_prompt}"

    # 做什么：根据回复内容判断是否需要升级。
    # 为什么：补充意图识别之外的兜底升级信号。
    def _needs_escalation(self, content: str) -> bool:
        keywords = ["转人工", "人工客服", "专员跟进", "无法直接确认", "需要人工审核"]
        return any(keyword in content for keyword in keywords)

    # 做什么：清洗字符串中的非法代理字符。
    # 为什么：避免上下文中出现异常字符导致 LLM 请求失败。
    @staticmethod
    def _clean(value: str) -> str:
        return value.encode("utf-8", errors="ignore").decode("utf-8")


class GuideAgent(BaseAgent):
    """导购 Agent。"""

    agent_type = AgentType.GUIDE
    system_prompt = (
        "你是 MallPilot 的导购助手。"
        "请围绕商品推荐、参数对比、预算建议、送礼场景和搭配方案给出清晰、克制、可执行的建议。"
        "如果缺少关键条件，请先澄清预算、类目、使用场景或品牌偏好。"
        "不要编造库存、活动资格、下单结果或物流状态。"
    )


class OrderAgent(BaseAgent):
    """订单 Agent。"""

    agent_type = AgentType.ORDER
    system_prompt = (
        "你是 MallPilot 的订单服务助手。"
        "请基于订单事实回答订单状态、物流进度、地址、支付、优惠券和发票问题。"
        "如果缺少订单号或订单事实，请明确说明需要补充信息，不能臆造订单结果。"
    )


class AfterSalesAgent(BaseAgent):
    """售后 Agent。"""

    agent_type = AgentType.AFTER_SALES
    system_prompt = (
        "你是 MallPilot 的售后服务助手。"
        "请围绕退款、退货、换货、质量问题、售后进度和投诉给出保守、可核验的处理建议。"
        "涉及实际退款成功、换货审核通过或人工补偿时，必须明确说明需要核验或人工处理。"
    )


class AgentOrchestrator:
    """MallPilot 多 Agent 编排器。"""

    _INTENT_ROUTING: Dict[IntentCategory, AgentType] = {
        IntentCategory.GUIDE: AgentType.GUIDE,
        IntentCategory.ORDER: AgentType.ORDER,
        IntentCategory.AFTER_SALES: AgentType.AFTER_SALES,
        IntentCategory.COMPLAINT: AgentType.AFTER_SALES,
        IntentCategory.ESCALATION: AgentType.ESCALATION,
    }

    # 做什么：初始化意图识别器和 Agent 池。
    # 为什么：让 API、评测和 CLI 都能复用同一套编排逻辑。
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        skill_manager: Optional[Any] = None,
    ):
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncAnthropic(**kwargs)

        self._intent_recognizer = IntentRecognizer(api_key=api_key, base_url=base_url, model=model)
        self._skill_manager = skill_manager
        self._pool: Dict[AgentType, List[BaseAgent]] = {
            AgentType.GUIDE: [GuideAgent(client, model, skill_manager)],
            AgentType.ORDER: [OrderAgent(client, model, skill_manager)],
            AgentType.AFTER_SALES: [AfterSalesAgent(client, model, skill_manager)],
        }

    # 做什么：在运行时更新 Skill 管理器引用。
    # 为什么：支持 `/skills/reload` 热加载后立即生效。
    def set_skill_manager(self, skill_manager: Optional[Any]) -> None:
        self._skill_manager = skill_manager
        for agents in self._pool.values():
            for agent in agents:
                agent._skill_manager = skill_manager

    # 做什么：执行完整编排流程。
    # 为什么：把意图识别、路由、并行协作、降级和升级统一封装。
    async def run(self, req: Request) -> OrchestratorResult:
        t0 = time.monotonic()

        # 做什么：在调用方没预判时执行意图识别。
        # 为什么：保证所有入口都能走统一的识别逻辑。
        if req.intent is None:
            intent_result = await self._intent_recognizer.recognize(req.message, history=req.history)
            req.intent = intent_result.intent
            req.urgency = intent_result.urgency

        # 做什么：先判断是否需要多 Agent 并行。
        # 为什么：导购、订单、售后问题经常会混合出现。
        collaboration_targets = self._collaboration_targets(req)
        if len(collaboration_targets) > 1:
            return await self.run_parallel(req, collaboration_targets)

        agent_type = self._route(req.intent, req.urgency)
        response = await self._execute(req, agent_type)

        escalated = False
        if response.escalate or req.urgency == UrgencyLevel.CRITICAL or req.intent == IntentCategory.ESCALATION:
            escalated = True
            logger.warning("请求 %s 触发升级: intent=%s urgency=%s", req.request_id, req.intent, req.urgency)

        return OrchestratorResult(
            request_id=req.request_id,
            response=response.content,
            agent_type=response.agent_type,
            intent=req.intent,
            escalated=escalated,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    # 做什么：并行调用多个 Agent 并合并结果。
    # 为什么：复合型零售问题不能只选一个 Agent，否则容易漏答。
    async def run_parallel(self, req: Request, agent_types: List[AgentType]) -> OrchestratorResult:
        t0 = time.monotonic()
        tasks = [self._execute(req, agent_type) for agent_type in agent_types]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        parts: List[str] = []
        escalated = False
        for response in responses:
            if isinstance(response, AgentResponse):
                escalated = escalated or response.escalate
                if response.success:
                    parts.append(f"[{response.agent_type.value}]\n{response.content}")

        if not parts:
            parts.append("抱歉，这个复合问题我暂时没能完整处理。你可以拆开说商品、订单或售后诉求，我继续帮你跟进。")

        return OrchestratorResult(
            request_id=req.request_id,
            response="\n\n".join(parts),
            agent_type=agent_types[0],
            intent=req.intent,
            escalated=escalated,
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    # 做什么：根据意图和紧急度选择主 Agent。
    # 为什么：把升级优先级和默认导购兜底规则放在同一处。
    def _route(self, intent: Optional[IntentCategory], urgency: Optional[UrgencyLevel]) -> AgentType:
        if urgency == UrgencyLevel.CRITICAL:
            return AgentType.ESCALATION
        if intent and intent in self._INTENT_ROUTING:
            target = self._INTENT_ROUTING[intent]
            if target in self._pool and self._pool[target]:
                return target
            if target == AgentType.ESCALATION:
                return AgentType.ESCALATION
        return AgentType.GUIDE

    # 做什么：识别复合问题需要的 Agent 集合。
    # 为什么：意图识别一般只返回主意图，复合场景还要补充关键词命中。
    def _collaboration_targets(self, req: Request) -> List[AgentType]:
        message = req.message.lower()
        targets: List[AgentType] = []

        guide_keywords = ["推荐", "对比", "哪个好", "预算", "送礼", "适合", "手机", "耳机", "书桌", "吹风机"]
        order_keywords = ["订单", "物流", "发货", "签收", "快递", "地址", "发票", "支付", "优惠券", "运单"]
        after_sales_keywords = ["退款", "退货", "换货", "售后", "质量", "破损", "投诉", "没到账", "补偿"]

        if req.intent == IntentCategory.GUIDE or any(keyword in message for keyword in guide_keywords):
            targets.append(AgentType.GUIDE)
        if req.intent == IntentCategory.ORDER or any(keyword in message for keyword in order_keywords):
            targets.append(AgentType.ORDER)
        if req.intent in (IntentCategory.AFTER_SALES, IntentCategory.COMPLAINT) or any(
            keyword in message for keyword in after_sales_keywords
        ):
            targets.append(AgentType.AFTER_SALES)

        deduped = list(dict.fromkeys(targets))
        return [agent_type for agent_type in deduped if self._pool.get(agent_type)]

    # 做什么：从同类型 Agent 中选最优实例。
    # 为什么：为未来同类多实例扩展保留在线择优能力。
    def _best_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        agents = self._pool.get(agent_type, [])
        if not agents:
            return None
        return max(agents, key=lambda agent: agent.stats.routing_score())

    # 做什么：执行单个 Agent，并在失败时降级。
    # 为什么：即使专属 Agent 出错，也尽量给用户一个保底回复。
    async def _execute(self, req: Request, agent_type: AgentType) -> AgentResponse:
        if agent_type == AgentType.ESCALATION:
            return AgentResponse(
                agent_type=AgentType.AFTER_SALES,
                content="这个问题需要升级给人工专员继续核验，我先帮你记录当前诉求。",
                success=True,
                escalate=True,
            )

        agent = self._best_agent(agent_type) or self._best_agent(AgentType.GUIDE)
        if agent is None:
            return AgentResponse(
                agent_type=AgentType.GUIDE,
                content="服务暂时不可用，请稍后再试。",
                success=False,
            )

        response = await agent.handle(req)

        # 做什么：专属 Agent 失败时回退到导购 Agent。
        # 为什么：导购 Agent 作为兜底角色，至少能先解释下一步所需信息。
        if not response.success and agent_type != AgentType.GUIDE:
            fallback = self._best_agent(AgentType.GUIDE)
            if fallback:
                logger.warning("%s 执行失败，降级到 guide", agent_type.value)
                response = await fallback.handle(req)
        return response

    # 做什么：暴露 Agent 在线统计。
    # 为什么：供 `/health`、`/monitor` 和监控闭环读取。
    def get_stats(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for agent_type, agents in self._pool.items():
            for index, agent in enumerate(agents):
                key = f"{agent_type.value}_{index}"
                result[key] = {
                    "total": agent.stats.total,
                    "success_rate": round(agent.stats.success_rate, 3),
                    "avg_ms": round(agent.stats.avg_ms, 1),
                    "monitor_penalty": round(agent.stats.monitor_penalty, 3),
                    "routing_score": round(agent.stats.routing_score(), 3),
                }
        return result

    # 做什么：接收 Monitor 计算出的路由惩罚项。
    # 为什么：把在线表现反馈回下一轮路由决策。
    def update_routing_penalties(self, penalties: Dict[str, float]) -> None:
        for agent_type, agents in self._pool.items():
            for index, agent in enumerate(agents):
                key = f"{agent_type.value}_{index}"
                agent.stats.monitor_penalty = min(max(penalties.get(key, 0.0), 0.0), 0.9)
